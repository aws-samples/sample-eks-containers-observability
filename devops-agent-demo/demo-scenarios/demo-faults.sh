#!/bin/bash
# Fault injection for the developer self-service debugging demo
# Breaks and resets one real fault at a time on the demo EKS cluster, so a
# developer can ask AWS DevOps Agent what is wrong instead of using kubectl.
#
# Usage:
#   ./demo-faults.sh list                 # show the scenarios (no cluster access)
#   ./demo-faults.sh status               # show which faults are active
#   ./demo-faults.sh break <1-7>          # inject one fault
#   ./demo-faults.sh reset <1-7|all>      # restore the known-good state
#
# Environment:
#   AWS_PROFILE       standard AWS CLI profile selection (optional)
#   AWS_REGION        cluster region (default us-east-1)
#   CLUSTER_NAME      EKS cluster name (default dev-eks-automode)
#   The account ID comes from `aws sts get-caller-identity`; the expected
#   kubectl cluster ARN and the ECR registry are derived from it.
#   ASSUME_YES=1      skip the confirmation prompt on break
#   PYTHON=python3    interpreter for traffic-generator.py (scenario 6)
#   LOAD_DURATION=900 seconds of load for scenario 6
#   Scenario 7 (memory-hungry pod) tunables, see the break_7 block below:
#   HOG_REPLICAS, HOG_LEAK_MB, HOG_STEP_SECONDS, HOG_CAP_MB,
#   HOG_MAX_RUNTIME, HOG_REQUEST_MEM, HOG_MODE (tmpfs|anon), HOG_TARGET_NODE.
#
# This script never uses a :latest tag as a fault image, only opens port-forwards on
# 127.0.0.1, and never changes IAM or EKS access entries.
# See DEVELOPER_SELF_SERVICE_SCENARIOS.md for prompts and expected findings.

set -euo pipefail

NAMESPACE="default"
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${CLUSTER_NAME:-dev-eks-automode}"
# Set by resolve_aws_env from the caller's AWS identity.
AWS_ACCOUNT_ID=""
CLUSTER_ARN=""
REGISTRY=""
STATE_DIR="${HOME}/.devops-agent-demo-faults"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRAFFIC_GENERATOR="${SCRIPT_DIR}/../traffic-generator.py"
GO_APP_SRC="${SCRIPT_DIR}/../../go-otel-sample-app"
PYTHON="${PYTHON:-python3}"

# Known-good values, verified on the live cluster. They match the CDK manifests.
# The image values depend on REGISTRY and are set by resolve_aws_env.
OTEL_IMAGE_GOOD=""
OTEL_IMAGE_BAD=""
GO_IMAGE_GOOD=""
GO_IMAGE_BAD=""
JAVA_LIMITS_GOOD="cpu=400m,memory=512Mi"
JAVA_REQUESTS_GOOD="cpu=200m,memory=256Mi"
JAVA_MEMORY_BAD="128Mi"
OTLP_VAR="OTEL_EXPORTER_OTLP_ENDPOINT"
OTLP_GOOD="http://otel-collector.opentelemetry:4317"
OTLP_BAD="http://otel-collector.wrong:4317"
LOAD_PORT=8081
LOAD_DURATION="${LOAD_DURATION:-900}"

# Scenario 7: cascading node failure from a memory-hungry pod.
HOG_NS="team-reports"
HOG_DEPLOY="report-generator"
# Public base image, no new ECR repo. Multi-arch, so it runs on amd64 nodes.
HOG_IMAGE="public.ecr.aws/docker/library/python:3.12-slim"
HOG_REPLICAS="${HOG_REPLICAS:-2}"          # hog pods packed onto the one target node
HOG_LEAK_MB="${HOG_LEAK_MB:-100}"          # MiB added per step (clear ramp in metrics)
HOG_STEP_SECONDS="${HOG_STEP_SECONDS:-10}" # seconds between steps
HOG_CAP_MB="${HOG_CAP_MB:-3000}"           # per-replica ceiling, then it stops growing
HOG_MAX_RUNTIME="${HOG_MAX_RUNTIME:-900}"  # hard self-stop: free memory and idle after N s
HOG_REQUEST_MEM="${HOG_REQUEST_MEM:-64Mi}" # small request, NO limit (the whole point)
HOG_MODE="${HOG_MODE:-tmpfs}"              # tmpfs = memory-backed emptyDir, anon = heap

KUBE_CONTEXT=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info() { echo "$*"; }
ok()   { echo "✓ $*"; }
warn() { echo "⚠ $*" >&2; }
die()  { echo "✗ $*" >&2; exit 1; }

banner() {
    echo "=========================================="
    echo "$*"
    echo "=========================================="
}

usage() {
    echo "Usage: $0 list | status | break <1-7> | reset <1-7|all>"
}

# Derive the account, expected cluster ARN, ECR registry and image names from
# the caller's AWS identity (AWS_PROFILE / AWS_REGION / CLUSTER_NAME).
resolve_aws_env() {
    local identity caller_arn partition
    identity="$(aws sts get-caller-identity --query '[Account,Arn]' --output text 2>/dev/null)" \
        || die "Cannot get the AWS caller identity. Set AWS_PROFILE or credentials; if an SSO session expired, run: aws sso login"
    read -r AWS_ACCOUNT_ID caller_arn <<< "$identity"
    [[ "$AWS_ACCOUNT_ID" =~ ^[0-9]{12}$ ]] || die "Unexpected account ID from sts get-caller-identity: '${AWS_ACCOUNT_ID}'"
    partition="$(echo "$caller_arn" | cut -d: -f2)"
    CLUSTER_ARN="arn:${partition}:eks:${AWS_REGION}:${AWS_ACCOUNT_ID}:cluster/${CLUSTER_NAME}"
    REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    OTEL_IMAGE_GOOD="${REGISTRY}/otel-sample-app:latest"
    OTEL_IMAGE_BAD="${REGISTRY}/otel-sample-app:v2-typo"
    GO_IMAGE_GOOD="${REGISTRY}/go-otel-sample-app:latest"
    GO_IMAGE_BAD="${REGISTRY}/go-otel-sample-app:arm64-only"
}

# Refuse to run unless the current kubectl context points at CLUSTER_ARN.
require_cluster() {
    local cluster
    KUBE_CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
    [ -n "$KUBE_CONTEXT" ] || die "No current kubectl context. Run: aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION}"
    cluster="$(kubectl config view --minify -o jsonpath='{.contexts[0].context.cluster}')"
    if [ "$cluster" != "$CLUSTER_ARN" ]; then
        die "Current kubectl context '${KUBE_CONTEXT}' points at '${cluster}', not ${CLUSTER_ARN}. Refusing to run. To switch: aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION}"
    fi
    kubectl --context "$KUBE_CONTEXT" get --raw /readyz >/dev/null 2>&1 \
        || die "Cannot reach the cluster. If an SSO session expired, run: aws sso login"
}

k() { kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" "$@"; }

container_image() {
    k get deploy "$1" -o jsonpath="{.spec.template.spec.containers[?(@.name==\"$1\")].image}"
}

otlp_endpoint() {
    k get deploy otel-sample-app \
        -o jsonpath="{.spec.template.spec.containers[?(@.name==\"otel-sample-app\")].env[?(@.name==\"${OTLP_VAR}\")].value}"
}

java_memory_limit() {
    k get deploy java-otel-sample-app \
        -o jsonpath='{.spec.template.spec.containers[?(@.name=="java-otel-sample-app")].resources.limits.memory}'
}

java_resources() {
    k get deploy java-otel-sample-app \
        -o jsonpath='{.spec.template.spec.containers[?(@.name=="java-otel-sample-app")].resources}'
}

metrics_node_selector() {
    k get deploy sample-metrics-app -o jsonpath='{.spec.template.spec.nodeSelector}'
}

assert_not_latest() {
    case "$1" in
        *:latest) die "Refusing to use a :latest tag as a fault image: $1" ;;
    esac
}

confirm() {
    if [ "${ASSUME_YES:-0}" = "1" ]; then
        return 0
    fi
    read -p "$1 (y/n) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || die "Cancelled."
}

record_break() {
    date -u +%Y-%m-%dT%H:%M:%SZ > "${STATE_DIR}/scenario-$1.broken-at"
    ok "Scenario $1 injected at $(cat "${STATE_DIR}/scenario-$1.broken-at"). Wait 5-10 minutes before asking the agent."
}

clear_break() {
    rm -f "${STATE_DIR}/scenario-$1.broken-at"
}

# Non-fatal, so "reset all" keeps going if one rollout is slow.
wait_rollout() {
    info "Waiting for deploy/$1 to roll out..."
    if k rollout status "deploy/$1" --timeout=300s; then
        ok "deploy/$1 is back to its known-good state"
    else
        warn "deploy/$1 did not finish rolling out in 300s. Check: kubectl get pods -n ${NAMESPACE} -l app=$1"
    fi
}

# pid_alive <name> <pattern>: true if the PID in STATE_DIR/<name>.pid is running a matching command.
pid_alive() {
    local pid_file="${STATE_DIR}/$1.pid" pid
    [ -f "$pid_file" ] || return 1
    pid="$(cat "$pid_file")"
    ps -p "$pid" -o command= 2>/dev/null | grep -q -- "$2"
}

stop_pid() {
    local pid_file="${STATE_DIR}/$1.pid"
    if pid_alive "$1" "$2"; then
        kill "$(cat "$pid_file")"
        ok "Stopped $1 (pid $(cat "$pid_file"))"
    else
        info "  $1 is not running"
    fi
    rm -f "$pid_file"
}

require_otel_baseline() {
    if [ "$(container_image otel-sample-app)" != "$OTEL_IMAGE_GOOD" ] || [ "$(otlp_endpoint)" != "$OTLP_GOOD" ]; then
        die "otel-sample-app is not in its known-good state (scenario 1 or 4 may be active). Run: $0 reset 1 && $0 reset 4"
    fi
}

# ---------------------------------------------------------------------------
# Scenario 1: bad image tag after a deploy (otel-sample-app)
# ---------------------------------------------------------------------------

break_1() {
    require_otel_baseline
    assert_not_latest "$OTEL_IMAGE_BAD"
    if aws ecr describe-images --region "$AWS_REGION" --repository-name otel-sample-app \
        --image-ids imageTag=v2-typo >/dev/null 2>&1; then
        die "Tag v2-typo exists in ECR. This scenario needs a tag that does not exist."
    fi
    confirm "Set otel-sample-app to the non-existent tag :v2-typo?"
    k set image deploy/otel-sample-app "otel-sample-app=${OTEL_IMAGE_BAD}"
    record_break 1
    info "Verify: kubectl get pods -n ${NAMESPACE} -l app=otel-sample-app   (one pod in ErrImagePull/ImagePullBackOff, two Running)"
}

reset_1() {
    if [ "$(container_image otel-sample-app)" != "$OTEL_IMAGE_GOOD" ]; then
        k set image deploy/otel-sample-app "otel-sample-app=${OTEL_IMAGE_GOOD}"
        wait_rollout otel-sample-app
    else
        ok "Scenario 1 is not active"
    fi
    clear_break 1
}

# ---------------------------------------------------------------------------
# Scenario 2: image built for the wrong CPU architecture (go-otel-sample-app)
# ---------------------------------------------------------------------------

break_2() {
    [ "$(container_image go-otel-sample-app)" = "$GO_IMAGE_GOOD" ] \
        || die "go-otel-sample-app is not on ${GO_IMAGE_GOOD}. Run: $0 reset 2"
    assert_not_latest "$GO_IMAGE_BAD"
    confirm "Build and push ${GO_IMAGE_BAD} (linux/arm64 only) and deploy it to go-otel-sample-app?"

    if aws ecr describe-images --region "$AWS_REGION" --repository-name go-otel-sample-app \
        --image-ids imageTag=arm64-only >/dev/null 2>&1; then
        ok "Reusing existing ${GO_IMAGE_BAD}"
    else
        command -v docker >/dev/null 2>&1 || die "docker is required to build the arm64-only image"
        docker buildx version >/dev/null 2>&1 || die "docker buildx is required to build the arm64-only image"
        [ -f "${GO_APP_SRC}/Dockerfile" ] || die "Cannot find ${GO_APP_SRC}/Dockerfile"
        aws ecr get-login-password --region "$AWS_REGION" \
            | docker login --username AWS --password-stdin "$REGISTRY"
        # Single-platform manifest, no attestations, so the pod pulls it and fails at exec time.
        docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
            -t "$GO_IMAGE_BAD" --push "$GO_APP_SRC"
    fi

    k set image deploy/go-otel-sample-app "go-otel-sample-app=${GO_IMAGE_BAD}"
    record_break 2
    info "Verify: kubectl get pods -n ${NAMESPACE} -l app=go-otel-sample-app   (one new pod in CrashLoopBackOff)"
}

reset_2() {
    if [ "$(container_image go-otel-sample-app)" != "$GO_IMAGE_GOOD" ]; then
        k set image deploy/go-otel-sample-app "go-otel-sample-app=${GO_IMAGE_GOOD}"
        wait_rollout go-otel-sample-app
    else
        ok "Scenario 2 is not active"
    fi
    clear_break 2
    info "  The :arm64-only tag stays in ECR. To delete it:"
    info "  aws ecr batch-delete-image --region ${AWS_REGION} --repository-name go-otel-sample-app --image-ids imageTag=arm64-only"
}

# ---------------------------------------------------------------------------
# Scenario 3: OOMKilled JVM (java-otel-sample-app)
# ---------------------------------------------------------------------------

break_3() {
    [ "$(java_memory_limit)" = "512Mi" ] \
        || die "java-otel-sample-app memory limit is '$(java_memory_limit)', expected 512Mi. Run: $0 reset 3"
    confirm "Set java-otel-sample-app memory request and limit to ${JAVA_MEMORY_BAD}?"
    # The request must not exceed the limit, so both are lowered.
    k set resources deploy/java-otel-sample-app -c java-otel-sample-app \
        --limits="memory=${JAVA_MEMORY_BAD}" --requests="memory=${JAVA_MEMORY_BAD}"
    record_break 3
    info "Verify: kubectl get pods -n ${NAMESPACE} -l app=java-otel-sample-app   (restarts climbing on the new pod)"
}

reset_3() {
    local current
    current="$(java_resources)"
    if [ "$current" != '{"limits":{"cpu":"400m","memory":"512Mi"},"requests":{"cpu":"200m","memory":"256Mi"}}' ]; then
        k set resources deploy/java-otel-sample-app -c java-otel-sample-app \
            --limits="$JAVA_LIMITS_GOOD" --requests="$JAVA_REQUESTS_GOOD"
        wait_rollout java-otel-sample-app
    else
        ok "Scenario 3 is not active"
    fi
    clear_break 3
}

# ---------------------------------------------------------------------------
# Scenario 4: traces vanish after a config change (otel-sample-app)
# ---------------------------------------------------------------------------

break_4() {
    require_otel_baseline
    confirm "Set ${OTLP_VAR} on otel-sample-app to ${OTLP_BAD}?"
    k set env deploy/otel-sample-app -c otel-sample-app "${OTLP_VAR}=${OTLP_BAD}"
    record_break 4
    info "Verify: kubectl logs -n ${NAMESPACE} deploy/otel-sample-app --tail=50 | grep -i -E 'otlp endpoint|export|unavailable'"
}

reset_4() {
    if [ "$(otlp_endpoint)" != "$OTLP_GOOD" ]; then
        k set env deploy/otel-sample-app -c otel-sample-app "${OTLP_VAR}=${OTLP_GOOD}"
        wait_rollout otel-sample-app
    else
        ok "Scenario 4 is not active"
    fi
    clear_break 4
}

# ---------------------------------------------------------------------------
# Scenario 5: pending pods from a node selector no node pool satisfies (sample-metrics-app)
# ---------------------------------------------------------------------------

break_5() {
    [ -z "$(metrics_node_selector)" ] \
        || die "sample-metrics-app already has nodeSelector $(metrics_node_selector). Run: $0 reset 5"
    confirm "Add nodeSelector team=does-not-exist to sample-metrics-app?"
    k patch deploy/sample-metrics-app \
        -p '{"spec":{"template":{"spec":{"nodeSelector":{"team":"does-not-exist"}}}}}'
    record_break 5
    info "Verify: kubectl get pods -n ${NAMESPACE} -l app=sample-metrics-app   (new pods Pending)"
}

reset_5() {
    if [ -n "$(metrics_node_selector)" ]; then
        k patch deploy/sample-metrics-app --type=json \
            -p '[{"op":"remove","path":"/spec/template/spec/nodeSelector"}]'
        wait_rollout sample-metrics-app
    else
        ok "Scenario 5 is not active"
    fi
    clear_break 5
}

# ---------------------------------------------------------------------------
# Scenario 6: error spike under load (java-otel-sample-app)
# ---------------------------------------------------------------------------

break_6() {
    local i
    [ -f "$TRAFFIC_GENERATOR" ] || die "Cannot find ${TRAFFIC_GENERATOR}"
    "$PYTHON" -c 'import requests' 2>/dev/null \
        || die "Python package 'requests' is missing. Run: pip install -r ${SCRIPT_DIR}/../requirements.txt"
    if pid_alive port-forward "port-forward" || pid_alive traffic "traffic-generator"; then
        die "Load is already running. Run: $0 reset 6"
    fi
    if lsof -nP -iTCP:"$LOAD_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
        die "Port ${LOAD_PORT} is already in use. Stop that process first."
    fi
    confirm "Send ${LOAD_DURATION}s of load (20 rps, 25% bad requests) to java-otel-sample-app?"

    nohup kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" port-forward --address 127.0.0.1 \
        svc/java-otel-sample-app "${LOAD_PORT}:8080" > "${STATE_DIR}/port-forward.log" 2>&1 &
    echo $! > "${STATE_DIR}/port-forward.pid"

    for i in $(seq 1 15); do
        if curl -sf "http://127.0.0.1:${LOAD_PORT}/health" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    curl -sf "http://127.0.0.1:${LOAD_PORT}/health" >/dev/null 2>&1 || {
        stop_pid port-forward "port-forward"
        die "java-otel-sample-app did not answer on 127.0.0.1:${LOAD_PORT}. See ${STATE_DIR}/port-forward.log"
    }
    ok "Port-forward 127.0.0.1:${LOAD_PORT} -> svc/java-otel-sample-app:8080 is up after ${i}s"

    PYTHONUNBUFFERED=1 nohup "$PYTHON" "$TRAFFIC_GENERATOR" --app java-otel \
        --base-url "http://127.0.0.1:${LOAD_PORT}" --duration "$LOAD_DURATION" \
        --rps 20 --error-rate 0.25 > "${STATE_DIR}/traffic.log" 2>&1 &
    echo $! > "${STATE_DIR}/traffic.pid"
    record_break 6
    info "Verify: tail -f ${STATE_DIR}/traffic.log   and   kubectl get hpa java-otel-sample-app-hpa -n ${NAMESPACE} -w"
}

reset_6() {
    stop_pid traffic "traffic-generator"
    stop_pid port-forward "port-forward"
    clear_break 6
}

# ---------------------------------------------------------------------------
# Scenario 7: cascading node failure from a memory-hungry pod (team-reports)
# ---------------------------------------------------------------------------

# kn <namespace> <args...>: kubectl scoped to a namespace other than default.
kn() { kubectl --context "$KUBE_CONTEXT" -n "$1" "${@:2}"; }

scenario_7_active() {
    kubectl --context "$KUBE_CONTEXT" get namespace "$HOG_NS" >/dev/null 2>&1
}

# Echo the node that runs prometheus-server (the AMP evidence source), or "" if none.
amp_evidence_node() {
    kubectl --context "$KUBE_CONTEXT" -n monitoring get pods -l app=prometheus-server \
        -o jsonpath='{.items[0].spec.nodeName}' 2>/dev/null || true
}

# Choose ONE general-purpose, Ready node to pin the hog to. Prefer a node that
# hosts sample-app pods but NOT prometheus-server, so AMP metrics survive the
# fault. Honour HOG_TARGET_NODE if the caller set it.
select_hog_target_node() {
    local avoid gp_nodes n app_count best="" best_count=-1
    if [ -n "${HOG_TARGET_NODE:-}" ]; then
        echo "$HOG_TARGET_NODE"; return 0
    fi
    local ready
    avoid="$(amp_evidence_node)"
    gp_nodes="$(kubectl --context "$KUBE_CONTEXT" get nodes \
        -l karpenter.sh/nodepool=general-purpose \
        -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null)"
    [ -n "$gp_nodes" ] || return 1
    while IFS= read -r n; do
        [ -n "$n" ] || continue
        ready="$(kubectl --context "$KUBE_CONTEXT" get node "$n" \
            -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)"
        [ "$ready" = "True" ] || continue
        [ "$n" = "$avoid" ] && continue
        app_count="$(kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get pods \
            --field-selector "spec.nodeName=${n},status.phase=Running" \
            --no-headers 2>/dev/null | wc -l | tr -d ' ')"
        if [ "$app_count" -gt "$best_count" ]; then best="$n"; best_count="$app_count"; fi
    done <<< "$gp_nodes"
    # Fall back to any general-purpose node if every one of them runs prometheus.
    if [ -z "$best" ]; then
        best="$(echo "$gp_nodes" | head -n1)"
    fi
    echo "$best"
}

# Render the team-reports namespace, quota/limit-free, with the hog Deployment
# pinned to $1 via a required hostname affinity. Params come from HOG_* vars.
render_hog_manifest() {
    local target="$1"
    cat <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${HOG_NS}
  labels:
    demo-fault: "7"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${HOG_DEPLOY}
  namespace: ${HOG_NS}
  labels:
    app: ${HOG_DEPLOY}
    demo-fault: "7"
spec:
  replicas: ${HOG_REPLICAS}
  selector:
    matchLabels:
      app: ${HOG_DEPLOY}
  template:
    metadata:
      labels:
        app: ${HOG_DEPLOY}
        demo-fault: "7"
    spec:
      # Pin to one general-purpose node. If Auto Mode replaces that node, the
      # hostname disappears and the hog can no longer schedule, so it self-stops.
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: kubernetes.io/hostname
                    operator: In
                    values: ["${target}"]
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
        seccompProfile:
          type: RuntimeDefault
      terminationGracePeriodSeconds: 5
      containers:
        - name: ${HOG_DEPLOY}
          image: ${HOG_IMAGE}
          command: ["python3", "-u", "-c"]
          args:
            - |
              import os, time, gc, glob
              mode = os.environ.get("HOG_MODE", "tmpfs")
              leak = int(os.environ.get("HOG_LEAK_MB", "100"))
              step = float(os.environ.get("HOG_STEP_SECONDS", "10"))
              cap = int(os.environ.get("HOG_CAP_MB", "3000"))
              maxrun = float(os.environ.get("HOG_MAX_RUNTIME", "900"))
              path = os.environ.get("HOG_PATH", "/pagecache")
              mb = 1024 * 1024
              start = time.time()
              held = 0
              blocks = []
              print("report-generator start mode=%s leak=%dMiB/%.0fs cap=%dMiB maxrun=%.0fs"
                    % (mode, leak, step, cap, maxrun), flush=True)
              while time.time() - start < maxrun:
                  if held < cap:
                      if mode == "anon":
                          b = bytearray(leak * mb)
                          for i in range(0, len(b), 4096):
                              b[i] = 1
                          blocks.append(b)
                      else:
                          fn = os.path.join(path, "chunk-%06d" % held)
                          with open(fn, "wb") as fh:
                              buf = b"\0" * mb
                              for _ in range(leak):
                                  fh.write(buf)
                              fh.flush()
                              os.fsync(fh.fileno())
                      held += leak
                      print("working_set_mb=%d" % held, flush=True)
                  time.sleep(step)
              # Hard self-stop: release everything so the node recovers even if
              # the presenter forgets to reset or the SSO session expires.
              blocks = []
              try:
                  for fn in glob.glob(os.path.join(path, "chunk-*")):
                      os.remove(fn)
              except OSError as e:
                  print("cleanup error %r" % e, flush=True)
              gc.collect()
              print("deadline reached: released memory, idling", flush=True)
              while True:
                  time.sleep(3600)
          env:
            - name: HOG_MODE
              value: "${HOG_MODE}"
            - name: HOG_LEAK_MB
              value: "${HOG_LEAK_MB}"
            - name: HOG_STEP_SECONDS
              value: "${HOG_STEP_SECONDS}"
            - name: HOG_CAP_MB
              value: "${HOG_CAP_MB}"
            - name: HOG_MAX_RUNTIME
              value: "${HOG_MAX_RUNTIME}"
            - name: HOG_PATH
              value: "/pagecache"
          resources:
            requests:
              cpu: "100m"
              memory: "${HOG_REQUEST_MEM}"
            # No memory limit on purpose: this is the fault under investigation.
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: pagecache
              mountPath: /pagecache
            - name: tmp
              mountPath: /tmp
      volumes:
        # Memory-backed scratch space. In tmpfs mode the hog fills this, which
        # drains node RAM as unreclaimable page cache while the process RSS
        # stays low, so the kernel OOM killer scores neighbours above the hog.
        - name: pagecache
          emptyDir:
            medium: Memory
            sizeLimit: 4Gi
        - name: tmp
          emptyDir: {}
EOF
}

break_7() {
    local target
    scenario_7_active && die "Namespace ${HOG_NS} already exists (scenario 7 may be active). Run: $0 reset 7"
    assert_not_latest "$HOG_IMAGE"
    target="$(select_hog_target_node)"
    [ -n "$target" ] || die "Could not find a general-purpose node to target."

    # Safety: never target the tainted arm64 system pool.
    local pool
    pool="$(kubectl --context "$KUBE_CONTEXT" get node "$target" \
        -o jsonpath='{.metadata.labels.karpenter\.sh/nodepool}' 2>/dev/null)"
    [ "$pool" = "general-purpose" ] \
        || die "Target node ${target} is in node pool '${pool}', not general-purpose. Refusing."

    info "Target node: ${target} (node pool ${pool})"
    info "  AMP evidence node (prometheus-server): $(amp_evidence_node) -- kept clear where possible"
    info "  Co-tenants that may be disrupted on ${target}:"
    kubectl --context "$KUBE_CONTEXT" get pods -A \
        --field-selector "spec.nodeName=${target}" \
        -o custom-columns=NS:.metadata.namespace,POD:.metadata.name --no-headers 2>/dev/null \
        | sed 's/^/    /'
    confirm "Deploy ${HOG_REPLICAS}x ${HOG_DEPLOY} (no memory limit, ${HOG_MODE} leak ${HOG_LEAK_MB}MiB/${HOG_STEP_SECONDS}s, self-stop ${HOG_MAX_RUNTIME}s) pinned to ${target}?"

    render_hog_manifest "$target" | kubectl --context "$KUBE_CONTEXT" apply -f -
    echo "$target" > "${STATE_DIR}/scenario-7.target-node"
    record_break 7
    info "Verify: kubectl get pods -n ${HOG_NS} -o wide   (hog pods Running on ${target})"
    info "        kubectl describe node ${target} | grep -A6 Conditions   (MemoryPressure flips to True)"
    info "        kubectl get events -A --sort-by=.lastTimestamp | grep -iE 'evict|oom|memory'"
}

reset_7() {
    if scenario_7_active; then
        info "Deleting namespace ${HOG_NS} (removes the hog and all its pods)..."
        kubectl --context "$KUBE_CONTEXT" delete namespace "$HOG_NS" --wait=true --timeout=180s \
            || warn "Namespace ${HOG_NS} did not delete cleanly; check: kubectl get ns ${HOG_NS}"
        if ! kubectl --context "$KUBE_CONTEXT" wait --for=delete "namespace/${HOG_NS}" --timeout=120s >/dev/null 2>&1; then
            # If the fault froze the node (kubelet unreachable), its pods cannot
            # terminate and the namespace stays Terminating until the node is gone.
            warn "Namespace ${HOG_NS} is still Terminating. If the target node is NotReady/unreachable, retire it so its pods are force-removed:"
            warn "  kubectl get nodeclaims -o wide   # find the NodeClaim for the frozen node"
            warn "  kubectl delete nodeclaim <name>  # Auto Mode terminates it and GCs the stuck pods"
        fi
    else
        ok "Scenario 7 is not active"
    fi
    clear_break 7
    rm -f "${STATE_DIR}/scenario-7.target-node"
    verify_scenario_7_recovery
}

# Confirm the cluster is healthy after the memory fault: nodes Ready, every app
# plus hello-app and the collector rolled out and Ready.
verify_scenario_7_recovery() {
    info "Verifying recovery..."
    local notready
    notready="$(kubectl --context "$KUBE_CONTEXT" get nodes \
        -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' 2>/dev/null \
        | awk '$2!="True"{print $1}')"
    if [ -n "$notready" ]; then
        warn "Nodes not Ready: $(echo "$notready" | tr '\n' ' ')"
    else
        ok "All nodes Ready"
    fi
    local d
    for d in sample-metrics-app otel-sample-app java-otel-sample-app go-otel-sample-app error-generator-app; do
        if k rollout status "deploy/$d" --timeout=180s >/dev/null 2>&1; then
            ok "default/$d ready"
        else
            warn "default/$d not ready"
        fi
    done
    if kn hello-app rollout status deploy/hello-app --timeout=180s >/dev/null 2>&1; then
        ok "hello-app/hello-app ready"
    else
        warn "hello-app/hello-app not ready"
    fi
    if kn opentelemetry rollout status deploy/otel-collector --timeout=180s >/dev/null 2>&1; then
        ok "opentelemetry/otel-collector ready"
    else
        warn "opentelemetry/otel-collector not ready"
    fi
}

reset_all() {
    banner "Resetting all scenarios"
    reset_7
    reset_6
    reset_1
    reset_2
    reset_3
    reset_4
    reset_5
    echo ""
    show_status
}

# ---------------------------------------------------------------------------
# Status and list
# ---------------------------------------------------------------------------

state_line() {
    local n="$1" active="$2" label="$3" since=""
    if [ -f "${STATE_DIR}/scenario-${n}.broken-at" ]; then
        since=" (injected $(cat "${STATE_DIR}/scenario-${n}.broken-at"))"
    fi
    if [ "$active" = "yes" ]; then
        echo "  ${n}  ACTIVE  ${label}${since}"
    else
        echo "  ${n}  clear   ${label}"
    fi
}

show_status() {
    local s1=no s2=no s3=no s4=no s5=no s6=no s7=no hog_target=""
    banner "Demo fault status (context: ${KUBE_CONTEXT})"
    [ "$(container_image otel-sample-app)" = "$OTEL_IMAGE_BAD" ] && s1=yes
    [ "$(container_image go-otel-sample-app)" = "$GO_IMAGE_BAD" ] && s2=yes
    [ "$(java_memory_limit)" = "$JAVA_MEMORY_BAD" ] && s3=yes
    [ "$(otlp_endpoint)" = "$OTLP_BAD" ] && s4=yes
    [ -n "$(metrics_node_selector)" ] && s5=yes
    if pid_alive traffic "traffic-generator" || pid_alive port-forward "port-forward"; then s6=yes; fi
    if scenario_7_active; then s7=yes; fi
    [ -f "${STATE_DIR}/scenario-7.target-node" ] && hog_target=" on $(cat "${STATE_DIR}/scenario-7.target-node")"

    state_line 1 "$s1" "otel-sample-app image: $(container_image otel-sample-app)"
    state_line 2 "$s2" "go-otel-sample-app image: $(container_image go-otel-sample-app)"
    state_line 3 "$s3" "java-otel-sample-app memory limit: $(java_memory_limit)"
    state_line 4 "$s4" "otel-sample-app ${OTLP_VAR}: $(otlp_endpoint)"
    state_line 5 "$s5" "sample-metrics-app nodeSelector: $(metrics_node_selector)"
    state_line 6 "$s6" "load on java-otel-sample-app via 127.0.0.1:${LOAD_PORT}"
    state_line 7 "$s7" "memory-hungry ${HOG_DEPLOY} in namespace ${HOG_NS}${hog_target}"
    echo ""
    k get deploy sample-metrics-app otel-sample-app java-otel-sample-app go-otel-sample-app error-generator-app
    echo ""
    echo "Pods that are not fully ready:"
    k get pods -o wide | awk 'NR==1 {print; next} {split($2, a, "/"); if (a[1] != a[2] || $3 != "Running") print}'
}

list_scenarios() {
    banner "Developer self-service scenarios"
    cat <<'EOF'
  1  Bad image tag after a deploy       otel-sample-app       ImagePullBackOff
  2  Image built for the wrong CPU arch go-otel-sample-app    exec format error
  3  JVM does not fit its memory limit  java-otel-sample-app  OOMKilled / restarts
  4  Traces vanish after config change otel-sample-app      export errors, no X-Ray traces
  5  New replicas stuck Pending         sample-metrics-app    FailedScheduling (node selector)
  6  Error spike under load             java-otel-sample-app  HTTP 500 on /api/users
  7  Cascading node failure (mem hog)   team-reports/report-generator  node MemoryPressure, neighbour evictions
EOF
    echo ""
    usage
}

main() {
    local action="${1:-}" target="${2:-}"
    case "$action" in
        list) list_scenarios; return 0 ;;
        status|break|reset) ;;
        *) usage; exit 1 ;;
    esac

    resolve_aws_env
    require_cluster
    mkdir -p "$STATE_DIR"
    chmod 700 "$STATE_DIR"

    case "$action" in
        status) show_status ;;
        break)
            case "$target" in
                [1-7]) banner "Breaking scenario ${target}"; "break_${target}" ;;
                *) usage; exit 1 ;;
            esac
            ;;
        reset)
            case "$target" in
                [1-7]) banner "Resetting scenario ${target}"; "reset_${target}" ;;
                all) reset_all ;;
                *) usage; exit 1 ;;
            esac
            ;;
    esac
}

# Only run when executed directly, so the functions can be sourced for testing.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi

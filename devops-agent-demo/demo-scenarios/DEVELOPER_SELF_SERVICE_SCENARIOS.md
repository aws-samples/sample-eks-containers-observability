# Developer Self-Service Debugging with AWS DevOps Agent

These scenarios show developers debugging their own workloads on the EKS platform by asking AWS DevOps Agent, instead of being given kubectl access.

## Overview

The persona is an application developer who owns a service on `dev-eks-automode` but has no kubectl access to the cluster. When something breaks, the developer would normally open a ticket with the platform team and wait. In this demo the developer asks the DevOps Agent instead. The agent has read-only access to the cluster through an EKS access entry, plus read access to CloudWatch Logs, Amazon Managed Prometheus (AMP), X-Ray and ECR. It reads events, pod status, logs, metrics and traces, and returns the root cause and the fix without a ticket.

Each scenario injects one real fault into the cluster. No logs or metrics are fabricated. The presenter (who does have cluster access) breaks and resets the fault with `demo-faults.sh`. The developer only talks to the agent.

| # | Scenario | Workload | What the developer sees |
|---|----------|----------|-------------------------|
| 1 | Bad image tag after a deploy | `otel-sample-app` | "The new version never came up" |
| 2 | Image built for the wrong CPU architecture | `go-otel-sample-app` | "The new pod crash-loops, the old ones are fine" |
| 3 | JVM does not fit its memory limit | `java-otel-sample-app` | "It keeps restarting, no errors in my code" |
| 4 | Traces vanish after a config change | `otel-sample-app` | "The service works but traces stopped" |
| 5 | New replicas stuck Pending | `sample-metrics-app` | "Is the cluster out of capacity?" |
| 6 | Error spike under load | `java-otel-sample-app` | "Customers report errors on my API" |
| 7 | Cascading node failure from a memory-hungry pod | `team-reports/report-generator` (hits a neighbour such as `go-otel-sample-app`) | "My app went down and I didn't deploy anything" |

## Prerequisites

### Environment

Verified on a live development cluster deployed from this repo. `demo-faults.sh` derives the account-specific values at runtime:

| Item | Value |
|------|-------|
| AWS credentials / region | your usual credentials, selected with `AWS_PROFILE` if needed / `AWS_REGION` (default `us-east-1`) |
| Cluster name | `CLUSTER_NAME` (default `dev-eks-automode`, from `eks_platform/config/environment_config.py`) |
| Account ID | from `aws sts get-caller-identity` |
| kubectl context | `arn:aws:eks:<region>:<account-id>:cluster/<cluster-name>` (the context `aws eks update-kubeconfig` creates) |
| ECR registry | `<account-id>.dkr.ecr.<region>.amazonaws.com` (tags are mutable, so never push a fault image as `:latest`) |
| Apps (namespace `default`, ClusterIP) | `sample-metrics-app`, `otel-sample-app`, `java-otel-sample-app`, `go-otel-sample-app`, `error-generator-app` |
| Node pools | `general-purpose`: amd64 only, untainted, runs the apps. `system`: amd64 or arm64, tainted `CriticalAddonsOnly` (today one arm64 `c6g.large` node) |
| HPAs | `sample-metrics-app-hpa` (2-4), `otel-sample-app-hpa` (2-3), `go-otel-sample-app-hpa` (2-6), `java-otel-sample-app-hpa` (1-4). `error-generator-app` has no HPA |
| OTEL endpoint env var | `otel-sample-app` and `java-otel-sample-app`: `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.opentelemetry:4317` |
| Collector | `deploy/otel-collector` in `opentelemetry`; traces go to X-Ray, OTLP logs to `/aws/eks/automode-platform/applications` (stream `otel-collector-logs`) |
| X-Ray service names | `otel_sample_app`, `go-otel-sample-app`, `unknown_service:java` (the Java app) |

```bash
export AWS_PROFILE=<your-profile> AWS_REGION=us-east-1 CLUSTER_NAME=dev-eks-automode
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$AWS_REGION"
# Used by the manual commands below
REGISTRY="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.${AWS_REGION}.amazonaws.com"
```

If a command fails with `ExpiredToken` or a refresh error, refresh your credentials (for IAM Identity Center: `aws sso login --profile <your-profile>`).

### Agent access: make it read-only (recommended, not applied)

The story is "the agent can look but not touch". Today the agent role (the role passed to CDK as `devops_agent_role_arn`) has `AmazonEKSClusterAdminPolicy` (cluster scope), set in `eks_platform/platform/devops_agent/devops_agent_eks_access.py`. For this demo it SHOULD be read-only.

`AmazonEKSViewPolicy` covers pods, pods/log, events, deployments, replicasets and HPAs, but not cluster-scoped objects such as nodes or Auto Mode node pools. Scenarios 2 and 5 need node architecture, taints and node pool requirements, so add a small node-reader ClusterRole bound to a Kubernetes group on the access entry.

1. Create the ClusterRole and binding (as a cluster admin):

   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRole
   metadata:
     name: devops-agent-node-reader
   rules:
     - apiGroups: [""]
       resources: ["nodes"]
       verbs: ["get", "list", "watch"]
     - apiGroups: ["karpenter.sh"]
       resources: ["nodepools", "nodeclaims"]
       verbs: ["get", "list", "watch"]
     - apiGroups: ["eks.amazonaws.com"]
       resources: ["nodeclasses"]
       verbs: ["get", "list", "watch"]
   ---
   apiVersion: rbac.authorization.k8s.io/v1
   kind: ClusterRoleBinding
   metadata:
     name: devops-agent-node-reader
   roleRef:
     apiGroup: rbac.authorization.k8s.io
     kind: ClusterRole
     name: devops-agent-node-reader
   subjects:
     - apiGroup: rbac.authorization.k8s.io
       kind: Group
       name: devops-agent-node-readers
   ```

2. Point the access entry at the group, add the view policy, then remove cluster admin:

   ```bash
   # The DevOps Agent role, for example arn:aws:iam::<account-id>:role/service-role/<devops-agent-role>
   AGENT_ROLE="${DEVOPS_AGENT_ROLE_ARN:?set DEVOPS_AGENT_ROLE_ARN to the DevOps Agent role ARN}"

   aws eks update-access-entry --cluster-name "$CLUSTER_NAME" \
     --principal-arn "$AGENT_ROLE" --kubernetes-groups devops-agent-node-readers

   aws eks associate-access-policy --cluster-name "$CLUSTER_NAME" \
     --principal-arn "$AGENT_ROLE" \
     --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy \
     --access-scope type=cluster

   aws eks disassociate-access-policy --cluster-name "$CLUSTER_NAME" \
     --principal-arn "$AGENT_ROLE" \
     --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy
   ```

3. Verify:

   ```bash
   aws eks list-associated-access-policies --cluster-name "$CLUSTER_NAME" --principal-arn "$AGENT_ROLE"
   kubectl auth can-i list nodes --as demo-check --as-group devops-agent-node-readers   # yes
   kubectl auth can-i patch deployments --as demo-check --as-group devops-agent-node-readers   # no
   ```

Making the change with the CLI is drift from CDK. To keep it, change the `policyArn` in `devops_agent_eks_access.py` and add the group there as well. These scenarios also work with cluster admin. The read-only setup only makes the "no write access" claim true.

### Demo hygiene

- **Do not run `../push-logs-simple.py`.** It writes 44 fabricated log entries (5 streams, for example `otel-collector-errors`) describing an OTEL collector IRSA failure into `/aws/eks/automode-platform/applications`. The live collector is healthy, so the agent would find fake evidence that contradicts the cluster. `../AGENT_INSTRUCTIONS.md` describes the same fabricated story; do not give it to the agent. None of those streams exist in the log group today. Keep it that way.
- **Inject each fault 5-10 minutes before asking the agent**, so events, metrics and the trace gap have time to build up.
- **Run one scenario per workload at a time.** Scenarios 1 and 4 both change `otel-sample-app`, and 3 and 6 both use `java-otel-sample-app`. `demo-faults.sh` refuses to break 1 or 4 while the other is active.
- **The four sample apps are CDK-managed** (they carry the `aws.cdk.eks/prune-*` label). Every break is drift from the CDK manifest. A `cdk deploy` that updates those manifests overwrites the fault; a deploy with no manifest change leaves it in place. Always reset with the script. `error-generator-app` was applied with `kubectl apply`, not CDK, and is not used here.
- **Rolling updates keep the old pods serving.** Every app uses the default strategy (`maxSurge 25%`, `maxUnavailable 25%`). With 2 replicas that means one new pod and no old pod removed, so in scenarios 1 to 4 the service keeps serving while the new pod fails. That is the realistic shape of a bad deploy, and the prompts are written for it.

## Using the Fault Script

`demo-faults.sh` lives next to this file. It refuses to run unless the current kubectl context points at the expected cluster (`arn:aws:eks:<region>:<account-id>:cluster/<cluster-name>`, built from `AWS_REGION`, `CLUSTER_NAME` and the account of your current AWS credentials), never pushes or deploys a `:latest` fault tag, only opens port-forwards on `127.0.0.1`, and never touches IAM or access entries. Reset restores the known-good values that match the CDK manifests, so it has the same effect as `kubectl rollout undo` without depending on revision history.

```bash
cd devops-agent-demo/demo-scenarios

./demo-faults.sh list         # scenarios, no cluster access needed
./demo-faults.sh status       # which faults are active, pods that are not ready
./demo-faults.sh break 3      # inject scenario 3 (asks for confirmation)
./demo-faults.sh reset 3      # restore scenario 3
./demo-faults.sh reset all    # restore everything
```

Set `ASSUME_YES=1` to skip the confirmation prompt. Injection times, port-forward and traffic logs are kept in `~/.devops-agent-demo-faults/`.

## Example Scenarios

### Scenario 1: Bad Image Tag After a Deploy

**Fault:** `otel-sample-app` is updated to the tag `v2-typo`, which does not exist in ECR.

**Break:**

```bash
./demo-faults.sh break 1
# Equivalent manual command:
kubectl set image deploy/otel-sample-app -n default \
  otel-sample-app="${REGISTRY}/otel-sample-app:v2-typo"
```

**Verify the fault is active:**

```bash
kubectl get pods -n default -l app=otel-sample-app      # 1 pod ErrImagePull/ImagePullBackOff, 2 Running
kubectl get rs -n default -l app=otel-sample-app        # new RS 0/1, old RS 2/2
aws ecr describe-images --repository-name otel-sample-app --image-ids imageTag=v2-typo   # ImageNotFoundException
```

**Developer prompts:**

> I shipped otel-sample-app on EKS cluster dev-eks-automode 20 minutes ago and the new version never came up. What's wrong?

> What should I change, and are my users affected right now?

**Expected agent findings:**

- The rollout is stuck: the new ReplicaSet's pod is in `ImagePullBackOff` (pod status and `Failed to pull image ... v2-typo ... not found` events).
- The tag `v2-typo` does not exist in the `otel-sample-app` ECR repository; only `latest` does (ECR `DescribeImages`).
- The two old pods are still Running and Ready, so the Service keeps serving the previous version and users are not affected (ReplicaSet and endpoint status).

**Fix:** deploy a tag that exists (fix the typo in the pipeline or manifest), or roll back.

**Reset:**

```bash
./demo-faults.sh reset 1
# Manual equivalent: kubectl rollout undo deploy/otel-sample-app -n default
kubectl get pods -n default -l app=otel-sample-app      # 2/2 Running, no ImagePullBackOff
```

### Scenario 2: Image Built for the Wrong CPU Architecture

**Fault:** a developer builds `go-otel-sample-app` on an Apple Silicon laptop without `--platform` and ships an arm64-only image. The app node pool (`general-purpose`) is amd64-only, so the new pod cannot execute its binary. The only arm64 node is in the `system` pool, which is tainted `CriticalAddonsOnly` and does not run apps.

The script builds a separate tag, `:arm64-only`, and never overwrites `:latest`. It needs Docker with buildx and ECR push rights; the build takes a few minutes, so run it well before the demo. If the tag already exists, the script reuses it.

**Break:**

```bash
./demo-faults.sh break 2
# Equivalent manual commands (from the repo root):
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
docker buildx build --platform linux/arm64 --provenance=false --sbom=false \
  -t "${REGISTRY}/go-otel-sample-app:arm64-only" --push go-otel-sample-app
kubectl set image deploy/go-otel-sample-app -n default \
  go-otel-sample-app="${REGISTRY}/go-otel-sample-app:arm64-only"
```

**Verify the fault is active:**

```bash
kubectl get pods -n default -l app=go-otel-sample-app -o wide   # new pod CrashLoopBackOff, 2 old pods Running
kubectl logs -n default <new-pod>                                # exec ./main: exec format error
kubectl get nodes -L kubernetes.io/arch,karpenter.sh/nodepool    # app nodes are amd64
docker buildx imagetools inspect "${REGISTRY}/go-otel-sample-app:arm64-only"
```

If the image was pushed as an index instead of a single manifest, the pod fails earlier with `ErrImagePull ... no match for platform in manifest`. The cause and fix are the same.

**Developer prompts:**

> I pushed a new go-otel-sample-app build from my laptop. The new pod crash-loops with no app logs, but the old pods are fine and it runs on my Mac. Why?

> What should I change in my build?

**Expected agent findings:**

- Only the pod from the new ReplicaSet crash-loops; the old pods run the multi-arch `:latest` image (pod status, ReplicaSet images).
- The container log is a single `exec format error`, so the binary never started; this is not an application bug (pod logs, `lastState.terminated`).
- The pod runs on an amd64 node in the `general-purpose` pool, and that pool only allows amd64 (node labels, node pool requirements; needs the node-reader role).
- The new tag was built for arm64 only, which matches building on an Apple Silicon laptop.

**Fix:** build multi-arch, as `go-otel-sample-app/deploy-with-otel.sh` already does (`docker buildx build --platform linux/amd64,linux/arm64 --push ...`), or at least `--platform linux/amd64`.

**Reset:**

```bash
./demo-faults.sh reset 2
kubectl get pods -n default -l app=go-otel-sample-app            # 2/2 Running
# Optional: delete the fault tag
aws ecr batch-delete-image --repository-name go-otel-sample-app --image-ids imageTag=arm64-only
```

### Scenario 3: JVM Does Not Fit Its Memory Limit

**Fault:** the memory request and limit of `java-otel-sample-app` drop from 256Mi/512Mi to 128Mi. The image runs `java -jar app.jar` with no `-Xmx` or `JAVA_OPTS`, so the Spring Boot JVM does not fit in 128Mi.

The proposed `kubectl set resources --limits=memory=128Mi` alone is rejected by the API server, because the existing 256Mi request would exceed the limit. Both must be lowered.

**Break:**

```bash
./demo-faults.sh break 3
# Equivalent manual command:
kubectl set resources deploy/java-otel-sample-app -n default -c java-otel-sample-app \
  --limits=memory=128Mi --requests=memory=128Mi
```

**Verify the fault is active:**

```bash
kubectl get pods -n default -l app=java-otel-sample-app          # new pod restarts climbing, CrashLoopBackOff
kubectl get pod <new-pod> -n default -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'
```

Expect `reason: OOMKilled, exitCode: 137`. If the JVM fails inside the heap first, you see `exitCode: 1` with `java.lang.OutOfMemoryError` in the log instead. Both are the same root cause; note which one you got in rehearsal.

**Developer prompts:**

> java-otel-sample-app keeps restarting. There are no errors in my code. What's going on?

> What memory settings should I use?

**Expected agent findings:**

- Only the new ReplicaSet's pod restarts; the two old pods (512Mi limit) keep serving (pod status, ReplicaSet diff).
- The container is killed with `OOMKilled` / exit code 137 during Spring Boot startup, before the readiness probe passes (`lastState.terminated`, `BackOff` events).
- The memory limit changed from 512Mi to 128Mi in the latest rollout, and the JVM sizes its heap from the container limit because no `-Xmx` or `MaxRAMPercentage` is set (Deployment spec, Dockerfile `CMD`).
- No metrics arrive from the failing pod, because it dies before `/actuator/prometheus` serves anything.

**Fix:** restore the limit to 512Mi (or measure working set and size from that), and set the heap explicitly, for example `JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=75`.

**Reset:**

```bash
./demo-faults.sh reset 3
# Manual equivalent: kubectl rollout undo deploy/java-otel-sample-app -n default
kubectl get deploy java-otel-sample-app -n default \
  -o jsonpath='{.spec.template.spec.containers[0].resources}'    # limits 400m/512Mi, requests 200m/256Mi
```

The Java app is slow to start (readiness waits 30s), so the reset rollout takes about a minute.

### Scenario 4: Traces Vanish After a Config Change

**Fault:** `OTEL_EXPORTER_OTLP_ENDPOINT` on `otel-sample-app` is changed from `http://otel-collector.opentelemetry:4317` to `http://otel-collector.wrong:4317`. The namespace `wrong` does not exist, so DNS fails. The app keeps serving and its health checks stay green, so the rollout completes and every pod ends up on the bad value.

**Break:**

```bash
./demo-faults.sh break 4
# Equivalent manual command:
kubectl set env deploy/otel-sample-app -n default -c otel-sample-app \
  OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.wrong:4317
```

**Verify the fault is active:**

```bash
kubectl get pods -n default -l app=otel-sample-app               # 2/2 Running, Ready
kubectl logs -n default deploy/otel-sample-app --tail=100 | grep -i -E 'otlp endpoint|unavailable|export'
# "Using OTLP endpoint: http://otel-collector.wrong:4317" and exporter retry errors
```

In the X-Ray console, `otel_sample_app` traces stop a minute or two after the break time shown by `./demo-faults.sh status`.

**Developer prompts:**

> My service otel-sample-app works, but I've stopped seeing its traces in X-Ray in the last 15 minutes. What changed?

> What exactly should I change back?

**Expected agent findings:**

- The app is healthy: pods Ready, no restarts, probes passing (pod status).
- X-Ray traces for `otel_sample_app` stop at a specific time, while `go-otel-sample-app` and the Java app keep reporting, so the collector is not the problem (X-Ray service graph and trace summaries).
- A new ReplicaSet appeared at that time, and the only difference is `OTEL_EXPORTER_OTLP_ENDPOINT` changing to `otel-collector.wrong:4317` (ReplicaSet pod templates).
- The app logs show the new endpoint and repeated export failures (`StatusCode.UNAVAILABLE` / name resolution errors); the collector logs show no spans from `otel_sample_app` after that time (pod logs).
- OTLP logs from this app also stop arriving in the `otel-collector-logs` stream of `/aws/eks/automode-platform/applications` (CloudWatch Logs).

**Fix:** set `OTEL_EXPORTER_OTLP_ENDPOINT` back to `http://otel-collector.opentelemetry:4317`.

**Reset:**

```bash
./demo-faults.sh reset 4
# Manual equivalent: kubectl rollout undo deploy/otel-sample-app -n default
kubectl get deploy otel-sample-app -n default \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="OTEL_EXPORTER_OTLP_ENDPOINT")].value}'
# http://otel-collector.opentelemetry:4317
```

### Scenario 5: New Replicas Stuck Pending

**Fault:** a `nodeSelector` of `team: does-not-exist` is added to `sample-metrics-app`. No node has that label and neither node pool defines it, so Auto Mode will not launch a node for it.

> **WARNING:** do not demo "pending pods" with large CPU or memory requests. Auto Mode will try to satisfy them and may launch a large, expensive instance. The unsatisfiable label is safe because no node pool can produce it.

**Break:**

```bash
./demo-faults.sh break 5
# Equivalent manual command:
kubectl patch deploy/sample-metrics-app -n default \
  -p '{"spec":{"template":{"spec":{"nodeSelector":{"team":"does-not-exist"}}}}}'
```

**Verify the fault is active:**

```bash
kubectl get pods -n default -l app=sample-metrics-app            # new pods Pending, old pods Running
kubectl get events -n default --field-selector reason=FailedScheduling
kubectl get nodeclaims                                           # no new node claim
```

At 4 replicas the rollout surges 1 pod and removes 1 old pod, so 2 new pods are Pending and 3 old pods keep serving.

**Developer prompts:**

> My new sample-metrics-app replicas have been pending for 10 minutes. Is the cluster out of capacity?

> What should I change in my deployment?

**Expected agent findings:**

- This is not a capacity problem: the existing nodes have spare room and Auto Mode did not try to add a node (node status, node claims).
- `FailedScheduling` events say no node matches the pod's node selector, and the `system` node is excluded by its `CriticalAddonsOnly` taint (pod events).
- Auto Mode reports the pod as incompatible with the `general-purpose` and `system` node pools because the label `team` has no known values (pod events, node pool requirements; needs the node-reader role).
- The selector was added in the latest rollout (ReplicaSet pod template diff).

**Fix:** remove the `nodeSelector`, or use a label a node pool actually provides (for example `karpenter.sh/nodepool: general-purpose`).

**Reset:**

```bash
./demo-faults.sh reset 5
# Manual equivalent: kubectl rollout undo deploy/sample-metrics-app -n default
kubectl get pods -n default -l app=sample-metrics-app            # all Running, none Pending
```

### Scenario 6: Error Spike Under Load

This merges the existing [README Scenario 2: Simulated Incident](../README.md#scenario-2-simulated-incident) into the developer story. It uses the same traffic generator, but on a `127.0.0.1`-only port-forward and with developer prompts.

It targets `java-otel-sample-app`, not `error-generator-app`. `error-generator-app` has no HPA, sends no traces, logs errors every 2-6 seconds by design (so "when did it start" has no answer), and `traffic-generator.py` has no option for it. The Java app returns real HTTP 500s on `/api/users` (10% of calls) and `/api/products` (5%), sends traces to X-Ray, and has an HPA.

**Fault:** 20 requests per second for 15 minutes. 25% of requests go to `/error-test-endpoint` (HTTP 404, the generator's `--error-rate`); the rest hit `/health`, `/api/users` and `/api/products`, where the app's own 500s appear.

**Break:**

```bash
./demo-faults.sh break 6
# Equivalent manual commands:
kubectl port-forward --address 127.0.0.1 svc/java-otel-sample-app 8081:8080 -n default &
python3 ../traffic-generator.py --app java-otel --base-url http://127.0.0.1:8081 \
  --duration 900 --rps 20 --error-rate 0.25
```

Requires the `requests` package (`pip install -r ../requirements.txt`).

**Verify the fault is active:**

```bash
tail -f ~/.devops-agent-demo-faults/traffic.log                  # success rate well below 100%
kubectl get hpa java-otel-sample-app-hpa -n default -w            # replicas rising (max 4)
```

PromQL (AMP or the in-cluster Prometheus):

```promql
sum by (uri, status) (rate(http_server_requests_seconds_count{app="java-otel-sample-app", status=~"4..|5.."}[1m]))
```

A port-forward sends all traffic to one pod, so the HPA may not reach its maximum of 4.

**Developer prompts:**

> Customers report errors on my API, java-otel-sample-app. When did it start, and which endpoint is failing?

> Is this my code or the platform? What should I fix first?

**Expected agent findings:**

- Request and error rates rise at the time the load starts (AMP: `http_server_requests_seconds_count`).
- The server errors are HTTP 500 on `/api/users` (most) and `/api/products`, thrown by the application (`Internal server error`, `Product service unavailable`); the agent should separate these from the 404s on `/error-test-endpoint`, which are client errors (metric labels `uri` and `status`, pod logs).
- X-Ray traces for `unknown_service:java` show faults on the same routes (X-Ray trace summaries).
- The HPA scales the Deployment out; the platform is healthy and the errors are in application code (HPA events, pod status).

**Fix:** handle the failing dependency calls in `ApiController` (the random `RuntimeException`s at `/api/users` and `/api/products`); remove or fix the client calling `/error-test-endpoint`.

**Reset:**

```bash
./demo-faults.sh reset 6
# Manual equivalent: stop the generator (Ctrl+C) and kill the port-forward:
#   kill %1    or    pkill -f "port-forward --address 127.0.0.1 svc/java-otel-sample-app"
./demo-faults.sh status                                          # scenario 6 clear
lsof -nP -iTCP:8081 -sTCP:LISTEN                                  # nothing listening
```

The HPA scales back down on its own within a few minutes.

### Scenario 7: Cascading Node Failure From a Memory-Hungry Pod

> **Status: trialled live on 2026-11-26, reached outcome tier (a) on the first attempt.** The target node went `NotReady` ~3m45s after the break, its pods were evicted by the node-not-ready taint ~5 min later and rescheduled onto the surviving node and a brand-new Auto Mode node, and the leaker self-stopped (went `Pending`) because of its hostname pin. One subtlety the trial exposed: the node did not flip `MemoryPressure=True` and perform graceful per-pod eviction — it starved so hard that the **kubelet stopped posting status** (conditions went to `Unknown`) and the node froze. The collateral therefore came from the node failing and its pods being evicted and rescheduled, not from in-place kubelet evictions or OOM-kills of the neighbours. On this cluster AMP does not expose per-pod memory for the leaker (see the metrics note below); the authoritative evidence is node conditions and events. Node and pod names below are placeholders from the trial.

**The story.** A batch workload, `report-generator` in namespace `team-reports`, is deployed with a small memory request and **no memory limit**. It leaks memory gradually. Because it has no limit, nothing caps it at the container level; it keeps growing until the whole node runs low on memory. The node reports `MemoryPressure`, the kubelet starts evicting pods, and the Linux OOM killer starts killing processes. The victims are often the *neighbouring* application pods on the same node, not the leaker, so an app owner who deployed nothing sees their service go down. Auto Mode may declare the node `NotReady` and replace it. This is the hardest failure to debug from the app side, because the cause is another team's workload on shared infrastructure.

**Fault:** `demo-faults.sh break 7` creates the `team-reports` namespace and a `report-generator` Deployment (2 replicas by default) **pinned to one general-purpose node** that hosts sample-app pods. Each replica:

- requests `64Mi` memory and sets **no memory limit** (QoS `Burstable`);
- leaks `100Mi` every `10s` (a clear ramp in metrics) up to a per-replica cap of `3000Mi`;
- in the default `tmpfs` mode writes the memory into a **memory-backed `emptyDir`** (`medium: Memory`). Memory-backed `emptyDir` pages are unreclaimable and drain node RAM, while the writing process keeps a low resident set. This biases the kernel OOM killer toward the higher-RSS neighbour pods instead of the leaker — the collateral damage the scenario needs. (`HOG_MODE=anon` switches to a plain heap leak, which the earlier tier analysis showed usually just gets the leaker itself evicted; it is kept only as a tunable for comparison.)

Why these choices (see the realism note at the end of this scenario): a naive leaker with a small request is ranked first by both kubelet eviction (its usage far exceeds its request) and the kernel OOM killer (it has the largest resident set), so it tends to kill only itself — a non-cascading "tier (c)" outcome that is not an acceptable demo. The `tmpfs` mechanism, two replicas packed on one node, and the gradual-but-unbounded ramp are chosen to push real pressure onto the node and its other tenants.

**Target node selection and telemetry.** The script picks a Ready `general-purpose` node and **avoids the node running `prometheus-server`** (the AMP metrics source), so the AMP series of the annotation-scraped apps keep flowing during the fault. On this cluster that selects the node that also hosts `otel-collector` and one of the two CoreDNS replicas:

- AMP (Prometheus) metrics keep flowing, because `prometheus-server` runs on the other node.
- DNS keeps working, because the second CoreDNS replica runs on the tainted `system` node.
- Traces and OTLP logs may have a gap while `otel-collector` is evicted and rescheduled (it is a single replica). This is noted so you do not mistake the telemetry gap for the app failure.

If the cluster ever has only one general-purpose node, the script targets it anyway and the AMP metrics are then also at risk; note that during the demo.

**Safety built into the hog:**

- It runs as non-root (uid 1000), `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, drops **ALL** capabilities, `seccompProfile: RuntimeDefault`. No privileged mode, no `hostPID`, no `hostPath`.
- It uses the public image `public.ecr.aws/docker/library/python:3.12-slim`. No new ECR repository.
- **Hard self-stop.** After `HOG_MAX_RUNTIME` (default `900s`) the process frees everything it allocated and idles, so the node recovers even if the presenter forgets to reset or the SSO session expires.
- **Second self-stop on node replacement.** The pod is pinned with a *required* `kubernetes.io/hostname` affinity. If Auto Mode replaces the target node, that hostname disappears and the hog can no longer schedule (it goes `Pending`), so it cannot chase the workload onto a fresh node.

**Break:**

```bash
./demo-faults.sh break 7
# Tunables (defaults shown):
#   HOG_REPLICAS=2 HOG_LEAK_MB=100 HOG_STEP_SECONDS=10 HOG_CAP_MB=3000 \
#   HOG_MAX_RUNTIME=900 HOG_REQUEST_MEM=64Mi HOG_MODE=tmpfs \
#   HOG_TARGET_NODE=<node>   ./demo-faults.sh break 7
```

The script prints the chosen target node and lists the co-tenant pods that may be disrupted before it asks for confirmation.

**Verify the fault is active:**

```bash
TARGET=$(cat ~/.devops-agent-demo-faults/scenario-7.target-node)
kubectl get pods -n team-reports -o wide                       # 2 report-generator pods Running on $TARGET
kubectl logs -n team-reports -l app=report-generator --tail=3 --prefix   # working_set_mb climbing ~100Mi/10s
kubectl get node "$TARGET" -w                                  # Ready -> NotReady after ~3-4 min
kubectl describe node "$TARGET" | grep -A8 Conditions          # conditions flip to Unknown "Kubelet stopped posting node status"
kubectl get events -A --sort-by=.lastTimestamp | grep -iE 'NodeNotReady|evict|oom|memory|Zram' | tail -20
```

> **Note:** this cluster has no `metrics-server` (the `metrics.k8s.io` API is served by prometheus-adapter for custom metrics only), so `kubectl top` does **not** work. Track the ramp with the leaker's own stdout (`working_set_mb=...`) and watch the node condition flip instead.

**Observed timeline (trial, break at T0):**

| Time | Event |
|------|-------|
| T0 | `break 7`; 2 `report-generator` pods scheduled on the target node |
| ~T+45s | pods ramping, logs show `working_set_mb` rising ~100Mi/10s per replica |
| ~T+3m | `kubectl` calls to the node's kubelet start timing out (TLS handshake timeout) — the node is starving |
| ~T+3m5s | kubelet stops posting node status; node conditions go to `Unknown` |
| ~T+3m45s | node observed `NotReady`; `node.kubernetes.io/unreachable` NoSchedule+NoExecute taints applied |
| ~T+8m30s | NoExecute toleration (300s) expires; TaintManager evicts every pod off the node; apps reschedule to the other node and to a **new Auto Mode node** that came up ~1 min earlier; the two `report-generator` pods go `Pending` (`FailedScheduling`, hostname affinity no longer satisfiable) |
| after reset | the frozen node did not self-heal or get auto-repaired within ~18 min (its CoreDNS replica's PDB blocked voluntary disruption); deleting its Karpenter `NodeClaim` retired the EC2 instance, which force-removed the stuck pods and let the `team-reports` namespace finish deleting |

**Developer prompts** (an app owner who changed nothing):

> My app otel-sample-app (or go-otel-sample-app) went down / restarted around HH:MM on EKS cluster dev-eks-automode. We didn't deploy anything. What happened?

Follow-ups:

> Which workload caused it?

> How do we stop this happening again?

Platform-engineer variant:

> Why did node `<node-name>` go NotReady / report MemoryPressure?

**Expected agent findings** (as observed in the trial):

- The impacted app's pods did not crash on their own: they were **evicted off a node and rescheduled**, all from the same node `<culprit-node>`. Each shows an event `NodeNotReady` ("Node is not ready") followed by `TaintManagerEviction`, and the replacement pods are `Running` on other nodes. (In this trial the neighbours were *not* OOMKilled in place — the node froze first. Watch for both: `reason: Evicted` and, if the ramp is slower, `lastState.terminated reason: OOMKilled` exit 137.)
- That node's conditions transitioned `Ready: True -> Unknown` with reason `NodeStatusUnknown`, message **"Kubelet stopped posting node status"**, and `MemoryPressure`/`DiskPressure`/`PIDPressure` likewise went to `Unknown`. The node went `NotReady` and `node.kubernetes.io/unreachable` taints were applied (node conditions and events; needs the node-reader role). The EKS node-monitoring agent also emitted a `ZramHighUsage` warning — Auto Mode's Bottlerocket nodes use a zram compressed-swap device that fills under memory pressure.
- **Auto Mode launched a replacement node** (`<new-node>`, a new `general-purpose` NodeClaim) to absorb the rescheduled pods — visible as `nodeclaim ... Launched/Registered/Ready` events and a new node joining (node-reader role / NodeClaims).
- The culprit is the only pod still stuck: `report-generator` in `team-reports` goes `Pending` with `FailedScheduling: ... node(s) didn't match Pod's node affinity/selector ... untolerated taint {node.kubernetes.io/unreachable}` — it is pinned to the dead node. Its Deployment spec shows a memory **request but no limit**.
- Root cause: `team-reports/report-generator` has a memory request but no limit and leaks (its logs show `working_set_mb` climbing to multiple GiB), so nothing caps it and it starves the node it shares with the app pods. It is a different team's batch job, not the app owner's code.

**Metrics note — what is and is not available on this cluster.** AMP is fed by **annotation-based pod scraping** (the `kubernetes-pods` job scrapes pods that expose a Prometheus endpoint), not by cAdvisor or kube-state-metrics. There is therefore **no `container_memory_working_set_bytes`** series, and because `report-generator` exposes no metrics endpoint, AMP has **no memory series for the leaker at all**. There is also no `metrics-server` and no CloudWatch Container Insights. So the per-pod memory ramp is visible only in the leaker's own stdout; the diagnosis rests on **node conditions and events**, which are authoritative here. The annotation-scraped apps (for example `otel-sample-app`, the JVM apps) do have `container_memory_utilization`, `jvm_memory_used_bytes`, etc. in AMP, and those series simply gap while their pods are rescheduled.

If a future cluster adds cAdvisor/kube-state-metrics to AMP (or Container Insights), these queries would show the ramp directly:

```promql
# (only if cAdvisor metrics are scraped into AMP)
sum by (pod) (container_memory_working_set_bytes{namespace="team-reports", pod=~"report-generator.*"}) / 1024 / 1024
sum by (node) (container_memory_working_set_bytes{node="<culprit-node>"}) / 1024 / 1024
sum by (pod) (kube_pod_container_status_restarts_total{namespace="default"})
```

Query AMP with SigV4 (no `awscurl` needed — botocore signs the request). Spaces in the PromQL must be percent-encoded as `%20`, so sign the full URL rather than letting a form-encoder turn them into `+`:

```python
import urllib.parse, urllib.request, json
import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
WS, REGION = "<ws-id>", "us-east-1"
q = 'container_memory_utilization{Namespace="default"}'
url = (f"https://aps-workspaces.{REGION}.amazonaws.com/workspaces/{WS}/api/v1/query?"
       + urllib.parse.urlencode({"query": q}, quote_via=urllib.parse.quote))
creds = botocore.session.Session().get_credentials().get_frozen_credentials()
req = AWSRequest(method="GET", url=url); SigV4Auth(creds, "aps", REGION).add_auth(req)
print(json.load(urllib.request.urlopen(urllib.request.Request(url, headers=dict(req.headers)))))
```

(The Grafana workspace is `<grafana-workspace-id>`; the same queries drive its panels.)

**Fix:**

- Give `report-generator` a memory **limit** (and a right-sized request), so the container is capped and only it is affected if it misbehaves.
- Add a **`LimitRange`** to `team-reports` so any pod without an explicit limit gets a default one, and a **`ResourceQuota`** so the namespace cannot consume the whole node:

  ```yaml
  apiVersion: v1
  kind: LimitRange
  metadata:
    name: default-mem-limit
    namespace: team-reports
  spec:
    limits:
      - type: Container
        default:        { memory: 512Mi }
        defaultRequest: { memory: 128Mi }
  ---
  apiVersion: v1
  kind: ResourceQuota
  metadata:
    name: team-reports-quota
    namespace: team-reports
  spec:
    hard:
      requests.memory: 1Gi
      limits.memory: 2Gi
  ```

- Optionally add **PriorityClasses** so latency-sensitive apps outrank batch jobs, and batch work is preempted first under pressure.

**Reset:**

```bash
./demo-faults.sh reset 7
# Deletes the team-reports namespace, waits for it to be gone, then verifies:
#   all nodes Ready; the 5 default apps + hello-app rolled out; otel-collector Ready.
kubectl get pods -n team-reports            # Error from server (NotFound): namespace deleted
kubectl get nodes                           # all Ready
```

**Realism note (why the design is what it is).** Kubelet eviction ranks pods whose usage most exceeds their requests first, and the kernel OOM killer favours high usage-to-request ratios and large resident sets. A single, small-request, anonymous-memory hog therefore usually just evicts or OOM-kills *itself* — tier (c), no collateral, which is a failed demo. The three outcome tiers this scenario can land in are:

- **(a)** target node goes `NotReady`, Auto Mode replaces it, app pods reschedule elsewhere;
- **(b)** node reports `MemoryPressure` and neighbour pods are evicted or OOMKilled while the node stays up;
- **(c)** only the hog dies — the design failed and needs tuning (more replicas, faster ramp, larger request, or the `tmpfs` vector).

The `tmpfs` mechanism plus two packed replicas is chosen to reach tier (a) or (b) reliably.

**Trial result (2026-11-26).** The default configuration (2 replicas, `tmpfs`, 100Mi/10s, 64Mi request, no limit) reached **tier (a)** on the first attempt: the target node went `NotReady` ~3m45s after the break, and ~5 min after that the node-not-ready taint evicted every pod off it and they rescheduled onto the surviving node plus a new Auto Mode node. The leaker self-stopped (`Pending`, hostname affinity). The failure mode was a hard node freeze ("Kubelet stopped posting node status"), not graceful kubelet `MemoryPressure` eviction or in-place neighbour OOM-kills — the two `report-generator` replicas drove node memory (and the zram swap device) to exhaustion faster than the kubelet could react. So the demo lands cleanly on tier (a) "node down, apps move, trace it to the leaker"; it did **not** produce tier (b) in-place neighbour OOM-kills in this run. If you want tier (b) instead (neighbours OOMKilled while the node survives), lower the pressure: a single replica (`HOG_REPLICAS=1`) and/or a smaller cap (`HOG_CAP_MB=1500`) so the node stays Ready while the kernel OOM killer picks off a neighbour.

**Recovery caveat.** Because the node froze (unreachable kubelet), its pods cannot terminate gracefully and EKS node auto-repair did not retire it within ~18 min — the CoreDNS replica's PodDisruptionBudget blocked voluntary disruption. `reset 7` deletes the `team-reports` namespace, but the namespace stays `Terminating` until the dead node's pods are gone. To finish recovery, retire the frozen node the Auto Mode-native way:

```bash
kubectl get nodeclaims -o wide                       # find the NodeClaim whose NODE is the frozen one
kubectl delete nodeclaim <nodeclaim-for-culprit-node>   # Karpenter terminates the instance and force-GCs its pods
```

After the instance is gone the namespace finishes deleting and `./demo-faults.sh status` shows scenario 7 clear. Allow ~5 minutes after the break before concluding from the app metrics in AMP, which lags scraping.

## Cleanup All

```bash
./demo-faults.sh reset all
./demo-faults.sh status          # every scenario "clear", no pods listed as not ready
kubectl get deploy -n default    # all apps at full READY
```

`reset all` runs `reset 7` first: it deletes the `team-reports` namespace, waits for it to be gone, and then verifies recovery (all nodes Ready; the 5 default apps, `hello-app` and `otel-collector` rolled out). If the fault replaced a node, Auto Mode brings a new one up automatically; `reset 7` reports any node that is still not Ready.

Optional:

```bash
aws ecr batch-delete-image --repository-name go-otel-sample-app --image-ids imageTag=arm64-only
kubectl get namespace team-reports    # should be NotFound; delete it by hand if a reset was interrupted
rm -rf ~/.devops-agent-demo-faults
```

If you applied the read-only agent setup and want to undo it, re-associate `AmazonEKSClusterAdminPolicy`, disassociate `AmazonEKSViewPolicy`, and delete the `devops-agent-node-reader` ClusterRole and ClusterRoleBinding.

## Quick Reference

| # | Break | Workload | Symptom | Evidence the agent uses | Fix | Reset |
|---|-------|----------|---------|-------------------------|-----|-------|
| 1 | `break 1` | `otel-sample-app` | `ImagePullBackOff` on new RS, old pods serve | events, ReplicaSets, ECR | use an existing tag | `reset 1` |
| 2 | `break 2` | `go-otel-sample-app` | `exec format error`, new pod crash-loops | pod logs, node arch, node pools | multi-arch build | `reset 2` |
| 3 | `break 3` | `java-otel-sample-app` | `OOMKilled` (137), restarts | pod status, events, Deployment spec | 512Mi limit, `MaxRAMPercentage` | `reset 3` |
| 4 | `break 4` | `otel-sample-app` | healthy app, no traces | X-Ray, pod logs, RS env diff | restore OTLP endpoint | `reset 4` |
| 5 | `break 5` | `sample-metrics-app` | new pods Pending | `FailedScheduling` events, node pools | remove `nodeSelector` | `reset 5` |
| 6 | `break 6` | `java-otel-sample-app` | 500s on `/api/users`, HPA scales | AMP, X-Ray, pod logs, HPA | fix app error handling | `reset 6` |
| 7 | `break 7` | `team-reports/report-generator` | app pods on a node evicted/OOMKilled, node `MemoryPressure`/`NotReady` | node conditions/events, `NodeNotReady`/`TaintManagerEviction` and eviction/OOM events, `report-generator` logs (`working_set_mb`) | set memory limit + `LimitRange`/`ResourceQuota` | `reset 7` |

## Relationship to Existing Demo Scenarios

| Existing | Where | Relationship |
|----------|-------|--------------|
| Scenario 1: Normal Load Testing | [README.md](../README.md) | Baseline traffic. Useful before any scenario here, so the agent has normal data to compare against |
| Scenario 2: Simulated Incident | [README.md](../README.md) | Merged into Scenario 6 above |
| Scenario 3: Multi-Application Load | [README.md](../README.md) | Not duplicated. Can run alongside scenarios 1-5 as background traffic |
| Quick test / incident simulation / targeted load | [QUICKSTART.md](../QUICKSTART.md) | Same traffic patterns as the README scenarios |
| OTEL collector IRSA failure | [AGENT_INSTRUCTIONS.md](../AGENT_INSTRUCTIONS.md), [push-logs-simple.py](../push-logs-simple.py) | Fabricated logs; not used, see Demo hygiene |

## Resources

- [AWS DevOps Agent Documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/)
- [EKS access policy permissions](https://docs.aws.amazon.com/eks/latest/userguide/access-policy-permissions.html)
- [Main demo README](../README.md)

# Instructions for AWS DevOps Agent

## CloudWatch Logs Location

**Log Group**: `/aws/eks/automode-platform/applications`
**Region**: `us-east-1`

### Available Log Streams (with data):

1. **otel-collector-errors** ← Use this for OTEL collector logs
   - Contains IAM role assumption failures
   - Shows IRSA misconfiguration errors
   - 13 log entries

2. **go-otel-app-errors**
   - Connection refused errors to OTEL collector
   - 8 log entries

3. **java-otel-app-errors**
   - GRPC connection failures
   - 8 log entries

4. **python-otel-app-warnings**
   - Intermittent connection issues
   - 7 log entries

5. **sample-metrics-app-info**
   - Healthy operation logs
   - 8 log entries

### ⚠️ Do NOT use:
- `otel-collector-logs` (empty, no data)

## Key Log Entries

### OTEL Collector Root Cause
```
Log Stream: otel-collector-errors
Key Messages:
- "[ERROR] OTEL Collector CrashLoopBackOff - IAM Role Assumption Failure"
- "Error: invalid configuration: extensions::sigv4auth: could not retrieve credential provider"
- "failed to refresh cached credentials, failed to retrieve credentials"
- "operation error STS: AssumeRoleWithWebIdentity"
- "https response error StatusCode: 403"
- "api error AccessDenied: Not authorized to perform sts:AssumeRoleWithWebIdentity"
- "Root Cause: OTEL collector service account cannot assume IAM role"
- "IAM Role: EKS-ADOT-PrometheusRemoteWrite-EKS-Platform-Cluster"
- "Issue: IRSA (IAM Roles for Service Accounts) misconfiguration"
```

### Application Impact
```
Go App (go-otel-app-errors):
- "transport: Error while dialing: dial tcp 172.20.154.180:4317: connect: connection refused"
- "Impact: 100% request failure rate (8,970 failed requests)"

Java App (java-otel-app-errors):
- "Connection refused: otel-collector.opentelemetry.svc.cluster.local:4317"
- "Impact: 100% request failure rate (8,985 failed requests)"

Python App (python-otel-app-warnings):
- "ConnectionError: Failed to connect to otel-collector:4317"
- "Impact: 84.55% success rate (1,386 failed out of 8,970 requests)"
```

## Kubernetes Resources

**Cluster**: `dev-eks-automode`
**Region**: `us-east-1`

### Pods to Check:
- `otel-collector` in namespace `opentelemetry` (CrashLoopBackOff)
- `go-otel-sample-app` in namespace `default`
- `java-otel-sample-app` in namespace `default`
- `otel-sample-app` in namespace `default`
- `sample-metrics-app` in namespace `default`

### Service Account to Inspect:
- Name: `otel-collector-sa`
- Namespace: `opentelemetry`
- Issue: Missing or incorrect `eks.amazonaws.com/role-arn` annotation

### IAM Role to Check:
- Role Name: `EKS-ADOT-PrometheusRemoteWrite-EKS-Platform-Cluster`
- Issue: Trust policy may not include EKS OIDC provider

## Root Cause Summary

**Problem**: OTEL collector cannot start due to IAM role assumption failure

**Technical Details**:
1. OTEL collector uses IRSA (IAM Roles for Service Accounts)
2. Service account `otel-collector-sa` needs annotation: `eks.amazonaws.com/role-arn`
3. IAM role needs trust relationship with EKS OIDC provider
4. Without valid credentials, collector fails to write to Amazon Managed Prometheus
5. Collector crashes, becomes unavailable on port 4317
6. Applications cannot export telemetry, causing connection failures

**Impact**:
- Primary: OTEL collector 100% unavailable
- Secondary: Go and Java apps 100% failure rate
- Tertiary: Python app 15% failure rate
- No impact: Sample metrics app (no OTEL dependency)

## Recommended Fixes

1. **Immediate**: Fix IRSA configuration
   - Add proper annotation to service account
   - Verify IAM role trust policy
   - Restart OTEL collector deployment

2. **Short-term**: Add monitoring
   - CloudWatch alarms for collector pod status
   - Alerts for connection failures

3. **Long-term**: Improve resilience
   - Add liveness/readiness probes
   - Implement graceful degradation in apps
   - Enable local telemetry buffering

## Verification Commands

```bash
# View logs
aws logs tail /aws/eks/automode-platform/applications \
  --log-stream-names otel-collector-errors \
  --since 10m \
  --region us-east-1

# Check pod status
kubectl get pods -n opentelemetry
kubectl describe pod -l app=otel-collector -n opentelemetry

# Check service account
kubectl describe serviceaccount otel-collector-sa -n opentelemetry

# Check IAM role
aws iam get-role --role-name EKS-ADOT-PrometheusRemoteWrite-EKS-Platform-Cluster
```

## Permissions Configured

✅ Kubernetes API access (EKS Cluster Admin)
✅ CloudWatch Logs read access (logs:GetLogEvents)
✅ CloudWatch Metrics access
✅ EKS describe permissions

All permissions are attached to: `TestDevOpsAgentSpace-DevOpsAgentRole`

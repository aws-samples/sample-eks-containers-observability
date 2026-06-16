# Pluggable Observability Backend

This document describes how to extend the platform to support third-party observability backends (e.g., Datadog, New Relic, Splunk) alongside or instead of the default AWS-native services.

## Current Architecture

The platform uses **OpenTelemetry** as the collection layer with AWS-native exporters:

| Signal  | Exporter                    | Destination                          |
|---------|-----------------------------|--------------------------------------|
| Traces  | `awsxray`                   | AWS X-Ray                            |
| Metrics | `prometheusremotewrite`     | Amazon Managed Service for Prometheus |
| Metrics | `awsemf`                    | CloudWatch Embedded Metrics           |
| Logs    | `awscloudwatchlogs`         | CloudWatch Logs                      |

**Key insight**: Since OpenTelemetry is already the collection layer, only the *exporters* need to change — application instrumentation remains untouched.

## Integration Points

### Files That Need Changes

| Layer | File | Change |
|-------|------|--------|
| Config | `eks_platform/config/environment_config.py` | Add backend selector and credentials config |
| Platform | `eks_platform/platform/monitoring/observability_stack.py` | Gate Grafana/AMP creation based on backend |
| Apps | `eks_platform/applications/workloads/otel_app_construct.py` | Template OTEL collector exporters |
| Apps | `eks_platform/applications/workloads/go_otel_app_construct.py` | Same as above |
| Apps | `eks_platform/applications/workloads/java_otel_app_construct.py` | Same as above |
| Infra | `app.py` | Read `observability_backend` from CDK context |
| Security | New | Mount third-party API key into collector pods |

## Implementation Plan

### Step 1: Extend Configuration

In `eks_platform/config/environment_config.py`, extend `MonitoringConfig`:

```python
@dataclass
class MonitoringConfig:
    # Existing fields
    prometheus_enabled: bool = True
    grafana_enabled: bool = True
    retention_days: int = 30
    scrape_interval: str = "15s"
    namespace: str = "monitoring"

    # New: observability backend selection
    backend: str = "aws"  # "aws" | "datadog" | "both"
    datadog_api_key_secret_arn: Optional[str] = None  # AWS Secrets Manager ARN
    datadog_site: str = "datadoghq.com"  # datadoghq.com | datadoghq.eu | us3.datadoghq.com | etc.
```

### Step 2: Gate AWS-Native Resources

In `observability_stack.py`, conditionally create Grafana and AMP:

```python
if monitoring_config.backend in ("aws", "both"):
    # Existing: Create AMP workspace, Grafana workspace, IAM roles
    ...

if monitoring_config.backend in ("datadog", "both"):
    # New: Create Datadog API key secret reference, any IAM permissions needed
    ...
```

### Step 3: Template OTEL Collector Exporters

The ADOT collector config in `otel_app_construct.py` (and Go/Java variants) uses standard OTEL Collector pipeline format. Swap or add exporters based on the backend choice.

#### AWS-only (current default)

```yaml
exporters:
  awsxray:
    region: {region}
  prometheusremotewrite:
    endpoint: https://aps-workspaces.{region}.amazonaws.com/workspaces/{workspace_id}/api/v1/remote_write
    auth:
      authenticator: sigv4auth
  awscloudwatchlogs:
    region: {region}
    log_group_name: "/aws/eks/automode-platform/applications"

service:
  pipelines:
    traces:
      exporters: [awsxray]
    metrics:
      exporters: [prometheusremotewrite]
    logs:
      exporters: [awscloudwatchlogs]
```

#### Datadog-only

```yaml
exporters:
  datadog:
    api:
      key: "${DD_API_KEY}"
      site: datadoghq.com
    metrics:
      histograms:
        mode: distributions
      resource_attributes_as_tags: true
    traces:
      endpoint: https://trace.agent.datadoghq.com
    logs:
      endpoint: https://http-intake.logs.datadoghq.com

service:
  pipelines:
    traces:
      exporters: [datadog]
    metrics:
      exporters: [datadog]
    logs:
      exporters: [datadog]
```

#### Both (fan-out)

```yaml
exporters:
  awsxray:
    region: {region}
  prometheusremotewrite:
    endpoint: ...
  datadog:
    api:
      key: "${DD_API_KEY}"
      site: datadoghq.com

service:
  pipelines:
    traces:
      exporters: [awsxray, datadog]
    metrics:
      exporters: [prometheusremotewrite, datadog]
    logs:
      exporters: [awscloudwatchlogs, datadog]
```

### Step 4: Secret Management

Store the third-party API key in AWS Secrets Manager and inject it into the collector pod:

1. Create a Kubernetes Secret from Secrets Manager:
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: datadog-api-key
     namespace: opentelemetry
   type: Opaque
   data:
     api-key: <base64-encoded-key>
   ```

2. Mount as environment variable in the ADOT collector sidecar:
   ```yaml
   env:
     - name: DD_API_KEY
       valueFrom:
         secretKeyRef:
           name: datadog-api-key
           key: api-key
   ```

Alternatively, use **External Secrets Operator** or **EKS Pod Identity** to sync from Secrets Manager automatically.

### Step 5: CDK Context Toggle

Deploy-time selection via CDK context:

```bash
# AWS native (default)
cdk deploy

# Datadog only
cdk deploy \
  --context observability_backend=datadog \
  --context datadog_api_key_secret_arn=arn:aws:secretsmanager:us-west-2:123456789012:secret:datadog-api-key

# Both (fan-out to AWS + Datadog)
cdk deploy \
  --context observability_backend=both \
  --context datadog_api_key_secret_arn=arn:aws:secretsmanager:us-west-2:123456789012:secret:datadog-api-key

# Datadog EU site
cdk deploy \
  --context observability_backend=datadog \
  --context datadog_site=datadoghq.eu \
  --context datadog_api_key_secret_arn=arn:aws:secretsmanager:eu-west-1:123456789012:secret:datadog-api-key
```

## Extending to Other Backends

The same pattern works for any OTEL-compatible backend:

| Backend    | Exporter Name      | Key Config                              |
|------------|--------------------|-----------------------------------------|
| Datadog    | `datadog`          | `api.key`, `api.site`                   |
| New Relic  | `otlp`             | `endpoint: otlp.nr-data.net:4317`       |
| Splunk     | `splunk_hec`       | `token`, `endpoint`                     |
| Grafana Cloud | `otlp`          | `endpoint: otlp-gateway-prod-*.grafana.net` |
| Dynatrace  | `otlphttp`        | `endpoint`, `Authorization` header      |

To add a new backend:
1. Add config fields to `MonitoringConfig`
2. Add the exporter block to the OTEL collector config template
3. Wire the secret/credentials injection
4. Gate any backend-specific infrastructure (dashboards, alerts) in the CDK stack

## What Stays the Same

- **Application instrumentation code** — All apps use OpenTelemetry SDK; no changes needed
- **Prometheus scraping** — The local Prometheus server and annotations still work
- **HPA auto-scaling** — Prometheus Adapter continues to serve custom metrics to HPA
- **OTEL receivers and processors** — Only exporters change

## Considerations

- **Cost**: Running `both` mode doubles egress for telemetry data
- **Latency**: Adding exporters increases collector memory/CPU requirements
- **HPA dependency**: If you disable AWS Prometheus entirely, you need an alternative metrics source for HPA (e.g., Datadog Cluster Agent with External Metrics)
- **Collector image**: The default ADOT image includes AWS exporters. For Datadog, use the upstream `otel/opentelemetry-collector-contrib` image which includes the Datadog exporter

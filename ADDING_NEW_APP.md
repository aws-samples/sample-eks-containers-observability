# Adding a New Application to EKS Fargate Platform

This guide explains how to add a new application to the existing EKS Fargate platform with full observability integration.

## Prerequisites

- Application containerized with Dockerfile
- Basic understanding of Kubernetes manifests
- AWS CDK knowledge for infrastructure changes

## Step 1: Application Code Requirements

### 1.1 OpenTelemetry Instrumentation

Add OpenTelemetry SDK to your application:

**Python Example:**
```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# Configure OTEL
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
```

**Go Example:**
```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
)
```

### 1.2 Required Metrics

Implement these standard metrics in your application:

**HTTP Metrics:**
- `http_requests_total` - Counter of HTTP requests by method, endpoint, status
- `http_request_duration_seconds` - Histogram of request latencies

**System Metrics:**
- `app_cpu_usage_percent` - CPU usage percentage
- `app_memory_usage_bytes` - Memory usage in bytes
- `app_memory_usage_percent` - Memory usage percentage

**Business Metrics (Optional):**
- Application-specific counters and gauges

### 1.3 Metrics Endpoint

Expose metrics on `/metrics` endpoint for Prometheus scraping:

```python
@app.route('/metrics')
def metrics():
    # Return Prometheus format metrics
    return prometheus_metrics_output
```

### 1.4 Health Check

Implement health check endpoint:

```python
@app.route('/health')
def health():
    return {"status": "healthy"}
```

## Step 2: Infrastructure Changes

### 2.1 Create ECR Repository

Add to `eks_fargate_platform/infrastructure/ecr_construct.py`:

```python
# Add new repository
self.new_app_repository = ecr.Repository(
    self, "NewAppRepository",
    repository_name="new-app",
    removal_policy=RemovalPolicy.DESTROY
)

# Add output
CfnOutput(self, "NewAppRepoUri",
    value=self.new_app_repository.repository_uri,
    description="ECR repository URI for new app"
)
```

### 2.2 Create Application Construct

Create `eks_fargate_platform/applications/workloads/new_app_construct.py`:

```python
from aws_cdk import (
    aws_eks as eks,
    CfnOutput
)
from constructs import Construct

class NewAppConstruct(Construct):
    def __init__(self, scope, construct_id, cluster, repository_uri, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Create deployment
        app_deployment = cluster.add_manifest("NewAppDeployment", {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "new-app",
                "namespace": "default",
                "labels": {"app": "new-app", "workload": "fargate"}
            },
            "spec": {
                "replicas": 2,
                "selector": {"matchLabels": {"app": "new-app"}},
                "template": {
                    "metadata": {
                        "labels": {"app": "new-app", "workload": "fargate"},
                        "annotations": {
                            "prometheus.io/scrape": "true",
                            "prometheus.io/port": "8080",
                            "prometheus.io/path": "/metrics"
                        }
                    },
                    "spec": {
                        "tolerations": [{
                            "key": "eks.amazonaws.com/compute-type",
                            "operator": "Equal",
                            "value": "fargate",
                            "effect": "NoSchedule"
                        }],
                        "containers": [{
                            "name": "new-app",
                            "image": f"{repository_uri}:latest",
                            "ports": [
                                {"containerPort": 8000, "name": "http"},
                                {"containerPort": 8080, "name": "metrics"}
                            ],
                            "env": [
                                {"name": "OTEL_EXPORTER_OTLP_ENDPOINT", 
                                 "value": "http://otel-collector.opentelemetry:4317"},
                                {"name": "OTEL_SERVICE_NAME", "value": "new-app"},
                                {"name": "AWS_REGION", "value": "eu-west-1"}
                            ],
                            "resources": {
                                "requests": {"memory": "128Mi", "cpu": "100m"},
                                "limits": {"memory": "256Mi", "cpu": "200m"}
                            },
                            "readinessProbe": {
                                "httpGet": {"path": "/health", "port": 8000},
                                "initialDelaySeconds": 10,
                                "periodSeconds": 5
                            },
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": 8000},
                                "initialDelaySeconds": 15,
                                "periodSeconds": 10
                            }
                        }]
                    }
                }
            }
        })
        
        # Create service
        app_service = cluster.add_manifest("NewAppService", {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "new-app", "namespace": "default"},
            "spec": {
                "selector": {"app": "new-app"},
                "ports": [
                    {"port": 8000, "targetPort": 8000, "name": "http"},
                    {"port": 8080, "targetPort": 8080, "name": "metrics"}
                ]
            }
        })
        
        # Create HPA with custom metrics (optional)
        app_hpa = cluster.add_manifest("NewAppHPA", {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": "new-app-hpa", "namespace": "default"},
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "new-app"
                },
                "minReplicas": 1,
                "maxReplicas": 5,
                "metrics": [
                    # Resource-based scaling
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {"type": "Utilization", "averageUtilization": 70}
                        }
                    },
                    # Custom metrics scaling (via Prometheus Adapter)
                    {
                        "type": "Pods",
                        "pods": {
                            "metric": {"name": "new_app_requests_rate"},
                            "target": {"type": "AverageValue", "averageValue": "10"}
                        }
                    }
                ]
            }
        })
```

### 2.3 Update Stack Definition

Add to your main stack file:

```python
from eks_fargate_platform.applications.workloads.new_app_construct import NewAppConstruct

# In your stack __init__ method
new_app = NewAppConstruct(
    self, "NewApp",
    cluster=cluster,
    repository_uri=ecr_stack.new_app_repository.repository_uri
)
```

## Step 3: OTEL Collector Configuration

### 3.1 Update Metric Filters

Add your app metrics to the OTEL collector filter in `otel_app_construct.py`:

```yaml
filter:
  metrics:
    include:
      match_type: regexp
      metric_names:
        - new_app_.*  # Add this line
        - pod_cpu_utilization
        - pod_memory_utilization
        # ... existing metrics
```

### 3.2 Prometheus Adapter Configuration (For Custom HPA Metrics)

If you want to use custom metrics for HPA scaling, update the Prometheus Adapter configuration in `prometheus_construct.py`:

```yaml
# Add to prometheus-adapter ConfigMap
rules:
- seriesQuery: 'http_requests_total{app="new-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    matches: "^http_requests_total"
    as: "new_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="new-app",<<.LabelMatchers>>}[2m])'
```

### 3.3 Update Resource Processor

Ensure the resource processor doesn't override your service name:

```yaml
resource:
  attributes:
    - action: insert
      key: service.namespace
      value: "default"
    # Remove hardcoded service.name to preserve app names
```

## Step 4: Grafana Dashboard

### 4.1 Create Dashboard JSON

Create `grafana_dashboard/new-app-dashboard.json`:

```json
{
  "dashboard": {
    "title": "New App Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "type": "stat",
        "targets": [{
          "expr": "rate(http_requests_total{app=\"new-app\"}[5m])"
        }]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [{
          "expr": "(rate(http_requests_total{app=\"new-app\",status=\"500\"}[5m]) / rate(http_requests_total{app=\"new-app\"}[5m])) * 100 or vector(0)"
        }]
      },
      {
        "title": "CPU Usage",
        "type": "stat",
        "targets": [{
          "expr": "new_app_cpu_usage_percent{app=\"new-app\"}"
        }]
      },
      {
        "title": "Available Replicas",
        "type": "stat",
        "targets": [{
          "expr": "count(up{app=\"new-app\"})"
        }]
      }
    ]
  }
}
```

### 4.2 Update README

Add dashboard documentation to main README.md:

```markdown
### **New App Dashboard**
**File**: `new-app-dashboard.json`

![New App Dashboard](grafana_dashboard/new-app-dashboard.png)

**Features**:
- Application performance metrics
- Error rate monitoring
- Resource utilization
- Pod replica tracking
```

## Step 5: Deployment Process

### 5.1 Build and Push Image

```bash
# Get ECR repository URI
NEW_APP_ECR_REPO=$(aws cloudformation describe-stacks --stack-name EcrStack --query "Stacks[0].Outputs[?OutputKey=='NewAppRepoUri'].OutputValue" --output text)

# Build and push
aws ecr get-login-password --region $(aws configure get region) | docker login --username AWS --password-stdin $NEW_APP_ECR_REPO
docker build -t $NEW_APP_ECR_REPO:latest ./new-app
docker push $NEW_APP_ECR_REPO:latest
```

### 5.2 Deploy Infrastructure

```bash
cdk deploy --all
```

### 5.3 Verify Deployment

```bash
# Check pods
kubectl get pods -l app=new-app

# Check metrics endpoint
kubectl port-forward svc/new-app 8080:8080
curl http://localhost:8080/metrics

# Check HPA
kubectl get hpa new-app-hpa
```

## Step 6: Monitoring Verification

### 6.1 Prometheus Metrics

Verify metrics are being scraped:

```bash
kubectl port-forward -n monitoring svc/prometheus-service 9090:9090
# Check http://localhost:9090/targets for new-app targets
```

### 6.2 OTEL Collector Logs

Check if traces/logs are being received:

```bash
kubectl logs -n opentelemetry deployment/otel-collector | grep "new-app"
```

### 6.3 CloudWatch Logs

Verify logs are appearing in CloudWatch:

```bash
aws logs describe-log-streams --log-group-name "/aws/eks/fargate-platform/applications"
```

### 6.4 Prometheus Adapter (For Custom HPA Metrics)

If using custom metrics for HPA, verify the Prometheus Adapter can access your metrics:

```bash
# Check if custom metrics are available
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1

# Check specific metric for your app
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1/namespaces/default/pods/*/new_app_requests_rate

# Check adapter logs
kubectl logs -n monitoring deployment/prometheus-adapter
```

## Step 7: Troubleshooting

### Common Issues

1. **Metrics not appearing**: Check Prometheus annotations and port configuration
2. **OTEL data not flowing**: Verify OTEL_EXPORTER_OTLP_ENDPOINT environment variable
3. **Pods not starting**: Check resource limits and Fargate tolerations
4. **HPA not scaling**: Verify metrics-server and custom metrics are available

### Debug Commands

```bash
# Check pod logs
kubectl logs -l app=new-app

# Check service endpoints
kubectl get endpoints new-app

# Check HPA metrics
kubectl describe hpa new-app-hpa

# Check custom metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1
```

## Best Practices

1. **Use consistent naming**: Follow `app-name` pattern for all resources
2. **Add proper labels**: Include `app` and `workload` labels
3. **Set resource limits**: Always define CPU/memory requests and limits
4. **Implement health checks**: Add readiness and liveness probes
5. **Use structured logging**: Log in JSON format for better parsing
6. **Add monitoring annotations**: Include Prometheus scraping annotations
7. **Test locally**: Verify metrics endpoint before deployment
8. **Document metrics**: Update README with new metrics and dashboard info

## Example Applications

Refer to existing applications for implementation examples:
- `otel-sample-app/` - Python Flask with full OTEL integration
- `go-otel-sample-app/` - Go application with system monitoring
- `sample-metrics-app/` - Basic Prometheus metrics integration
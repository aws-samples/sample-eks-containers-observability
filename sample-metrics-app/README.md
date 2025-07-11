# Sample Metrics App for EKS Fargate

This is a simple Python application that generates sample metrics and logs for demonstration purposes. It's designed to be deployed to an EKS Fargate cluster and expose Prometheus metrics.

## Features

- Generates sample HTTP request metrics (count, latency)
- Simulates memory and CPU usage metrics
- Produces various log levels (INFO, WARNING, ERROR)
- Exposes metrics via Prometheus endpoint on port 8000

## Deployment Instructions

1. Configure kubectl for your EKS cluster:
   ```bash
   # For the Fargate cluster
   aws eks update-kubeconfig --name <FARGATE_CLUSTER_NAME> --region <AWS_REGION>
   kubectl config use-context <FARGATE_CLUSTER_NAME>

   # For the Auto Mode cluster
   aws eks update-kubeconfig --name <AUTO_MODE_CLUSTER_NAME> --region <AWS_REGION>
   kubectl config use-context <AUTO_MODE_CLUSTER_NAME>
   ```

   Note: Replace `<FARGATE_CLUSTER_NAME>`, `<AUTO_MODE_CLUSTER_NAME>`, and `<AWS_REGION>` with the actual values from the CDK outputs.

2. Make sure you have the AWS CLI and Docker configured:
   ```bash
   aws configure
   ```

3. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

4. Verify the deployment:
   ```bash
   kubectl get pods -l app=sample-metrics-app
   ```

5. Access the metrics locally:
   ```bash
   kubectl port-forward svc/sample-metrics-app 8000:8000
   ```
   Then open http://localhost:8000 in your browser.

## Metrics Available

- `app_requests_total`: Counter of HTTP requests (labels: endpoint, status)
- `app_request_latency_seconds`: Histogram of request latency (labels: endpoint)
- `app_memory_usage_bytes`: Gauge of memory usage
- `app_cpu_usage_percent`: Gauge of CPU usage percentage

## Integration with AWS Managed Prometheus

The deployment includes Prometheus annotations for automatic scraping:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/"
```

## Switching Between Clusters

To switch between your EKS clusters:

```bash
# Get available contexts
kubectl config get-contexts

# Switch to Fargate cluster
kubectl config use-context <FARGATE_CLUSTER_NAME>

# Switch to Auto Mode cluster
kubectl config use-context <AUTO_MODE_CLUSTER_NAME>
```

After CDK deployment, you can find the exact commands in the stack outputs.

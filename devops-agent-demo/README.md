# AWS DevOps Agent Demo

This folder contains tools and scripts to demonstrate AWS DevOps Agent capabilities with the EKS Platform applications.

## Overview

The AWS DevOps Agent is a frontier agent that helps you respond to incidents, identify root causes, and prevent future issues through systematic analysis of operational data. This demo generates realistic traffic patterns and metrics that the DevOps Agent can analyze.

## Prerequisites

- EKS cluster deployed with sample applications (sample-metrics-app, otel-sample-app, go-otel-sample-app, java-otel-sample-app)
- kubectl configured to access the cluster
- Python 3.7+ with requests library
- AWS DevOps Agent deployed via CDK (see [DEVOPS_AGENT_GUIDE.md](../DEVOPS_AGENT_GUIDE.md))
- Agent Space created in AWS Console

## Traffic Generator

The `traffic-generator.py` script generates HTTP traffic to your deployed applications to produce metrics for analysis.

### Installation

```bash
# Install required Python packages
pip install requests

# Make the script executable
chmod +x traffic-generator.py
```

### Usage

#### Basic Usage

Generate traffic to all applications for 5 minutes at 10 requests/second:

```bash
python traffic-generator.py --app all --duration 300 --rps 10
```

#### Target Specific Application

```bash
# Sample Metrics App
python traffic-generator.py --app sample-metrics --duration 300 --rps 20

# Python OTEL App
python traffic-generator.py --app otel --duration 300 --rps 15

# Go OTEL App
python traffic-generator.py --app go-otel --duration 300 --rps 15

# Java OTEL App
python traffic-generator.py --app java-otel --duration 300 --rps 15
```

#### Custom Error Rate

Generate traffic with 20% error rate to simulate issues:

```bash
python traffic-generator.py --app all --duration 300 --rps 10 --error-rate 0.2
```

### Command Line Options

- `--app`: Target application (choices: sample-metrics, otel, go-otel, java-otel, all)
- `--duration`: Duration in seconds (default: 300)
- `--rps`: Requests per second (default: 10)
- `--error-rate`: Error rate as decimal (default: 0.1 = 10%)
- `--base-url`: Override base URL for custom endpoints

## Setting Up Port Forwarding

Before running the traffic generator, set up port forwarding to access the applications:

```bash
# Sample Metrics App (port 8000)
kubectl port-forward svc/sample-metrics-app 8000:8000 -n default &

# Python OTEL App (port 8080)
kubectl port-forward svc/otel-sample-app 8080:8000 -n default &

# Go OTEL App (port 8090)
kubectl port-forward svc/go-otel-sample-app 8090:8080 -n default &

# Java OTEL App (port 8081)
kubectl port-forward svc/java-otel-sample-app 8081:8080 -n default &
```

## Testing with AWS DevOps Agent

### Step 1: Generate Traffic and Metrics

Run the traffic generator to create realistic load:

```bash
# Generate normal traffic
python traffic-generator.py --app all --duration 600 --rps 15

# Or generate traffic with errors to simulate incidents
python traffic-generator.py --app all --duration 600 --rps 20 --error-rate 0.3
```

### Step 2: Monitor Metrics

Check that metrics are being collected:

```bash
# View HPA status (should show scaling based on metrics)
kubectl get hpa -A

# Check custom metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq .

# View specific metric values
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1/namespaces/default/pods/*/sample_app_requests_rate | jq .
```

### Step 3: Access AWS DevOps Agent

1. Open the AWS Console and navigate to AWS DevOps Agent
2. Select your Agent Space
3. Click on "Operator access" to open the DevOps Agent web app
4. Start a new investigation:
   - Choose "High CPU usage" or "Error rate spike" as starting point
   - Select the time range when you generated traffic
   - Provide the AWS Account ID and region (us-east-1)

### Step 4: Analyze Results

The AWS DevOps Agent will:
- Correlate metrics from Amazon Managed Prometheus
- Analyze logs from CloudWatch Logs
- Review application topology and dependencies
- Identify patterns and anomalies
- Provide root cause analysis
- Suggest mitigation strategies

## Example Scenarios

### Scenario 1: Normal Load Testing

Generate steady traffic to establish baseline metrics:

```bash
python traffic-generator.py --app all --duration 900 --rps 10 --error-rate 0.05
```

**Expected Outcome:**
- Applications scale based on HPA rules
- Metrics show consistent request rates
- Low error rates (5%)
- DevOps Agent can establish normal operational patterns

### Scenario 2: Simulated Incident

Generate high load with elevated error rates:

```bash
python traffic-generator.py --app java-otel --duration 600 --rps 30 --error-rate 0.25
```

**Expected Outcome:**
- HPA scales up replicas
- Error rates spike in metrics
- CloudWatch alarms may trigger
- DevOps Agent can investigate the incident and identify:
  - Which application is affected
  - Error patterns and rates
  - Resource utilization
  - Potential root causes

### Scenario 3: Multi-Application Load

Test all applications simultaneously with different patterns:

```bash
# Terminal 1: Normal load on sample-metrics-app
python traffic-generator.py --app sample-metrics --duration 1200 --rps 15 --error-rate 0.05 &

# Terminal 2: High load on go-otel-app
python traffic-generator.py --app go-otel --duration 1200 --rps 25 --error-rate 0.1 &

# Terminal 3: Problematic load on java-otel-app
python traffic-generator.py --app java-otel --duration 1200 --rps 20 --error-rate 0.3 &
```

**Expected Outcome:**
- DevOps Agent can differentiate between applications
- Identify which service has issues
- Correlate metrics across the platform
- Provide targeted recommendations

## Monitoring and Observability

### Prometheus Metrics

Access Prometheus to view raw metrics:

```bash
kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring
```

Open http://localhost:9090 and query:
- `http_requests_total` - Total HTTP requests
- `go_app_requests_rate` - Go app request rate
- `sample_app_requests_rate` - Sample app request rate
- `pod_cpu_utilization` - CPU utilization

### Grafana Dashboards

Import the pre-built dashboards from the `grafana_dashboard/` folder:
- `otel-app-dashboard.json` - Python OTEL app metrics
- `go-otel-app-dashboard.json` - Go OTEL app metrics
- `java-otel-app-dashboard.json` - Java OTEL app metrics
- `api-monitoring.json` - API performance metrics

### CloudWatch Logs

View application logs:

```bash
# List log streams
aws logs describe-log-streams \
  --log-group-name /aws/eks/automode-platform/applications \
  --region us-east-1

# View recent logs
aws logs tail /aws/eks/automode-platform/applications --follow --region us-east-1
```

## Troubleshooting

### Port Forwarding Issues

If you can't access applications:

```bash
# Check if services exist
kubectl get svc -n default

# Check if pods are running
kubectl get pods -n default

# Restart port forwarding
pkill -f "port-forward"
# Then run port-forward commands again
```

### Traffic Generator Not Connecting

```bash
# Test connectivity manually
curl http://localhost:8000  # sample-metrics-app
curl http://localhost:8080  # otel-sample-app
curl http://localhost:8090  # go-otel-sample-app
curl http://localhost:8081  # java-otel-sample-app
```

### Metrics Not Appearing

```bash
# Check HPA status
kubectl get hpa -A

# Check Prometheus adapter
kubectl logs -n monitoring -l app=prometheus-adapter

# Check Prometheus server
kubectl logs -n monitoring -l app=prometheus-server
```

## Integration with AWS DevOps Agent

The traffic generator creates realistic operational data that AWS DevOps Agent can analyze:

1. **Metrics**: Request rates, error rates, CPU utilization
2. **Logs**: Application logs with request/response information
3. **Traces**: Distributed traces via OpenTelemetry (OTEL apps)
4. **Topology**: Application dependencies and relationships

This data enables the DevOps Agent to:
- Detect anomalies and incidents
- Correlate events across services
- Identify root causes
- Recommend mitigation strategies
- Learn from patterns over time

## Next Steps

1. Run the traffic generator to create baseline metrics
2. Configure AWS DevOps Agent to monitor your EKS cluster
3. Create an Agent Space for your application
4. Set up integrations with CloudWatch, Prometheus, and GitHub
5. Trigger investigations manually or automatically via alarms
6. Review agent findings and implement recommendations

## Resources

- [AWS DevOps Agent Documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/)
- [AWS DevOps Agent Blog Post](https://aws.amazon.com/blogs/aws/aws-devops-agent-helps-you-accelerate-incident-response-and-improve-system-reliability-preview/)
- [Amazon Managed Prometheus](https://docs.aws.amazon.com/prometheus/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

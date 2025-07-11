# OpenTelemetry Sample Application

This is a sample Flask application instrumented with OpenTelemetry to demonstrate observability integration with AWS services:

- **Metrics**: Sent to AWS Managed Prometheus
- **Traces**: Sent to AWS X-Ray
- **Logs**: Sent to AWS CloudWatch Logs

## Features

- REST API endpoints with simulated workloads
- Complete OpenTelemetry instrumentation
- AWS X-Ray trace format compatibility
- Prometheus metrics export
- Structured logging

## Endpoints

- `/`: Home endpoint
- `/api/users`: Users endpoint (occasionally returns errors)
- `/api/products`: Products endpoint
- `/api/orders`: Orders endpoint (with simulated database queries)
- `/health`: Health check endpoint

## Environment Variables

- `OTEL_SERVICE_NAME`: Service name (default: "otel-sample-app")
- `OTEL_SERVICE_NAMESPACE`: Service namespace (default: "default")
- `OTEL_DEPLOYMENT_ENVIRONMENT`: Deployment environment (default: "test")
- `AWS_REGION`: AWS region (default: "us-west-2")
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP endpoint (default: "http://otel-collector.opentelemetry:4317")

## Building and Deployment

The application is deployed to Amazon EKS using AWS CDK. The OpenTelemetry Collector is deployed as a sidecar to collect and export telemetry data.

```bash
# Build and push the Docker image
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker build -t <account-id>.dkr.ecr.<region>.amazonaws.com/otel-sample-app:latest .
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/otel-sample-app:latest
```

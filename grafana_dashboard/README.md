# Grafana Dashboards

This directory contains Grafana dashboard configurations for monitoring the EKS Fargate platform applications.

## Image Sources

All dashboard screenshots (PNG files) in this directory are original works created specifically for this project. They are screenshots of the actual dashboards running with the sample applications and are licensed under the same MIT-0 license as the rest of the project. No third-party images or logos are used in these screenshots.

## Available Dashboards

### API Monitoring Dashboard (`api-monitoring.json`)
Monitors the sample metrics application with the following panels:
- HTTP Request Rate
- HTTP Request Latency (95th and 50th percentiles)
- Active Users
- Error Rate
- CPU Usage
- Memory Usage
- Available Replicas

### OpenTelemetry Application Dashboard (`otel-app-dashboard.json`)
Monitors the OpenTelemetry-instrumented Python application:
- Request Rate by Endpoint
- Response Time Distribution
- Error Rate Tracking
- Custom Business Metrics
- Distributed Tracing Integration
- Resource Utilization

### Go OpenTelemetry Application Dashboard (`go-otel-app-dashboard.json`)
Monitors the Go OpenTelemetry-instrumented application:
- HTTP Request Rate with method/endpoint breakdown
- Request Latency Percentiles (95th and 50th)
- Active Users Gauge
- Error Rate Percentage
- CPU and Memory Usage
- Pod Replica Status
- Real-time OTLP metrics integration

## Dashboard Features

- **Real-time Monitoring**: 30-second refresh rate
- **Multi-dimensional Metrics**: Breakdown by endpoint, method, and status code
- **Alerting Ready**: Thresholds configured for key metrics
- **Resource Monitoring**: CPU and memory usage tracking
- **Kubernetes Integration**: Pod and deployment status
- **OpenTelemetry Integration**: OTLP traces and metrics

## Import Instructions

1. Open Grafana UI
2. Navigate to Dashboards → Import
3. Upload the JSON file or paste the content
4. Configure the Prometheus datasource
5. Save the dashboard

## Datasource Configuration

Ensure your Prometheus datasource is configured to scrape metrics from:
- `sample-metrics-app` service
- `otel-sample-app` service
- `go-otel-sample-app` service
- Kubernetes metrics (via kube-state-metrics)
- Container metrics (via cAdvisor)
- OTLP metrics (via ADOT Collector)

## Customization

Dashboards can be customized by:
- Adjusting time ranges and refresh intervals
- Adding new panels for additional metrics
- Modifying alert thresholds
- Adding template variables for filtering
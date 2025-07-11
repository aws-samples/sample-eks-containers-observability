# Go OpenTelemetry Sample Application

A sample Go application instrumented with OpenTelemetry for distributed tracing and metrics collection.

## Features

- **HTTP Server**: REST API with multiple endpoints
- **OpenTelemetry Tracing**: Distributed tracing with OTLP export
- **OpenTelemetry Metrics**: Custom metrics with OTLP export
- **OpenTelemetry Logging**: Structured logging with OTLP export
- **System Monitoring**: CPU and memory usage metrics
- **Health Checks**: Health endpoint for Kubernetes probes
- **Error Simulation**: 10% error rate for testing
- **Background Tasks**: Simulated background log generation

## Endpoints

- `GET /health` - Health check endpoint
- `GET /api` - Main API endpoint with tracing
- `GET /metrics` - Business metrics endpoint

## Metrics Exported

### HTTP Metrics
- `http_requests_total` - Counter of HTTP requests by method, endpoint, and status
- `http_request_duration_seconds` - Histogram of request latencies
- `active_users` - Gauge of active users (simulated)

### System Metrics
- `go_cpu_usage_percent` - CPU usage percentage
- `go_memory_usage_bytes` - Memory usage in bytes
- `go_memory_usage_percent` - Memory usage percentage

## Environment Variables

- `PORT` - Server port (default: 8080)
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` - OTLP traces endpoint
- `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` - OTLP metrics endpoint
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` - OTLP logs endpoint
- `ENVIRONMENT` - Environment name for resource attributes
- `AWS_REGION` - AWS region for resource attributes
- `PROMETHEUS_WORKSPACE_ID` - Prometheus workspace ID

## Dependencies

- `go.opentelemetry.io/otel` - OpenTelemetry SDK
- `github.com/shirou/gopsutil/v3` - System metrics collection
- Standard Go libraries for HTTP server and JSON handling

## Local Development

```bash
go mod tidy
go run main.go
```

## Docker Build

```bash
docker build -t go-otel-sample-app .
docker run -p 8080:8080 go-otel-sample-app
```

## Kubernetes Deployment

```bash
chmod +x deploy-with-otel.sh
./deploy-with-otel.sh
```

## Testing

```bash
# Health check
curl http://localhost:8080/health

# API endpoint
curl http://localhost:8080/api

# Metrics endpoint
curl http://localhost:8080/metrics
```

## Grafana Dashboard

![Go OTEL App Dashboard](../grafana_dashboard/go-otel-dashboard.png)

A pre-configured Grafana dashboard is available at `../grafana_dashboard/go-otel-app-dashboard.json`.
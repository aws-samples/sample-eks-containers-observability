"""
Constants used throughout the EKS Fargate Platform
"""

# EKS Configuration
EKS_VERSION = "1.32"
DEFAULT_NAMESPACE = "default"
MONITORING_NAMESPACE = "monitoring"
OPENTELEMETRY_NAMESPACE = "opentelemetry"

# Auto Mode handles workload scheduling automatically
# No special labels required

# Prometheus Configuration
PROMETHEUS_IMAGE = "prom/prometheus:v2.40.0"
PROMETHEUS_SCRAPE_INTERVAL = "15s"

# ADOT Configuration
ADOT_IMAGE = "public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3"

# Resource Defaults
DEFAULT_CPU_REQUEST = "100m"
DEFAULT_MEMORY_REQUEST = "128Mi"
DEFAULT_CPU_LIMIT = "200m"
DEFAULT_MEMORY_LIMIT = "256Mi"
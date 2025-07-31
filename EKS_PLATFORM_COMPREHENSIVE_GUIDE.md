# EKS Platform with Comprehensive Observability: Complete Implementation Guide

## Introduction

Modern containerized applications demand robust infrastructure that can automatically scale while providing deep visibility into performance and behavior. Organizations often struggle with choosing the right compute model for their Kubernetes workloads and implementing comprehensive observability that goes beyond basic metrics.

Amazon Elastic Kubernetes Service (EKS) offers multiple compute options including the new EKS Auto Mode and AWS Fargate, each with distinct advantages. However, many organizations deploy these without proper observability or rely on basic CPU/memory metrics for autoscaling, missing opportunities for optimization and cost savings.

This comprehensive guide demonstrates how to build an Amazon EKS platform that combines flexible compute options with comprehensive observability using AWS native services and OpenTelemetry. The solution addresses three critical challenges: compute management complexity, observability gaps, and autoscaling based on infrastructure metrics rather than application behavior.

## Prerequisites

### AWS Account Setup:
- AWS CLI configured with appropriate permissions
- CDK CLI installed globally

### Development Environment:
- Node.js 14+ and npm installed
- Python 3.9+ and pip installed
- Docker installed
- kubectl installed

### Knowledge Requirements:
- Basic understanding of Kubernetes concepts
- Familiarity with AWS networking
- Understanding of observability concepts

## Solution Overview

Our solution addresses the key challenges through a unified platform that provides:

- **Flexible compute deployment** supporting both EKS Auto Mode and AWS Fargate with a single codebase
- **Comprehensive observability pipeline** using Amazon Managed Service for Prometheus, AWS X-Ray, and Amazon CloudWatch
- **Real metrics-based autoscaling** using custom Prometheus metrics instead of basic resource utilization
- **Cost optimization** through strategic VPC endpoints and compute mode selection
- **Production-ready security** with proper IAM roles and network isolation

The platform follows a modular architecture pattern with clear separation between infrastructure, platform services, and applications, enabling teams to adapt components based on their specific requirements.

## Architecture Overview

### High-Level Architecture

The solution implements a fully managed Kubernetes environment with two distinct compute modes, each optimized for different use cases:

**EKS Auto Mode Architecture** provides zero node management with automatic scaling based on workload demands. This mode includes integrated networking, storage, and load balancing capabilities, making it ideal for general workloads and cost-optimized deployments.

**AWS Fargate Architecture** offers serverless container execution with strong isolation, where each pod runs in its own compute environment. This approach works best for security-sensitive workloads and applications requiring granular cost control.

### Flexible Compute Options

#### EKS Auto Mode
EKS Auto Mode represents AWS's latest approach to managed Kubernetes compute:

- **Zero Node Management**: No need to configure node groups or instance types
- **Automatic Scaling**: Compute resources scale based on actual workload demands
- **Cost Optimization**: Pay only for resources your workloads actually use
- **Integrated Services**: Automatic VPC CNI, EBS CSI driver, and load balancer configuration

#### AWS Fargate
AWS Fargate provides serverless container execution:

- **Complete Serverless**: No EC2 instances to manage
- **Security Isolation**: Each pod runs in its own compute environment
- **Per-Pod Billing**: Granular cost control at the pod level
- **Automatic Scaling**: Individual pods scale without capacity planning

The key architectural difference lies in networking and scaling behavior. Auto Mode uses shared node networking with cluster-wide scaling decisions, while Fargate provides isolated pod networking with individual pod scaling.

### Comprehensive Observability Pipeline

The observability architecture implements the three pillars of observability using AWS native services:

**Metrics Collection and Storage:**
- Dual collection strategy combining direct Prometheus scraping and OpenTelemetry SDK
- Local Prometheus server for HPA metrics and Prometheus Adapter integration
- Amazon Managed Service for Prometheus for long-term storage and querying
- Custom metrics exposed through Kubernetes custom metrics API

**Distributed Tracing:**
- OpenTelemetry SDK integration for automatic trace collection
- AWS Distro for OpenTelemetry (ADOT) collector for data processing
- AWS X-Ray for trace storage and service map visualization
- End-to-end transaction monitoring across microservices

**Centralized Logging:**
- OpenTelemetry SDK for structured application logging
- FluentBit for container log collection
- Amazon CloudWatch Logs with proper retention policies
- Log correlation with traces and metrics for comprehensive debugging

## Key Features and Benefits

### Real Metrics-Based Autoscaling

One of the platform's most powerful features is using actual application metrics for autoscaling decisions. Instead of relying on basic CPU and memory metrics, the solution implements a Prometheus Adapter that exposes custom metrics to Kubernetes HPA.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: java-otel-sample-app-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: java-otel-sample-app
  minReplicas: 1
  maxReplicas: 4
  metrics:
  - type: Pods
    pods:
      metric:
        name: java_app_requests_rate
      target:
        type: AverageValue
        averageValue: "10"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
```

This approach enables more intelligent scaling decisions based on actual application load, resulting in better resource efficiency and improved application performance.

### Infrastructure Optimization

#### Cost-Effective VPC Endpoints
The platform includes strategic VPC endpoints to reduce NAT Gateway costs and improve security:

```python
def _add_vpc_endpoints(self):
    """Add VPC Gateway and Interface Endpoints for internal AWS service access"""
    
    # Gateway Endpoints (free, for S3 and DynamoDB)
    self.vpc.add_gateway_endpoint(
        "S3GatewayEndpoint",
        service=ec2.GatewayVpcEndpointAwsService.S3,
        subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
    )
    
    self.vpc.add_gateway_endpoint(
        "DynamoDBGatewayEndpoint",
        service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
    )
    
    # Interface Endpoints (paid, for other AWS services)
    # ECR endpoints for container image pulls
    self.vpc.add_interface_endpoint(
        "EcrDockerEndpoint",
        service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
        subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
    )
    
    # CloudWatch endpoints for logging and metrics
    self.vpc.add_interface_endpoint(
        "CloudWatchLogsEndpoint",
        service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
        subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
    )
    
    # STS endpoint for IAM role assumptions (fixes IRSA issues)
    self.vpc.add_interface_endpoint(
        "StsEndpoint",
        service=ec2.InterfaceVpcEndpointAwsService.STS,
        subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
    )
```

#### Modular Architecture Design

The platform follows a clear modular structure:

```python
# Environment-specific configuration based on compute mode
if compute_mode == "fargate":
    config = EnvironmentConfig.fargate_development(account, region)
else:  # auto-mode
    config = EnvironmentConfig.development(account, region)

# Create the infrastructure layer
vpc_stack = VpcStack(
    app, 
    "NetworkStack", 
    network_config=config.network,
    env=cdk_env
)

# Create the platform layer
observability_stack = ObservabilityStack(
    app, 
    "ObservabilityStack",
    monitoring_config=config.monitoring,
    env=cdk_env
)

# Create the EKS cluster
eks_cluster_stack = EksClusterStack(
    app, 
    "EksClusterStack",
    vpc=vpc_stack.vpc,
    kubectl_layer=kubectl_layer_stack.kubectl_layer,
    eks_config=config.eks,
    env=cdk_env
)
```

This separation allows teams to modify individual components without affecting the entire platform.

## Implementation Details

### Deployment Process

The platform supports flexible deployment with simple context variables:

```bash
# Deploy with EKS Auto Mode (default)
cdk deploy

# Deploy with AWS Fargate
cdk deploy --context compute_mode=fargate
```

### Environment Configuration

The solution uses a sophisticated configuration system that adapts to different compute modes:

```python
@dataclass
class ComputeConfig:
    """Compute configuration for EKS cluster"""
    mode: str = "auto-mode"  # "fargate" or "auto-mode"
    fargate_profiles: List[str] = field(default_factory=lambda: ["default", "monitoring", "kube-system"])
    auto_mode_enabled: bool = True

@dataclass
class EksConfig:
    cluster_name: str
    version: str = "1.32"
    compute: ComputeConfig = field(default_factory=ComputeConfig)
    admin_user_arn: Optional[str] = None
    admin_role_arn: Optional[str] = None

@classmethod
def development(cls, account: str, region: str) -> 'EnvironmentConfig':
    """Development environment configuration (Auto Mode)"""
    return cls(
        environment_name="dev",
        account=account,
        region=region,
        network=NetworkConfig(
            nat_gateways=1,
            enable_flow_logs=False
        ),
        eks=EksConfig(
            cluster_name="dev-eks-automode",
            version="1.32",
            compute=ComputeConfig(
                mode="auto-mode",
                auto_mode_enabled=True
            )
        ),
        monitoring=MonitoringConfig(
            prometheus_enabled=True,
            grafana_enabled=True,
            retention_days=7
        )
    )
```

### EKS Cluster Creation

The platform creates different cluster configurations based on compute mode:

```python
def _create_auto_mode_cluster(self, eks_config, vpc, kubectl_layer, cluster_role):
    """Create EKS cluster for Auto Mode"""
    return eks.Cluster(self, f"AutoModeCluster{eks_config.compute.mode.replace('-', '').title()}",
        version=eks.KubernetesVersion.of(eks_config.version),
        cluster_name=eks_config.cluster_name,
        vpc=vpc,
        kubectl_layer=kubectl_layer,
        role=cluster_role,
        default_capacity=0,  # No default capacity for Auto Mode
        endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
        vpc_subnets=[ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )],
        authentication_mode=eks.AuthenticationMode.API_AND_CONFIG_MAP
    )

def _create_fargate_cluster(self, eks_config, vpc, kubectl_layer, cluster_role):
    """Create EKS cluster for Fargate"""
    return eks.Cluster(self, f"FargateCluster{eks_config.compute.mode.replace('-', '').title()}",
        version=eks.KubernetesVersion.of(eks_config.version),
        cluster_name=eks_config.cluster_name,
        vpc=vpc,
        kubectl_layer=kubectl_layer,
        role=cluster_role,
        default_capacity=0,  # No default capacity for Fargate
        endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
        vpc_subnets=[ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )],
        authentication_mode=eks.AuthenticationMode.API_AND_CONFIG_MAP
    )
```

### Auto Mode Enablement

The platform uses a custom Lambda function to enable Auto Mode:

```python
def _enable_auto_mode(self, node_group_role):
    """Enable Auto Mode using Provider Framework with external Lambda function"""
    from aws_cdk import custom_resources as cr
    from aws_cdk import aws_logs as logs
    from aws_cdk import aws_lambda as lambda_
    from aws_cdk import CustomResource
    import os
    
    # Create IAM role for the Lambda function
    auto_mode_lambda_role = iam.Role(
        self, "AutoModeLambdaRole",
        assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        managed_policies=[
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSLambdaBasicExecutionRole"
            )
        ]
    )
    
    # Add comprehensive permissions directly to the Lambda role
    auto_mode_lambda_role.add_to_policy(
        iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["eks:*"],
            resources=["*"]
        )
    )
    
    # Create the Lambda function using external file
    auto_mode_lambda = lambda_.Function(
        self, "AutoModeLambda",
        runtime=lambda_.Runtime.PYTHON_3_9,
        handler="auto_mode_lambda.on_event",
        code=lambda_.Code.from_asset(os.path.dirname(__file__)),
        role=auto_mode_lambda_role,
        timeout=Duration.minutes(15),
        description="Lambda function to enable EKS Auto Mode with nodePools"
    )
    
    # Create the custom resource
    self.auto_mode_enabler = CustomResource(
        self, "EnableAutoMode",
        service_token=auto_mode_provider.service_token,
        properties={
            "ClusterName": self.cluster.cluster_name,
            "NodeRoleArn": node_group_role.role_arn
        }
    )
```

### Observability Configuration

The solution automatically configures comprehensive monitoring:

```python
def __init__(
    self, 
    scope: Construct, 
    construct_id: str, 
    monitoring_config: MonitoringConfig,
    **kwargs
) -> None:
    super().__init__(scope, construct_id, **kwargs)
    
    # Create Amazon Managed Prometheus workspace
    self.prometheus_workspace = aps.CfnWorkspace(
        self, 
        "AmpWorkspace",
        alias="eks-automode-platform"
    )
    
    # Create CloudWatch Log Group for application logs
    self.log_group = logs.LogGroup(
        self, 
        "ApplicationLogGroup",
        log_group_name="/aws/eks/automode-platform/applications",
        removal_policy=RemovalPolicy.DESTROY,
        retention=self._get_retention_days(monitoring_config.retention_days)
    )
    
    # Create CloudWatch Log Group for OpenTelemetry logs
    self.otel_log_group = logs.LogGroup(
        self, 
        "OtelAppLogGroup",
        log_group_name="/aws/eks/automode-platform/otel",
        removal_policy=RemovalPolicy.DESTROY,
        retention=self._get_retention_days(monitoring_config.retention_days)
    )
```

## Application Integration

### Sample Applications

The platform includes multiple sample applications demonstrating proper OpenTelemetry instrumentation:

#### Python Flask Application with OTEL SDK

```python
# Configure service name and other attributes
service_name = os.environ.get("OTEL_SERVICE_NAME", "otel_sample_app")
service_namespace = os.environ.get("OTEL_SERVICE_NAMESPACE", "default")
deployment_environment = os.environ.get("OTEL_DEPLOYMENT_ENVIRONMENT", "test")
aws_region = os.environ.get("AWS_REGION", "eu-west-1")
cluster_name = os.environ.get("CLUSTER_NAME", "fargate-cluster")

# Create a resource with service information
resource = Resource.create({
    "service.name": service_name,
    "service.namespace": service_namespace,
    "deployment.environment": deployment_environment,
    "aws.region": aws_region,
    "ClusterName": cluster_name,
    "Namespace": service_namespace,
    "PodName": os.environ.get("HOSTNAME", "unknown-pod")
})

# Configure tracing with AWS X-Ray ID generator
trace_provider = TracerProvider(
    resource=resource,
    id_generator=AwsXRayIdGenerator()
)
otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# Create metrics with otel_sample_app prefix
request_counter = meter.create_counter(
    name="otel_sample_app_request_count",
    description="Count of requests",
    unit="1"
)

request_duration = meter.create_histogram(
    name="otel_sample_app_request_duration",
    description="Duration of requests",
    unit="s"
)

@app.route('/api/users')
def users():
    with tracer.start_as_current_span("get_users") as span:
        active_requests.add(1)
        start_time = time.time()
        request_id = f"req-{random.randint(1000, 9999)}"

        # Add attributes to the span
        span.set_attribute("endpoint", "api_users")
        span.set_attribute("request.id", request_id)

        # Log the request with request ID
        logger.info(f"[{request_id}] Processing request to users endpoint")
        logger.info(json.dumps({
            "request_id": request_id,
            "endpoint": "api_users",
            "client_ip": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", "Unknown")
        }))

        # Simulate some work
        time.sleep(random.uniform(0.05, 0.2))

        # Record metrics
        request_counter.add(1, {"endpoint": "api_users", "status": "success"})
        duration = time.time() - start_time
        request_duration.record(duration, {"endpoint": "api_users", "status": "success"})
        active_requests.add(-1)

        return jsonify({
            "users": [
                {"id": 1, "name": "User 1"},
                {"id": 2, "name": "User 2"},
                {"id": 3, "name": "User 3"}
            ]
        })
```

#### Go Application with HTTP Request Metrics

```go
func initTelemetry() func() {
    ctx := context.Background()

    // Create resource
    res, err := resource.New(ctx,
        resource.WithAttributes(
            attribute.String("service.name", "go-otel-sample-app"),
            attribute.String("service.version", "1.0.0"),
            attribute.String("environment", getEnv("ENVIRONMENT", "development")),
        ),
    )
    if err != nil {
        log.Fatal("Failed to create resource:", err)
    }

    // Setup tracing
    traceExporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint(getEnv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "localhost:4317")),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        log.Fatal("Failed to create trace exporter:", err)
    }

    tracerProvider := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(traceExporter),
        sdktrace.WithResource(res),
    )
    otel.SetTracerProvider(tracerProvider)

    // Create metrics
    requestCounter, _ = meter.Int64Counter(
        "http_requests_total",
        metric.WithDescription("Total number of HTTP requests"),
    )

    requestLatency, _ = meter.Float64Histogram(
        "http_request_duration_seconds",
        metric.WithDescription("HTTP request latency in seconds"),
    )

    return func() {
        tracerProvider.Shutdown(ctx)
        meterProvider.Shutdown(ctx)
        loggerProvider.Shutdown(ctx)
    }
}

func apiHandler(w http.ResponseWriter, r *http.Request) {
    ctx, span := tracer.Start(r.Context(), "api_request")
    defer span.End()

    start := time.Now()
    
    // Log the request
    logData, _ := json.Marshal(map[string]interface{}{
        "timestamp": time.Now().Format(time.RFC3339),
        "level": "info",
        "message": "API request received",
        "endpoint": "/api",
        "method": r.Method,
        "trace_id": span.SpanContext().TraceID().String(),
    })
    log.Printf("%s", logData)

    // Simulate some processing time
    time.Sleep(time.Duration(rand.Intn(100)) * time.Millisecond)

    status := "200"
    if rand.Float32() < 0.1 { // 10% error rate
        status = "500"
        atomic.AddInt64(&errorRequests, 1)
        w.WriteHeader(http.StatusInternalServerError)
        fmt.Fprintf(w, `{"error": "Internal server error"}`)
    } else {
        atomic.AddInt64(&apiRequests, 1)
        w.Header().Set("Content-Type", "application/json")
        fmt.Fprintf(w, `{
            "message": "Hello from Go OTEL app!",
            "request_id": "%s",
            "timestamp": "%s"
        }`, span.SpanContext().TraceID().String(), time.Now().Format(time.RFC3339))
    }

    requestCounter.Add(ctx, 1, metric.WithAttributes(
        attribute.String("method", r.Method),
        attribute.String("endpoint", "/api"),
        attribute.String("status", status),
    ))

    duration := time.Since(start).Seconds()
    requestLatency.Record(ctx, duration, metric.WithAttributes(
        attribute.String("method", r.Method),
        attribute.String("endpoint", "/api"),
    ))
}
```

#### Java Spring Boot Application with Micrometer Integration

```java
@RestController
public class ApiController {

    private static final Logger logger = LoggerFactory.getLogger(ApiController.class);
    private final Random random = new Random();
    
    private final Counter httpRequestsTotal;
    private final Timer httpRequestDuration;

    public ApiController(MeterRegistry meterRegistry) {
        this.httpRequestsTotal = Counter.builder("http_requests_total")
                .description("Total HTTP requests")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
                
        this.httpRequestDuration = Timer.builder("http_request_duration_seconds")
                .description("HTTP request duration")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
                
        Gauge.builder("java_cpu_usage_percent", this, ApiController::getCpuUsage)
                .description("CPU usage percentage")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
                
        Gauge.builder("java_memory_usage_bytes", this, ApiController::getMemoryUsage)
                .description("Memory usage in bytes")
                .tag("app", "java-otel-sample-app")
                .register(meterRegistry);
    }

    @GetMapping("/api/users")
    public Map<String, Object> getUsers() {
        Timer.Sample sample = Timer.start();
        
        try {
            Thread.sleep(random.nextInt(100));
            
            if (random.nextDouble() < 0.1) {
                httpRequestsTotal.increment();
                logger.error("Internal server error occurred - endpoint: /api/users, service: java-otel-sample-app, error_type: simulated_error");
                throw new RuntimeException("Internal server error");
            }
            
            httpRequestsTotal.increment();
            
            Map<String, Object> response = new HashMap<>();
            response.put("users", new String[]{"user1", "user2", "user3"});
            response.put("count", 3);
            response.put("timestamp", Instant.now().toString());
            
            logger.info("Users endpoint accessed - service: java-otel-sample-app, endpoint: /api/users, method: GET, response_count: {}", response.get("count"));
            
            return response;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException(e);
        } finally {
            sample.stop(httpRequestDuration);
        }
    }

    private double getCpuUsage() {
        try {
            com.sun.management.OperatingSystemMXBean osBean = 
                (com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
            double cpuLoad = osBean.getProcessCpuLoad();
            return cpuLoad >= 0 ? cpuLoad * 100 : 0.0;
        } catch (Exception e) {
            logger.warn("Failed to get CPU usage: {}", e.getMessage());
            return 0.0;
        }
    }
}
```

#### Custom Prometheus Metrics for Business Logic Monitoring

```python
import time
import random
import logging
import os
from prometheus_client import start_http_server, Counter, Gauge, Histogram, Summary

# Create metrics
REQUEST_COUNT = Counter('sample_app_requests_total', 'Total app requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('sample_app_request_latency_seconds', 'Request latency', ['endpoint'])
MEMORY_USAGE = Gauge('sample_app_memory_usage_bytes', 'Memory usage in bytes')
CPU_USAGE = Gauge('sample_app_cpu_usage_percent', 'CPU usage percentage')
ACTIVE_REQUESTS = Gauge('sample_app_active_requests', 'Number of active requests')

def generate_metrics():
    """Generate sample metrics and logs."""
    endpoints = ['/', '/api/users', '/api/products', '/api/orders']
    statuses = ['200', '404', '500']

    counter = 0

    while True:
        counter += 1

        # Simulate request count
        endpoint = random.choice(endpoints)
        status = random.choice(statuses)
        REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()

        # Simulate request latency
        latency = random.uniform(0.001, 2.0)
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)

        # Simulate memory and CPU usage
        MEMORY_USAGE.set(random.uniform(10 * 1024 * 1024, 100 * 1024 * 1024))
        CPU_USAGE.set(random.uniform(0, 100))

        # Simulate active requests
        ACTIVE_REQUESTS.set(random.randint(1, 10))

        # Generate logs
        if random.random() < 0.7:
            logger.info(f"Request #{counter} to {endpoint} completed with status {status} in {latency:.3f}s")
        elif random.random() < 0.9:
            logger.warning(f"Slow response #{counter} on {endpoint}: {latency:.3f}s")
        else:
            logger.error(f"Error #{counter} processing request to {endpoint}: status {status}")

        time.sleep(random.uniform(0.1, 0.5))

if __name__ == '__main__':
    # Start Prometheus metrics server
    start_http_server(8000)
    logger.info("Metrics server started on port 8000")
    
    # Generate metrics
    generate_metrics()
```

## Monitoring and Visualization

### Prometheus Adapter Configuration

The solution includes a sophisticated Prometheus Adapter that enables Kubernetes HPA to use custom metrics:

```python
def _get_auto_mode_config(self) -> str:
    """Auto Mode-specific Prometheus Adapter configuration"""
    return """
rules:
# Java OTEL App - using http_requests_total
- seriesQuery: 'http_requests_total{app="java-otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "java_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="java-otel-sample-app",<<.LabelMatchers>>}[1m]) * 60'

# Go OTEL App - using http_requests_total
- seriesQuery: 'http_requests_total{app="go-otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "go_app_requests_rate"
  metricsQuery: 'rate(http_requests_total{app="go-otel-sample-app",<<.LabelMatchers>>}[1m]) * 60'

# Sample Metrics App - using sample_app_requests_total
- seriesQuery: 'sample_app_requests_total{app="sample-metrics-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "sample_app_requests_rate"
  metricsQuery: 'rate(sample_app_requests_total{app="sample-metrics-app",<<.LabelMatchers>>}[1m]) * 60'

# OTEL Sample App - using pod_cpu_utilization
- seriesQuery: 'pod_cpu_utilization{app="otel-sample-app"}'
  resources:
    overrides:
      kubernetes_namespace: {resource: "namespace"}
      kubernetes_pod_name: {resource: "pod"}
  name:
    as: "pod_cpu_utilization"
  metricsQuery: 'pod_cpu_utilization{app="otel-sample-app",<<.LabelMatchers>>}'
"""
```

### Application Deployment with HPA

The platform automatically creates HPA configurations for each application:

```python
# Create HPA for Java OTEL sample app
java_hpa = cluster.add_manifest("JavaOtelSampleAppHPA", {
    "apiVersion": "autoscaling/v2",
    "kind": "HorizontalPodAutoscaler",
    "metadata": {
        "name": "java-otel-sample-app-hpa",
        "namespace": "default"
    },
    "spec": {
        "scaleTargetRef": {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "name": "java-otel-sample-app"
        },
        "minReplicas": 1,
        "maxReplicas": 4,
        "metrics": [
            {
                "type": "Pods",
                "pods": {
                    "metric": {"name": "java_app_requests_rate"},
                    "target": {"type": "AverageValue", "averageValue": "10"}
                }
            }
        ],
        "behavior": {
            "scaleUp": {
                "stabilizationWindowSeconds": 60,
                "policies": [{
                    "type": "Percent",
                    "value": 100,
                    "periodSeconds": 15
                }]
            },
            "scaleDown": {
                "stabilizationWindowSeconds": 300,
                "policies": [{
                    "type": "Percent",
                    "value": 10,
                    "periodSeconds": 60
                }]
            }
        }
    }
})
```

### Grafana Dashboards

The platform includes comprehensive pre-built dashboards for different application types:

Each dashboard provides:
- Real-time application performance metrics
- Infrastructure resource utilization tracking
- Error rate monitoring and alerting
- Auto-scaling visualization and trends

## Production Benefits

### Operational Excellence

**Reduced Management Overhead:**
- Amazon Managed Service for Prometheus eliminates infrastructure management
- Automatic scaling and high availability across multiple Availability Zones
- Built-in 150 days of metrics retention
- No need for Prometheus server maintenance or upgrades

**Simplified Operations:**
- Single codebase supports multiple compute modes
- Automated cluster configuration and addon management
- Integrated security with IAM Roles for Service Accounts (IRSA)

### Cost Optimization

**Strategic Resource Usage:**
- EKS Auto Mode provides cost-effective scaling for general workloads
- Fargate offers granular billing for variable usage patterns
- VPC endpoints reduce NAT Gateway costs for AWS service traffic
- Real metrics-based scaling prevents over-provisioning

### Security and Compliance

**AWS Security Best Practices:**
- Proper IAM role separation and least privilege access
- VPC isolation with private subnets for workloads
- Network segmentation through security groups
- Fargate mode provides additional pod-level isolation

### Real-World Performance

In deployments, the platform demonstrates effective autoscaling based on real application metrics. For example:

- **Java application**: 9.666 requests/second against 10 req/sec threshold, maintaining 4 replicas
- **Go application**: 7.999 requests/second, ready to scale at 10 req/sec threshold
- **Python application**: 25% CPU utilization against 50% threshold, maintaining stable replica count

This real metrics-based approach provides more accurate scaling decisions compared to traditional CPU-based scaling, resulting in better resource utilization and improved application performance.

## Getting Started

### Quick Deployment

```bash
# Install dependencies
npm install -g aws-cdk
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Deploy the platform
cdk deploy
```

### Application Deployment

Build and deploy sample applications to see the observability features in action:

```bash
# Get ECR repository URI from stack outputs
ECR_REPO=$(aws cloudformation describe-stacks --stack-name SampleAppStack \
  --query "Stacks[0].Outputs[?OutputKey=='SampleMetricsAppRepoUri'].OutputValue" --output text)

# Build and push sample application
docker build -t $ECR_REPO:latest ./sample-metrics-app
docker push $ECR_REPO:latest
```

### Accessing Observability Tools

Configure kubectl and access monitoring dashboards:

```bash
# Configure kubectl access
aws eks update-kubeconfig --name <cluster-name>

# Verify HPA metrics
kubectl get hpa
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1
```

## Best Practices and Recommendations

### Compute Mode Selection

- **Choose EKS Auto Mode** when you're building general-purpose applications that benefit from cost optimization and operational simplicity. This mode is ideal for teams managing mixed workload types who want to leverage integrated AWS service features without the complexity of node management. Auto Mode provides the best balance of cost efficiency and ease of operations for most production workloads.

- **Choose AWS Fargate** when security isolation is paramount for your applications, particularly when running batch or event-driven workloads that require strong container isolation. Fargate is the preferred choice for organizations requiring granular cost attribution at the pod level or when compliance mandates dictate complete container isolation from underlying infrastructure. This mode excels in scenarios where security requirements outweigh the need for shared resource optimization.

### Observability Strategy

**Metrics Design:**
- Use business metrics for HPA scaling decisions
- Implement proper metric labeling for filtering and aggregation
- Monitor both application and infrastructure metrics
- Set up alerting based on SLI/SLO definitions

**Tracing Implementation:**
- Instrument critical code paths with OpenTelemetry
- Use consistent trace context propagation
- Monitor service dependencies through X-Ray service maps
- Implement proper error handling and trace sampling

## Conclusion

This EKS platform demonstrates how organizations can achieve production-ready Kubernetes deployments that balance flexibility, observability, and cost optimization. By combining EKS Auto Mode or Fargate with comprehensive AWS native observability services, teams can focus on application development while maintaining deep visibility into system performance.

The real metrics-based autoscaling approach represents a significant improvement over traditional resource-based scaling, enabling more intelligent infrastructure decisions that align with actual application behavior. Combined with the flexible compute options and modular architecture, this platform provides a robust foundation for modern containerized applications at scale.

### Key Takeaways

- **Flexible compute options** enable optimization for different workload types
- **Real application metrics** provide better autoscaling decisions than infrastructure metrics
- **AWS managed services** reduce operational overhead while improving reliability
- **Comprehensive observability** requires integration across metrics, traces, and logs
- **Modular architecture** enables customization without sacrificing core functionality

Organizations implementing this solution can expect reduced operational complexity, improved cost efficiency, and enhanced visibility into their containerized applications, enabling faster development cycles and more reliable production deployments.
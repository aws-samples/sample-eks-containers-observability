#!/usr/bin/env python3
import os

from aws_cdk import App, Environment, Aspects
from cdk_nag import AwsSolutionsChecks, HIPAASecurityChecks

from eks_platform import (
    VpcStack,
    KubectlLayerStack,
    ObservabilityStack,
    EksClusterStack,
    PrometheusConstruct,
    PrometheusAdapterConstruct,
    ContainerAppConstruct,
    DeploymentConstruct,
    SampleAppConstruct,
    EcrRepositoriesStack,
    EnvironmentConfig,
    NetworkConfig,
    EksConfig,
    MonitoringConfig
)
from eks_platform.applications.workloads.otel_app_construct import OtelAppConstruct
from eks_platform.applications.workloads.go_otel_app_construct import GoOtelAppConstruct
from eks_platform.applications.workloads.java_otel_app_construct import JavaOtelAppConstruct

# Initialize the CDK app
app = App()

# Get compute mode from context
compute_mode = app.node.try_get_context("compute_mode") or "auto-mode"



# Create environment configuration
account = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION')
cdk_env = Environment(account=account, region=region)

# Create environment-specific configuration based on compute mode
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

kubectl_layer_stack = KubectlLayerStack(
    app, 
    "KubectlLayerStack", 
    env=cdk_env
)

# Create the platform layer
observability_stack = ObservabilityStack(
    app, 
    "ObservabilityStack",
    monitoring_config=config.monitoring,
    env=cdk_env
)
# Create ECR repositories for applications
ecr_stack = EcrRepositoriesStack(
    app, 
    "EcrStack",
    repository_names=["sample-metrics-app", "otel-sample-app", "go-otel-sample-app", "java-otel-sample-app"],
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



# Add Prometheus to the EKS cluster as a construct
prometheus = PrometheusConstruct(
    eks_cluster_stack,
    "Prometheus",
    cluster=eks_cluster_stack.cluster,
    workspace_id=observability_stack.prometheus_workspace_id,
    region=region,
    monitoring_namespace=eks_cluster_stack.monitoring_namespace,
    compute_config=config.eks.compute
)
prometheus.node.add_dependency(eks_cluster_stack)
prometheus.node.add_dependency(eks_cluster_stack.monitoring_namespace)

# Add Prometheus Adapter for custom metrics (created after Prometheus with delay)
prometheus_adapter = PrometheusAdapterConstruct(
    eks_cluster_stack,
    "PrometheusAdapter",
    cluster=eks_cluster_stack.cluster,
    prometheus_workspace_id=observability_stack.prometheus_workspace_id,
    region=region,
    compute_mode=config.eks.compute.mode  # Pass compute mode for configuration
)
prometheus_adapter.node.add_dependency(eks_cluster_stack)
prometheus_adapter.node.add_dependency(prometheus)  # Ensure Prometheus is ready first
prometheus_adapter.node.add_dependency(eks_cluster_stack.monitoring_namespace) 

# Deploy the sample metrics app (HPA created last with delay)
sample_app = SampleAppConstruct(
    eks_cluster_stack,
    "SampleMetricsApp",
    cluster=eks_cluster_stack.cluster,
    repository_uri=f"{account}.dkr.ecr.{region}.amazonaws.com/sample-metrics-app",
    compute_config=config.eks.compute
)
# Ensure HPA is created after Prometheus Adapter
sample_app.node.add_dependency(prometheus_adapter)

# Deploy the OpenTelemetry sample app (HPA created last with delay)
otel_app = OtelAppConstruct(
    eks_cluster_stack,
    "OtelSampleApp",
    cluster=eks_cluster_stack.cluster,
    repository_uri=f"{account}.dkr.ecr.{region}.amazonaws.com/otel-sample-app",
    region=region,
    prometheus_workspace_id=observability_stack.prometheus_workspace_id,
    opentelemetry_namespace=eks_cluster_stack.opentelemetry_namespace,
    compute_config=config.eks.compute
)
otel_app.node.add_dependency(eks_cluster_stack.opentelemetry_namespace)
# Ensure HPA is created after Prometheus Adapter
otel_app.node.add_dependency(prometheus_adapter)

# Deploy the Go OpenTelemetry sample app (HPA created last with delay)
go_otel_app = GoOtelAppConstruct(
    eks_cluster_stack,
    "GoOtelSampleApp",
    cluster=eks_cluster_stack.cluster,
    repository_uri=f"{account}.dkr.ecr.{region}.amazonaws.com/go-otel-sample-app",
    region=region,
    prometheus_workspace_id=observability_stack.prometheus_workspace_id,
    compute_config=config.eks.compute
)
# Ensure HPA is created after Prometheus Adapter
go_otel_app.node.add_dependency(prometheus_adapter)

# Deploy the Java OpenTelemetry sample app (HPA created last with delay)
java_otel_app = JavaOtelAppConstruct(
    eks_cluster_stack,
    "JavaOtelSampleApp",
    cluster=eks_cluster_stack.cluster,
    repository_uri=f"{account}.dkr.ecr.{region}.amazonaws.com/java-otel-sample-app",
    region=region,
    prometheus_workspace_id=observability_stack.prometheus_workspace_id,
    compute_config=config.eks.compute
)
# Ensure HPA is created after Prometheus Adapter
java_otel_app.node.add_dependency(prometheus_adapter)

# Add dependencies
eks_cluster_stack.add_dependency(vpc_stack)
eks_cluster_stack.add_dependency(kubectl_layer_stack)
eks_cluster_stack.add_dependency(observability_stack)

# Apply cdk-nag suppressions
from eks_platform.nag_suppressions import add_nag_suppressions
add_nag_suppressions([vpc_stack, observability_stack, eks_cluster_stack])

# Synthesize the CloudFormation templates
app.synth()
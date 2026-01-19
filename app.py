#!/usr/bin/env python3
import os
import sys

from aws_cdk import App, Environment, Aspects, Tags
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
    MonitoringConfig,
    DevOpsAgentConfig
)
from eks_platform.applications.workloads.otel_app_construct import OtelAppConstruct
from eks_platform.applications.workloads.go_otel_app_construct import GoOtelAppConstruct
from eks_platform.applications.workloads.java_otel_app_construct import JavaOtelAppConstruct
from eks_platform.platform.devops_agent.devops_agent_stack import DevOpsAgentStack
from eks_platform.platform.devops_agent.devops_agent_eks_access import DevOpsAgentEksAccess


def print_deployment_menu():
    """Display deployment options menu"""
    print("\n" + "="*60)
    print("EKS Platform Deployment Configuration")
    print("="*60)
    print("\nDeployment Options:")
    print("  1. Compute Mode:")
    print("     - auto-mode (default)")
    print("     - fargate")
    print("\n  2. DevOps Agent:")
    print("     - enabled")
    print("     - disabled (default)")
    print("\nUsage Examples:")
    print("  # Deploy with Auto Mode (default)")
    print("  cdk deploy --all")
    print("\n  # Deploy with Fargate")
    print("  cdk deploy --all -c compute_mode=fargate")
    print("\n  # Deploy with DevOps Agent enabled")
    print("  cdk deploy --all -c deploy_devops_agent=true")
    print("\n  # Deploy with Fargate and DevOps Agent")
    print("  cdk deploy --all -c compute_mode=fargate -c deploy_devops_agent=true")
    print("\n  # Show this menu")
    print("  python app.py --help")
    print("="*60 + "\n")


# Check for help flag
if "--help" in sys.argv or "-h" in sys.argv:
    print_deployment_menu()
    sys.exit(0)

# Initialize the CDK app
app = App()

# Get compute mode from context
compute_mode = app.node.try_get_context("compute_mode") or "auto-mode"

# Get DevOps Agent deployment flag from context
deploy_devops_agent_flag = app.node.try_get_context("deploy_devops_agent")
deploy_devops_agent = str(deploy_devops_agent_flag).lower() == "true" if deploy_devops_agent_flag else False

# Get DevOps Agent role ARN from context (required if deploying DevOps Agent)
devops_agent_role_arn = app.node.try_get_context("devops_agent_role_arn")

# Print current configuration
print(f"\n🚀 Deploying EKS Platform with:")
print(f"   - Compute Mode: {compute_mode}")
print(f"   - DevOps Agent: {'enabled' if deploy_devops_agent else 'disabled'}")
print()

# Add custom tags to all resources
Tags.of(app).add("DemosFor", "OTEL-DevOpsAgent-AIforOperations")

# Create environment configuration
account = os.getenv('CDK_DEFAULT_ACCOUNT')
region = os.getenv('CDK_DEFAULT_REGION', 'us-east-1')  # Default to us-east-1
cdk_env = Environment(account=account, region=region)

# Create environment-specific configuration based on compute mode
if compute_mode == "fargate":
    config = EnvironmentConfig.fargate_development(account, region)
else:  # auto-mode
    config = EnvironmentConfig.development(account, region)

# Configure DevOps Agent based on deployment flag
if deploy_devops_agent:
    if not devops_agent_role_arn:
        print("⚠️  Warning: deploy_devops_agent=true but no devops_agent_role_arn provided")
        print("   Please provide the DevOps Agent role ARN:")
        print("   cdk deploy --all -c deploy_devops_agent=true -c devops_agent_role_arn=<ROLE_ARN>")
        sys.exit(1)
    
    config.devops_agent = DevOpsAgentConfig(
        enabled=True,
        agent_space_name=f"{config.eks.cluster_name}-agent-space",
        role_arn=devops_agent_role_arn,
        create_eks_access=True,
        grant_cluster_admin=True
    )

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

# Create the EKS cluster with a better name
eks_cluster_stack = EksClusterStack(
    app, 
    "EKS-Platform-Cluster",
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
    monitoring_namespace=eks_cluster_stack.monitoring_namespace,
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

# Optional: Deploy AWS DevOps Agent integration
if config.devops_agent.enabled:
    print(f"📋 Deploying DevOps Agent Stack...")
    devops_agent_stack = DevOpsAgentStack(
        app,
        "DevOpsAgentStack",
        cluster_name=config.eks.cluster_name,
        log_group_name=observability_stack.log_group.log_group_name,
        devops_agent_role_arn=config.devops_agent.role_arn,
        agent_space_name=config.devops_agent.agent_space_name,
        env=cdk_env
    )
    devops_agent_stack.add_dependency(observability_stack)
    
    # Grant EKS access to DevOps Agent if configured
    if config.devops_agent.create_eks_access:
        devops_agent_eks_access = DevOpsAgentEksAccess(
            eks_cluster_stack,
            "DevOpsAgentEksAccess",
            cluster=eks_cluster_stack.cluster,
            devops_agent_role=devops_agent_stack.devops_agent_role
        )
        devops_agent_eks_access.node.add_dependency(devops_agent_stack)

# Add dependencies
eks_cluster_stack.add_dependency(vpc_stack)
eks_cluster_stack.add_dependency(kubectl_layer_stack)
eks_cluster_stack.add_dependency(observability_stack)

# Apply cdk-nag suppressions
from eks_platform.nag_suppressions import add_nag_suppressions
add_nag_suppressions([vpc_stack, observability_stack, eks_cluster_stack])

# Synthesize the CloudFormation templates
app.synth()
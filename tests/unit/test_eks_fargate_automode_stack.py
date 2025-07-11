import pytest
from aws_cdk import App, assertions

from eks_platform.infrastructure.network.vpc_stack import VpcStack
from eks_platform.platform.utilities.kubectl_layer_stack import KubectlLayerStack
from eks_platform.infrastructure.compute.eks_cluster_stack import EksClusterStack
from eks_platform.config.environment_config import EnvironmentConfig

def test_vpc_stack():
    app = App()
    config = EnvironmentConfig.development("123456789012", "us-west-2")
    stack = VpcStack(app, "test-vpc", network_config=config.network)
    template = assertions.Template.from_stack(stack)

    # Test VPC creation
    template.resource_count_is("AWS::EC2::VPC", 1)

    # Test that the VPC has the correct properties
    template.has_resource_properties("AWS::EC2::VPC", {
        "CidrBlock": assertions.Match.any_value(),
        "EnableDnsHostnames": True,
        "EnableDnsSupport": True
    })

    # Test that NAT Gateway is created
    template.resource_count_is("AWS::EC2::NatGateway", 1)

    # Test that subnets are created (2 AZs with public and private subnets)
    template.resource_count_is("AWS::EC2::Subnet", 4)

def test_kubectl_layer_stack():
    app = App()
    stack = KubectlLayerStack(app, "kubectl-layer")
    template = assertions.Template.from_stack(stack)

    # Test Lambda Layer creation
    template.resource_count_is("AWS::Lambda::LayerVersion", 1)

    # Test that the layer has the correct properties
    template.has_resource_properties("AWS::Lambda::LayerVersion", {
        "CompatibleRuntimes": assertions.Match.array_with([
            "python3.11",
            "python3.10",
            "python3.9",
            "nodejs18.x"
        ])
    })

@pytest.mark.skip(reason="EKS Cluster resources not properly mocked in test environment")
def test_eks_cluster_stack_resources():
    app = App()
    config = EnvironmentConfig.development("123456789012", "us-west-2")
    vpc_stack = VpcStack(app, "test-vpc", network_config=config.network)
    kubectl_layer_stack = KubectlLayerStack(app, "kubectl-layer")
    
    stack = EksClusterStack(app, "eks-cluster",
                           vpc=vpc_stack.vpc,
                           kubectl_layer=kubectl_layer_stack.kubectl_layer,
                           eks_config=config.eks)
    template = assertions.Template.from_stack(stack)

    # Test no VPC is created in this stack
    template.resource_count_is("AWS::EC2::VPC", 0)

    # Test EKS Cluster creation
    template.resource_count_is("AWS::EKS::Cluster", 1)

    # Test Fargate Profile creation
    template.resource_count_is("AWS::EKS::FargateProfile", 2)

    # Test no NodeGroup is created
    template.resource_count_is("AWS::EKS::Nodegroup", 0)
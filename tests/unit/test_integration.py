import os
import pytest
from unittest.mock import patch
from aws_cdk import App

from eks_platform.infrastructure.network.vpc_stack import VpcStack
from eks_platform.platform.utilities.kubectl_layer_stack import KubectlLayerStack
from eks_platform.infrastructure.compute.eks_cluster_stack import EksClusterStack
from eks_platform.platform.monitoring.observability_stack import ObservabilityStack
from eks_platform.config.environment_config import EnvironmentConfig

@pytest.mark.skip(reason="Integration test requires proper mocking of CDK resources")
def test_full_stack_integration():
    """Test that all stacks can be integrated together"""
    with patch.dict(os.environ, {
        "CDK_DEFAULT_ACCOUNT": "123456789012",
        "CDK_DEFAULT_REGION": "us-west-2"
    }):
        app = App()
        config = EnvironmentConfig.development("123456789012", "us-west-2")

        # Create all stacks
        vpc_stack = VpcStack(app, "NetworkStack", network_config=config.network)
        kubectl_layer_stack = KubectlLayerStack(app, "KubectlLayerStack")
        observability_stack = ObservabilityStack(app, "ObservabilityStack", 
                                                monitoring_config=config.monitoring)
        eks_cluster_stack = EksClusterStack(app, "EksClusterStack",
                                          vpc=vpc_stack.vpc,
                                          kubectl_layer=kubectl_layer_stack.kubectl_layer,
                                          eks_config=config.eks)

        # Add dependencies
        eks_cluster_stack.add_dependency(vpc_stack)
        eks_cluster_stack.add_dependency(kubectl_layer_stack)
        eks_cluster_stack.add_dependency(observability_stack)

        # Verify that stacks are created
        assert vpc_stack is not None
        assert kubectl_layer_stack is not None
        assert eks_cluster_stack is not None
        assert observability_stack is not None
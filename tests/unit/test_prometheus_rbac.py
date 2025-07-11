import pytest
from aws_cdk import App
from unittest.mock import MagicMock, patch

from eks_platform.infrastructure.network.vpc_stack import VpcStack
from eks_platform.platform.utilities.kubectl_layer_stack import KubectlLayerStack
from eks_platform.infrastructure.compute.eks_cluster_stack import EksClusterStack
from eks_platform.platform.monitoring.prometheus_construct import PrometheusConstruct
from eks_platform.config.environment_config import EnvironmentConfig

@pytest.mark.skip(reason="KubernetesManifest mocking needs to be implemented")
def test_prometheus_construct():
    app = App()
    
    # Create a mock cluster
    mock_cluster = MagicMock()
    mock_cluster.add_manifest.return_value = MagicMock()
    mock_cluster.add_service_account.return_value = MagicMock()
    
    # Create a mock monitoring namespace
    mock_namespace = MagicMock()

    # Create Prometheus construct
    prometheus = PrometheusConstruct(
        app,
        "prometheus-test",
        cluster=mock_cluster,
        workspace_id="test-workspace-id",
        region="us-west-2",
        monitoring_namespace=mock_namespace
    )

    # Verify the construct was created
    assert prometheus is not None
    
    # Verify that service account was created
    mock_cluster.add_service_account.assert_called()
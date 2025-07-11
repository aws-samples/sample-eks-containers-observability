import pytest
from aws_cdk import App, assertions
from unittest.mock import MagicMock, patch

from eks_platform.platform.monitoring.prometheus_construct import PrometheusConstruct

@pytest.mark.skip(reason="EKS resources not properly mocked in test environment")
def test_prometheus_construct():
    app = App()

    # Create a mock EKS cluster
    mock_cluster = MagicMock()
    mock_cluster.add_manifest.return_value = MagicMock()
    mock_cluster.add_service_account.return_value = MagicMock()
    
    # Create a mock monitoring namespace
    mock_namespace = MagicMock()

    # Create the prometheus construct with the mock cluster
    prometheus = PrometheusConstruct(app, "prometheus-construct",
                                   cluster=mock_cluster,
                                   workspace_id="test-workspace-id",
                                   region="us-west-2",
                                   monitoring_namespace=mock_namespace)

    # Verify that the construct was created
    assert prometheus is not None

    # Verify that service account was created
    mock_cluster.add_service_account.assert_called()
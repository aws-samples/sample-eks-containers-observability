import aws_cdk as core
from aws_cdk import assertions
from unittest.mock import MagicMock

from eks_platform.applications.deployments.deployment_construct import DeploymentConstruct

def test_deployment_construct():
    """Test that the deployment construct can be created"""
    app = core.App()
    
    # Create a mock cluster
    mock_cluster = MagicMock()
    mock_cluster.add_manifest.return_value = MagicMock()
    
    # Create deployment construct
    deployment = DeploymentConstruct(
        app,
        "test-deployment",
        cluster=mock_cluster
    )
    
    # Verify the construct was created
    assert deployment is not None
    assert deployment.cluster == mock_cluster
    assert deployment.manifests == []
    
    # Test adding a namespace
    namespace = deployment.add_namespace("test-namespace")
    assert namespace is not None
    assert len(deployment.manifests) == 1
    
    # Test adding a deployment
    test_manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "test-app"}
    }
    deployment_manifest = deployment.add_deployment("test-app", test_manifest)
    assert deployment_manifest is not None
    assert len(deployment.manifests) == 2
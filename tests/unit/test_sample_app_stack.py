import aws_cdk as core
from aws_cdk import assertions
from unittest.mock import MagicMock

from eks_platform.applications.workloads.sample_app_construct import SampleAppConstruct
from eks_platform.infrastructure.storage.ecr_stack import EcrRepositoriesStack

def test_sample_app_construct():
    app = core.App()
    
    # Create a mock cluster
    mock_cluster = MagicMock()
    mock_cluster.add_manifest.return_value = MagicMock()

    # Create sample app construct
    sample_app = SampleAppConstruct(
        app,
        "sample-app-construct",
        cluster=mock_cluster,
        repository_uri="123456789012.dkr.ecr.us-west-2.amazonaws.com/sample-metrics-app"
    )

    # Verify the construct was created
    assert sample_app is not None
    
    # Verify that manifests were added to the cluster
    assert mock_cluster.add_manifest.call_count == 3  # Deployment, Service, HPA

def test_ecr_repositories_stack():
    app = core.App()
    stack = EcrRepositoriesStack(app, "ecr-stack", repository_names=["sample-metrics-app", "otel-sample-app"])
    template = assertions.Template.from_stack(stack)

    # Test ECR repository creation
    template.resource_count_is("AWS::ECR::Repository", 2)
    template.has_resource_properties("AWS::ECR::Repository", {
        "RepositoryName": "sample-metrics-app"
    })
    template.has_resource_properties("AWS::ECR::Repository", {
        "RepositoryName": "otel-sample-app"
    })
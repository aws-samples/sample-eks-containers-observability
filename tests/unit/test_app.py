import os
from aws_cdk import App
import pytest
from unittest.mock import patch

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "CDK_DEFAULT_ACCOUNT": "123456789012",
        "CDK_DEFAULT_REGION": "us-west-2"
    }):
        yield

def test_app_synth(mock_env):
    """Test that the app can be synthesized without errors"""
    # Import app.py only inside the test to use the mocked environment
    import app

    # The app should have created all the stacks
    assert len(app.app.node.children) >= 4  # At least 4 main stacks

    # Just verify that key stacks exist
    stack_ids = [child.node.id for child in app.app.node.children]
    assert "NetworkStack" in stack_ids
    assert "KubectlLayerStack" in stack_ids
    assert "EksClusterStack" in stack_ids
    assert "ObservabilityStack" in stack_ids
    assert "EcrStack" in stack_ids

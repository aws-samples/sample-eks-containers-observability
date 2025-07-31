import os
import pytest
from unittest.mock import patch

@pytest.fixture(scope="function", autouse=True)
def mock_environment():
    """Mock AWS environment variables for all tests"""
    with patch.dict(os.environ, {
        "CDK_DEFAULT_ACCOUNT": "123456789012",
        "CDK_DEFAULT_REGION": "us-west-2"
    }):
        yield

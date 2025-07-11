from aws_cdk import (
    Stack,
    aws_lambda as lambda_
)
from constructs import Construct

class KubectlLayerStack(Stack):
    """
    Creates a Lambda layer containing kubectl for use with EKS
    """
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a kubectl Lambda layer with the correct directory structure
        self.kubectl_layer = lambda_.LayerVersion(self, "KubectlLayer",
            code=lambda_.Code.from_asset("lambda/kubectl-layer"),
            compatible_runtimes=[
                lambda_.Runtime.PYTHON_3_11,
                lambda_.Runtime.PYTHON_3_10,
                lambda_.Runtime.PYTHON_3_9,
                lambda_.Runtime.NODEJS_18_X
            ],
            description="A layer that contains kubectl"
        )
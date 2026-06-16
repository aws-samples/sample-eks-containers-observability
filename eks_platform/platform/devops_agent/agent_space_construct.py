"""
AWS DevOps Agent Space Construct
Creates an Agent Space via CloudFormation and derives the service-linked role ARN.
Uses CfnResource directly to support aws-cdk-lib < 2.254.
"""

from aws_cdk import (
    CfnOutput,
    CfnResource,
    Fn,
)
from constructs import Construct


class AgentSpaceConstruct(Construct):
    """Creates a DevOps Agent Space and exposes the service-linked role ARN."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        space_name: str,
        description: str = "EKS cluster investigation agent space",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.agent_space = CfnResource(
            self,
            "AgentSpace",
            type="AWS::DevOpsAgent::AgentSpace",
            properties={
                "Name": space_name,
                "Description": description,
                "Tags": [{"Key": "ManagedBy", "Value": "CDK"}],
            },
        )

        self.space_name = space_name
        self.space_id = self.agent_space.get_att("AgentSpaceId").to_string()
        self.space_arn = self.agent_space.get_att("Arn").to_string()

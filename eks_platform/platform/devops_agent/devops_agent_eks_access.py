"""
DevOps Agent EKS Access Configuration
Creates EKS access entry and associates cluster admin policy
"""

from aws_cdk import (
    aws_eks as eks,
    aws_iam as iam,
    custom_resources as cr,
    CustomResource,
    Duration
)
from constructs import Construct


class DevOpsAgentEksAccess(Construct):
    """
    Construct to grant AWS DevOps Agent access to EKS cluster
    Creates access entry and associates cluster admin policy
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cluster: eks.Cluster,
        devops_agent_role: iam.IRole,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.cluster = cluster
        self.devops_agent_role = devops_agent_role

        # Create access entry for DevOps Agent
        self._create_access_entry()

    def _create_access_entry(self) -> None:
        """Create EKS access entry for DevOps Agent role"""
        
        # Create custom resource to manage EKS access entry
        # This uses AWS SDK calls since CDK doesn't have native L2 constructs yet
        
        on_event_handler = cr.AwsCustomResource(
            self,
            "DevOpsAgentAccessEntry",
            on_create=self._create_access_entry_call(),
            on_update=self._create_access_entry_call(),
            on_delete=self._delete_access_entry_call(),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=[
                        "eks:CreateAccessEntry",
                        "eks:DeleteAccessEntry",
                        "eks:DescribeAccessEntry",
                        "eks:AssociateAccessPolicy",
                        "eks:DisassociateAccessPolicy",
                        "eks:ListAssociatedAccessPolicies"
                    ],
                    resources=[
                        self.cluster.cluster_arn,
                        f"{self.cluster.cluster_arn}/*"
                    ]
                )
            ]),
            timeout=Duration.minutes(5)
        )

        # Associate cluster admin policy
        associate_policy = cr.AwsCustomResource(
            self,
            "DevOpsAgentAccessPolicy",
            on_create=self._associate_policy_call(),
            on_delete=self._disassociate_policy_call(),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=[
                        "eks:AssociateAccessPolicy",
                        "eks:DisassociateAccessPolicy",
                        "eks:ListAssociatedAccessPolicies"
                    ],
                    resources=[
                        self.cluster.cluster_arn,
                        f"{self.cluster.cluster_arn}/*"
                    ]
                )
            ]),
            timeout=Duration.minutes(5)
        )

        # Ensure policy is associated after access entry is created
        associate_policy.node.add_dependency(on_event_handler)

    def _create_access_entry_call(self) -> cr.AwsSdkCall:
        """AWS SDK call to create access entry"""
        return cr.AwsSdkCall(
            service="EKS",
            action="createAccessEntry",
            parameters={
                "clusterName": self.cluster.cluster_name,
                "principalArn": self.devops_agent_role.role_arn,
                "type": "STANDARD"
            },
            physical_resource_id=cr.PhysicalResourceId.of(
                f"{self.cluster.cluster_name}-devops-agent-access"
            ),
            ignore_error_codes_matching="ResourceInUseException"
        )

    def _delete_access_entry_call(self) -> cr.AwsSdkCall:
        """AWS SDK call to delete access entry"""
        return cr.AwsSdkCall(
            service="EKS",
            action="deleteAccessEntry",
            parameters={
                "clusterName": self.cluster.cluster_name,
                "principalArn": self.devops_agent_role.role_arn
            },
            ignore_error_codes_matching="ResourceNotFoundException"
        )

    def _associate_policy_call(self) -> cr.AwsSdkCall:
        """AWS SDK call to associate cluster admin policy"""
        return cr.AwsSdkCall(
            service="EKS",
            action="associateAccessPolicy",
            parameters={
                "clusterName": self.cluster.cluster_name,
                "principalArn": self.devops_agent_role.role_arn,
                "policyArn": "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy",
                "accessScope": {
                    "type": "cluster"
                }
            },
            physical_resource_id=cr.PhysicalResourceId.of(
                f"{self.cluster.cluster_name}-devops-agent-policy"
            ),
            ignore_error_codes_matching="ResourceInUseException"
        )

    def _disassociate_policy_call(self) -> cr.AwsSdkCall:
        """AWS SDK call to disassociate cluster admin policy"""
        return cr.AwsSdkCall(
            service="EKS",
            action="disassociateAccessPolicy",
            parameters={
                "clusterName": self.cluster.cluster_name,
                "principalArn": self.devops_agent_role.role_arn,
                "policyArn": "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
            },
            ignore_error_codes_matching="ResourceNotFoundException"
        )

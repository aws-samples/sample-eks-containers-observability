"""
AWS DevOps Agent EKS Access Configuration
Grants existing AWS DevOps Agent service-linked role access to EKS cluster.
Optionally creates the Agent Space via CfnAgentSpace when no role ARN is provided.
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
    Tags
)
from constructs import Construct
from typing import Optional

from .agent_space_construct import AgentSpaceConstruct


class DevOpsAgentStack(Stack):
    """
    Stack to grant AWS DevOps Agent access to EKS cluster.
    If devops_agent_role_arn is provided, it imports the existing role.
    If not, it creates an Agent Space via CfnAgentSpace and derives the role ARN.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cluster_name: str,
        log_group_name: str,
        devops_agent_role_arn: Optional[str] = None,
        agent_space_name: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.cluster_name = cluster_name
        self.log_group_name = log_group_name
        self.agent_space_name = agent_space_name or f"{cluster_name}-agent-space"

        if devops_agent_role_arn:
            # Use existing Agent Space role
            self.devops_agent_role_arn = devops_agent_role_arn
        else:
            # Create the Agent Space and derive the service-linked role ARN
            self.agent_space = AgentSpaceConstruct(
                self,
                "AgentSpace",
                space_name=self.agent_space_name,
                description=f"DevOps Agent for EKS cluster {cluster_name}",
            )
            self.devops_agent_role_arn = (
                f"arn:aws:iam::{self.account}:role/service-role/"
                f"{self.agent_space_name}-DevOpsAgentRole"
            )

        # Extract role name from ARN
        self.role_name = self.devops_agent_role_arn.split('/')[-1]

        # Import the DevOps Agent role (created automatically by the service)
        self.devops_agent_role = iam.Role.from_role_arn(
            self,
            "DevOpsAgentRole",
            role_arn=self.devops_agent_role_arn
        )

        # Create managed policies for the DevOps Agent role
        self._create_cloudwatch_logs_policy()
        self._create_eks_policy()
        self._create_cloudwatch_metrics_policy()

        # Create outputs
        self._create_outputs()

        # Add tags
        Tags.of(self).add("Purpose", "DevOpsAgent")
        Tags.of(self).add("ManagedBy", "CDK")

    def _create_cloudwatch_logs_policy(self) -> None:
        """Create CloudWatch Logs read policy"""
        
        policy = iam.ManagedPolicy(
            self,
            "DevOpsAgentCloudWatchLogsPolicy",
            managed_policy_name=f"{self.agent_space_name}-CloudWatchLogs",
            description=f"CloudWatch Logs access for DevOps Agent - {self.cluster_name}",
            statements=[
                iam.PolicyStatement(
                    sid="CloudWatchLogsRead",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:GetLogEvents",
                        "logs:FilterLogEvents",
                        "logs:DescribeLogStreams",
                        "logs:DescribeLogGroups",
                        "logs:GetLogRecord",
                        "logs:GetQueryResults",
                        "logs:StartQuery",
                        "logs:StopQuery",
                        "logs:TestMetricFilter",
                        "logs:GetLogGroupFields"
                    ],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:{self.log_group_name}*",
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*",
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/eks/*"
                    ]
                ),
                iam.PolicyStatement(
                    sid="CloudWatchLogsDescribe",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams"
                    ],
                    resources=["*"]
                )
            ],
            roles=[self.devops_agent_role]
        )

    def _create_eks_policy(self) -> None:
        """Create EKS cluster access policy"""
        
        policy = iam.ManagedPolicy(
            self,
            "DevOpsAgentEKSPolicy",
            managed_policy_name=f"{self.agent_space_name}-EKSAccess",
            description=f"EKS cluster access for DevOps Agent - {self.cluster_name}",
            statements=[
                iam.PolicyStatement(
                    sid="EKSAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "eks:DescribeCluster",
                        "eks:ListClusters",
                        "eks:DescribeNodegroup",
                        "eks:ListNodegroups",
                        "eks:DescribeAddon",
                        "eks:ListAddons",
                        "eks:AccessKubernetesApi",
                        "eks:ListAccessEntries",
                        "eks:DescribeAccessEntry",
                        "eks:ListAssociatedAccessPolicies"
                    ],
                    resources=[
                        f"arn:aws:eks:{self.region}:{self.account}:cluster/{self.cluster_name}",
                        f"arn:aws:eks:{self.region}:{self.account}:cluster/{self.cluster_name}/*"
                    ]
                ),
                iam.PolicyStatement(
                    sid="EKSList",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "eks:ListClusters"
                    ],
                    resources=["*"]
                )
            ],
            roles=[self.devops_agent_role]
        )

    def _create_cloudwatch_metrics_policy(self) -> None:
        """Create CloudWatch Metrics and observability policy"""
        
        policy = iam.ManagedPolicy(
            self,
            "DevOpsAgentMetricsPolicy",
            managed_policy_name=f"{self.agent_space_name}-Metrics",
            description=f"CloudWatch Metrics and observability access for DevOps Agent - {self.cluster_name}",
            statements=[
                iam.PolicyStatement(
                    sid="CloudWatchMetrics",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudwatch:GetMetricData",
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:ListMetrics",
                        "cloudwatch:DescribeAlarms",
                        "cloudwatch:DescribeAlarmsForMetric",
                        "cloudwatch:GetMetricWidgetImage"
                    ],
                    resources=["*"]
                ),
                iam.PolicyStatement(
                    sid="PrometheusAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "aps:QueryMetrics",
                        "aps:GetMetricMetadata",
                        "aps:GetSeries",
                        "aps:GetLabels",
                        "aps:DescribeWorkspace",
                        "aps:ListWorkspaces"
                    ],
                    resources=["*"]
                ),
                iam.PolicyStatement(
                    sid="XRayAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "xray:GetTraceSummaries",
                        "xray:GetTraceGraph",
                        "xray:GetServiceGraph",
                        "xray:GetTimeSeriesServiceStatistics",
                        "xray:BatchGetTraces"
                    ],
                    resources=["*"]
                )
            ],
            roles=[self.devops_agent_role]
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs"""
        
        CfnOutput(
            self,
            "DevOpsAgentRoleArn",
            value=self.devops_agent_role_arn,
            description="IAM Role ARN for AWS DevOps Agent",
            export_name=f"{self.stack_name}-DevOpsAgentRoleArn"
        )

        CfnOutput(
            self,
            "AgentSpaceName",
            value=self.agent_space_name,
            description="DevOps Agent Space Name",
            export_name=f"{self.stack_name}-AgentSpaceName"
        )

        CfnOutput(
            self,
            "ClusterName",
            value=self.cluster_name,
            description="EKS Cluster Name for investigation",
            export_name=f"{self.stack_name}-ClusterName"
        )

        CfnOutput(
            self,
            "SetupInstructions",
            value=f"Grant EKS access with:\n"
                  f"aws eks create-access-entry --cluster-name {self.cluster_name} "
                  f"--principal-arn {self.devops_agent_role_arn} --type STANDARD --region {self.region}\n"
                  f"aws eks associate-access-policy --cluster-name {self.cluster_name} "
                  f"--principal-arn {self.devops_agent_role_arn} "
                  f"--policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy "
                  f"--access-scope type=cluster --region {self.region}",
            description="Commands to grant EKS access to DevOps Agent"
        )

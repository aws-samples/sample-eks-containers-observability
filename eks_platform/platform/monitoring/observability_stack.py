from aws_cdk import (
    Stack,
    aws_logs as logs,
    aws_aps as aps,
    aws_grafana as grafana,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput
)
from constructs import Construct
from eks_platform.config import MonitoringConfig

class ObservabilityStack(Stack):
    """
    Creates AWS Managed Prometheus, CloudWatch Logs, and Grafana resources
    """
    
    
    def _get_retention_days(self, days: int) -> logs.RetentionDays:
        """Map the retention days to the correct RetentionDays enum value"""
        if days <= 1:
            return logs.RetentionDays.ONE_DAY
        elif days <= 3:
            return logs.RetentionDays.THREE_DAYS
        elif days <= 5:
            return logs.RetentionDays.FIVE_DAYS
        elif days <= 7:
            return logs.RetentionDays.ONE_WEEK
        elif days <= 14:
            return logs.RetentionDays.TWO_WEEKS
        elif days <= 30:
            return logs.RetentionDays.ONE_MONTH
        elif days <= 60:
            return logs.RetentionDays.TWO_MONTHS
        elif days <= 90:
            return logs.RetentionDays.THREE_MONTHS
        elif days <= 120:
            return logs.RetentionDays.FOUR_MONTHS
        elif days <= 150:
            return logs.RetentionDays.FIVE_MONTHS
        elif days <= 180:
            return logs.RetentionDays.SIX_MONTHS
        elif days <= 365:
            return logs.RetentionDays.ONE_YEAR
        elif days <= 400:
            return logs.RetentionDays.THIRTEEN_MONTHS
        elif days <= 545:
            return logs.RetentionDays.EIGHTEEN_MONTHS
        elif days <= 731:
            return logs.RetentionDays.TWO_YEARS
        elif days <= 1827:
            return logs.RetentionDays.FIVE_YEARS
        elif days <= 3653:
            return logs.RetentionDays.TEN_YEARS
        else:
            return logs.RetentionDays.INFINITE
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        monitoring_config: MonitoringConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # KMS key removed for simplicity
        
        # Create Amazon Managed Prometheus workspace
        self.prometheus_workspace = aps.CfnWorkspace(
            self, 
            "AmpWorkspace",
            alias="eks-automode-platform"
        )
        
        # Store the workspace ID for other stacks to use
        self.prometheus_workspace_id = self.prometheus_workspace.attr_workspace_id
        
        # Create CloudWatch Log Group for application logs
        self.log_group = logs.LogGroup(
            self, 
            "ApplicationLogGroup",
            log_group_name="/aws/eks/automode-platform/applications",
            removal_policy=RemovalPolicy.DESTROY,
            retention=self._get_retention_days(monitoring_config.retention_days)
        )
        
        # Create CloudWatch Log Group for OpenTelemetry logs
        self.otel_log_group = logs.LogGroup(
            self, 
            "OtelAppLogGroup",
            log_group_name="/aws/eks/automode-platform/otel",
            removal_policy=RemovalPolicy.DESTROY,
            retention=self._get_retention_days(monitoring_config.retention_days)
        )
        
        # Create Grafana workspace if enabled
        if monitoring_config.grafana_enabled:
            # Create main Grafana service role
            grafana_service_role = iam.Role(
                self,
                "GrafanaServiceRole",
                assumed_by=iam.ServicePrincipal("grafana.amazonaws.com")
            )
            
            # Create Grafana assume role for Prometheus
            self.grafana_prometheus_role = iam.Role(
                self,
                "GrafanaPrometheusRole",
                role_name="grafana-prometheus-assume-role",
                assumed_by=iam.ArnPrincipal(grafana_service_role.role_arn)
            )
            
            # Add AMP permissions to Prometheus role
            self.grafana_prometheus_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "aps:QueryMetrics",
                        "aps:GetLabels",
                        "aps:GetSeries",
                        "aps:GetMetricMetadata",
                        "aps:ListWorkspaces",
                        "aps:DescribeWorkspace"
                    ],
                    resources=["*"]
                )
            )
            
            # Create Grafana assume role for CloudWatch
            self.grafana_cloudwatch_role = iam.Role(
                self,
                "GrafanaCloudWatchRole",
                role_name="grafana-cloudwatch-assume-role",
                assumed_by=iam.ArnPrincipal(grafana_service_role.role_arn)
            )
            
            # Add CloudWatch permissions
            self.grafana_cloudwatch_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "cloudwatch:DescribeAlarmsForMetric",
                        "cloudwatch:DescribeAlarmHistory",
                        "cloudwatch:DescribeAlarms",
                        "cloudwatch:ListMetrics",
                        "cloudwatch:GetMetricStatistics",
                        "cloudwatch:GetMetricData",
                        "logs:StartQuery",
                        "logs:GetQueryResults",
                        "logs:GetLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams"
                    ],
                    resources=["*"]
                )
            )
            
            # Create Grafana assume role for X-Ray
            self.grafana_xray_role = iam.Role(
                self,
                "GrafanaXRayRole",
                role_name="grafana-xray-assume-role",
                assumed_by=iam.ArnPrincipal(grafana_service_role.role_arn)
            )
            
            # Add X-Ray permissions
            self.grafana_xray_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "xray:GetServiceGraph",
                        "xray:GetTraceSummaries",
                        "xray:GetTraceGraph",
                        "xray:GetGroups",
                        "xray:GetTimeSeriesServiceStatistics",
                        "xray:GetInsightSummaries",
                        "xray:GetInsight",
                        "xray:BatchGetTraces"
                    ],
                    resources=["*"]
                )
            )
            
            self.grafana_workspace = grafana.CfnWorkspace(
                self, 
                "GrafanaWorkspace",
                account_access_type="CURRENT_ACCOUNT",
                authentication_providers=["AWS_SSO"],
                permission_type="SERVICE_MANAGED",
                role_arn=grafana_service_role.role_arn,
                data_sources=["PROMETHEUS", "CLOUDWATCH", "XRAY"],
                name="eks-automode-platform"
            )
            
            # Output Grafana workspace URL
            CfnOutput(
                self, 
                "GrafanaWorkspaceUrl",
                value=f"https://{self.grafana_workspace.attr_endpoint}",
                description="URL for the Grafana workspace"
            )
        
        # Outputs
        CfnOutput(
            self, 
            "PrometheusWorkspaceId",
            value=self.prometheus_workspace_id,
            description="ID of the Amazon Managed Prometheus workspace"
        )
        
        if monitoring_config.grafana_enabled:
            CfnOutput(
                self, 
                "GrafanaWorkspaceId",
                value=self.grafana_workspace.attr_id,
                description="ID of the Amazon Managed Grafana workspace"
            )
            
            CfnOutput(
                self, 
                "GrafanaServiceRoleArn",
                value=f"arn:aws:iam::{self.account}:role/service-role/AmazonGrafanaServiceRole",
                description="ARN of the Grafana service role for data source access"
            )
            
            CfnOutput(
                self, 
                "GrafanaPrometheusRoleArn",
                value=self.grafana_prometheus_role.role_arn,
                description="ARN of the Grafana assume role for Prometheus data source"
            )
            
            CfnOutput(
                self, 
                "GrafanaCloudWatchRoleArn",
                value=self.grafana_cloudwatch_role.role_arn,
                description="ARN of the Grafana assume role for CloudWatch data source"
            )
            
            CfnOutput(
                self, 
                "GrafanaXRayRoleArn",
                value=self.grafana_xray_role.role_arn,
                description="ARN of the Grafana assume role for X-Ray data source"
            )
        
        # Output Prometheus workspace URL
        CfnOutput(
            self, 
            "PrometheusWorkspaceUrl",
            value=f"https://aps-workspaces.{self.region}.amazonaws.com/workspaces/{self.prometheus_workspace_id}",
            description="URL of the Amazon Managed Prometheus workspace"
        )
        
        CfnOutput(
            self, 
            "LogGroupName",
            value=self.log_group.log_group_name,
            description="Name of the CloudWatch Log Group for application logs"
        )
        
        CfnOutput(
            self, 
            "OtelLogGroupName",
            value=self.otel_log_group.log_group_name,
            description="Name of the CloudWatch Log Group for OpenTelemetry logs"
        )
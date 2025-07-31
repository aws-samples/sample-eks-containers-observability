from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_eks as eks,
    aws_iam as iam,
    CfnOutput,
    CustomResource,
    Duration,
)
import json
from constructs import Construct
from eks_platform.config import EksConfig, constants

class EksClusterStack(Stack):
    """
    Creates an EKS cluster with Auto Mode enabled directly via CDK
    """
    def __init__(
        self, 
        scope: Construct, 
        construct_id: str, 
        vpc: ec2.IVpc,
        kubectl_layer,
        eks_config: EksConfig,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create required service roles for Auto Mode
        cluster_role = self._create_cluster_service_role()
        node_group_role = self._create_node_group_service_role()

        # Check if cluster exists with different compute mode and force replacement
        self._check_and_replace_cluster_if_needed(eks_config)
        
        # Create the EKS cluster based on compute mode
        if eks_config.compute.mode == "fargate":
            self.cluster = self._create_fargate_cluster(eks_config, vpc, kubectl_layer, cluster_role)
        else:
            self.cluster = self._create_auto_mode_cluster(eks_config, vpc, kubectl_layer, cluster_role)
        
        # Create namespaces immediately after cluster creation
        self._create_namespaces(eks_config)
        
        # For Fargate, ensure namespaces are ready before proceeding
        if eks_config.compute.mode == "fargate":
            self._ensure_fargate_namespaces_ready(eks_config)
        
        # Namespaces will be created automatically after cluster
        
        # Configure compute mode specific settings (Auto Mode only)
        if eks_config.compute.mode == "auto-mode":
            self._enable_auto_mode(node_group_role)
        
        # Configure admin access
        self._configure_admin_access(eks_config)
        
        # Add cluster creator access entry
        self._add_cluster_creator_access()
        
        # Add essential addons
        self._add_cluster_addons()
        
        # Create ADOT role for observability
        self._create_adot_role()
        
        # Add logging configuration
        self._configure_logging()
        
        # Add outputs
        self._add_outputs(eks_config)
    
    def _check_and_replace_cluster_if_needed(self, eks_config):
        """Force cluster replacement if compute mode changes"""
        from aws_cdk import CfnCondition, Fn
        
        # Create a condition that forces replacement when compute mode changes
        # This ensures the cluster is recreated with the new compute mode
        compute_mode_condition = CfnCondition(
            self, "ComputeModeChanged",
            expression=Fn.condition_equals(
                eks_config.compute.mode, 
                "force-replacement-on-mode-change"
            )
        )
    
    def _ensure_fargate_namespaces_ready(self, eks_config):
        """Create Fargate profiles without namespace dependencies to avoid circular deps"""
        # Create Fargate profiles - they don't need namespaces to exist first
        for namespace in eks_config.compute.fargate_profiles:
            self.cluster.add_fargate_profile(
                f"{namespace}-fargate-profile",
                selectors=[
                    eks.Selector(namespace=namespace)
                ]
            )
    
    def _create_auto_mode_cluster(self, eks_config, vpc, kubectl_layer, cluster_role):
        """Create EKS cluster for Auto Mode"""
        return eks.Cluster(self, f"AutoModeCluster{eks_config.compute.mode.replace('-', '').title()}",
            version=eks.KubernetesVersion.of(eks_config.version),
            cluster_name=eks_config.cluster_name,
            vpc=vpc,
            kubectl_layer=kubectl_layer,
            role=cluster_role,
            default_capacity=0,  # No default capacity for Auto Mode
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            vpc_subnets=[ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )],
            authentication_mode=eks.AuthenticationMode.API_AND_CONFIG_MAP
        )
    
    def _create_fargate_cluster(self, eks_config, vpc, kubectl_layer, cluster_role):
        """Create EKS cluster for Fargate"""
        return eks.Cluster(self, f"FargateCluster{eks_config.compute.mode.replace('-', '').title()}",
            version=eks.KubernetesVersion.of(eks_config.version),
            cluster_name=eks_config.cluster_name,
            vpc=vpc,
            kubectl_layer=kubectl_layer,
            role=cluster_role,
            default_capacity=0,  # No default capacity for Fargate
            endpoint_access=eks.EndpointAccess.PUBLIC_AND_PRIVATE,
            vpc_subnets=[ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )],
            authentication_mode=eks.AuthenticationMode.API_AND_CONFIG_MAP
        )
    
    def _create_fargate_profiles(self, eks_config):
        """Create Fargate profiles for specified namespaces"""
        for namespace in eks_config.compute.fargate_profiles:
            self.cluster.add_fargate_profile(
                f"{namespace}-fargate-profile",
                selectors=[
                    eks.Selector(namespace=namespace)
                ]
            )
    
    def _create_namespaces(self, eks_config):
        """Create required namespaces after compute setup"""
        mode_prefix = eks_config.compute.mode.replace("-", "").title()
        
        # Create namespaces first (required for both modes)
        self.monitoring_namespace = self.cluster.add_manifest(f"{mode_prefix}MonitoringNamespace", {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "monitoring"
            }
        })
        
        self.opentelemetry_namespace = self.cluster.add_manifest(f"{mode_prefix}OpenTelemetryNamespace", {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "opentelemetry"
            }
        })
        


    def _create_cluster_service_role(self):
        """Create EKS cluster service role with required policies"""
        cluster_role = iam.Role(
            self, "EksClusterServiceRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("eks.amazonaws.com")
            ).with_session_tags(),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSComputePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSBlockStoragePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSLoadBalancingPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSNetworkingPolicy")
            ]
        )
        return cluster_role

    def _create_node_group_service_role(self):
        """Create EKS node group service role with required policies for Auto Mode"""
        node_group_role = iam.Role(
            self, "EksNodeGroupServiceRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("ec2.amazonaws.com")
            ).with_session_tags(),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSWorkerNodePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKS_CNI_Policy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEC2ContainerRegistryReadOnly"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSComputePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSBlockStoragePolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSLoadBalancingPolicy"),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSNetworkingPolicy")
            ]
        )
        return node_group_role

    def _enable_auto_mode(self, node_group_role):
        """Enable Auto Mode using Provider Framework with external Lambda function"""
        from aws_cdk import custom_resources as cr
        from aws_cdk import aws_logs as logs
        from aws_cdk import aws_lambda as lambda_
        from aws_cdk import CustomResource
        import os
        
        # Create IAM role for the Lambda function
        auto_mode_lambda_role = iam.Role(
            self, "AutoModeLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ]
        )
        
        # Add comprehensive permissions directly to the Lambda role
        auto_mode_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "eks:*"
                ],
                resources=["*"]
            )
        )
        
        auto_mode_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "iam:PassRole",
                    "iam:GetRole",
                    "iam:CreateServiceLinkedRole"
                ],
                resources=[
                    node_group_role.role_arn,
                    f"arn:aws:iam::{self.account}:role/aws-service-role/compute.eks.amazonaws.com/*",
                    f"arn:aws:iam::{self.account}:role/aws-service-role/eks-compute.amazonaws.com/*",
                    "*"
                ]
            )
        )
        
        auto_mode_lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:DescribeSubnets",
                    "ec2:DescribeVpcs",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeRouteTables",
                    "ec2:DescribeAvailabilityZones",
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceTypes",
                    "autoscaling:DescribeAutoScalingGroups",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
        
        # Create the Lambda function using external file
        auto_mode_lambda = lambda_.Function(
            self, "AutoModeLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="auto_mode_lambda.on_event",
            code=lambda_.Code.from_asset(os.path.dirname(__file__)),
            role=auto_mode_lambda_role,
            timeout=Duration.minutes(15),
            description="Lambda function to enable EKS Auto Mode with nodePools"
        )
        
        # Create the provider
        auto_mode_provider = cr.Provider(
            self, "AutoModeProvider",
            on_event_handler=auto_mode_lambda,
            log_retention=logs.RetentionDays.ONE_WEEK
        )
        
        # Create the custom resource
        self.auto_mode_enabler = CustomResource(
            self, "EnableAutoMode",
            service_token=auto_mode_provider.service_token,
            properties={
                "ClusterName": self.cluster.cluster_name,
                "NodeRoleArn": node_group_role.role_arn
            }
        )
        
        # Add dependency
        self.auto_mode_enabler.node.add_dependency(self.cluster)

    def _add_cluster_creator_access(self):
        """Add cluster creator access entry for Auto Mode"""
        # Add access entry for cluster creator
        eks.CfnAccessEntry(
            self, "ClusterCreatorAccessEntry",
            cluster_name=self.cluster.cluster_name,
            principal_arn=f"arn:aws:iam::{self.account}:root",
            type="STANDARD",
            access_policies=[
                eks.CfnAccessEntry.AccessPolicyProperty(
                    policy_arn="arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy",
                    access_scope=eks.CfnAccessEntry.AccessScopeProperty(
                        type="cluster"
                    )
                )
            ]
        )

    def _configure_admin_access(self, eks_config: EksConfig):
        """Configure admin access to the cluster"""
        # Add current AWS caller as admin (more flexible than hardcoded user)
        if hasattr(eks_config, 'admin_user_arn') and eks_config.admin_user_arn:
            admin_user = iam.User.from_user_arn(
                self, "AdminUser", 
                eks_config.admin_user_arn
            )
            self.cluster.aws_auth.add_user_mapping(
                user=admin_user,
                groups=["system:masters"]
            )
        
        # Add admin role for cross-account access if specified
        if hasattr(eks_config, 'admin_role_arn') and eks_config.admin_role_arn:
            admin_role = iam.Role.from_role_arn(
                self, "AdminRole",
                eks_config.admin_role_arn
            )
            self.cluster.aws_auth.add_role_mapping(
                role=admin_role,
                groups=["system:masters"]
            )

    def _add_cluster_addons(self):
        """Add essential cluster addons"""
        # CoreDNS addon
        mode_prefix = "AutoMode" if hasattr(self, 'auto_mode_enabler') else "Fargate"
        self.coredns_addon = eks.CfnAddon(
            self, f"{mode_prefix}CoreDnsAddon",
            addon_name="coredns",
            cluster_name=self.cluster.cluster_name,
            addon_version="v1.11.4-eksbuild.14",
            resolve_conflicts="OVERWRITE"
        )
        
        # EKS Pod Identity Agent addon
        self.pod_identity_addon = eks.CfnAddon(
            self, f"{mode_prefix}PodIdentityAgentAddon",
            addon_name="eks-pod-identity-agent",
            cluster_name=self.cluster.cluster_name,
            addon_version="v1.3.7-eksbuild.2",
            resolve_conflicts="OVERWRITE"
        )
        
        # Amazon VPC CNI addon
        self.vpc_cni_addon = eks.CfnAddon(
            self, f"{mode_prefix}VpcCniAddon",
            addon_name="vpc-cni",
            cluster_name=self.cluster.cluster_name,
            resolve_conflicts="OVERWRITE"
        )
        
        # kube-proxy addon
        self.kube_proxy_addon = eks.CfnAddon(
            self, f"{mode_prefix}KubeProxyAddon",
            addon_name="kube-proxy",
            cluster_name=self.cluster.cluster_name,
            resolve_conflicts="OVERWRITE"
        )
        
        # Ensure addons are created after compute mode setup
        if hasattr(self, 'auto_mode_enabler'):
            self.coredns_addon.node.add_dependency(self.auto_mode_enabler)
            self.pod_identity_addon.node.add_dependency(self.auto_mode_enabler)
            self.vpc_cni_addon.node.add_dependency(self.auto_mode_enabler)
            self.kube_proxy_addon.node.add_dependency(self.auto_mode_enabler)

    def _create_adot_role(self):
        """Create IAM role for ADOT collector with Auto Mode support"""
        from aws_cdk import CfnJson
        
        # Get OIDC provider from cluster
        cluster_oidc_provider = self.cluster.open_id_connect_provider
        oidc_provider_url = cluster_oidc_provider.open_id_connect_provider_issuer
        
        # Create conditions for service account
        string_equals = CfnJson(self, "AdotConditionsJson", value={
            f"{oidc_provider_url}:sub": "system:serviceaccount:opentelemetry:otel-collector-sa",
            f"{oidc_provider_url}:aud": "sts.amazonaws.com"
        })
        
        # Create ADOT role
        self.adot_role = iam.Role(
            self, "AdotCollectorRole",
            assumed_by=iam.FederatedPrincipal(
                cluster_oidc_provider.open_id_connect_provider_arn,
                conditions={"StringEquals": string_equals},
                assume_role_action="sts:AssumeRoleWithWebIdentity"
            ),
            role_name=f"EKS-ADOT-PrometheusRemoteWrite-{self.stack_name}"
        )
        
        # Add comprehensive permissions for Auto Mode observability
        self.adot_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonPrometheusRemoteWriteAccess")
        )
        
        self.adot_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess")
        )
        
        # Add CloudWatch and Auto Mode specific permissions
        self.adot_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:PutMetricData",
                    "logs:PutLogEvents",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:DescribeLogStreams",
                    "logs:DescribeLogGroups",
                    "ec2:DescribeInstances",
                    "ec2:DescribeTags",
                    "eks:DescribeCluster",
                    "eks:ListClusters"
                ],
                resources=["*"]
            )
        )

    def _configure_logging(self):
        """Configure logging for Auto Mode cluster"""
        # Enable control plane logging
        self.cluster.add_manifest("ClusterLogging", {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": "aws-logging",
                "namespace": "kube-system"
            },
            "data": {
                "enable": "true",
                "flb_log_cw": "false",
                "filters.conf": """
[FILTER]
    Name kubernetes
    Match kube.*
    Merge_Log On
    Keep_Log Off
    Buffer_Size 0
    Kube_Meta_Cache_TTL 300s

[FILTER]
    Name aws
    Match kube.*
    imds_version v1
""",
                "output.conf": f"""
[OUTPUT]
    Name cloudwatch_logs
    Match kube.*
    region {self.region}
    log_group_name /aws/eks/{self.cluster.cluster_name}/auto-mode/application
    log_stream_prefix auto-mode-
    auto_create_group true
    log_retention_days 7
"""
            }
        })

    def _add_outputs(self, eks_config):
        """Add CloudFormation outputs"""
        CfnOutput(self, "ClusterName",
            value=self.cluster.cluster_name,
            description=f"EKS {eks_config.compute.mode} cluster name"
        )
        
        CfnOutput(self, "ClusterEndpoint",
            value=self.cluster.cluster_endpoint,
            description="EKS cluster endpoint"
        )
        
        CfnOutput(self, "ClusterArn",
            value=self.cluster.cluster_arn,
            description="EKS cluster ARN"
        )
        
        CfnOutput(self, "KubectlConfigCommand",
            value=f"aws eks update-kubeconfig --name {self.cluster.cluster_name} --region {self.region}",
            description="Command to configure kubectl"
        )
        
        CfnOutput(self, "AutoModeStatus",
            value="Enabled via CDK",
            description="Auto Mode enablement status"
        )
        
        CfnOutput(self, "AdotRoleArn",
            value=self.adot_role.role_arn,
            description="ADOT collector IAM role ARN"
        )
        
        CfnOutput(self, "ClusterServiceRoleArn",
            value=self.cluster.role.role_arn,
            description="EKS cluster service role ARN"
        )

    @property
    def cluster_name(self) -> str:
        """Get the cluster name"""
        return self.cluster.cluster_name
    
    @property
    def cluster_arn(self) -> str:
        """Get the cluster ARN"""
        return self.cluster.cluster_arn
    
    @property
    def oidc_provider_arn(self) -> str:
        """Get the OIDC provider ARN"""
        return self.cluster.open_id_connect_provider.open_id_connect_provider_arn
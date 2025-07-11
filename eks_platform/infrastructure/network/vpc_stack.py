from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
)
from constructs import Construct
from cdk_nag import NagSuppressions
from eks_platform.config import NetworkConfig

class VpcStack(Stack):
    """
    Creates a VPC for EKS clusters with configurable parameters
    """
    def __init__(self, scope: Construct, construct_id: str, network_config: NetworkConfig, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a VPC for our EKS clusters
        self.vpc = ec2.Vpc(self, "EksVpc",
            max_azs=network_config.max_azs,
            nat_gateways=network_config.nat_gateways,
            vpc_name=f"{construct_id}-vpc",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    map_public_ip_on_launch=False
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                )
            ],
            flow_logs=network_config.enable_flow_logs and {
                "flow-logs": {
                    "destination": ec2.FlowLogDestination.to_cloud_watch_logs(),
                    "traffic_type": ec2.FlowLogTrafficType.ALL
                }
            } or {}
        )
        
        # Add VPC Endpoints for internal AWS service access
        self._add_vpc_endpoints()

        # Suppress cdk-nag findings for VPC flow logs if not enabled
        if not network_config.enable_flow_logs:
            NagSuppressions.add_resource_suppressions(
                self.vpc,
                [
                    {
                        "id": "AwsSolutions-VPC7",
                        "reason": "VPC Flow Logs not required for this environment"
                    }
                ]
            )

        # Export the VPC for other stacks to use
        self.vpc_id = self.vpc.vpc_id
    
    def _add_vpc_endpoints(self):
        """Add VPC Gateway and Interface Endpoints for internal AWS service access"""
        
        # Gateway Endpoints (free, for S3 and DynamoDB)
        self.vpc.add_gateway_endpoint(
            "S3GatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
        )
        
        self.vpc.add_gateway_endpoint(
            "DynamoDBGatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
        )
        
        # Interface Endpoints (paid, for other AWS services)
        # ECR endpoints for container image pulls
        self.vpc.add_interface_endpoint(
            "EcrDockerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        
        self.vpc.add_interface_endpoint(
            "EcrEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        
        # CloudWatch endpoints for logging and metrics
        self.vpc.add_interface_endpoint(
            "CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        
        self.vpc.add_interface_endpoint(
            "CloudWatchEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        
        # STS endpoint for IAM role assumptions (fixes IRSA issues)
        self.vpc.add_interface_endpoint(
            "StsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.STS,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        
        # EKS endpoint for cluster API access
        self.vpc.add_interface_endpoint(
            "EksEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.EKS,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
        
        # EC2 endpoint for Auto Mode
        self.vpc.add_interface_endpoint(
            "Ec2Endpoint",
            service=ec2.InterfaceVpcEndpointAwsService.EC2,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )
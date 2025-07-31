from aws_cdk import Stack
from cdk_nag import NagSuppressions

def add_nag_suppressions(stacks):
    """
    Add suppressions for cdk-nag findings
    """
    # VPC Stack suppressions
    vpc_stack = next((stack for stack in stacks if stack.stack_name.endswith('NetworkStack')), None)
    if vpc_stack:
        NagSuppressions.add_resource_suppressions(
            vpc_stack, [
                {
                    "id": "HIPAA.Security-VPCFlowLogsEnabled",
                    "reason": "VPC Flow Logs are enabled in production but disabled in development for cost reasons"
                },
                {
                    "id": "HIPAA.Security-VPCSubnetAutoAssignPublicIpDisabled",
                    "reason": "Public subnets require auto-assign public IP for NAT Gateway functionality"
                },
                {
                    "id": "HIPAA.Security-VPCNoUnrestrictedRouteToIGW",
                    "reason": "Public subnets require route to IGW for NAT Gateway functionality"
                }
            ],
            apply_to_children=True
        )
    
    # Observability Stack suppressions
    observability_stack = next((stack for stack in stacks if stack.stack_name.endswith('ObservabilityStack')), None)
    if observability_stack:
        NagSuppressions.add_resource_suppressions_by_path(
            observability_stack,
            [
                "/ObservabilityStack/ApplicationLogGroup/Resource",
                "/ObservabilityStack/OtelAppLogGroup/Resource"
            ],
            [
                {
                    "id": "HIPAA.Security-CloudWatchLogGroupEncrypted",
                    "reason": "Log group encryption is not required for non-sensitive data in development environment"
                }
            ]
        )
    
    # EKS Cluster Stack suppressions
    eks_stack = next((stack for stack in stacks if stack.stack_name.endswith('EksClusterStack')), None)
    if eks_stack:
        # Suppress EKS findings at stack level instead of resource level
        NagSuppressions.add_stack_suppressions(
            eks_stack,
            [
                {
                    "id": "AwsSolutions-EKS1",
                    "reason": "Public endpoint is required for development environment"
                },
                {
                    "id": "AwsSolutions-EKS2",
                    "reason": "Control plane logging is enabled in production but disabled in development for cost reasons"
                }
            ]
        )
        
        # Suppress IAM findings for managed policies
        NagSuppressions.add_stack_suppressions(
            eks_stack,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies are required for EKS functionality"
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions are required for EKS functionality"
                },
                {
                    "id": "HIPAA.Security-IAMNoInlinePolicy",
                    "reason": "Inline policies are required for EKS functionality"
                }
            ]
        )
        
        # Suppress Lambda findings
        NagSuppressions.add_stack_suppressions(
            eks_stack,
            [
                {
                    "id": "HIPAA.Security-LambdaConcurrency",
                    "reason": "Lambda concurrency limits are not required for CDK-generated Lambda functions"
                },
                {
                    "id": "HIPAA.Security-LambdaDLQ",
                    "reason": "Dead letter queues are not required for CDK-generated Lambda functions"
                },
                {
                    "id": "HIPAA.Security-LambdaInsideVPC",
                    "reason": "VPC configuration is not required for CDK-generated Lambda functions"
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Lambda runtime is managed by CDK"
                }
            ]
        )
        
        # Suppress Step Functions findings
        NagSuppressions.add_stack_suppressions(
            eks_stack,
            [
                {
                    "id": "AwsSolutions-SF1",
                    "reason": "Step Functions logging is managed by CDK"
                },
                {
                    "id": "AwsSolutions-SF2",
                    "reason": "X-Ray tracing is not required for CDK-generated Step Functions"
                }
            ]
        )
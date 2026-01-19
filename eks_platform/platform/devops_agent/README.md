# AWS DevOps Agent Integration

This module provides CDK constructs to configure AWS DevOps Agent for investigating your EKS cluster.

## Overview

The DevOps Agent integration automatically configures:
- IAM role with necessary permissions for cluster investigation
- CloudWatch Logs read access
- EKS Kubernetes API access
- CloudWatch Metrics and Prometheus access
- X-Ray tracing access

## Usage

### Deploy with DevOps Agent Support

```bash
# Deploy with DevOps Agent integration
cdk deploy --context deploy_devops_agent=true

# Deploy without DevOps Agent (default)
cdk deploy
```

### What Gets Created

1. **IAM Role**: `{cluster-name}-agent-space-DevOpsAgentRole`
   - Trust policy for devops-agent.amazonaws.com
   - CloudWatch Logs read permissions
   - EKS cluster access permissions
   - CloudWatch Metrics read permissions
   - Prometheus workspace access
   - X-Ray read access

2. **EKS Access Entry**: Grants the IAM role Kubernetes API access
   - Type: STANDARD
   - Policy: AmazonEKSClusterAdminPolicy
   - Scope: Cluster-wide

## Stack Outputs

After deployment, the stack provides:

- `DevOpsAgentRoleArn`: IAM role ARN to use when creating Agent Space
- `DevOpsAgentRoleName`: IAM role name
- `AgentSpaceName`: Suggested name for your Agent Space
- `ClusterName`: EKS cluster name for investigation
- `SetupInstructions`: Complete setup commands

## Creating an Agent Space

After deploying the stack:

1. **Open AWS DevOps Agent Console** (us-east-1)
2. **Create Agent Space**:
   - Name: Use the `AgentSpaceName` from stack outputs
   - IAM Role: Use the `DevOpsAgentRoleArn` from stack outputs
3. **Configure Integrations**:
   - CloudWatch: Automatically configured
   - EKS: Automatically configured
   - Prometheus: Automatically configured

## Permissions Granted

### CloudWatch Logs
- Read log events from application and system logs
- Query and filter logs
- Access log groups: `/aws/eks/automode-platform/*`, `/aws/lambda/*`, `/aws/eks/*`

### EKS Cluster
- Describe cluster configuration
- List and describe node groups
- Access Kubernetes API (via access entry)
- Query pods, deployments, services, etc.

### CloudWatch Metrics
- Get metric data and statistics
- List available metrics
- Describe alarms

### Amazon Managed Prometheus
- Query metrics
- Get metric metadata
- List workspaces

### AWS X-Ray
- Get trace summaries and graphs
- View service graphs
- Analyze distributed traces

## Architecture

```
┌─────────────────────────────────────┐
│   AWS DevOps Agent Service          │
│   (devops-agent.amazonaws.com)      │
└──────────────┬──────────────────────┘
               │ AssumeRole
               ▼
┌─────────────────────────────────────┐
│   DevOps Agent IAM Role             │
│   - CloudWatch Logs Read            │
│   - EKS Access                      │
│   - Metrics Read                    │
│   - Prometheus Access               │
└──────────────┬──────────────────────┘
               │
               ├──────────────┐
               │              │
               ▼              ▼
┌──────────────────┐  ┌──────────────────┐
│  EKS Cluster     │  │  CloudWatch      │
│  - Kubernetes API│  │  - Logs          │
│  - Pods/Services │  │  - Metrics       │
│  - Deployments   │  │  - Alarms        │
└──────────────────┘  └──────────────────┘
```

## Example Investigation Scenarios

### Scenario 1: High CPU Usage
The agent can:
- Query Kubernetes API for pod resource usage
- Read CloudWatch metrics for CPU utilization
- Analyze HPA scaling behavior
- Review application logs for errors

### Scenario 2: Application Errors
The agent can:
- Read application logs from CloudWatch
- Correlate errors across multiple services
- Check pod status and restart counts
- Review recent deployments

### Scenario 3: OTEL Collector Issues
The agent can:
- Read OTEL collector logs
- Check service account IAM role configuration
- Verify Prometheus connectivity
- Analyze trace export failures

## Troubleshooting

### Agent Can't Access Logs

**Issue**: Access denied when reading CloudWatch Logs

**Solution**: Verify IAM role has correct permissions:
```bash
aws iam get-role-policy \
  --role-name {cluster-name}-agent-space-DevOpsAgentRole \
  --policy-name CloudWatchLogsRead
```

### Agent Can't Access Kubernetes API

**Issue**: 401 Unauthorized when querying Kubernetes resources

**Solution**: Verify EKS access entry exists:
```bash
aws eks describe-access-entry \
  --cluster-name {cluster-name} \
  --principal-arn {DevOpsAgentRoleArn}
```

### Permissions Not Propagating

**Issue**: Agent still shows access denied after deployment

**Solution**: Wait 2-5 minutes for IAM permissions to propagate globally, then start a new investigation.

## Cleanup

To remove the DevOps Agent integration:

```bash
cdk destroy DevOpsAgentStack
```

This will:
- Delete the IAM role
- Remove the EKS access entry
- Clean up all associated resources

## Security Considerations

- The IAM role follows least-privilege principles
- Read-only access to logs and metrics
- Cluster admin access is scoped to investigation needs
- Trust policy restricts role assumption to DevOps Agent service
- Account-specific trust conditions prevent cross-account access

## Cost

The DevOps Agent integration itself has no additional cost. You only pay for:
- AWS DevOps Agent usage (during preview: free)
- CloudWatch Logs storage (existing logs)
- CloudWatch Metrics queries (minimal)

## References

- [AWS DevOps Agent Documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/)
- [EKS Access Entries](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html)
- [IAM Roles for Service Accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)

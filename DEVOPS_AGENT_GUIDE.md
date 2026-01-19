# AWS DevOps Agent Integration Guide

> **Note**: This integration works with existing AWS DevOps Agent service-linked roles. You must first create an Agent Space in the AWS DevOps Agent console, then use the CDK to grant that role access to your EKS cluster.

This guide explains how to deploy and use the AWS DevOps Agent integration with your EKS platform.

## Overview

The DevOps Agent integration provides AI-powered cluster investigation and troubleshooting capabilities by automatically configuring:
- Managed IAM policies for CloudWatch Logs, EKS, and CloudWatch Metrics access
- EKS access entry with cluster admin policy
- All necessary permissions for investigating EKS clusters

## Prerequisites

1. **Create an Agent Space** in AWS DevOps Agent console
2. **Note the service-linked role ARN** (format: `arn:aws:iam::ACCOUNT:role/service-role/AGENT_SPACE_NAME-DevOpsAgentRole`)

## Quick Start

### Step 1: Create Agent Space (AWS Console)

1. Navigate to AWS DevOps Agent console
2. Click "Create Agent Space"
3. Enter a name (e.g., "TestDevOpsAgentSpace")
4. AWS will automatically create a service-linked role
5. Note the role ARN from the Agent Space details

### Step 2: Deploy with CDK

```bash
# Deploy with your Agent Space role ARN
cdk deploy --all \
  -c deploy_devops_agent=true \
  -c devops_agent_role_arn="arn:aws:iam::ACCOUNT:role/service-role/YOUR_AGENT_SPACE-DevOpsAgentRole"

# Example:
cdk deploy --all \
  -c deploy_devops_agent=true \
  -c devops_agent_role_arn="arn:aws:iam::YOUR_ACCOUNT_ID:role/service-role/YOUR_AGENT_SPACE-DevOpsAgentRole"
```

### Step 3: Verify Deployment

```bash
# Check managed policies were attached
aws iam list-attached-role-policies --role-name YOUR_AGENT_SPACE-DevOpsAgentRole

# Check EKS access entry
aws eks describe-access-entry \
  --cluster-name dev-eks-automode \
  --principal-arn arn:aws:iam::ACCOUNT:role/service-role/YOUR_AGENT_SPACE-DevOpsAgentRole
```

## What Gets Deployed

### IAM Role

The stack creates an IAM role with:

**CloudWatch Logs Permissions:**
- Read access to EKS application logs
- Read access to Lambda logs
- Query and filter capabilities

**EKS Permissions:**
- Describe cluster and nodegroups
- List clusters and addons
- Access Kubernetes API

**CloudWatch Metrics Permissions:**
- Read metrics and statistics
- List available metrics
- Access to Prometheus workspaces
- X-Ray trace access

### EKS Access Configuration

Automatically creates:
- EKS access entry for the DevOps Agent role
- Association with `AmazonEKSClusterAdminPolicy`
- Cluster-wide access scope

## Configuration

### Enable by Default

Edit `eks_platform/config/environment_config.py`:

```python
@classmethod
def development(cls, account: str, region: str) -> 'EnvironmentConfig':
    return cls(
        # ... other config ...
        devops_agent=DevOpsAgentConfig(
            enabled=True,  # Enable by default
            agent_space_name="my-agent-space",
            create_eks_access=True,
            grant_cluster_admin=True
        )
    )
```

### Context Variables

Pass configuration via CDK context:

```bash
# Enable DevOps Agent
cdk deploy --all -c deploy_devops_agent=true

# Choose compute mode
cdk deploy --all -c compute_mode=fargate

# Combine options
cdk deploy --all -c compute_mode=auto-mode -c deploy_devops_agent=true
```

## Troubleshooting

### Issue: "Access Denied" in Agent

Wait 2-3 minutes for IAM permissions to propagate after deployment.

### Issue: "Can't see Kubernetes resources"

Verify access entry:
```bash
CLUSTER_NAME=$(aws cloudformation describe-stacks \
  --stack-name DevOpsAgentStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterName`].OutputValue' \
  --output text)

aws eks list-access-entries --cluster-name $CLUSTER_NAME
```

### Issue: "Can't read CloudWatch Logs"

Check log groups exist:
```bash
aws logs describe-log-groups --log-group-name-prefix /aws/eks/automode-platform
```

## Cleanup

```bash
# Destroy DevOps Agent stack only
cdk destroy DevOpsAgentStack

# Destroy all stacks
cdk destroy --all
```

## Architecture

```
DevOpsAgentStack
├── IAM Role (DevOpsAgentRole)
│   ├── Trust Policy (devops-agent.amazonaws.com)
│   ├── CloudWatch Logs Policy
│   ├── EKS Access Policy
│   └── CloudWatch Metrics Policy
│
└── DevOpsAgentEksAccess (Custom Resource)
    ├── EKS Access Entry
    └── Cluster Admin Policy Association
```

## Benefits

- **Fully Automated**: No manual configuration required
- **Infrastructure as Code**: All configuration version controlled
- **Repeatable**: Deploy consistently across environments
- **Integrated**: Works seamlessly with the EKS platform
- **Secure**: Follows AWS IAM best practices

## Demo Scenarios

See the `devops-agent-demo/` directory for example investigation scenarios:
- Traffic generation scripts
- Log pushing utilities
- Sample investigation workflows

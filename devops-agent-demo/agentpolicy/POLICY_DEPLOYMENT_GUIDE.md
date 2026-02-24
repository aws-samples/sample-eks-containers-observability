# DevOps Agent IAM Policy Deployment Guide

## Overview
The DevOps Agent requires **13 IAM managed policies** to function properly with tag-based resource filtering. These policies provide read-only access to AWS resources tagged with `DemosFor: OTEL-DevOpsAgent-AIforOperations`.

## Critical: Two-Tier Permission Model

### Part 0 - Discovery Policy (NO TAG FILTERING)
**File:** `tag-filtered-policy-part0-discovery.json`

This policy is **CRITICAL** and must be deployed first. It contains actions that:
- Do NOT support resource-level permissions
- Are required for initial resource discovery
- Enable the agent to find tagged resources
- Allow alarm and metric discovery
- **Enable log analysis and filtering (logs:FilterLogEvents)**
- **Enable CloudWatch metrics analysis**
- **Enable ECS task and service investigation**

**Why No Tag Filtering?**
AWS services like `ecs:ListClusters`, `lambda:ListFunctions`, `cloudwatch:DescribeAlarms`, and **`logs:FilterLogEvents`** don't support resource-level conditions. The agent needs these to discover resources, then filters by tags in subsequent API calls.

**Critical Actions Included:**
- `logs:FilterLogEvents` - Search application logs for errors
- `logs:GetLogEvents` - Retrieve log entries
- `logs:StartQuery` - Run CloudWatch Insights queries
- `cloudwatch:GetMetricData` - Analyze error rate metrics
- `cloudwatch:DescribeAlarmHistory` - Check alarm trigger history
- `ecs:DescribeServices` - Get ECS service details
- `ecs:DescribeTasks` - Investigate running/stopped tasks

### Parts 1-12 - Service-Specific Policies (WITH TAG FILTERING)
These policies apply tag-based filtering and provide detailed read-only access to specific services.

## Deployment Order

### Step 1: Create Part 0 (Discovery Policy)
```bash
aws iam create-policy \
  --policy-name DevOpsAgent-Discovery \
  --policy-document file://tag-filtered-policy-part0-discovery.json
```

### Step 2: Create Parts 1-12 (Service Policies)
```bash
# Part 1 - Core Compute
aws iam create-policy \
  --policy-name DevOpsAgent-CoreCompute \
  --policy-document file://tag-filtered-policy-part1-v2.json

# Part 2 - Observability
aws iam create-policy \
  --policy-name DevOpsAgent-Observability \
  --policy-document file://tag-filtered-policy-part2-v2.json

# Part 3 - Security
aws iam create-policy \
  --policy-name DevOpsAgent-Security \
  --policy-document file://tag-filtered-policy-part3-v2.json

# Part 4 - DataAnalytics
aws iam create-policy \
  --policy-name DevOpsAgent-DataAnalytics \
  --policy-document file://tag-filtered-policy-part4-v2.json

# Part 5 - DatabasesNetworking
aws iam create-policy \
  --policy-name DevOpsAgent-DatabasesNetworking \
  --policy-document file://tag-filtered-policy-part5-v2.json

# Part 6 - StorageDevelopment
aws iam create-policy \
  --policy-name DevOpsAgent-StorageDevelopment \
  --policy-document file://tag-filtered-policy-part6-v2.json

# Part 7 - Management
aws iam create-policy \
  --policy-name DevOpsAgent-Management \
  --policy-document file://tag-filtered-policy-part7-v2.json

# Part 8 - AIMLApplications
aws iam create-policy \
  --policy-name DevOpsAgent-AIMLApplications \
  --policy-document file://tag-filtered-policy-part8-v2.json

# Part 9 - IdentityIoT
aws iam create-policy \
  --policy-name DevOpsAgent-IdentityIoT \
  --policy-document file://tag-filtered-policy-part9-v2.json

# Part 10 - MediaBusiness
aws iam create-policy \
  --policy-name DevOpsAgent-MediaBusiness \
  --policy-document file://tag-filtered-policy-part10-v2.json

# Part 11 - AdditionalServices
aws iam create-policy \
  --policy-name DevOpsAgent-AdditionalServices \
  --policy-document file://tag-filtered-policy-part11-v2.json

# Part 12 - Miscellaneous
aws iam create-policy \
  --policy-name DevOpsAgent-Miscellaneous \
  --policy-document file://tag-filtered-policy-part12-v2.json
```

### Step 3: Attach All Policies to DevOps Agent Role
```bash
ROLE_NAME="<YOUR_DEVOPS_AGENT_ROLE_NAME>"
ACCOUNT_ID="<YOUR_ACCOUNT_ID>"

# Attach Part 0 (Discovery)
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/DevOpsAgent-Discovery

# Attach Parts 1-12
for i in {1..12}; do
  POLICY_NAME="DevOpsAgent-Part${i}"
  aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}
done
```

## Policy Coverage

### Part 0 - Discovery (NO TAG FILTER)
- Resource discovery across all services
- CloudWatch alarms and metrics
- Log group discovery
- API Gateway discovery

### Part 1 - Core Compute & Containers
- EC2, EKS, ECS, ECR, Lambda
- Auto Scaling, ELB, Batch
- Lightsail, WorkSpaces, Nimble, Deadline, M2

### Part 2 - Observability & Monitoring
- CloudWatch, Logs, X-Ray
- APS, Grafana, CloudTrail
- Application Signals, Synthetics, RUM
- Evidently, DevOps Guru, OAM

### Part 3 - Security & Compliance
- GuardDuty, SecurityHub, Detective
- Macie, Inspector, Security Lake
- Shield, WAF, Fraud Detector

### Part 4 - Data & Analytics
- Glue, Athena, Lake Formation
- Kinesis, Kafka, Firehose
- DataBrew, Data Pipeline, Timestream

### Part 5 - Databases & Networking
- RDS, DynamoDB, ElastiCache, Redshift
- Route53, CloudFront, Global Accelerator
- Network Manager, VPC Lattice

### Part 6 - Storage, Backup & Development
- S3, Backup, EFS, FSx
- CodePipeline, CodeBuild, CodeDeploy
- CodeCommit, CodeArtifact, Image Builder

### Part 7 - Management & Governance
- CloudFormation, SSM, Organizations
- Config, EventBridge, Step Functions
- Resource Groups, Service Quotas

### Part 8 - AI/ML & Applications
- Bedrock, SageMaker, Comprehend, Rekognition
- Amplify, AppSync, AppConfig
- SNS, SQS, Scheduler

### Part 9 - Identity & IoT
- Cognito, IAM, SSO
- SES, Connect, Chatbot
- IoT (all variants), Greengrass

### Part 10 - Media & Business Apps
- MediaLive, MediaPackage, IVS
- Q Business, Clean Rooms, Omics
- GameLift, RoboMaker, Ground Station

### Part 11 - Security & Migration
- KMS, Secrets Manager, ACM
- Transfer Family, Proton
- Elastic Beanstalk, EMR

### Part 12 - Miscellaneous
- Device Farm, Schemas, Lex
- Cost Explorer, Budgets, Health

## Verification

After deployment, verify the agent has all permissions:

```bash
aws iam list-attached-role-policies --role-name <YOUR_DEVOPS_AGENT_ROLE_NAME>
```

You should see 13 policies attached.

## Troubleshooting

### Agent Still Reports Missing Permissions
1. Verify all 13 policies are attached to the role
2. Check that Part 0 (Discovery) is included - this is the most critical
3. Wait 1-2 minutes for IAM changes to propagate
4. Verify resources are tagged with `DemosFor: OTEL-DevOpsAgent-AIforOperations`

### Tag Filtering Not Working
- Ensure resources have the exact tag: `DemosFor: OTEL-DevOpsAgent-AIforOperations`
- Tag keys and values are case-sensitive
- Some AWS services don't support tag-based filtering (covered by Part 0)

## Security Notes

- All policies provide **read-only access** only
- No write, modify, or delete permissions granted
- Part 0 allows discovery without tag filtering (required for agent functionality)
- Parts 1-12 enforce tag-based resource filtering
- S3 CDK assets have special conditions for Amplify service access

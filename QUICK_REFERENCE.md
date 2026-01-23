# Quick Reference - EKS Platform with DevOps Agent

## Deployment Commands

### Standard Deployment (No DevOps Agent)
```bash
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
cdk deploy --all
```

### With DevOps Agent Integration
```bash
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
cdk deploy --all --context deploy_devops_agent=true
```

### Fargate Mode with DevOps Agent
```bash
cdk deploy --all --context compute_mode=fargate --context deploy_devops_agent=true
```

## Traffic Generation

```bash
# Setup port forwarding
cd devops-agent-demo
./setup-port-forwarding.sh

# Generate traffic (10 min, 15 RPS, 15% errors)
python traffic-generator.py --app all --duration 600 --rps 15 --error-rate 0.15

# Push logs to CloudWatch
python push-logs-simple.py
```

## DevOps Agent Setup

### 1. Get Stack Outputs
```bash
aws cloudformation describe-stacks --stack-name DevOpsAgentStack \
  --query 'Stacks[0].Outputs' --output table
```

### 2. Create Agent Space
- Console: https://console.aws.amazon.com/devops-agent/
- Use Role ARN from outputs
- Use suggested Agent Space name

### 3. Start Investigation
- Open Operator access link
- Choose "Error rate spike"
- Time range: Last 30 minutes
- Review findings

## Useful Commands

### Check Cluster Status
```bash
kubectl get pods -A
kubectl get hpa -A
kubectl get nodes
```

### View Logs
```bash
# CloudWatch
aws logs tail /aws/eks/automode-platform/applications --follow

# Kubernetes
kubectl logs deployment/otel-collector -n opentelemetry
kubectl logs deployment/go-otel-sample-app -n default
```

### Check Metrics
```bash
# HPA metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq .

# Prometheus (with port-forward)
kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring
```

### Verify DevOps Agent Access
```bash
# EKS access entry
aws eks describe-access-entry \
  --cluster-name dev-eks-automode \
  --principal-arn <ROLE_ARN>

# IAM policies
aws iam list-role-policies --role-name <ROLE_NAME>
```

## Stack Names

| Stack | Purpose |
|-------|---------|
| `NetworkStack` | VPC and networking |
| `KubectlLayerStack` | Lambda layer for kubectl |
| `ObservabilityStack` | Prometheus, Grafana, CloudWatch |
| `EcrStack` | Container registries |
| `EKS-Platform-Cluster` | EKS cluster and applications |
| `DevOpsAgentStack` | DevOps Agent IAM role and permissions |

## Context Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `compute_mode` | `auto-mode`, `fargate` | `auto-mode` | EKS compute mode |
| `deploy_devops_agent` | `true`, `false` | `false` | Deploy DevOps Agent integration |

## Cleanup

```bash
# Destroy specific stack
cdk destroy DevOpsAgentStack

# Destroy all
cdk destroy --all
```

## Documentation

- **Main README**: [README.md](README.md)
- **DevOps Agent Deployment**: [DEVOPS_AGENT_DEPLOYMENT.md](DEVOPS_AGENT_DEPLOYMENT.md)
- **DevOps Agent Demo**: [devops-agent-demo/](devops-agent-demo/)
- **CDK Integration**: [devops-agent-demo/CDK_INTEGRATION_SUMMARY.md](devops-agent-demo/CDK_INTEGRATION_SUMMARY.md)

## Support

- AWS DevOps Agent: https://docs.aws.amazon.com/devopsagent/
- EKS Documentation: https://docs.aws.amazon.com/eks/
- CDK Documentation: https://docs.aws.amazon.com/cdk/

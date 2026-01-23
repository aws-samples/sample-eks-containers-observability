# Quick Start Guide - AWS DevOps Agent Demo

This guide will help you quickly test AWS DevOps Agent with your deployed EKS applications.

## Prerequisites Check

```bash
# Verify cluster access
kubectl get nodes

# Verify applications are running
kubectl get pods -n default

# Verify HPA is working
kubectl get hpa -A
```

## Step 1: Setup Port Forwarding (2 minutes)

```bash
cd devops-agent-demo

# Option A: Use the automated script
./setup-port-forwarding.sh

# Option B: Manual setup
kubectl port-forward svc/sample-metrics-app 8000:8000 -n default &
kubectl port-forward svc/otel-sample-app 8080:8000 -n default &
kubectl port-forward svc/go-otel-sample-app 8090:8080 -n default &
kubectl port-forward svc/java-otel-sample-app 8081:8080 -n default &
```

## Step 2: Install Dependencies (1 minute)

```bash
pip install -r requirements.txt
```

## Step 3: Generate Traffic (5-10 minutes)

### Option A: Quick Test (5 minutes, normal load)

```bash
python traffic-generator.py --app all --duration 300 --rps 10 --error-rate 0.05
```

### Option B: Incident Simulation (10 minutes, with errors)

```bash
python traffic-generator.py --app all --duration 600 --rps 20 --error-rate 0.25
```

### Option C: Targeted Load (Java app only)

```bash
python traffic-generator.py --app java-otel --duration 300 --rps 30 --error-rate 0.15
```

## Step 4: Verify Metrics (2 minutes)

While traffic is generating, check metrics in another terminal:

```bash
# Check HPA scaling
watch kubectl get hpa -A

# Check custom metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq '.resources[].name'

# Check pod status
kubectl get pods -n default -w
```

## Step 5: Access AWS DevOps Agent

### Via AWS Console

1. Open AWS Console → AWS DevOps Agent (us-east-1)
2. Select your Agent Space
3. Click "Operator access" to open the web app
4. Click "Start Investigation"

### Investigation Options

**Option 1: Error Rate Spike**
- Starting point: "Error rate spike"
- Time: Last 15 minutes
- Account: Your AWS account ID
- Region: us-east-1

**Option 2: High CPU Usage**
- Starting point: "High CPU usage"
- Time: Last 15 minutes
- Account: Your AWS account ID
- Region: us-east-1

**Option 3: Latest Alarm**
- Starting point: "Latest alarm"
- This will investigate the most recent CloudWatch alarm

## Step 6: Review Agent Findings

The AWS DevOps Agent will:

1. **Discover Topology** (30 seconds)
   - Map your EKS cluster resources
   - Identify application dependencies
   - Review recent deployments

2. **Analyze Metrics** (1-2 minutes)
   - Query Prometheus metrics
   - Check CloudWatch metrics
   - Identify anomalies

3. **Review Logs** (1-2 minutes)
   - Analyze CloudWatch Logs
   - Correlate error patterns
   - Extract relevant log entries

4. **Provide Analysis** (1 minute)
   - Root cause identification
   - Impact assessment
   - Mitigation recommendations

## Expected Results

### Normal Load Test
- ✅ Applications scale based on HPA rules
- ✅ Request rates match traffic generator settings
- ✅ Low error rates (5-10%)
- ✅ Agent identifies normal operational patterns

### Incident Simulation
- ⚠️ Elevated error rates (20-30%)
- ⚠️ Potential HPA scaling events
- ⚠️ CloudWatch alarms may trigger
- ✅ Agent identifies:
  - Affected applications
  - Error patterns and rates
  - Resource utilization issues
  - Potential root causes
  - Recommended mitigations

## Troubleshooting

### Can't access applications?

```bash
# Check services
kubectl get svc -n default

# Check pods
kubectl get pods -n default

# Restart port-forwarding
pkill -f "port-forward"
./setup-port-forwarding.sh
```

### Traffic generator fails?

```bash
# Test connectivity
curl http://localhost:8000
curl http://localhost:8080
curl http://localhost:8090
curl http://localhost:8081

# Check Python version
python --version  # Should be 3.7+

# Reinstall dependencies
pip install --upgrade requests
```

### No metrics in DevOps Agent?

```bash
# Verify Prometheus is collecting metrics
kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring &
# Open http://localhost:9090 and query: http_requests_total

# Check CloudWatch Logs
aws logs tail /aws/eks/automode-platform/applications --follow --region us-east-1

# Verify HPA is working
kubectl describe hpa -n default
```

## Next Steps

1. **Configure Automatic Investigations**
   - Set up CloudWatch alarms
   - Configure ServiceNow integration
   - Enable automatic incident response

2. **Integrate with CI/CD**
   - Connect GitHub repository
   - Track deployment history
   - Correlate deployments with incidents

3. **Customize Agent Space**
   - Add custom MCP servers
   - Configure Slack notifications
   - Set up custom runbooks

4. **Review Recommendations**
   - Implement suggested improvements
   - Add missing observability
   - Enhance error handling

## Useful Commands

```bash
# View all metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq .

# Check Prometheus targets
kubectl port-forward svc/prometheus-service 9090:9090 -n monitoring &
# Visit http://localhost:9090/targets

# View application logs
kubectl logs -f deployment/sample-metrics-app -n default
kubectl logs -f deployment/otel-sample-app -n default
kubectl logs -f deployment/go-otel-sample-app -n default
kubectl logs -f deployment/java-otel-sample-app -n default

# Check HPA events
kubectl describe hpa sample-metrics-app-hpa -n default

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/EKS \
  --metric-name cluster_failed_node_count \
  --dimensions Name=ClusterName,Value=dev-eks-automode \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1
```

## Demo Script

For a complete demo presentation:

```bash
# 1. Show the cluster (1 min)
kubectl get nodes
kubectl get pods -A
kubectl get hpa -A

# 2. Setup port forwarding (1 min)
./setup-port-forwarding.sh

# 3. Start traffic generation (background)
python traffic-generator.py --app all --duration 900 --rps 15 --error-rate 0.2 &

# 4. Monitor in real-time (2 min)
watch kubectl get hpa -A

# 5. Open AWS DevOps Agent console (2 min)
# Navigate to AWS Console → DevOps Agent → Start Investigation

# 6. Review findings (5 min)
# Show topology, metrics, logs, and recommendations

# 7. Discuss results and next steps (5 min)
```

Total demo time: ~15-20 minutes

## Resources

- [AWS DevOps Agent Documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/)
- [Main README](README.md) - Detailed documentation
- [Traffic Generator Help](traffic-generator.py) - Run with `--help`

#!/bin/bash
set -e

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)


# Create ECR repository if it doesn't exist
aws ecr describe-repositories --repository-names sample-metrics-app || \
  aws ecr create-repository --repository-name sample-metrics-app

# Build and push Docker image
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/sample-metrics-app"

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build and push the image
docker build -t ${ECR_REPO}:latest .
docker buildx build --platform linux/amd64 --push -t ${ECR_REPO}:latest .

# Replace placeholders in deployment.yaml
sed -e "s|\${AWS_REGION}|${AWS_REGION}|g" -e "s|\${ECR_REPO}|${ECR_REPO}|g" deployment-with-prometheus.yaml > deployment_updated.yaml


# Deploy to Kubernetes
kubectl apply -f deployment_updated.yaml

echo "Deployment completed successfully!"
echo "To check the status, run: kubectl get pods -l app=sample-metrics-app"
echo "To view the metrics, run: kubectl port-forward svc/sample-metrics-app 8000:8000"
echo "Then open http://localhost:8000 in your browser"
echo ""

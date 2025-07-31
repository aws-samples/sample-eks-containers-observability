#!/bin/bash

set -e

echo "🚀 Deploying Java OTEL Sample App..."

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/java-otel-sample-app"

echo "Building and pushing Java OTEL sample app..."

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

if [ -z "$ECR_URI" ]; then
    echo "❌ ECR repository not found. Please run 'cdk deploy --all' first."
    exit 1
fi

echo "📦 ECR Repository: $ECR_URI"

# Build the application
echo "🔨 Building Java application..."
mvn clean package -q

# Build Docker image
echo "🐳 Building Docker image..."
docker build -t java-otel-sample-app .

# Login to ECR
echo "🔐 Logging into ECR..."

# Tag and push image
echo "📤 Pushing image to ECR..."
docker tag java-otel-sample-app:latest $ECR_URI:latest
docker buildx build --platform linux/amd64 --push -t $ECR_URI:latest .

# Get cluster name
echo "🔍 Getting EKS cluster name..."
CLUSTER_NAME=$(aws cloudformation describe-stacks \
    --stack-name EksClusterStack \
    --query "Stacks[0].Outputs[?OutputKey=='ClusterName'].OutputValue" \
    --output text 2>/dev/null || echo "")

if [ -z "$CLUSTER_NAME" ]; then
    echo "❌ EKS cluster not found. Please run 'cdk deploy --all' first."
    exit 1
fi

# Update kubeconfig
echo "⚙️  Updating kubeconfig..."
aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION

# Restart deployment to pull new image
echo "🔄 Restarting Java OTEL app deployment..."
kubectl rollout restart deployment/java-otel-sample-app -n default

# Wait for rollout
echo "⏳ Waiting for deployment to complete..."
kubectl rollout status deployment/java-otel-sample-app -n default --timeout=300s

# Check pod status
echo "✅ Checking pod status..."
kubectl get pods -l app=java-otel-sample-app -n default

# Get service info
echo "🌐 Service information:"
kubectl get svc java-otel-sample-app -n default

echo ""
echo "🎉 Java OTEL Sample App deployed successfully!"
echo ""
echo "📋 Quick commands:"
echo "   View pods:    kubectl get pods -l app=java-otel-sample-app"
echo "   View logs:    kubectl logs -l app=java-otel-sample-app -f"
echo "   Port forward: kubectl port-forward svc/java-otel-sample-app 8080:8080"
echo "   Test health:  curl http://localhost:8080/health"
echo "   Test API:     curl http://localhost:8080/api/users"
echo "   View metrics: curl http://localhost:8080/actuator/prometheus"
echo ""
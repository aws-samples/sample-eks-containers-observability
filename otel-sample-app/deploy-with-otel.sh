#!/bin/bash
set -e

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)

# Get ECR repository URI
ECR_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/otel-sample-app"

# Build and tag the Docker image
echo "Building Docker image..."

# Log in to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPO_URI}

# Push the image to ECR
echo "Pushing image to ECR..."
docker buildx build --platform linux/amd64 --push -t ${ECR_REPO_URI}:latest .

echo "Image pushed successfully to ${ECR_REPO_URI}:latest"

# Get EKS cluster name
EKS_CLUSTER_NAME=$(aws eks list-clusters --query "clusters[0]" --output text)

# Update kubeconfig
echo "Updating kubeconfig for cluster ${EKS_CLUSTER_NAME}..."
aws eks update-kubeconfig --name ${EKS_CLUSTER_NAME} --region ${AWS_REGION}

echo "Deployment script completed successfully!"
echo "The CDK deployment will use this image for the OpenTelemetry sample app."

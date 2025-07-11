#!/bin/bash

# Build and push Docker image
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/go-otel-sample-app"

echo "Building and pushing Go OTEL sample app..."

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Build and push
docker build -t go-otel-sample-app .
docker tag go-otel-sample-app:latest $ECR_URI:latest
docker buildx build --platform linux/amd64 --push -t $ECR_URI:latest .
echo "Pushing image to ECR..."

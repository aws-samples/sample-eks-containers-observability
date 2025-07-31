# Dockerfile Notice

This repository contains several Dockerfiles used to build container images for demonstration purposes:

- `go-otel-sample-app/Dockerfile`
- `java-otel-sample-app/Dockerfile`
- `otel-sample-app/Dockerfile`
- `sample-metrics-app/Dockerfile`

## Important Notice for Distribution

If you plan to distribute Docker images built from these Dockerfiles (by publishing to public ECR, DockerHub, S3, etc.), you must:

1. Follow the appropriate distribution process for your organization
2. Obtain approval for distribution
3. Ensure compliance with the licenses of all base images and included software

## Base Images Used

The Dockerfiles in this repository use the following base images:

- `python:3.9-slim` - For Python applications
- `golang:1.20-alpine` - For Go applications
- `eclipse-temurin:17-jre-alpine` - For Java applications

Users should review the licenses of these base images before distribution.

## Local Use

For local development and testing purposes, these Dockerfiles can be used without additional review or approval.
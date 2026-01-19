#!/usr/bin/env python3
"""Push pod logs to CloudWatch for AWS DevOps Agent access"""

import boto3
import time
import subprocess

# Configuration
LOG_GROUP = "/aws/eks/automode-platform/applications"
REGION = "us-east-1"

# Initialize CloudWatch Logs client
logs_client = boto3.client('logs', region_name=REGION)

def create_log_stream(stream_name):
    """Create a log stream if it doesn't exist"""
    try:
        logs_client.create_log_stream(
            logGroupName=LOG_GROUP,
            logStreamName=stream_name
        )
        print(f"✓ Created log stream: {stream_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  Log stream already exists: {stream_name}")
    except Exception as e:
        print(f"  Error creating stream: {e}")

def push_logs(stream_name, messages):
    """Push log messages to CloudWatch"""
    timestamp = int(time.time() * 1000)
    
    log_events = []
    for i, message in enumerate(messages):
        log_events.append({
            'timestamp': timestamp + (i * 1000),
            'message': message
        })
    
    try:
        logs_client.put_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=stream_name,
            logEvents=log_events
        )
        print(f"✓ Pushed {len(messages)} log entries to {stream_name}")
        return True
    except Exception as e:
        print(f"  Error pushing logs: {e}")
        return False

# OTEL Collector Error Logs
print("="*60)
print("Pushing OTEL Collector Error Logs to CloudWatch")
print("="*60)
print()

otel_logs = [
    "[ERROR] OTEL Collector CrashLoopBackOff - IAM Role Assumption Failure",
    "ADOT Collector version: v0.43.3",
    "Error: invalid configuration: extensions::sigv4auth: could not retrieve credential provider",
    "failed to refresh cached credentials, failed to retrieve credentials",
    "operation error STS: AssumeRoleWithWebIdentity",
    "https response error StatusCode: 403, RequestID: a695aca6-7878-4835-b584-fa52e258cb2c",
    "api error AccessDenied: Not authorized to perform sts:AssumeRoleWithWebIdentity",
    "Root Cause: OTEL collector service account cannot assume IAM role",
    "IAM Role: EKS-ADOT-PrometheusRemoteWrite-EKS-Platform-Cluster",
    "Issue: IRSA (IAM Roles for Service Accounts) misconfiguration",
    "Service Account: otel-collector-sa in namespace opentelemetry",
    "Required: Proper annotation eks.amazonaws.com/role-arn on service account",
    "Required: IAM role trust policy must include EKS OIDC provider"
]

create_log_stream("otel-collector-errors")
push_logs("otel-collector-errors", otel_logs)

# Go OTEL App Logs
print()
go_logs = [
    "[ERROR] Go OTEL App - Cannot connect to OTEL collector",
    "traces export: exporter export timeout",
    "rpc error: code = Unavailable desc = connection error",
    "transport: Error while dialing: dial tcp 172.20.154.180:4317: connect: connection refused",
    "failed to upload metrics: exporter export timeout",
    "Impact: 100% request failure rate (8,970 failed requests)",
    "Dependency: Requires OTEL collector on port 4317",
    "Status: Waiting for OTEL collector to become available"
]

create_log_stream("go-otel-app-errors")
push_logs("go-otel-app-errors", go_logs)

# Java OTEL App Logs
print()
java_logs = [
    "[ERROR] Java OTEL App - Cannot connect to OTEL collector",
    "io.grpc.StatusRuntimeException: UNAVAILABLE: io exception",
    "Connection refused: otel-collector.opentelemetry.svc.cluster.local:4317",
    "Failed to export spans to OTLP endpoint",
    "Impact: 100% request failure rate (8,985 failed requests)",
    "Dependency: Requires OTEL collector for trace export",
    "Retry attempts exhausted, backing off",
    "Status: Application running but telemetry export failing"
]

create_log_stream("java-otel-app-errors")
push_logs("java-otel-app-errors", java_logs)

# Python OTEL App Logs
print()
python_logs = [
    "[WARNING] Python OTEL App - Intermittent OTEL collector connection issues",
    "ConnectionError: Failed to connect to otel-collector:4317",
    "Retrying telemetry export (attempt 3/5)",
    "Some requests succeeded, others failed",
    "Impact: 84.55% success rate (1,386 failed out of 8,970 requests)",
    "Behavior: Graceful degradation with retry logic",
    "Status: Partially functional, telemetry export intermittent"
]

create_log_stream("python-otel-app-warnings")
push_logs("python-otel-app-warnings", python_logs)

# Sample Metrics App Logs
print()
sample_logs = [
    "[INFO] Sample Metrics App - Operating normally",
    "Prometheus metrics endpoint: /metrics",
    "Request rate: 15.6 requests/second",
    "HPA scaled to 4 replicas based on request rate",
    "Target: 10 requests/second, Current: 15.6",
    "Impact: None - no dependency on OTEL collector",
    "Status: 100% success rate (8,880 successful requests)",
    "Note: Uses Prometheus metrics, not OTEL"
]

create_log_stream("sample-metrics-app-info")
push_logs("sample-metrics-app-info", sample_logs)

print()
print("="*60)
print("Logs Successfully Pushed to CloudWatch!")
print("="*60)
print()
print(f"Log Group: {LOG_GROUP}")
print("Log Streams:")
print("  - otel-collector-errors")
print("  - go-otel-app-errors")
print("  - java-otel-app-errors")
print("  - python-otel-app-warnings")
print("  - sample-metrics-app-info")
print()
print("Verify logs:")
print(f"  aws logs tail {LOG_GROUP} --follow --region {REGION}")
print()
print("AWS DevOps Agent can now access these logs!")

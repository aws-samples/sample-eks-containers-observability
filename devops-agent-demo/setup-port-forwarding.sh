#!/bin/bash
# Setup port forwarding for all EKS platform applications
# This script creates background port-forward processes for easy access to services

set -e

echo "=========================================="
echo "Setting up port forwarding for EKS apps"
echo "=========================================="

# Kill any existing port-forward processes
echo "Cleaning up existing port-forward processes..."
pkill -f "kubectl port-forward" || true
sleep 2

# Function to setup port forwarding
setup_port_forward() {
    local service=$1
    local local_port=$2
    local remote_port=$3
    local namespace=${4:-default}
    
    echo "Setting up port-forward: $service ($local_port -> $remote_port)"
    kubectl port-forward svc/$service $local_port:$remote_port -n $namespace > /dev/null 2>&1 &
    sleep 1
    
    # Verify the port-forward is working
    if curl -s http://localhost:$local_port > /dev/null 2>&1; then
        echo "✓ $service is accessible at http://localhost:$local_port"
    else
        echo "⚠ $service port-forward started but not yet responding"
    fi
}

# Setup port forwarding for all applications
setup_port_forward "sample-metrics-app" 8000 8000 "default"
setup_port_forward "otel-sample-app" 8080 8000 "default"
setup_port_forward "go-otel-sample-app" 8090 8080 "default"
setup_port_forward "java-otel-sample-app" 8081 8080 "default"

# Optional: Setup Prometheus and Grafana
read -p "Do you want to setup port-forwarding for Prometheus (9090)? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    setup_port_forward "prometheus-service" 9090 9090 "monitoring"
fi

echo ""
echo "=========================================="
echo "Port forwarding setup complete!"
echo "=========================================="
echo ""
echo "Application endpoints:"
echo "  Sample Metrics App:  http://localhost:8000"
echo "  Python OTEL App:     http://localhost:8080"
echo "  Go OTEL App:         http://localhost:8090"
echo "  Java OTEL App:       http://localhost:8081"
echo ""
echo "To stop all port-forwarding:"
echo "  pkill -f 'kubectl port-forward'"
echo ""
echo "To view port-forward processes:"
echo "  ps aux | grep 'kubectl port-forward'"
echo ""

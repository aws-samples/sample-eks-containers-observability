#!/bin/bash

# Generate traffic for Java OTEL sample app
echo "Starting traffic generation for Java OTEL sample app..."

# Get service URL
SERVICE_URL="http://localhost:8081"
if kubectl get svc java-otel-sample-app >/dev/null 2>&1; then
    echo "Using Kubernetes service via port-forward"
    kubectl port-forward svc/java-otel-sample-app 8081:8080 &
    PORT_FORWARD_PID=$!
    sleep 3
fi

# Function to make requests
make_request() {
    local endpoint=$1
    local method=${2:-GET}
    
    response=$(curl -s -w "%{http_code}" -X $method "$SERVICE_URL$endpoint" 2>/dev/null)
    http_code="${response: -3}"
    
    if [[ $http_code -eq 200 ]]; then
        echo "✓ $method $endpoint - Status: $http_code"
    else
        echo "✗ $method $endpoint - Status: $http_code"
    fi
}

# Generate traffic for 5 minutes
echo "Generating traffic for 5 minutes..."
end_time=$(($(date +%s) + 300))

while [ $(date +%s) -lt $end_time ]; do
    # Health checks (frequent)
    make_request "/health"
    
    # API endpoints
    make_request "/api/users"
    make_request "/api/products"
    make_request "/actuator/prometheus"
    
    # Random delay between requests
    sleep $(echo "scale=2; $RANDOM/32767*2+0.5" | bc -l)
done

# Cleanup
if [[ -n $PORT_FORWARD_PID ]]; then
    kill $PORT_FORWARD_PID 2>/dev/null
fi

echo "Traffic generation completed!"
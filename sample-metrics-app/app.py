import time
import random
import logging
import os
from prometheus_client import start_http_server, Counter, Gauge, Histogram, Summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Create metrics
REQUEST_COUNT = Counter('sample_app_requests_total', 'Total app requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('sample_app_request_latency_seconds', 'Request latency', ['endpoint'])
MEMORY_USAGE = Gauge('sample_app_memory_usage_bytes', 'Memory usage in bytes')
CPU_USAGE = Gauge('sample_app_cpu_usage_percent', 'CPU usage percentage')
ACTIVE_REQUESTS = Gauge('sample_app_active_requests', 'Number of active requests')
REQUEST_SIZE = Summary('sample_app_request_size_bytes', 'Request size in bytes')

def generate_metrics():
    """Generate sample metrics and logs."""
    endpoints = ['/', '/api/users', '/api/products', '/api/orders']
    statuses = ['200', '404', '500']

    # Initialize counter to ensure we're generating metrics
    counter = 0

    while True:
        counter += 1

        # Simulate request count
        endpoint = random.choice(endpoints)
        status = random.choice(statuses)
        REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()

        # Simulate request latency
        latency = random.uniform(0.001, 2.0)
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)

        # Simulate memory and CPU usage
        MEMORY_USAGE.set(random.uniform(10 * 1024 * 1024, 100 * 1024 * 1024))
        CPU_USAGE.set(random.uniform(0, 100))

        # Simulate active requests
        ACTIVE_REQUESTS.set(random.randint(1, 10))

        # Simulate request size
        REQUEST_SIZE.observe(random.uniform(100, 10000))

        # Generate logs
        if random.random() < 0.7:
            logger.info(f"Request #{counter} to {endpoint} completed with status {status} in {latency:.3f}s")
        elif random.random() < 0.9:
            logger.warning(f"Slow response #{counter} on {endpoint}: {latency:.3f}s")
        else:
            logger.error(f"Error #{counter} processing request to {endpoint}: status {status}")

        # Log metrics every 10 iterations to confirm they're being generated
        if counter % 10 == 0:
            logger.info(f"Generated {counter} metrics samples. Latest: endpoint={endpoint}, status={status}, latency={latency:.3f}")

        time.sleep(random.uniform(0.1, 0.5))  # Generate metrics more frequently

if __name__ == '__main__':
    # Start Prometheus metrics server
    start_http_server(8000)
    logger.info("Metrics server started on port 8000")

    # Log environment variables
    aws_region = os.environ.get('AWS_REGION', 'unknown')
    logger.info(f"AWS Region: {aws_region}")
    logger.info("Starting to generate metrics...")

    # Generate metrics
    generate_metrics()

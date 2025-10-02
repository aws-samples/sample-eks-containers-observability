import time
import random
import logging
import os
import json
import psutil
import threading
from flask import Flask, request, jsonify
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View, ExplicitBucketHistogramAggregation
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.extension.aws.trace import AwsXRayIdGenerator
from opentelemetry.propagators.aws.aws_xray_propagator import AwsXRayPropagator
from opentelemetry.propagate import set_global_textmap
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter

# Configure service name and other attributes
service_name = os.environ.get("OTEL_SERVICE_NAME", "otel_sample_app")
service_namespace = os.environ.get("OTEL_SERVICE_NAMESPACE", "default")
deployment_environment = os.environ.get("OTEL_DEPLOYMENT_ENVIRONMENT", "test")
aws_region = os.environ.get("AWS_REGION", "eu-west-1")
cluster_name = os.environ.get("CLUSTER_NAME", "fargate-cluster")

# Set explicit OTLP endpoint from environment variable
otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector.opentelemetry:4317")
print(f"Using OTLP endpoint: {otlp_endpoint}")

# Create a resource with service information
resource = Resource.create({
    "service.name": service_name,
    "service.namespace": service_namespace,
    "deployment.environment": deployment_environment,
    "aws.region": aws_region,
    "ClusterName": cluster_name,
    "Namespace": service_namespace,
    "PodName": os.environ.get("HOSTNAME", "unknown-pod")
})

# Configure AWS X-Ray propagator
set_global_textmap(AwsXRayPropagator())

# Configure tracing with AWS X-Ray ID generator
trace_provider = TracerProvider(
    resource=resource,
    id_generator=AwsXRayIdGenerator()
)
otlp_trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer(__name__)

# Configure metrics with explicit OTLP exporter configuration
otlp_metric_exporter = OTLPMetricExporter(
    endpoint=otlp_endpoint,
    insecure=True  # Use insecure for http:// endpoints
)
metric_reader = PeriodicExportingMetricReader(
    otlp_metric_exporter,
    export_interval_millis=15000  # Export metrics every 15 seconds
)
# Configure histogram buckets
histogram_view = View(
    instrument_name="otel_sample_app_request_duration",
    aggregation=ExplicitBucketHistogramAggregation(
        boundaries=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
    )
)

metric_provider = MeterProvider(
    resource=resource,
    metric_readers=[metric_reader],
    views=[histogram_view]
)
metrics.set_meter_provider(metric_provider)
meter = metrics.get_meter(__name__)

# Configure logs
logger_provider = LoggerProvider(resource=resource)
otlp_log_exporter = OTLPLogExporter(endpoint=otlp_endpoint)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_log_exporter))
set_logger_provider(logger_provider)

# Create metrics with otel_sample_app prefix (using underscores for Prometheus compatibility)
request_counter = meter.create_counter(
    name="otel_sample_app_request_count",
    description="Count of requests",
    unit="1"
)

request_duration = meter.create_histogram(
    name="otel_sample_app_request_duration",
    description="Duration of requests",
    unit="s"
)

active_requests = meter.create_up_down_counter(
    name="otel_sample_app_active_requests",
    description="Number of active requests",
    unit="1"
)

# Create pod metrics with correct callback format
def cpu_callback(options):
    from opentelemetry.metrics import Observation
    cpu_percent = psutil.cpu_percent()
    hostname = os.environ.get("HOSTNAME", "unknown-pod")
    return [
        Observation(value=cpu_percent, attributes={
            "ClusterName": cluster_name,
            "Namespace": service_namespace,
            "PodName": hostname
        })
    ]

def memory_callback(options):
    from opentelemetry.metrics import Observation
    memory_percent = psutil.virtual_memory().percent
    hostname = os.environ.get("HOSTNAME", "unknown-pod")
    return [
        Observation(value=memory_percent, attributes={
            "ClusterName": cluster_name,
            "Namespace": service_namespace,
            "PodName": hostname
        })
    ]

def container_cpu_callback(options):
    from opentelemetry.metrics import Observation
    cpu_percent = psutil.cpu_percent()
    hostname = os.environ.get("HOSTNAME", "unknown-pod")
    return [
        Observation(value=cpu_percent, attributes={
            "ClusterName": cluster_name,
            "Namespace": service_namespace,
            "PodName": hostname,
            "ContainerName": "otel-sample-app"
        })
    ]

def container_memory_callback(options):
    from opentelemetry.metrics import Observation
    memory_percent = psutil.virtual_memory().percent
    hostname = os.environ.get("HOSTNAME", "unknown-pod")
    return [
        Observation(value=memory_percent, attributes={
            "ClusterName": cluster_name,
            "Namespace": service_namespace,
            "PodName": hostname,
            "ContainerName": "otel-sample-app"
        })
    ]

def cpu_limit_callback(options):
    from opentelemetry.metrics import Observation
    hostname = os.environ.get("HOSTNAME", "unknown-pod")
    # Calculate CPU utilization over limit (using 200m as the limit from deployment)
    cpu_percent = psutil.cpu_percent()
    cpu_over_limit = (cpu_percent / 100) * (200 / 1000) * 100  # Convert to percentage of 200m limit
    return [
        Observation(value=cpu_over_limit, attributes={
            "ClusterName": cluster_name,
            "Namespace": service_namespace,
            "PodName": hostname
        })
    ]

def service_pods_callback(options):
    from opentelemetry.metrics import Observation
    # This would normally come from K8s API, but we'll hardcode for demo
    return [
        Observation(value=2, attributes={
            "ClusterName": cluster_name,
            "Namespace": service_namespace,
            "Service": "otel-sample-app"
        })
    ]

# Pod metrics
cpu_utilization = meter.create_observable_gauge(
    name="pod_cpu_utilization",
    description="CPU usage percentage",
    unit="percent",
    callbacks=[cpu_callback]
)

memory_utilization = meter.create_observable_gauge(
    name="pod_memory_utilization",
    description="Memory usage percentage",
    unit="percent",
    callbacks=[memory_callback]
)

# Container metrics
container_cpu_utilization = meter.create_observable_gauge(
    name="container_cpu_utilization",
    description="Container CPU usage percentage",
    unit="percent",
    callbacks=[container_cpu_callback]
)

container_memory_utilization = meter.create_observable_gauge(
    name="container_memory_utilization",
    description="Container memory usage percentage",
    unit="percent",
    callbacks=[container_memory_callback]
)

# CPU over limit metric
cpu_over_limit = meter.create_observable_gauge(
    name="pod_cpu_utilization_over_pod_limit",
    description="CPU usage over pod limit percentage",
    unit="percent",
    callbacks=[cpu_limit_callback]
)

# Service pods metric
service_pods = meter.create_observable_gauge(
    name="service_number_of_running_pods",
    description="Number of running pods for service",
    unit="1",
    callbacks=[service_pods_callback]
)

# Network metrics as counters
network_rx_bytes = meter.create_counter(
    name="pod_network_rx_bytes",
    description="Network bytes received",
    unit="bytes"
)

network_tx_bytes = meter.create_counter(
    name="pod_network_tx_bytes",
    description="Network bytes sent",
    unit="bytes"
)

# Configure logging WITHOUT OpenTelemetry instrumentation to avoid recursion
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Instrument Flask and Requests only (skip LoggingInstrumentor to avoid recursion)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Function to periodically update network metrics
def update_network_metrics():
    last_net_io = psutil.net_io_counters()
    last_time = time.time()

    while True:
        time.sleep(5)  # Update every 5 seconds
        current_net_io = psutil.net_io_counters()
        current_time = time.time()

        # Calculate bytes received/sent since last check
        rx_bytes = current_net_io.bytes_recv - last_net_io.bytes_recv
        tx_bytes = current_net_io.bytes_sent - last_net_io.bytes_sent

        # Update metrics
        network_rx_bytes.add(rx_bytes, {"ClusterName": cluster_name, "Namespace": service_namespace, "PodName": os.environ.get("HOSTNAME", "unknown-pod")})
        network_tx_bytes.add(tx_bytes, {"ClusterName": cluster_name, "Namespace": service_namespace, "PodName": os.environ.get("HOSTNAME", "unknown-pod")})

        # Update last values
        last_net_io = current_net_io
        last_time = current_time

# Start network metrics thread
network_thread = threading.Thread(target=update_network_metrics, daemon=True)
network_thread.start()

# Random log generation function
def generate_random_logs():
    """Generate random logs to simulate application activity"""
    log_scenarios = [
        {"level": "info", "message": "User authentication successful", "weight": 30},
        {"level": "info", "message": "Database connection established", "weight": 20},
        {"level": "info", "message": "Cache hit for user data", "weight": 25},
        {"level": "info", "message": "API request processed successfully", "weight": 35},
        {"level": "warning", "message": "High memory usage detected", "weight": 10},
        {"level": "warning", "message": "Slow database query detected", "weight": 8},
        {"level": "warning", "message": "Rate limit approaching for client", "weight": 5},
        {"level": "error", "message": "Failed to connect to external service", "weight": 3},
        {"level": "error", "message": "Database timeout occurred", "weight": 2},
        {"level": "error", "message": "Invalid request format received", "weight": 4},
        {"level": "debug", "message": "Processing background task", "weight": 15},
        {"level": "debug", "message": "Cache miss, fetching from database", "weight": 12}
    ]

    user_ids = [f"user_{i}" for i in range(1, 101)]
    endpoints = ["/api/users", "/api/products", "/api/orders", "/api/auth", "/health"]

    while True:
        # Generate 1-5 logs per cycle
        num_logs = random.randint(1, 5)

        for _ in range(num_logs):
            # Select log scenario based on weights
            scenarios = []
            weights = []
            for scenario in log_scenarios:
                scenarios.append(scenario)
                weights.append(scenario["weight"])

            selected_scenario = random.choices(scenarios, weights=weights)[0]

            # Add random context to the log message
            user_id = random.choice(user_ids)
            endpoint = random.choice(endpoints)
            request_id = f"req-{random.randint(10000, 99999)}"
            response_time = round(random.uniform(0.01, 2.5), 3)

            # Create structured log data
            log_data = {
                "request_id": request_id,
                "user_id": user_id,
                "endpoint": endpoint,
                "response_time_ms": response_time * 1000,
                "timestamp": time.time(),
                "service": service_name,
                "region": aws_region
            }

            # Generate the log message
            base_message = selected_scenario["message"]
            detailed_message = f"[{request_id}] {base_message} - User: {user_id}, Endpoint: {endpoint}, Response time: {response_time}s"

            # Log based on level
            if selected_scenario["level"] == "info":
                logger.info(detailed_message)
                logger.info(json.dumps(log_data))
            elif selected_scenario["level"] == "warning":
                logger.warning(detailed_message)
                logger.warning(json.dumps({**log_data, "alert_type": "performance"}))
            elif selected_scenario["level"] == "error":
                error_code = f"ERR-{random.randint(1000, 9999)}"
                logger.error(detailed_message + f" - Error code: {error_code}")
                logger.error(json.dumps({**log_data, "error_code": error_code, "severity": "high"}))
            elif selected_scenario["level"] == "debug":
                logger.debug(detailed_message)
                logger.debug(json.dumps({**log_data, "debug_info": "background_process"}))

        # Wait between 2-10 seconds before next batch
        time.sleep(random.uniform(2, 10))

# Start random log generation thread (optional - comment out if you only want API-triggered logs)
log_thread = threading.Thread(target=generate_random_logs, daemon=True)
log_thread.start()

@app.route('/')
def home():
    with tracer.start_as_current_span("home") as span:
        active_requests.add(1)
        start_time = time.time()

        # Add attributes to the span
        span.set_attribute("endpoint", "root")

        # Log the request
        logger.info("Processing request to home endpoint")

        # Simulate some work
        time.sleep(random.uniform(0.01, 0.1))

        # Record metrics
        request_counter.add(1, {"endpoint": "root"})
        duration = time.time() - start_time
        request_duration.record(duration, {"endpoint": "root"})
        active_requests.add(-1)

        return jsonify({
            "message": "Welcome to OpenTelemetry Sample App",
            "service": service_name,
            "region": aws_region
        })

@app.route('/api/users')
def users():
    with tracer.start_as_current_span("get_users") as span:
        active_requests.add(1)
        start_time = time.time()
        request_id = f"req-{random.randint(1000, 9999)}"

        # Add attributes to the span
        span.set_attribute("endpoint", "api_users")
        span.set_attribute("request.id", request_id)

        # Log the request with request ID
        logger.info(f"[{request_id}] Processing request to users endpoint")
        logger.info(json.dumps({
            "request_id": request_id,
            "endpoint": "api_users",
            "client_ip": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", "Unknown")
        }))

        # Simulate some work
        time.sleep(random.uniform(0.05, 0.2))

        # Simulate an error occasionally
        if random.random() < 0.1:
            error_id = f"err-{random.randint(1000, 9999)}"
            logger.error(f"[{request_id}] Error retrieving users data. Error ID: {error_id}")
            logger.error(json.dumps({
                "request_id": request_id,
                "error_id": error_id,
                "error_type": "data_retrieval_error",
                "endpoint": "api_users",
                "message": "Failed to retrieve users data"
            }))

            span.set_status(trace.Status(trace.StatusCode.ERROR, "Failed to retrieve users"))

            # Record metrics
            request_counter.add(1, {"endpoint": "api_users", "status": "error"})
            duration = time.time() - start_time
            request_duration.record(duration, {"endpoint": "api_users", "status": "error"})
            active_requests.add(-1)

            return jsonify({"error": "Failed to retrieve users", "error_id": error_id}), 500

        # Record metrics
        request_counter.add(1, {"endpoint": "api_users", "status": "success"})
        duration = time.time() - start_time
        request_duration.record(duration, {"endpoint": "api_users", "status": "success"})
        active_requests.add(-1)

        return jsonify({
            "users": [
                {"id": 1, "name": "User 1"},
                {"id": 2, "name": "User 2"},
                {"id": 3, "name": "User 3"}
            ]
        })

@app.route('/api/products')
def products():
    with tracer.start_as_current_span("get_products") as span:
        active_requests.add(1)
        start_time = time.time()

        # Add attributes to the span
        span.set_attribute("endpoint", "api_products")

        # Log the request
        logger.info("Processing request to products endpoint")

        # Simulate some work
        time.sleep(random.uniform(0.05, 0.2))

        # Record metrics
        request_counter.add(1, {"endpoint": "api_products"})
        duration = time.time() - start_time
        request_duration.record(duration, {"endpoint": "api_products"})
        active_requests.add(-1)

        return jsonify({
            "products": [
                {"id": 1, "name": "Product 1", "price": 10.99},
                {"id": 2, "name": "Product 2", "price": 20.99},
                {"id": 3, "name": "Product 3", "price": 30.99}
            ]
        })



@app.route('/metrics')
def metrics_endpoint():
    logger.info("Metrics endpoint called")
    hostname = os.environ.get("HOSTNAME", "unknown-pod")
    cpu_percent = psutil.cpu_percent()
    memory_percent = psutil.virtual_memory().percent

    # Get current network stats for RX/TX bytes
    net_io = psutil.net_io_counters()

    # Get container resource limits
    cpu_limit = 200  # 200m as defined in deployment
    memory_limit = 256  # 256Mi as defined in deployment

    # Return metrics in Prometheus format for scraping
    metric_output = f"""
# HELP pod_cpu_utilization CPU usage percentage
# TYPE pod_cpu_utilization gauge
pod_cpu_utilization{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}"}} {cpu_percent}

# HELP pod_memory_utilization Memory usage percentage
# TYPE pod_memory_utilization gauge
pod_memory_utilization{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}"}} {memory_percent}

# HELP container_cpu_utilization Container CPU usage percentage
# TYPE container_cpu_utilization gauge
container_cpu_utilization{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}",ContainerName="otel-sample-app"}} {cpu_percent}

# HELP container_memory_utilization Container memory usage percentage
# TYPE container_memory_utilization gauge
container_memory_utilization{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}",ContainerName="otel-sample-app"}} {memory_percent}

# HELP pod_cpu_utilization_over_pod_limit CPU usage over pod limit percentage
# TYPE pod_cpu_utilization_over_pod_limit gauge
pod_cpu_utilization_over_pod_limit{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}"}} {(cpu_percent / 100) * (200 / 1000) * 100}

# HELP pod_memory_utilization_over_pod_limit Memory usage over pod limit percentage
# TYPE pod_memory_utilization_over_pod_limit gauge
pod_memory_utilization_over_pod_limit{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}"}} {(memory_percent / 100) * (256 / 256) * 100}

# HELP container_cpu_limit Container CPU limit in millicores
# TYPE container_cpu_limit gauge
container_cpu_limit{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}",ContainerName="otel-sample-app"}} {cpu_limit}

# HELP container_memory_limit Container memory limit in MiB
# TYPE container_memory_limit gauge
container_memory_limit{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}",ContainerName="otel-sample-app"}} {memory_limit}

# HELP service_number_of_running_pods Number of running pods for service
# TYPE service_number_of_running_pods gauge
service_number_of_running_pods{{ClusterName="{cluster_name}",Namespace="{service_namespace}",Service="otel-sample-app"}} 2

# HELP pod_network_rx_bytes Network bytes received
# TYPE pod_network_rx_bytes counter
pod_network_rx_bytes{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}"}} {net_io.bytes_recv}

# HELP pod_network_tx_bytes Network bytes sent
# TYPE pod_network_tx_bytes counter
pod_network_tx_bytes{{ClusterName="{cluster_name}",Namespace="{service_namespace}",PodName="{hostname}"}} {net_io.bytes_sent}

# HELP otel_sample_app_request_count Count of requests
# TYPE otel_sample_app_request_count counter
otel_sample_app_request_count{{endpoint="root"}} 1
otel_sample_app_request_count{{endpoint="api_users",status="success"}} 1

# HELP otel_sample_app_request_duration Duration of requests
# TYPE otel_sample_app_request_duration histogram
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.005"}} 0
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.01"}} 0
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.025"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.05"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.075"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.1"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.25"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.5"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="0.75"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="1.0"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="2.5"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="5.0"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="7.5"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="10.0"}} 1
otel_sample_app_request_duration_bucket{{endpoint="root",le="+Inf"}} 1
otel_sample_app_request_duration_sum{{endpoint="root"}} 0.05
otel_sample_app_request_duration_count{{endpoint="root"}} 1

# HELP otel_sample_app_active_requests Number of active requests
# TYPE otel_sample_app_active_requests gauge
otel_sample_app_active_requests 0
"""
    return metric_output, 200, {'Content-Type': 'text/plain; version=0.0.4'}

@app.route('/health')
def health():
    logger.info("Health check endpoint called")
    return jsonify({"status": "healthy"})

@app.route('/generate-logs')
def generate_logs_api():
    """API endpoint to generate random logs on demand"""
    num_logs = request.args.get('count', 5, type=int)

    for _ in range(min(num_logs, 20)):  # Limit to 20 logs max
        user_id = f"user_{random.randint(1, 100)}"
        request_id = f"req-{random.randint(10000, 99999)}"

        if random.random() < 0.7:  # 70% info logs
            logger.info(f"[{request_id}] API triggered log generation - User: {user_id}")
        elif random.random() < 0.9:  # 20% warning logs
            logger.warning(f"[{request_id}] High load detected - User: {user_id}")
        else:  # 10% error logs
            logger.error(f"[{request_id}] Simulated error - User: {user_id}")

    return jsonify({"message": f"Generated {num_logs} random logs"})

if __name__ == '__main__':
    logger.info(f"Starting OpenTelemetry Sample App in {aws_region}")
    # Make sure metrics are exposed on port 8080 to match the Prometheus annotations
    from werkzeug.serving import run_simple

    # Create a WSGI app that serves metrics on port 8080
    def metrics_app(environ, start_response):
        if environ['PATH_INFO'] == '/metrics':
            response = metrics_endpoint()
            start_response('200 OK', [('Content-Type', 'text/plain; version=0.0.4')])
            return [response[0].encode()]
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'Not Found']

    # Start metrics server in a separate thread
    import threading
    threading.Thread(target=lambda: run_simple('0.0.0.0', 8080, metrics_app, threaded=True), daemon=True).start()

    # Start main application
    app.run(host='0.0.0.0', port=8000)

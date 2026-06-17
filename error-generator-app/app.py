"""Error Generator App - generates various exceptions with OTel metrics."""
import time
import random
import threading
import logging
import traceback
from flask import Flask, jsonify
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("error-generator")

# Prometheus metrics
ERROR_COUNTER = Counter('error_generator_errors_total', 'Total errors generated', ['error_type', 'severity'])
REQUEST_COUNTER = Counter('error_generator_requests_total', 'Total HTTP requests', ['endpoint', 'status'])
REQUEST_LATENCY = Histogram('error_generator_request_duration_seconds', 'Request latency', ['endpoint'])

ERRORS = [
    ("DatabaseConnectionError", "Connection to postgres:5432 refused", "critical"),
    ("TimeoutError", "Request to payment-service timed out after 30s", "high"),
    ("OutOfMemoryError", "Java heap space exhausted", "critical"),
    ("NullPointerException", "Cannot invoke method on null object", "high"),
    ("AuthenticationError", "Token expired for user_id=4821", "medium"),
    ("RateLimitExceeded", "API rate limit 1000/min exceeded", "medium"),
    ("DiskFullError", "/var/log partition at 100%", "critical"),
    ("CertificateExpiredError", "TLS certificate expired 2 hours ago", "high"),
]

error_count = 0

def background_error_generator():
    """Generates periodic errors in the background."""
    global error_count
    while True:
        time.sleep(random.uniform(2, 6))
        error_name, error_msg, severity = random.choice(ERRORS)
        error_count += 1
        ERROR_COUNTER.labels(error_type=error_name, severity=severity).inc()
        logger.error(f"[ERROR-{error_count:05d}] {error_name}: {error_msg}")
        if random.random() < 0.3:
            try:
                raise Exception(f"{error_name}: {error_msg}")
            except Exception:
                logger.error(f"[EXCEPTION]\n{traceback.format_exc()}")

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route("/health")
def health():
    REQUEST_COUNTER.labels(endpoint="/health", status="200").inc()
    return jsonify({"status": "ok", "errors": error_count}), 200

@app.route("/")
def index():
    REQUEST_COUNTER.labels(endpoint="/", status="200").inc()
    return jsonify({"service": "error-generator", "total_errors": error_count})

@app.route("/generate-error")
def generate_error():
    """Manually trigger a random error."""
    global error_count
    error_name, error_msg, severity = random.choice(ERRORS)
    error_count += 1
    ERROR_COUNTER.labels(error_type=error_name, severity=severity).inc()
    REQUEST_COUNTER.labels(endpoint="/generate-error", status="500").inc()
    logger.error(f"[MANUAL-ERROR-{error_count:05d}] {error_name}: {error_msg}")
    return jsonify({"error": error_name, "message": error_msg, "severity": severity}), 500

if __name__ == "__main__":
    t = threading.Thread(target=background_error_generator, daemon=True)
    t.start()
    logger.info("Error Generator started - producing errors every 2-6 seconds")
    app.run(host="0.0.0.0", port=8080)

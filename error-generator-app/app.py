"""Error Generator App - generates various exceptions and errors for DevOps Agent testing."""
import time
import random
import threading
import logging
import traceback
from flask import Flask, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("error-generator")

# Simulated error scenarios
ERRORS = [
    ("DatabaseConnectionError", "Connection to postgres:5432 refused - max retries exceeded"),
    ("TimeoutError", "Request to payment-service timed out after 30s"),
    ("OutOfMemoryError", "Java heap space exhausted - allocated 512MB, requested 1GB"),
    ("NullPointerException", "Cannot invoke method on null object at OrderService.processOrder()"),
    ("AuthenticationError", "Token expired for user_id=4821, session invalidated"),
    ("RateLimitExceeded", "API rate limit 1000/min exceeded for client app-frontend"),
    ("DiskFullError", "/var/log partition at 100% - cannot write audit logs"),
    ("CertificateExpiredError", "TLS certificate for api.internal.svc expired 2 hours ago"),
]

error_count = 0
crash_mode = False

def background_error_generator():
    """Generates periodic errors and exceptions in the background."""
    global error_count, crash_mode
    while True:
        time.sleep(random.uniform(2, 8))
        error_name, error_msg = random.choice(ERRORS)
        error_count += 1
        logger.error(f"[ERROR-{error_count:05d}] {error_name}: {error_msg}")
        
        # Occasionally generate stack traces
        if random.random() < 0.3:
            try:
                raise Exception(f"{error_name}: {error_msg}")
            except Exception:
                logger.error(f"[EXCEPTION-{error_count:05d}] Unhandled exception:\n{traceback.format_exc()}")
        
        # Simulate OOMKill-like memory spike every ~60 errors
        if crash_mode and error_count % 60 == 0:
            logger.critical(f"FATAL: Process terminating due to {error_name}")
            time.sleep(1)
            raise SystemExit(1)

@app.route("/health")
def health():
    if error_count > 100 and random.random() < 0.3:
        logger.warning("Health check degraded - high error rate detected")
        return jsonify({"status": "degraded", "errors": error_count}), 503
    return jsonify({"status": "ok", "errors": error_count}), 200

@app.route("/")
def index():
    return jsonify({
        "service": "error-generator",
        "purpose": "Generates errors for DevOps Agent investigation testing",
        "total_errors": error_count,
        "crash_mode": crash_mode
    })

@app.route("/crash")
def trigger_crash():
    """Endpoint to trigger a crash for testing."""
    global crash_mode
    crash_mode = True
    logger.critical("CRASH MODE ACTIVATED - process will terminate on next error cycle")
    return jsonify({"status": "crash scheduled"}), 200

@app.route("/oom")
def simulate_oom():
    """Simulate memory pressure."""
    logger.error("FATAL: Container OOMKilled - memory limit 256Mi exceeded (current: 312Mi)")
    data = []
    for i in range(50):
        data.append("X" * 1024 * 1024)  # ~50MB
        logger.warning(f"Memory allocation #{i}: {len(data)}MB consumed")
    return jsonify({"status": "oom triggered"}), 500

if __name__ == "__main__":
    # Start background error generator
    t = threading.Thread(target=background_error_generator, daemon=True)
    t.start()
    logger.info("Error Generator started - producing errors every 2-8 seconds")
    app.run(host="0.0.0.0", port=8080)

import os
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)

START_TIME = time.time()

# Chaos state
chaos_state = {
    "mode": None,
    "duration": None,
    "rate": None,
    "timer": None
}

MODE = os.environ.get("MODE", "stable")
VERSION = os.environ.get("APP_VERSION", "1.0.0")
PORT = int(os.environ.get("APP_PORT", 3000))

# ── Prometheus metrics ────────────────────────────────────────────────────────

# Total request counter — labelled by method, path, and status code
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"]
)

# Request duration histogram — tracks latency distribution
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Uptime gauge — seconds since server started
app_uptime_seconds = Gauge(
    "app_uptime_seconds",
    "Application uptime in seconds"
)

# Mode gauge — 0=stable, 1=canary
app_mode = Gauge(
    "app_mode",
    "Current deployment mode (0=stable, 1=canary)"
)

# Chaos state gauge — 0=none, 1=slow, 2=error
chaos_active = Gauge(
    "chaos_active",
    "Active chaos mode (0=none, 1=slow, 2=error)"
)


def update_gauges():
    """Update gauge metrics with current state."""
    app_uptime_seconds.set(time.time() - START_TIME)
    app_mode.set(1 if MODE == "canary" else 0)
    chaos_map = {"slow": 1, "error": 2}
    chaos_active.set(chaos_map.get(chaos_state["mode"], 0))


# ── Hooks ─────────────────────────────────────────────────────────────────────

@app.before_request
def before_request():
    """Record request start time and apply chaos if active."""
    request._start_time = time.time()

    if request.path in ("/metrics", "/chaos"):
        return

    if chaos_state["mode"] == "slow" and chaos_state["duration"]:
        time.sleep(chaos_state["duration"])
    elif chaos_state["mode"] == "error":
        if random.random() < (chaos_state["rate"] or 0.5):
            return jsonify({"error": "Chaos-induced error"}), 500


@app.after_request
def after_request(response):
    """Record metrics and attach headers after each request."""
    duration = time.time() - getattr(request, "_start_time", time.time())
    path = request.path
    method = request.method
    status = str(response.status_code)

    # Skip recording metrics for the /metrics endpoint itself
    if path != "/metrics":
        http_requests_total.labels(method=method, path=path, status_code=status).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)

    update_gauges()

    if MODE == "canary":
        response.headers["X-Mode"] = "canary"

    return response


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Welcome endpoint — returns mode, version, and current UTC timestamp."""
    return jsonify({
        "message": "Welcome to SwiftDeploy API",
        "mode": MODE,
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route("/healthz")
def healthz():
    """Liveness check — returns status and process uptime in seconds."""
    return jsonify({
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 2)
    })


@app.route("/metrics")
def metrics():
    """Expose Prometheus metrics in text format."""
    update_gauges()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/chaos", methods=["POST"])
def chaos():
    """
    Simulates degraded behaviour. Canary mode only.
    Accepts: { "mode": "slow", "duration": N }
             { "mode": "error", "rate": 0.5 }
             { "mode": "recover" }
    """
    if MODE != "canary":
        return jsonify({"error": "Chaos endpoint only available in canary mode"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    mode = data.get("mode")

    # Cancel any running recovery timer before applying new chaos
    if chaos_state["timer"]:
        chaos_state["timer"].cancel()
        chaos_state["timer"] = None

    if mode == "slow":
        duration = data.get("duration", 5)
        chaos_state["mode"] = "slow"
        chaos_state["duration"] = duration

        # Auto-recover after duration using a background thread
        def recover():
            chaos_state["mode"] = None
            chaos_state["duration"] = None
        t = threading.Timer(duration, recover)
        t.start()
        chaos_state["timer"] = t

        time.sleep(duration)
        return jsonify({"message": f"Slow mode activated for {duration}s"})

    elif mode == "error":
        rate = data.get("rate", 0.5)
        chaos_state["mode"] = "error"
        chaos_state["rate"] = rate
        return jsonify({"message": f"Error mode activated at {rate} rate"})

    elif mode == "recover":
        chaos_state.update({"mode": None, "duration": None, "rate": None})
        return jsonify({"message": "Chaos recovered"})

    return jsonify({"error": "Invalid chaos mode. Use: slow, error, recover"}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

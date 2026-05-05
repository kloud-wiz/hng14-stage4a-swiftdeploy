import os
import time
import random
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify

app = Flask(__name__)

START_TIME = time.time()

# Holds active chaos configuration — shared across requests
chaos_state = {
    "mode": None,
    "duration": None,
    "rate": None,
    "timer": None
}

MODE = os.environ.get("MODE", "stable")
VERSION = os.environ.get("APP_VERSION", "1.0.0")
PORT = int(os.environ.get("APP_PORT", 3000))


@app.after_request
def after_request(response):
    """Attach X-Mode header on every response in canary mode."""
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    return response


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


@app.before_request
def apply_chaos():
    """Apply active chaos behaviour before each request is handled."""
    if request.path == "/chaos":
        return

    if chaos_state["mode"] == "slow" and chaos_state["duration"]:
        time.sleep(chaos_state["duration"])
    elif chaos_state["mode"] == "error":
        if random.random() < (chaos_state["rate"] or 0.5):
            return jsonify({"error": "Chaos-induced error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

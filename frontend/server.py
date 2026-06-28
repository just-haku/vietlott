"""
SOUL · Vietlott Deterministic Universe — Web Dashboard Server

Flask backend serving the monitoring dashboard, REST API, and LLM endpoints.
Streams AI responses via Server-Sent Events (SSE).
"""

import json
import time
import random
import string
import threading
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty

from flask import Flask, request, jsonify, Response, send_from_directory

# ---------------------------------------------------------------------------
# Project paths (cross-platform)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
CONFIG_PATH = PROJECT_ROOT / "config.json"
DATASET_PATH = PROJECT_ROOT / "dataset_raw.jsonl"

# ---------------------------------------------------------------------------
# Try importing core modules (graceful fallback to mocks)
# ---------------------------------------------------------------------------
_ENGINE = None
_LLM_CLIENT = None
_ANALYZER = None
_DATASET = None
_BRAIN_MANAGER = None

try:
    from core.analyzer import Analyzer
    _ANALYZER = Analyzer()
except ImportError:
    _ANALYZER = None

try:
    from core.dataset import DatasetManager
    features_jsonl_path = PROJECT_ROOT / "data" / "features.jsonl"
    if features_jsonl_path.exists():
        _DATASET = DatasetManager(str(features_jsonl_path))
    else:
        _DATASET = None
except (ImportError, Exception):
    _DATASET = None

try:
    from core.brain import BrainManager
    brains_dir = PROJECT_ROOT / "brains"
    _BRAIN_MANAGER = BrainManager(str(brains_dir))
except ImportError:
    _BRAIN_MANAGER = None

try:
    from autoresearch.engine import ResearchEngine
except ImportError:
    ResearchEngine = None

try:
    from autoresearch.llm_client import LLMClient
except ImportError:
    LLMClient = None

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_start_time = time.time()
_research_thread = None
_research_running = False
_experiment_count = 0
_current_experiment = None
_sse_queue = Queue(maxsize=500)
_experiments_log = []
_lock = threading.Lock()


def _load_config():
    """Load config from disk or return defaults."""
    defaults = {
        "provider": "google",
        "model": "gemma-4-27b-it",
        "api_key": "",
        "temperature": 0.7,
        "train_split": 0.85,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except (json.JSONDecodeError, IOError):
            pass
    return defaults


def _save_config(cfg):
    """Persist config to disk."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _mask_key(key):
    """Mask an API key, showing first 4 and last 4 characters."""
    if not key or len(key) <= 8:
        return "*" * len(key) if key else ""
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


# ---------------------------------------------------------------------------
# Mock data generators (used when core modules aren't available)
# ---------------------------------------------------------------------------
def _mock_brains():
    """Generate 5 mock brains for the leaderboard."""
    brains = []
    base_scores = [0.312, 0.387, 0.445, 0.523, 0.619]
    descriptions = [
        "Digital-root recurrence on B with lag-3 differencing",
        "Composite modular arithmetic over A+C with periodicity 7",
        "Fibonacci-based offset prediction on E sequence",
        "Prime sieve filter applied to digital roots F, H",
        "Cyclical shift register on tens-digit sums I, K",
    ]
    for i, (score, desc) in enumerate(zip(base_scores, descriptions)):
        brain_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        brains.append({
            "rank": i + 1,
            "id": f"brain-{brain_id}",
            "score": round(score + random.uniform(-0.02, 0.02), 4),
            "formulas": [
                {"name": f"f{j}", "expression": f"(x[n-{j+1}] + x[n-{j+2}]) mod {j+3}"}
                for j in range(random.randint(1, 3))
            ],
            "description": desc,
            "created_at": datetime(2026, 6, 28 - i, 10 + i, 30, 0,
                                   tzinfo=timezone.utc).isoformat(),
        })
    return brains


def _mock_experiments(count=20):
    """Generate mock experiment entries."""
    experiments = []
    base_train = 0.7
    base_test = 0.65
    for i in range(count):
        improved = random.random() < 0.35
        train_score = round(base_train + random.uniform(-0.15, 0.15), 4)
        test_score = round(base_test + random.uniform(-0.15, 0.15), 4)
        if improved:
            base_train = min(base_train + 0.005, 0.95)
            base_test = min(base_test + 0.003, 0.90)
        experiments.append({
            "id": f"exp-{i+1:04d}",
            "timestamp": datetime(2026, 6, 28, 8, i * 3, 0,
                                   tzinfo=timezone.utc).isoformat(),
            "description": f"Iteration {i+1}: {'improved' if improved else 'no improvement'} "
                           f"— exploring {'digital root' if i % 3 == 0 else 'modular'} "
                           f"{'lag' if i % 2 == 0 else 'cycle'} formula",
            "train_score": train_score,
            "test_score": test_score,
            "status": "kept" if improved else "discarded",
        })
    return experiments


def _mock_features(count=50):
    """Generate mock feature data for charts."""
    features = []
    for i in range(count):
        main_nums = sorted(random.sample(range(1, 46), 6))
        special = random.randint(1, 45)
        a = sum(main_nums)
        b = _digital_root(a)
        c = a + special
        d = _digital_root(c)
        e = sum(n // 10 for n in main_nums)
        f = _digital_root(e)
        g = sum(n % 10 for n in main_nums)
        h = _digital_root(g)
        i_val = e + special // 10
        j = _digital_root(i_val)
        k = g + special % 10
        l = _digital_root(k)
        features.append({
            "draw_id": f"{i+1:05d}",
            "date": f"2024-{(i % 12)+1:02d}-{(i % 28)+1:02d}",
            "A": a, "B": b, "C": c, "D": d,
            "E": e, "F": f, "G": g, "H": h,
            "I": i_val, "J": j, "K": k, "L": l,
            "M1_ew": [((n % 10) * 10 if n % 10 != 0 else 100) for n in main_nums + [special]],
        })
    return features


def _digital_root(n):
    """Compute the single-digit digital root of n."""
    if n == 0:
        return 0
    return 1 + (n - 1) % 9


def _mock_feature_stats(features):
    """Compute summary statistics for mock features."""
    if not features:
        return {}
    stats = {}
    for key in "ABCDEFGHIJKL":
        values = [f[key] for f in features]
        sorted_v = sorted(values)
        n = len(values)
        mean = sum(values) / n
        median = sorted_v[n // 2] if n % 2 == 1 else (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2
        variance = sum((v - mean) ** 2 for v in values) / n
        std = variance ** 0.5
        stats[key] = {
            "mean": round(mean, 2),
            "median": round(median, 2),
            "std": round(std, 2),
            "min": min(values),
            "max": max(values),
            "count": n,
        }
    return stats


# Pre-generate mock data
_mock_brains_data = _mock_brains()
_mock_experiments_data = _mock_experiments()
_mock_features_data = _mock_features()
_mock_stats_data = _mock_feature_stats(_mock_features_data)

# ---------------------------------------------------------------------------
# Research engine background thread
# ---------------------------------------------------------------------------
def _research_loop():
    """Run the auto-research loop in a background thread."""
    global _research_running, _experiment_count, _current_experiment

    config = _load_config()

    # Try to use real engine
    if ResearchEngine and LLMClient:
        try:
            from core.dataset import DatasetManager
            from core.brain import BrainManager

            features_path = PROJECT_ROOT / "data" / "features.jsonl"
            brains_dir = PROJECT_ROOT / "brains"

            dataset = DatasetManager(str(features_path), train_ratio=config.get("train_split", 0.85))
            brain_manager = BrainManager(str(brains_dir))

            llm = LLMClient(
                provider=config["provider"],
                api_key=config["api_key"],
                model=config["model"],
                temperature=config["temperature"],
            )
            engine = ResearchEngine(
                dataset=dataset,
                brain_manager=brain_manager,
                llm_client=llm,
                config={"temperature": config["temperature"]}
            )
            while _research_running:
                result = engine.run_single_experiment()
                status_val = "improved" if result.get("improved") else "discarded"
                ui_result = {
                    "id": result.get("experiment_id", f"exp-{_experiment_count:04d}"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "description": result.get("description", ""),
                    "train_score": result.get("train_score", 0.0),
                    "test_score": result.get("test_score", 0.0),
                    "status": status_val,
                    "improved": result.get("improved", False)
                }
                with _lock:
                    _experiment_count += 1
                    _current_experiment = ui_result
                    _experiments_log.append(ui_result)
                _sse_queue.put(json.dumps({
                    "type": "experiment_complete",
                    "data": ui_result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
                time.sleep(1)
            return
        except Exception as e:
            _sse_queue.put(json.dumps({
                "type": "error",
                "data": {"message": f"Engine error: {str(e)}"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

    # Mock research loop
    while _research_running:
        time.sleep(random.uniform(2, 5))
        if not _research_running:
            break
        with _lock:
            _experiment_count += 1
            improved = random.random() < 0.3
            result = {
                "id": f"exp-{_experiment_count:04d}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": f"Mock iteration {_experiment_count}",
                "train_score": round(random.uniform(0.3, 0.8), 4),
                "test_score": round(random.uniform(0.3, 0.7), 4),
                "status": "improved" if improved else "discarded",
                "improved": improved
            }
            _current_experiment = result
            _experiments_log.append(result)

        _sse_queue.put(json.dumps({
            "type": "experiment_complete",
            "data": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        _sse_queue.put(json.dumps({
            "type": "ai_response",
            "data": {
                "provider": config.get("provider", "mock"),
                "model": config.get("model", "mock"),
                "prompt": f"Generate formula for iteration {_experiment_count}",
                "response": f"Analyzing feature correlations... "
                            f"Proposed formula: f(n) = (x[n-1] + x[n-2]) mod {random.randint(3,9)}\n"
                            f"```json\n{json.dumps({'formula': f'(x[n-1] + x[n-2]) mod {random.randint(3,9)}', 'score': round(random.uniform(0.3, 0.7), 4)}, indent=2)}\n```",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))


# ---------------------------------------------------------------------------
# Routes — Static & Dashboard
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Serve the dashboard HTML."""
    return send_from_directory(str(STATIC_DIR), "index.html")


@app.after_request
def add_cors_headers(response):
    """Add CORS headers to all responses."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------
@app.route("/api/status")
def api_status():
    """Return current engine status."""
    global _research_running, _experiment_count, _current_experiment
    uptime = int(time.time() - _start_time)
    return jsonify({
        "running": _research_running,
        "experiment_count": _experiment_count,
        "current_experiment": _current_experiment,
        "uptime": uptime,
    })


@app.route("/api/brains")
def api_brains():
    """Return top-5 leaderboard."""
    if _BRAIN_MANAGER:
        try:
            leaderboard = _BRAIN_MANAGER.get_leaderboard()
            formatted = []
            for i, brain in enumerate(leaderboard[:5]):
                formatted.append({
                    "rank": i + 1,
                    "id": brain.id,
                    "score": brain.test_entropy_score,
                    "formulas": brain.formulas,
                    "description": brain.description,
                    "created_at": brain.created_at
                })
            return jsonify(formatted)
        except Exception as e:
            print(f"Error serving leaderboard: {e}")
            pass
    return jsonify(_mock_brains_data)


@app.route("/api/experiments")
def api_experiments():
    """Return experiment history."""
    if _experiments_log:
        return jsonify(_experiments_log[-100:])  # Last 100
    return jsonify(_mock_experiments_data)


@app.route("/api/features")
def api_features():
    """Return processed feature data."""
    if _DATASET and getattr(_DATASET, "_features", None):
        return jsonify(_DATASET._features)
    return jsonify(_mock_features_data)


@app.route("/api/features/stats")
def api_features_stats():
    """Return summary statistics for features."""
    if _DATASET and getattr(_DATASET, "_features", None):
        return jsonify(_mock_feature_stats(_DATASET._features))
    return jsonify(_mock_stats_data)


@app.route("/api/ai-responses")
def api_ai_responses():
    """SSE stream of AI responses."""
    def generate():
        while True:
            try:
                message = _sse_queue.get(timeout=30)
                yield f"data: {message}\n\n"
            except Empty:
                # Send keepalive comment
                yield ": keepalive\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Return current configuration (keys masked)."""
    config = _load_config()
    config["api_key"] = _mask_key(config.get("api_key", ""))
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_set_config():
    """Update configuration."""
    data = request.get_json(force=True)
    config = _load_config()

    # Update only provided fields
    for key in ("provider", "model", "temperature", "train_split"):
        if key in data:
            config[key] = data[key]

    # Only update API key if a new one is provided (not masked)
    if "api_key" in data and "*" not in data["api_key"]:
        config["api_key"] = data["api_key"]

    _save_config(config)
    return jsonify({"status": "ok", "message": "Configuration saved"})


@app.route("/api/research/start", methods=["POST"])
def api_research_start():
    """Start the auto-research loop."""
    global _research_thread, _research_running

    if _research_running:
        return jsonify({"status": "already_running"})

    _research_running = True
    _research_thread = threading.Thread(target=_research_loop, daemon=True)
    _research_thread.start()

    _sse_queue.put(json.dumps({
        "type": "status",
        "data": {"running": True},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    return jsonify({"status": "started"})


@app.route("/api/research/stop", methods=["POST"])
def api_research_stop():
    """Stop the auto-research loop."""
    global _research_running

    _research_running = False

    _sse_queue.put(json.dumps({
        "type": "status",
        "data": {"running": False},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    return jsonify({"status": "stopped"})


@app.route("/api/llm/generate", methods=["POST"])
def api_llm_generate():
    """Direct LLM endpoint for testing."""
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")
    system_prompt = data.get("system_prompt", "")
    provider = data.get("provider")
    model = data.get("model")

    config = _load_config()
    provider = provider or config.get("provider", "google")
    model = model or config.get("model", "gemma-4-27b-it")

    # Try real LLM client
    if LLMClient:
        try:
            llm = LLMClient(
                provider=provider,
                api_key=config.get("api_key", ""),
                model=model,
                temperature=config.get("temperature", 0.7),
            )
            response_text = llm.generate(prompt=prompt, system_prompt=system_prompt)

            result = {
                "provider": provider,
                "model": model,
                "prompt": prompt,
                "response": response_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Also push to SSE
            _sse_queue.put(json.dumps({"type": "ai_response", "data": result}))
            return jsonify(result)

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Mock response
    mock_response = (
        f"[Mock LLM — {provider}/{model}]\n\n"
        f"Analyzing prompt: \"{prompt[:80]}...\"\n\n"
        f"Based on the deterministic universe hypothesis, I propose the following formula:\n\n"
        f"```json\n"
        f'{{\n  "formula": "(x[n-1] * 3 + x[n-2]) mod 9 + 1",\n'
        f'  "target_feature": "B",\n'
        f'  "confidence": 0.{random.randint(30, 85)}\n}}\n'
        f"```\n\n"
        f"This leverages the digital root periodicity observed in feature B."
    )

    result = {
        "provider": provider,
        "model": model,
        "prompt": prompt,
        "response": mock_response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    _sse_queue.put(json.dumps({"type": "ai_response", "data": result}))
    return jsonify(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def create_app(project_root=None):
    """Flask application factory (returns global app)."""
    return app


def main(host="0.0.0.0", port=5000, debug=False):
    """Start the dashboard server."""
    print(f"\n  ✦ SOUL · Vietlott Deterministic Universe")
    print(f"  ✦ Dashboard: http://localhost:{port}")
    print(f"  ✦ API:       http://localhost:{port}/api/status\n")
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main(debug=True)

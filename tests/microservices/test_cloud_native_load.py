import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "cloud_native_load.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cloud_native_load", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_uses_nearest_rank_p95_and_counts_errors():
    module = load_module()
    summary = module.summarize(
        latencies_ms=list(range(1, 101)),
        errors=5,
        elapsed_seconds=2.0,
        concurrency=8,
        status_codes={200: 95, 503: 5},
    )
    assert summary["requests"] == 100
    assert summary["successes"] == 95
    assert summary["errors"] == 5
    assert summary["throughput_rps"] == 50.0
    assert summary["average_ms"] == 50.5
    assert summary["p95_ms"] == 95.0
    assert summary["error_rate_percent"] == 5.0
    assert summary["concurrency"] == 8


def test_load_posts_streamhub_login_json(tmp_path):
    bodies: list[dict[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            bodies.append(json.loads(self.rfile.read(length)))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"token":"ok"}')

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        module = load_module()
        output = tmp_path / "load.json"
        result = module.run_load(
            url=f"http://127.0.0.1:{server.server_port}/api/auth/login",
            username="lab-user",
            password="lab-password",
            concurrency=2,
            duration_seconds=0.2,
            timeout_seconds=2.0,
        )
        output.write_text(json.dumps(result), encoding="utf-8")
    finally:
        server.shutdown()
        server.server_close()
    assert result["requests"] > 0
    assert result["errors"] == 0
    assert bodies
    assert bodies[0] == {"account": "lab-user", "password": "lab-password"}

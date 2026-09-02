import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "performance_load.py"


def load_module():
    spec = importlib.util.spec_from_file_location("performance_load", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_http_summary_uses_nearest_rank_p95():
    module = load_module()
    result = module.summarize_http(
        list(range(1, 101)),
        {200: 98, 503: 2},
        elapsed_seconds=2.0,
        concurrency=8,
    )
    assert result == {
        "concurrency": 8,
        "duration_seconds": 2.0,
        "requests": 100,
        "successes": 98,
        "errors": 2,
        "throughput_rps": 50.0,
        "average_ms": 50.5,
        "p95_ms": 95.0,
        "error_rate_percent": 2.0,
        "status_codes": {200: 98, 503: 2},
    }


def test_memory_units_are_normalized_to_bytes():
    module = load_module()
    assert module.parse_bytes("512B") == 512
    assert module.parse_bytes("1.5KiB") == 1536
    assert module.parse_bytes("12.5MiB") == 13_107_200
    assert module.parse_bytes("1GiB") == 1_073_741_824


def test_resource_summary_sums_containers_per_sample_before_aggregation():
    module = load_module()
    rows = [
        {"sample": 1, "group": "app", "cpu_percent": 10.0, "memory_bytes": 100},
        {"sample": 1, "group": "app", "cpu_percent": 20.0, "memory_bytes": 200},
        {"sample": 1, "group": "infra", "cpu_percent": 5.0, "memory_bytes": 500},
        {"sample": 2, "group": "app", "cpu_percent": 30.0, "memory_bytes": 300},
        {"sample": 2, "group": "app", "cpu_percent": 40.0, "memory_bytes": 400},
        {"sample": 2, "group": "infra", "cpu_percent": 7.0, "memory_bytes": 700},
    ]
    summary = module.summarize_resources(rows)
    assert summary["samples"] == 2
    assert summary["app_cpu_mean_percent"] == 50.0
    assert summary["app_cpu_peak_percent"] == 70.0
    assert summary["app_memory_mean_bytes"] == 500
    assert summary["app_memory_peak_bytes"] == 700
    assert summary["infra_cpu_mean_percent"] == 6.0
    assert summary["infra_memory_peak_bytes"] == 700


def test_load_sends_configured_request_and_counts_success():
    module = load_module()
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            seen.append(json.loads(body))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{}')

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = module.run_http_load(
            url=f"http://127.0.0.1:{server.server_port}/api/auth/login",
            method="POST",
            body=json.dumps({"account": "user", "password": "user123"}).encode(),
            headers={"Content-Type": "application/json"},
            concurrency=2,
            duration_seconds=0.2,
            timeout_seconds=2.0,
        )
    finally:
        server.shutdown()
        server.server_close()
    assert result["requests"] > 0
    assert result["errors"] == 0
    assert seen[0] == {"account": "user", "password": "user123"}


def test_performance_compose_is_isolated_and_resource_bounded():
    compose = yaml.safe_load((ROOT / "docker-compose.performance.yml").read_text(encoding="utf-8"))
    assert compose["name"] == "streamhub-perf"
    services = compose["services"]
    assert set(services) == {
        "postgres-perf",
        "minio-perf",
        "monolith",
        "user-service",
        "content-service",
        "social-service",
        "gateway",
    }
    assert "/var/lib/postgresql/data" in services["postgres-perf"]["tmpfs"]
    assert services["monolith"]["cpus"] == 0.5
    assert services["monolith"]["mem_limit"] == "512m"
    for service in ("user-service", "content-service", "social-service"):
        assert services[service]["cpus"] == 0.5
        assert services[service]["mem_limit"] == "512m"
    assert services["gateway"]["cpus"] == 0.25
    assert "volumes" not in compose


def test_runner_requires_three_rounds_same_data_and_raw_results():
    runner = (ROOT / "scripts" / "run-performance-comparison.ps1").read_text(encoding="utf-8")
    for required in (
        "[int]$Runs = 3",
        "migrate_monolith_data.py",
        "dataset-manifest.json",
        "/api/categories",
        "/api/videos?sort=latest&page=1&page_size=20",
        "/api/auth/login",
        "performance_load.py",
        "docker stats",
        "raw",
        "summary.json",
        "monolith",
        "microservices",
        "--no-interpolate",
    ):
        assert required in runner
    assert "down -v" not in runner
    assert "docker volume rm" not in runner


def test_submitted_performance_evidence_matches_reported_boundary():
    evidence = ROOT / "docs" / "microservices" / "evidence" / "performance"
    main = json.loads(
        (evidence / "20260831-114658527-main" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    dataset = json.loads(
        (evidence / "20260831-114658527-main" / "dataset-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    overload = json.loads(
        (evidence / "20260831-113157084-overload" / "summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert main["result"] == "PASS"
    assert len(main["raw_runs"]) == 18
    assert all(item["runs"] == 3 for item in main["aggregates"])
    assert all(item["http"]["error_rate_percent"] == 0 for item in main["raw_runs"])
    assert all(dataset["tables"][table]["equal"] for table in ("users", "categories", "videos"))
    overloaded = next(
        item
        for item in overload["aggregates"]
        if item["endpoint"] == "videos-latest" and item["version"] == "microservices"
    )
    assert overloaded["runs"] == 3
    assert overloaded["error_rate_percent"]["mean"] == 100.0
    report = (ROOT / "docs" / "microservices" / "performance-comparison.md").read_text(
        encoding="utf-8"
    )
    assert "本次没有测出“微服务性能提升”" in report

#!/usr/bin/env python3
import argparse
import csv
import json
import math
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread


UNIT_BYTES = {
    "B": 1,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
}


def parse_bytes(value: str) -> int:
    value = value.strip()
    for unit in sorted(UNIT_BYTES, key=len, reverse=True):
        if value.endswith(unit):
            number = float(value[: -len(unit)])
            return round(number * UNIT_BYTES[unit])
    raise ValueError(f"unsupported memory value: {value}")


def summarize_http(
    latencies_ms: list[float],
    status_codes: dict[int, int],
    elapsed_seconds: float,
    concurrency: int,
) -> dict:
    ordered = sorted(latencies_ms)
    requests = len(ordered)
    errors = sum(
        count for status, count in status_codes.items() if not 200 <= status < 300
    )
    p95_index = max(0, math.ceil(requests * 0.95) - 1)
    return {
        "concurrency": concurrency,
        "duration_seconds": round(elapsed_seconds, 3),
        "requests": requests,
        "successes": requests - errors,
        "errors": errors,
        "throughput_rps": round(requests / elapsed_seconds, 3) if elapsed_seconds else 0.0,
        "average_ms": round(sum(ordered) / requests, 3) if requests else 0.0,
        "p95_ms": round(ordered[p95_index], 3) if requests else 0.0,
        "error_rate_percent": round(errors * 100 / requests, 3) if requests else 0.0,
        "status_codes": dict(sorted(status_codes.items())),
    }


def run_http_load(
    url: str,
    method: str,
    body: bytes | None,
    headers: dict[str, str],
    concurrency: int,
    duration_seconds: float,
    timeout_seconds: float,
) -> dict:
    if concurrency < 1 or duration_seconds <= 0 or timeout_seconds <= 0:
        raise ValueError("concurrency, duration and timeout must be positive")
    latencies: list[float] = []
    status_codes: Counter[int] = Counter()
    lock = Lock()
    start = time.perf_counter()
    deadline = start + duration_seconds

    def worker() -> None:
        while time.perf_counter() < deadline:
            request_start = time.perf_counter()
            status = 0
            try:
                request = urllib.request.Request(
                    url, data=body, headers=headers, method=method
                )
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    status = response.status
                    response.read()
            except urllib.error.HTTPError as error:
                status = error.code
                error.read()
            except (OSError, TimeoutError):
                status = 0
            latency = (time.perf_counter() - request_start) * 1000
            with lock:
                latencies.append(latency)
                status_codes[status] += 1

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker) for _ in range(concurrency)]
        for future in futures:
            future.result()

    elapsed = time.perf_counter() - start
    return summarize_http(latencies, dict(status_codes), elapsed, concurrency)


def summarize_resources(rows: list[dict]) -> dict:
    totals: dict[tuple[int, str], dict[str, float]] = defaultdict(
        lambda: {"cpu": 0.0, "memory": 0.0}
    )
    for row in rows:
        key = (int(row["sample"]), str(row["group"]))
        totals[key]["cpu"] += float(row["cpu_percent"])
        totals[key]["memory"] += int(row["memory_bytes"])

    sample_ids = sorted({sample for sample, _group in totals})
    summary = {"samples": len(sample_ids)}
    for group in ("app", "infra"):
        cpu = [totals[(sample, group)]["cpu"] for sample in sample_ids]
        memory = [totals[(sample, group)]["memory"] for sample in sample_ids]
        summary[f"{group}_cpu_mean_percent"] = (
            round(statistics.mean(cpu), 3) if cpu else 0.0
        )
        summary[f"{group}_cpu_peak_percent"] = round(max(cpu), 3) if cpu else 0.0
        summary[f"{group}_memory_mean_bytes"] = (
            round(statistics.mean(memory)) if memory else 0
        )
        summary[f"{group}_memory_peak_bytes"] = max(memory) if memory else 0
    return summary


def capture_docker_stats(
    groups: dict[str, str],
    stop: Event,
    rows: list[dict],
    errors: list[str],
    interval_seconds: float = 1.0,
) -> None:
    sample = 0
    containers = list(groups)
    while not stop.is_set():
        sample += 1
        started = time.perf_counter()
        command = [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            *containers,
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            errors.append(completed.stderr.strip() or "docker stats failed")
            return
        parsed = [json.loads(line) for line in completed.stdout.splitlines() if line]
        names = {item["Name"] for item in parsed}
        if names != set(containers):
            errors.append(f"docker stats container mismatch: {sorted(names)}")
            return
        timestamp = datetime.now(timezone.utc).isoformat()
        for item in parsed:
            memory_used = item["MemUsage"].split("/", 1)[0].strip()
            rows.append(
                {
                    "timestamp_utc": timestamp,
                    "sample": sample,
                    "group": groups[item["Name"]],
                    "container": item["Name"],
                    "cpu_percent": float(item["CPUPerc"].rstrip("%")),
                    "memory_bytes": parse_bytes(memory_used),
                }
            )
        remaining = interval_seconds - (time.perf_counter() - started)
        if remaining > 0:
            stop.wait(remaining)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "timestamp_utc",
        "sample",
        "group",
        "container",
        "cpu_percent",
        "memory_bytes",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="StreamHub controlled HTTP benchmark")
    parser.add_argument("--url", required=True)
    parser.add_argument("--method", choices=("GET", "POST"), default="GET")
    parser.add_argument("--body-json")
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--app-container", action="append", default=[])
    parser.add_argument("--infra-container", action="append", default=[])
    parser.add_argument("--version", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--run", type=int, required=True)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()

    body = args.body_json.encode() if args.body_json is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if args.warmup > 0:
        run_http_load(
            args.url,
            args.method,
            body,
            headers,
            args.concurrency,
            args.warmup,
            args.timeout,
        )

    groups = {name: "app" for name in args.app_container}
    groups.update({name: "infra" for name in args.infra_container})
    if not groups:
        raise ValueError("at least one Docker container is required")

    resource_rows: list[dict] = []
    sampler_errors: list[str] = []
    stop = Event()
    sampler = Thread(
        target=capture_docker_stats,
        args=(groups, stop, resource_rows, sampler_errors),
        daemon=True,
    )
    sampler.start()
    http = run_http_load(
        args.url,
        args.method,
        body,
        headers,
        args.concurrency,
        args.duration,
        args.timeout,
    )
    stop.set()
    sampler.join(timeout=10)
    if sampler.is_alive():
        raise RuntimeError("docker stats sampler did not stop")
    if sampler_errors:
        raise RuntimeError(sampler_errors[0])
    if not resource_rows:
        raise RuntimeError("docker stats produced no samples")

    result = {
        "version": args.version,
        "endpoint": args.endpoint,
        "run": args.run,
        "url": args.url,
        "method": args.method,
        "warmup_seconds": args.warmup,
        "http": http,
        "resources": summarize_resources(resource_rows),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(args.csv, resource_rows)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if http["requests"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

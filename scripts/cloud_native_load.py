#!/usr/bin/env python3
import argparse
import json
import math
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock


def summarize(
    latencies_ms: list[float],
    errors: int,
    elapsed_seconds: float,
    concurrency: int,
    status_codes: dict[int, int],
) -> dict:
    ordered = sorted(latencies_ms)
    requests = len(ordered)
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


def run_load(
    url: str,
    username: str,
    password: str,
    concurrency: int,
    duration_seconds: float,
    timeout_seconds: float,
) -> dict:
    if concurrency < 1 or duration_seconds <= 0 or timeout_seconds <= 0:
        raise ValueError("concurrency, duration and timeout must be positive")
    payload = json.dumps({"account": username, "password": password}).encode()
    headers = {"Content-Type": "application/json"}
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
                request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    status = response.status
                    response.read()
            except urllib.error.HTTPError as error:
                status = error.code
                error.read()
            except (OSError, TimeoutError):
                status = 0
            elapsed_ms = (time.perf_counter() - request_start) * 1000
            with lock:
                latencies.append(elapsed_ms)
                status_codes[status] += 1

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker) for _ in range(concurrency)]
        for future in futures:
            future.result()

    elapsed = time.perf_counter() - start
    errors = sum(count for status, count in status_codes.items() if not 200 <= status < 300)
    return summarize(latencies, errors, elapsed, concurrency, dict(status_codes))


def main() -> int:
    parser = argparse.ArgumentParser(description="Fixed-duration StreamHub login load")
    parser.add_argument("--url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--duration", type=float, default=90.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    result = run_load(
        args.url,
        args.username,
        args.password,
        args.concurrency,
        args.duration,
        args.timeout,
    )
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["requests"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

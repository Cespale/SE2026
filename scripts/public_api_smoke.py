#!/usr/bin/env python3
"""Probe every catalogued public HTTP API through the gateway."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple


CATALOG_ROW = re.compile(
    r"^\| (GET|POST|PUT|PATCH|DELETE|WEBSOCKET) \| `([^`]+)` \| "
    r"(user|content|social) \| .* \| (API-[UCS]\d{3}) \|$"
)
UUID_ZERO = "00000000-0000-0000-0000-000000000000"


class ApiEntry(NamedTuple):
    method: str
    path: str
    owner: str
    test_id: str


class ProbeResult(NamedTuple):
    entry: ApiEntry
    status: int | None
    duration_ms: float
    passed: bool
    detail: str


def parse_catalog(path: Path) -> list[ApiEntry]:
    entries: list[ApiEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "## 内部接口":
            break
        match = CATALOG_ROW.match(line)
        if match:
            entries.append(ApiEntry(*match.groups()))
    if not entries:
        raise ValueError(f"no public API rows found in {path}")
    return entries


def materialize_path(path: str) -> str:
    replacements = {
        "status": "approved",
        "media_path": "api-smoke-missing.bin",
        "avatar_path": "api-smoke-missing.bin",
    }

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return replacements.get(name, UUID_ZERO)

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::path)?\}", replace, path)


def is_acceptable_response(status: int, body: bytes) -> bool:
    if status >= 500 or status == 405:
        return False
    if status == 404 and "接口不存在".encode("utf-8") in body:
        return False
    return 100 <= status < 500


def probe_http(base_url: str, entry: ApiEntry, timeout: float) -> ProbeResult:
    url = f"{base_url.rstrip('/')}{materialize_path(entry.path)}"
    data = b"{}" if entry.method in {"POST", "PUT", "PATCH"} else None
    request = urllib.request.Request(
        url,
        data=data,
        method=entry.method,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": f"api-smoke-{entry.test_id.lower()}",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            body = response.read(4096)
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read(4096)
    except (OSError, urllib.error.URLError) as error:
        duration = (time.perf_counter() - started) * 1000
        return ProbeResult(entry, None, duration, False, str(error))
    duration = (time.perf_counter() - started) * 1000
    passed = is_acceptable_response(status, body)
    detail = f"HTTP {status}"
    if not passed:
        detail = f"{detail}: {body.decode('utf-8', errors='replace')[:300]}"
    return ProbeResult(entry, status, duration, passed, detail)


def write_junit(results: list[ProbeResult], path: Path) -> None:
    failures = sum(not result.passed for result in results)
    suite = ET.Element(
        "testsuite",
        name="public-api-catalog-smoke",
        tests=str(len(results)),
        failures=str(failures),
        errors="0",
        skipped="0",
        time=f"{sum(item.duration_ms for item in results) / 1000:.3f}",
    )
    for result in results:
        case = ET.SubElement(
            suite,
            "testcase",
            classname=f"api.{result.entry.owner}",
            name=f"{result.entry.test_id} {result.entry.method} {result.entry.path}",
            time=f"{result.duration_ms / 1000:.3f}",
        )
        if not result.passed:
            failure = ET.SubElement(case, "failure", message=result.detail)
            failure.text = result.detail
        else:
            output = ET.SubElement(case, "system-out")
            output.text = result.detail
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def write_json(results: list[ProbeResult], path: Path) -> None:
    payload = {
        "total": len(results),
        "passed": sum(result.passed for result in results),
        "failed": sum(not result.passed for result in results),
        "http_runtime_probes": sum(result.entry.method != "WEBSOCKET" for result in results),
        "websocket_behavior_tests": sum(result.entry.method == "WEBSOCKET" for result in results),
        "results": [
            {
                "test_id": result.entry.test_id,
                "method": result.entry.method,
                "path": result.entry.path,
                "owner": result.entry.owner,
                "status": result.status,
                "duration_ms": round(result.duration_ms, 3),
                "passed": result.passed,
                "detail": result.detail,
            }
            for result in results
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument(
        "--catalog", default="docs/microservices/service-api-catalog.md", type=Path
    )
    parser.add_argument(
        "--junit", default=".ci-results/microservices-regression/public-api.xml", type=Path
    )
    parser.add_argument(
        "--json", default=".ci-results/microservices-regression/public-api.json", type=Path
    )
    parser.add_argument("--timeout", default=5.0, type=float)
    args = parser.parse_args()

    entries = parse_catalog(args.catalog)
    results: list[ProbeResult] = []
    for entry in entries:
        if entry.method == "WEBSOCKET":
            results.append(
                ProbeResult(
                    entry,
                    None,
                    0.0,
                    True,
                    "covered by the real service WebSocket behavior suite",
                )
            )
        else:
            results.append(probe_http(args.base_url, entry, args.timeout))

    write_junit(results, args.junit)
    write_json(results, args.json)
    passed = sum(result.passed for result in results)
    print(
        "PUBLIC_API_SMOKE="
        f"{'PASS' if passed == len(results) else 'FAIL'} "
        f"total={len(results)} passed={passed} failed={len(results) - passed} "
        f"http={sum(item.entry.method != 'WEBSOCKET' for item in results)} "
        f"websocket={sum(item.entry.method == 'WEBSOCKET' for item in results)}"
    )
    for result in results:
        if not result.passed:
            print(f"FAIL {result.entry.test_id} {result.entry.method} {result.entry.path}: {result.detail}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

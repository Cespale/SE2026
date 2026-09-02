#!/usr/bin/env bash
set -Eeuo pipefail

NAMESPACE=${NAMESPACE:-streamhub-ms}
GATEWAY_BASE_URL=${GATEWAY_BASE_URL:-}
EXPECTED_VERSION=${EXPECTED_VERSION:-${APP_VERSION:-}}
forward_pid=""
forward_log=""

cleanup() {
    if [[ -n "$forward_pid" ]]; then
        kill "$forward_pid" 2>/dev/null || true
        wait "$forward_pid" 2>/dev/null || true
    fi
    if [[ -n "$forward_log" ]]; then
        rm -f -- "$forward_log"
    fi
}
trap cleanup EXIT

if [[ -z "$GATEWAY_BASE_URL" ]]; then
    GATEWAY_BASE_URL=http://127.0.0.1:8100
    forward_log=$(mktemp)
    kubectl -n "$NAMESPACE" port-forward service/gateway 8100:80 \
        >"$forward_log" 2>&1 &
    forward_pid=$!
fi

ready=false
for _ in {1..30}; do
    if curl -fsS "$GATEWAY_BASE_URL/health" >/dev/null; then
        ready=true
        break
    fi
    sleep 1
done
if [[ "$ready" != "true" ]]; then
    echo "gateway did not become reachable" >&2
    exit 1
fi

paths=(
    /health
    /ready
    /version
    /_services/user/health
    /_services/user/ready
    /_services/user/version
    /_services/content/health
    /_services/content/ready
    /_services/content/version
    /_services/social/health
    /_services/social/ready
    /_services/social/version
)

for path in "${paths[@]}"; do
    body=$(curl -fsS "$GATEWAY_BASE_URL$path")
    if [[ "$path" == */version && "$body" != *'"version"'* ]]; then
        echo "version missing from $path" >&2
        exit 1
    fi
    if [[ "$path" == */version && -n "$EXPECTED_VERSION" ]]; then
        compact_body=$(printf '%s' "$body" | tr -d '[:space:]')
        if [[ "$compact_body" != *"\"version\":\"$EXPECTED_VERSION\""* ]]; then
            echo "version mismatch at $path: expected $EXPECTED_VERSION" >&2
            exit 1
        fi
    fi
    echo "$path PASS"
done

echo "MICROSERVICES_HEALTH_CHECK=PASS"

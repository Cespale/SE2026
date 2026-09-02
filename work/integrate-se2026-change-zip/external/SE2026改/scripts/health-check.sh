#!/usr/bin/env bash
# 健康检查：验证 K8s 中的后端、前端可访问
set -euo pipefail

NAMESPACE="${NAMESPACE:-streamhub}"

check_http() {
  local name="$1" svc="$2" port="$3" local_port="$4" path="$5"
  echo "==> 检查 ${name} (${svc}:${port}${path}) ..."
  kubectl -n "${NAMESPACE}" port-forward "svc/${svc}" "${local_port}:${port}" >/dev/null 2>&1 &
  local pf=$!
  sleep 4
  if curl -fsS "http://127.0.0.1:${local_port}${path}" >/dev/null 2>&1; then
    echo "  [OK] ${name} 健康检查通过"
  else
    echo "  [FAIL] ${name} 健康检查失败"
    kill "${pf}" 2>/dev/null || true
    exit 1
  fi
  kill "${pf}" 2>/dev/null || true
}

check_http "后端" "streamhub-backend" 8000 18000 "/openapi.json"
check_http "前端" "streamhub-frontend" 3266 13266 "/"
check_http "前端→后端 API 链路" "streamhub-frontend" 3266 23266 "/api/health"
check_http "MinIO" "streamhub-minio" 9000 19000 "/minio/health/live"
check_http "SRS 媒体服务器" "streamhub-srs" 1985 19850 "/api/v1/versions"

echo "==> 全部健康检查通过"

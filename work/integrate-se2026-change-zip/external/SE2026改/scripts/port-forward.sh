#!/usr/bin/env bash
# 一键启动「本机 → kind 集群」的全部端口转发
#
# 为什么需要：Windows 下 kind 的 NodePort 绑在 Docker 内网节点 IP 上，
# 宿主机无法直连 localhost:30000，所有访问都要经 kubectl port-forward。
# **重建集群后这些转发全部失效**，重新部署后跑一次本脚本即可。
#
# 用法：
#   bash scripts/port-forward.sh            # 启动全部转发
#   bash scripts/port-forward.sh --stop     # 停止由本脚本启动的转发
#
# 依赖：kubectl、node（用于 TCP 探测）

set -euo pipefail

NAMESPACE="${NAMESPACE:-streamhub}"

# 转发清单：<本地端口>:<svc/服务名>:<服务端口> <用途说明>
FORWARDS=(
  "13266:svc/streamhub-frontend:3266 前端页面 (http://127.0.0.1:13266)"
  "1935:svc/streamhub-srs:1935 OBS 推流 (rtmp://127.0.0.1:1935/live)"
  "8080:svc/streamhub-srs:8080 浏览器拉流 (HTTP-FLV)"
  "1985:svc/streamhub-srs:1985 SRS API (诊断用)"
)

PID_FILE="${TMPDIR:-/tmp}/streamhub-port-forward.pids"

# TCP 探测：端口通返回 0，不通返回 1
tcp_check() {
  node -e "
    const net = require('net');
    const s = net.connect($1, '127.0.0.1');
    s.setTimeout(2000);
    s.on('connect', () => process.exit(0));
    s.on('error', () => process.exit(1));
    s.on('timeout', () => { s.destroy(); process.exit(1); });
  "
}

if [ "${1:-}" = "--stop" ]; then
  if [ -f "${PID_FILE}" ]; then
    echo "==> 停止由本脚本启动的端口转发..."
    while read -r pid; do
      kill "${pid}" 2>/dev/null || true
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
    echo "==> 已停止"
  else
    echo "==> 没有本脚本启动的转发（PID 文件不存在）"
  fi
  exit 0
fi

echo "==> 命名空间: ${NAMESPACE}  目标: kind 集群"

# 预检：命名空间必须已部署
if ! kubectl get ns "${NAMESPACE}" >/dev/null 2>&1; then
  echo "[错误] 命名空间 ${NAMESPACE} 不存在，请先运行: bash scripts/deploy.sh" >&2
  exit 1
fi

: > "${PID_FILE}"

for entry in "${FORWARDS[@]}"; do
  local_port="${entry%%:*}"
  rest="${entry#*:}"
  svc_ref="${rest%% *}"
  desc="${rest#* }"
  svc_name="${svc_ref#svc/}"; svc_name="${svc_name%:*}"
  svc_port="${svc_ref##*:}"

  # 目标服务必须存在（deploy.sh 已包含 SRS 后应都有）
  if ! kubectl -n "${NAMESPACE}" get svc "${svc_name}" >/dev/null 2>&1; then
    echo "[跳过] 服务 ${svc_name} 不存在: ${desc}"
    continue
  fi

  # 本地端口已被占用 → 可能已有一个转发在跑，不重复启动
  if tcp_check "${local_port}"; then
    echo "[已存在] 本地端口 ${local_port} 已被占用，跳过: ${desc}"
    continue
  fi

  echo "==> 启动 ${local_port} → ${svc_ref}: ${desc}"
  # 注意：kubectl port-forward 的资源参数只能写 svc/名称（不含端口），
  # 端口放在后面的「本地:远端」，写进资源名会报 services "xx:3266" not found
  nohup kubectl -n "${NAMESPACE}" port-forward "svc/${svc_name}" "${local_port}:${svc_port}" >"${TMPDIR:-/tmp}/streamhub-pf-${local_port}.log" 2>&1 &
  echo $! >> "${PID_FILE}"
done

# kubectl port-forward 首次建立需要数秒（要协商 API Server 再连 Pod），轮询等待最多 15 秒
echo
echo "==> 等待端口就绪（最多 15 秒）..."
for attempt in $(seq 1 15); do
  pending=0
  for entry in "${FORWARDS[@]}"; do
    local_port="${entry%%:*}"
    if ! tcp_check "${local_port}"; then
      pending=1
    fi
  done
  [ "${pending}" -eq 0 ] && break
  sleep 1
done

echo
echo "==> 转发状态检查："
ok=0
total=0
for entry in "${FORWARDS[@]}"; do
  local_port="${entry%%:*}"
  total=$((total + 1))
  if tcp_check "${local_port}"; then
    echo "  [OK] 127.0.0.1:${local_port}"
    ok=$((ok + 1))
  else
    echo "  [!!] 127.0.0.1:${local_port} 15 秒内未监听（请检查 Pod 状态：kubectl get pods -n ${NAMESPACE}）"
  fi
done

echo
echo "==> 完成 (${ok}/${total} 个端口就绪)"
echo "  前端页面:    http://127.0.0.1:13266"
echo "  OBS 服务器:   rtmp://127.0.0.1:1935/live   (串流密钥用页面显示的房间 streamKey)"
echo "  停止转发:     bash scripts/port-forward.sh --stop"

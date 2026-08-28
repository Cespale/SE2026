#!/usr/bin/env bash
# 部署 StreamHub 到 Kubernetes
#
# 用法：
#   VERSION=<镜像版本号> bash scripts/deploy.sh
#
# 密钥来源（仓库里绝不出现明文）：
#   - CI 里由 GitHub Secrets 注入 POSTGRES_PASSWORD / SECRET_KEY
#   - 本地开发：先复制 .env.example 为 .env 并填好，脚本会自动 source
set -euo pipefail

# 本地优先读取 .env（已被 .gitignore 忽略，不会提交）
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

VERSION="${VERSION:?需要设置 VERSION（镜像版本号，例如 git 短 SHA）}"
NAMESPACE="${NAMESPACE:-streamhub}"

: "${POSTGRES_PASSWORD:?需要设置 POSTGRES_PASSWORD}"
: "${SECRET_KEY:?需要设置 SECRET_KEY}"

echo "==> 版本=${VERSION}  命名空间=${NAMESPACE}"

# 命名空间
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# 密钥：从环境变量注入，不写进仓库
kubectl -n "${NAMESPACE}" create secret generic streamhub-secrets \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  --from-literal=SECRET_KEY="${SECRET_KEY}" \
  --from-literal=DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@streamhub-postgres:5432/streamhub" \
  --dry-run=client -o yaml | kubectl apply -f -

# 数据库初始化 SQL → ConfigMap
kubectl -n "${NAMESPACE}" create configmap streamhub-db-init \
  --from-file=01_streamhub_backup.sql=backend/docker-init/01_streamhub_backup.sql \
  --dry-run=client -o yaml | kubectl apply -f -

# 应用各服务清单（替换版本占位符）
for f in k8s/postgres.yaml k8s/backend.yaml k8s/frontend.yaml; do
  sed "s/VERSION_PLACEHOLDER/${VERSION}/g" "$f" | kubectl -n "${NAMESPACE}" apply -f -
done

echo "==> 等待 Deployment 就绪..."
kubectl -n "${NAMESPACE}" rollout status deploy/streamhub-postgres --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/streamhub-backend --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/streamhub-frontend --timeout=180s

echo "==> 部署完成"

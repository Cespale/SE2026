#!/usr/bin/env bash
# 把单体后端 Kubernetes 部署回退到上一个不可变镜像版本（deploy.sh 的对偶）
#
# 用法：
#   VERSION=<上一可用镜像版本> bash scripts/rollback.sh
#
# 说明：
#   - 单体只有 streamhub-backend / streamhub-frontend 两个 Deployment 使用版本镜像
#     （VERSION_PLACEHOLDER）；postgres / minio 是固定镜像，不属于应用版本，不回滚。
#   - 数据库 Schema/数据不回滚：迁移与初始化只前滚，本脚本只做应用代码/镜像级回退。
#   - 回滚后跑 health-check.sh 确认后端、前端、MinIO 可用。
set -euo pipefail

NAMESPACE="${NAMESPACE:-streamhub}"
VERSION="${VERSION:?需要设置 VERSION（回滚到哪个不可变镜像版本，例如 git 短 SHA）}"

if [[ ! "$VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "VERSION contains unsupported characters" >&2
    exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "==> 回滚目标 version=${VERSION}  namespace=${NAMESPACE}"

current_image=$(
    kubectl -n "$NAMESPACE" get deployment streamhub-backend \
        -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true
)
if [[ -z "$current_image" ]]; then
    echo "找不到 streamhub-backend Deployment：该命名空间还没完成过一次前置单体部署，没有可回滚的目标。" >&2
    exit 2
fi
current_tag=${current_image##*:}
echo "==> 当前后端镜像：${current_image}"
if [[ "$current_tag" == "$VERSION" ]]; then
    echo "当前后端已运行 ${VERSION}，没有需要回滚的变更。" >&2
    exit 3
fi

changed=0
for dep in streamhub-backend streamhub-frontend; do
    if ! kubectl -n "$NAMESPACE" get deployment "$dep" >/dev/null 2>&1; then
        continue
    fi
    img=$(kubectl -n "$NAMESPACE" get deployment "$dep" \
        -o jsonpath='{.spec.template.spec.containers[0].image}')
    tag=${img##*:}
    if [[ -z "$img" || "$tag" == "$VERSION" ]]; then
        echo "==> ${dep} 已运行目标镜像 (${img})，跳过"
        continue
    fi
    new_image="${img%:*}:${VERSION}"
    echo "==> ${dep}: ${img} -> ${new_image}"
    kubectl -n "$NAMESPACE" set image "deployment/${dep}" "*=${new_image}"
    changed=1
done

if [[ "$changed" -eq 0 ]]; then
    echo "没有 Deployment 需要更换镜像；终止，未改动任何资源。" >&2
    exit 3
fi

echo "==> 等待滚动更新就绪..."
for dep in streamhub-backend streamhub-frontend; do
    if kubectl -n "$NAMESPACE" get deployment "$dep" >/dev/null 2>&1; then
        kubectl -n "$NAMESPACE" rollout status "deployment/${dep}" --timeout=180s
    fi
done

echo "==> 校验后端、前端、MinIO 健康..."
if NAMESPACE="$NAMESPACE" bash "$script_dir/health-check.sh"; then
    echo "ROLLBACK=PASS version=${VERSION}"
else
    echo "ROLLBACK=FAIL version=${VERSION}" >&2
    exit 1
fi

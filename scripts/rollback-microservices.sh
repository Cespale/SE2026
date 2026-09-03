#!/usr/bin/env bash
# 把 StreamHub 微服务 Kubernetes 部署回退到上一个不可变版本，并验证版本回到目标
#
# 用法：
#   IMAGE_TAG=<上一可用镜像版本> bash scripts/rollback-microservices.sh
#   IMAGE_TAG=<版本> APP_VERSION=<版本> bash scripts/rollback-microservices.sh
#
# 与 deploy-microservices.sh 的分工：
#   - deploy-microservices.sh 是前向部署：创建 ConfigMap/Secret、跑数据库迁移/种子、按新版本启动服务；
#   - 本脚本只做“发布后发现新版本有问题时退回上一可用版本”：
#       1. 把 ConfigMap streamhub-ms-config 的 APP_VERSION 改回目标版本（新 Pod 启动时读到一致版本号）；
#       2. 把版本化的业务 Deployment 镜像改回目标版本并等待滚动就绪；
#       3. 跑 health-check-microservices.sh，精确校验 /version 等于目标版本；
#       4. 全部通过输出 ROLLBACK=PASS。
#
# 明确不做的事（回滚边界）：
#   - 不回退数据库 Schema / 种子数据。数据库迁移始终前滚且幂等（schema-job 是 IF NOT EXISTS），
#     回滚只属于应用代码/镜像级；破坏性 schema 撤销不在本脚本职责内。
#   - 不重建 streamhub-ms-secrets：密钥与版本无关，沿用原 Secret 即可。
#   - postgres-ms / minio-ms / srs-ms 使用固定镜像，不属于应用版本，不参与回滚。
#   - BACKEND_ONLY 模式未部署的 frontend-ms / srs-ms 不会被当作漏部署强行处理。
set -Eeuo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
    if command -v kubectl.exe >/dev/null 2>&1; then
        kubectl() { kubectl.exe "$@"; }
    else
        echo "kubectl is required" >&2
        exit 2
    fi
fi

: "${IMAGE_TAG:?IMAGE_TAG is required (回滚到哪个不可变镜像版本)}"
APP_VERSION=${APP_VERSION:-$IMAGE_TAG}
NAMESPACE=${NAMESPACE:-streamhub-ms}

if [[ "${CI:-false}" == "true" && "$IMAGE_TAG" == "latest" ]]; then
    echo "CI rollback refuses the mutable latest tag" >&2
    exit 2
fi
if [[ ! "$IMAGE_TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "IMAGE_TAG contains unsupported characters" >&2
    exit 2
fi
if [[ ! "$APP_VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "APP_VERSION contains unsupported characters" >&2
    exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

echo "==> 回滚目标 tag=${IMAGE_TAG}  app=${APP_VERSION}  namespace=${NAMESPACE}"

current_version=$(
    kubectl -n "$NAMESPACE" get configmap streamhub-ms-config \
        -o jsonpath='{.data.APP_VERSION}' 2>/dev/null || true
)
if [[ -z "$current_version" ]]; then
    echo "未找到 ConfigMap streamhub-ms-config：该命名空间还没完成过一次前置部署，没有可回滚的目标。" >&2
    exit 2
fi
echo "==> 当前 ConfigMap 记录的版本：${current_version}"
if [[ "$current_version" == "$APP_VERSION" ]]; then
    echo "目标版本 (${APP_VERSION}) 与当前版本相同：没有需要回滚的变更。" >&2
    exit 3
fi

# 版本化的业务 Deployment（srs-ms / postgres-ms / minio-ms 使用固定镜像，不在此列）
versioned_deployments=(user-service content-service social-service gateway frontend-ms)

changed_deployments=()
for dep in "${versioned_deployments[@]}"; do
    if ! kubectl -n "$NAMESPACE" get deployment "$dep" >/dev/null 2>&1; then
        # 例如 BACKEND_ONLY 模式本来就没部署 frontend-ms，属于正常情况
        continue
    fi
    current_image=$(kubectl -n "$NAMESPACE" get deployment "$dep" \
        -o jsonpath='{.spec.template.spec.containers[0].image}')
    current_tag=${current_image##*:}
    if [[ -z "$current_image" || "$current_tag" == "$IMAGE_TAG" ]]; then
        echo "==> ${dep} 已运行目标镜像 (${current_image})，跳过"
        continue
    fi
    changed_deployments+=("$dep")
done

if [[ "${#changed_deployments[@]}" -eq 0 ]]; then
    echo "没有任何版本化 Deployment 需要更换镜像；终止，未改动任何资源。" >&2
    exit 3
fi

# 先改 ConfigMap，再换镜像：新 Pod 在创建时读到的是目标 APP_VERSION，避免“旧代码新版本号”。
kubectl -n "$NAMESPACE" patch configmap streamhub-ms-config \
    --type=merge -p "{\"data\":{\"APP_VERSION\":\"${APP_VERSION}\"}}"
echo "==> 已将 ConfigMap APP_VERSION 改为 ${APP_VERSION}"

for dep in "${changed_deployments[@]}"; do
    current_image=$(kubectl -n "$NAMESPACE" get deployment "$dep" \
        -o jsonpath='{.spec.template.spec.containers[0].image}')
    new_image="${current_image%:*}:${IMAGE_TAG}"
    echo "==> ${dep}: ${current_image} -> ${new_image}"
    kubectl -n "$NAMESPACE" set image "deployment/${dep}" "*=${new_image}"
done

echo "==> 等待滚动更新就绪..."
for dep in "${versioned_deployments[@]}"; do
    if kubectl -n "$NAMESPACE" get deployment "$dep" >/dev/null 2>&1; then
        kubectl -n "$NAMESPACE" rollout status "deployment/${dep}" --timeout=180s
    fi
done

echo "==> 校验健康/就绪与精确版本 (期望 ${APP_VERSION})..."
if EXPECTED_VERSION="$APP_VERSION" \
    NAMESPACE="$NAMESPACE" \
    APP_VERSION="$APP_VERSION" \
    bash "$script_dir/health-check-microservices.sh"; then
    echo "ROLLBACK=PASS version=${APP_VERSION} tag=${IMAGE_TAG}"
else
    echo "ROLLBACK=FAIL version=${APP_VERSION}" >&2
    exit 1
fi

#!/usr/bin/env bash
set -Eeuo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
    if command -v kubectl.exe >/dev/null 2>&1; then
        kubectl() { kubectl.exe "$@"; }
    else
        echo "kubectl is required" >&2
        exit 2
    fi
fi

: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${APP_VERSION:?APP_VERSION is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${USER_SERVICE_DB_PASSWORD:?USER_SERVICE_DB_PASSWORD is required}"
: "${CONTENT_SERVICE_DB_PASSWORD:?CONTENT_SERVICE_DB_PASSWORD is required}"
: "${SOCIAL_SERVICE_DB_PASSWORD:?SOCIAL_SERVICE_DB_PASSWORD is required}"
: "${SECRET_KEY:?SECRET_KEY is required}"
: "${MINIO_ROOT_USER:?MINIO_ROOT_USER is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD is required}"

if [[ "${CI:-false}" == "true" && "$IMAGE_TAG" == "latest" ]]; then
    echo "CI deployment refuses the mutable latest tag" >&2
    exit 2
fi

if [[ ! "$IMAGE_TAG" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "IMAGE_TAG contains unsupported characters" >&2
    exit 2
fi

for password_name in \
    USER_SERVICE_DB_PASSWORD \
    CONTENT_SERVICE_DB_PASSWORD \
    SOCIAL_SERVICE_DB_PASSWORD; do
    password=${!password_name}
    if [[ ! "$password" =~ ^[A-Za-z0-9._~-]+$ ]]; then
        echo "$password_name must be URL-safe" >&2
        exit 2
    fi
done

NAMESPACE=streamhub-ms
POSTGRES_DB=${POSTGRES_DB:-streamhub}
PUBLIC_GATEWAY_URL=${PUBLIC_GATEWAY_URL:-http://127.0.0.1:8100}
SRS_PUBLIC_RTMP_BASE=${SRS_PUBLIC_RTMP_BASE:-rtmp://127.0.0.1:1936/live}
SRS_PUBLIC_HTTP_BASE=${SRS_PUBLIC_HTTP_BASE:-http://127.0.0.1:8081/live}

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_root=$(cd "$script_dir/.." && pwd)
manifest_dir="$project_root/k8s/microservices"
rendered_dir=$(mktemp -d)

cleanup() {
    rm -rf -- "$rendered_dir"
}
trap cleanup EXIT

for manifest in "$manifest_dir"/*.yaml; do
    sed "s/:replace-me/:${IMAGE_TAG}/g" "$manifest" \
        > "$rendered_dir/$(basename "$manifest")"
done

kubectl apply -f "$rendered_dir/00-namespace.yaml"

kubectl create configmap streamhub-ms-config \
    -n "$NAMESPACE" \
    --from-literal=APP_VERSION="$APP_VERSION" \
    --from-literal=POSTGRES_DB="$POSTGRES_DB" \
    --from-literal=PUBLIC_GATEWAY_URL="$PUBLIC_GATEWAY_URL" \
    --from-literal=SRS_PUBLIC_RTMP_BASE="$SRS_PUBLIC_RTMP_BASE" \
    --from-literal=SRS_PUBLIC_HTTP_BASE="$SRS_PUBLIC_HTTP_BASE" \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic streamhub-ms-secrets \
    -n "$NAMESPACE" \
    --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    --from-literal=USER_SERVICE_DB_PASSWORD="$USER_SERVICE_DB_PASSWORD" \
    --from-literal=CONTENT_SERVICE_DB_PASSWORD="$CONTENT_SERVICE_DB_PASSWORD" \
    --from-literal=SOCIAL_SERVICE_DB_PASSWORD="$SOCIAL_SERVICE_DB_PASSWORD" \
    --from-literal=USER_DATABASE_URL="postgresql://streamhub_user_service:${USER_SERVICE_DB_PASSWORD}@postgres-ms:5432/${POSTGRES_DB}" \
    --from-literal=CONTENT_DATABASE_URL="postgresql://streamhub_content_service:${CONTENT_SERVICE_DB_PASSWORD}@postgres-ms:5432/${POSTGRES_DB}" \
    --from-literal=SOCIAL_DATABASE_URL="postgresql://streamhub_social_service:${SOCIAL_SERVICE_DB_PASSWORD}@postgres-ms:5432/${POSTGRES_DB}" \
    --from-literal=SECRET_KEY="$SECRET_KEY" \
    --from-literal=MINIO_ROOT_USER="$MINIO_ROOT_USER" \
    --from-literal=MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap streamhub-schema-files \
    -n "$NAMESPACE" \
    --from-file=01-service-schemas.sh="$project_root/database/init/01-service-schemas.sh" \
    --from-file=001-service-tables.sql="$project_root/database/migrations/001-service-tables.sql" \
    --from-file=00_monolith_backup.sql="$project_root/backend/docker-init/01_streamhub_backup.sql" \
    --from-file=02-service-seed.sql="$project_root/database/seed/02-service-seed.sql" \
    --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "$rendered_dir/postgres.yaml"
kubectl apply -f "$rendered_dir/minio.yaml"
kubectl rollout status deployment/postgres-ms -n "$NAMESPACE" --timeout=180s
kubectl rollout status deployment/minio-ms -n "$NAMESPACE" --timeout=180s

kubectl delete job/schema-migration -n "$NAMESPACE" --ignore-not-found
kubectl apply -f "$rendered_dir/schema-job.yaml"
kubectl wait --for=condition=complete job/schema-migration -n "$NAMESPACE" --timeout=180s

kubectl delete job/data-seed -n "$NAMESPACE" --ignore-not-found
kubectl apply -f "$rendered_dir/data-seed.yaml"
kubectl wait --for=condition=complete job/data-seed -n "$NAMESPACE" --timeout=180s

kubectl apply -f "$rendered_dir/user-service.yaml"
kubectl rollout status deployment/user-service -n "$NAMESPACE" --timeout=180s
kubectl apply -f "$rendered_dir/content-service.yaml"
kubectl rollout status deployment/content-service -n "$NAMESPACE" --timeout=180s
kubectl apply -f "$rendered_dir/social-service.yaml"
kubectl rollout status deployment/social-service -n "$NAMESPACE" --timeout=180s

kubectl apply -f "$rendered_dir/gateway.yaml"
kubectl rollout status deployment/gateway -n "$NAMESPACE" --timeout=180s
if [[ "${BACKEND_ONLY:-false}" != "true" ]]; then
    kubectl apply -f "$rendered_dir/frontend.yaml"
    kubectl rollout status deployment/frontend-ms -n "$NAMESPACE" --timeout=180s
    kubectl apply -f "$rendered_dir/srs.yaml"
    kubectl rollout status deployment/srs-ms -n "$NAMESPACE" --timeout=180s
fi

echo "STREAMHUB_MICROSERVICES_DEPLOYMENT=PASS version=$APP_VERSION tag=$IMAGE_TAG"

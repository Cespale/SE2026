#!/usr/bin/env bash
set -u

NAMESPACE=${NAMESPACE:-streamhub-ms}
OUTPUT_DIR=${1:-.ci-results/deployment/diagnostics}
mkdir -p "$OUTPUT_DIR"

kubectl get deployment,pods,services -n "$NAMESPACE" -o wide \
    >"$OUTPUT_DIR/resources.txt" 2>&1 || true
kubectl get events -n "$NAMESPACE" --sort-by=.metadata.creationTimestamp \
    >"$OUTPUT_DIR/events.txt" 2>&1 || true

for deployment in user-service content-service social-service gateway frontend-ms; do
    kubectl rollout status "deployment/$deployment" -n "$NAMESPACE" --timeout=10s \
        >"$OUTPUT_DIR/${deployment}-rollout.txt" 2>&1 || true
    kubectl describe "deployment/$deployment" -n "$NAMESPACE" \
        >"$OUTPUT_DIR/${deployment}-describe.txt" 2>&1 || true
    kubectl logs "deployment/$deployment" -n "$NAMESPACE" --all-containers --tail=200 \
        >"$OUTPUT_DIR/${deployment}-logs.txt" 2>&1 || true
done

kubectl get pods -n "$NAMESPACE" -o name >"$OUTPUT_DIR/pods.txt" 2>&1 || true
echo "DEPLOYMENT_DIAGNOSTICS=$OUTPUT_DIR"

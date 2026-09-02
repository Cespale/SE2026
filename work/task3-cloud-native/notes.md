# Notes: 云原生实验

## Constraints
- Source read-only: `C:\Users\lausu\Desktop\SE2026`.
- Working copy only: `C:\Users\lausu\Desktop\SE2026-microservices`.
- Local execution; no commit, push, or remote deployment.
- Preserve current Compose containers, volumes, media, and prior evidence.

## Findings
- Docker: 12 CPU、约 8 GB RAM；现有 Compose 保持运行。
- kubectl v1.36.1 可用，但无 current context；Kind/Minikube/k3d 原先均未安装。
- 三个业务服务已有 CPU 100m request、500m limit，满足 CPU HPA 计算前提。
- Gateway 使用 500ms connect timeout、全局 2s read timeout、502/503/504 固定 JSON 503；认证路由因 bcrypt 单独放宽到 10s。
- 采用 Kind v0.33.0、Metrics Server v0.8.0；Kind 二进制只放副本 `.tools`，独立 kubeconfig 不覆盖用户默认配置。
- HPA: user-service，40%，1-4 Pod，实验 scaleDown window 30s。

## Evidence
- RED: cloud-native contract 3 failures because HPA/setup/run scripts were missing.
- RED: load generator 2 failures because module was missing.
- GREEN: cloud-native contracts + load tests 18/18；PowerShell syntax passed.
- Kind v1.37.0 node Ready; Postgres, MinIO, user/content/social and Gateway Ready.
- Metrics Server v0.8.0 rollout passed; `kubectl top pods -n streamhub-ms` returned CPU/memory values.
- Setup preserved the existing Secret/PVC and scaled unrelated frontend/SRS workloads to 0.
- First complete run at concurrency 12 scaled 1→4→1 but had 78.509% errors; kept as overload evidence, not the primary result.
- Primary run at concurrency 4: 244 requests, 0 errors, 2.013 req/s, average 1975.251 ms, P95 3802.347 ms, Pod 1→4→1.
- Fault run: content 503 with designed Chinese fallback; user/social health both 200; content rollout recovered.

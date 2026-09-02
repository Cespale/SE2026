# Task Plan: HPA 与故障处理实验

## Goal
在本地副本和隔离的本地 Kubernetes 集群中，真实完成自动扩缩容与依赖故障处理实验，保留原始指标和可复跑脚本；不影响现有 Compose 数据。

## Phases
- [x] Phase 1: 审计 Kubernetes 清单、资源、网关和本机运行条件
- [x] Phase 2: 固化最小设计并以失败契约定义验收条件
- [x] Phase 3: 建立隔离 Kind 集群并部署微服务、Metrics Server
- [x] Phase 4: 执行 HPA 压测，记录扩容、缩容和性能指标
- [x] Phase 5: 执行依赖故障实验，验证提示与故障隔离
- [x] Phase 6: 重跑检查、固化证据和正式报告

## Design
- HPA：user-service；登录接口包含密码校验，能稳定制造 CPU，避免添加测试专用业务端点。
- 压测器：Python 标准库；记录请求数、并发、吞吐量、平均/P95、错误率和 Pod 时间线。
- 故障：将 content-service 副本缩为 0；Gateway 使用短超时和固定 JSON 503；同时探测 user/social。
- 集群：新建 `streamhub-lab` Kind；与现有 Compose 网络和持久卷隔离。

## Key Questions
1. 本机 Docker 资源是否足够运行 Kind、Metrics Server 和完整测试栈？
2. 现有资源请求/限制是否适合在单节点本地集群中触发 HPA？
3. 停止 content-service 后，Gateway 能否稳定返回设计提示且其他服务保持健康？

## Decisions Made
- 不用 Compose 副本数冒充 Kubernetes HPA。
- 不引入服务网格；Nginx 原生超时和错误页已满足本次故障处理要求。
- 不改原项目，不删除 Compose 容器、数据卷或既有证据。
- 用户已明确“直接做不用问”，本设计按预批准执行，不等待额外确认。

## Errors Encountered
- Kind first create failed pulling Docker Hub node image: Docker daemon proxy returned `x509: certificate signed by unknown authority`. Reproduced with no cached node image. Pulled the exact official digest through an alternate TLS endpoint, then tag locally; no TLS verification was disabled.
- First application deploy reached Kubernetes but Postgres hit the same Docker Hub certificate failure inside the Kind node; MinIO from Quay succeeded. Setup now preloads all manifest images already present locally (`postgres`, MinIO, SRS) together with five StreamHub images.
- Loading eight images in one Kind command failed with a missing content digest after six images were already present. Setup now imports one image at a time; Kind skips images already on the node and isolates any future failure.
- Single-image reproduction isolated the missing digest to the local multi-platform `postgres:16` image. Exporting only `linux/amd64` and loading the archive succeeded; setup now uses this path for Postgres and checks node tags before importing.
- `ossrs/srs:5` exposed the same all-platform import defect and was moved to the same amd64 archive path.
- Re-running setup rotated the Kubernetes Secret while PostgreSQL and MinIO PVCs retained their initial credentials; schema migration failed authentication. Setup now reuses all existing secret values and only generates them on first deploy.
- Business Pods were blocked by `runAsNonRoot` because the image declares named user `streamhub`. Image inspection proved UID 100/GID 101; all three manifests now pin those non-root IDs explicitly.
- Gateway dropped every Linux capability but official Nginx startup needs CHOWN/SETGID/SETUID before binding port 80. Manifest now adds only those three plus NET_BIND_SERVICE; privilege escalation remains disabled.
- Frontend liveness killed Webpack during first compile. Added a startupProbe (5s x 40) so liveness/readiness begin only after HTTP becomes available.
- HPA/fault experiments do not use frontend or SRS. Kind setup now requests backend-only deployment and scales leftovers to 0; normal deployment still includes both by default.
- kubectl could not fetch the remote Metrics Server manifest through the local TLS proxy. Setup now downloads the fixed official release with PowerShell and applies the local file.
- PowerShell treated `-o` after a kubectl scriptblock wrapper as an ambiguous common parameter. Removed the wrapper; every call now carries an explicit kubeconfig.
- Metrics Server Pods could not reach registry.k8s.io. Setup verifies the official v0.8.0 manifest hash, pulls the documented multi-platform digest through a reachable mirror, retags the original registry name, and preloads an amd64 archive.

## Status
**Complete** - 两项实验、原始证据、正式报告和全量验证均完成。

## 2026-08-31 实验失败记录

- 首次正式 HPA 实验在创建实验用户时返回 503，未生成压测结果，不能计为成功实验。
- Gateway 日志确认：`/api/auth/register` 等待 user-service 响应超过全局 `proxy_read_timeout 2s`。
- 同次请求实际触发 HPA 1→3，随后回落 3→1；这只能作为诊断证据，不能替代完整实验数据。
- 根因：bcrypt 密码哈希在 500m CPU 限制下可能超过 2 秒。最小修复：仅认证路由改为 10 秒，内容服务故障处理仍使用全局 2 秒。
- 修复后的并发 12 实验完成 1→4→1，但错误率 78.509%；保留为过载证据，不作为主展示。
- 并发 4 实验完成 1→4→1，244/244 请求成功，错误率 0%；故障隔离和恢复同时通过。
- 最终哈希时发现源目录 README 于 09:16 被其他进程改写。只读复算确认代入副本中复制时 README 后树哈希精确恢复 `5f37…`；版本脚本现以失败关闭方式区分冻结基线与当前源目录观察值，未修改或回滚源目录。

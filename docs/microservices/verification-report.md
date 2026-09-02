# StreamHub 微服务改造本地验证报告

验证日期：2026-08-31。本文件汇总课程“后 5 天”第 1–4 项本地结果：三业务微服务拆分、自动构建部署、HPA/故障处理和同条件性能对比。

教师终验总入口：`docs/microservices/teacher-final-audit.md`；其中把要求、实现、测试、原始证据、风险和现场演示顺序逐项对齐。

## 最终结论

| 项目 | 结果 |
|---|---|
| 工作区保护 | `WORKSPACE_GUARD=PASS`；只改 `SE2026-microservices` |
| 业务服务 | user/content/social 三项，镜像/Dockerfile/测试/Deployment 独立 |
| 数据隔离 | `SCHEMA_ISOLATION=PASS`；跨 Schema SQL 静态命中 0 |
| API 兼容 | 单体公开接口 85；服务公开接口 85；网关等价承接 `/api/health`，新增取消收藏 |
| 内部接口 | 11 项，全部列入清单；Gateway 对 `/internal/*` 返回 404 |
| 后端自动测试 | 本轮 130 passed：契约/共享 79、CI 契约 12、user 12、content 14、social 13；另有 Schema 隔离 PASS |
| 正式 E2E | 3 passed：UC01–02、UC03–05、UC06–08 |
| Compose | 8 个服务运行；数据库/MinIO/三业务服务/Gateway healthy |
| 业务链 | 注册→视频→点赞→Outbox 绝对计数回写→取消，PASS |
| 媒体链 | 头像上传 MinIO→Gateway 读取，724349 字节一致，PASS |
| 探针稳定性 | Task 7 记录 90/90；修复 Docker IPv6 DNS 后无间歇 503 |
| 独立镜像 | `streamhub-{user,content,social}-service:local-ms` 均构建成功 |
| Kubernetes 本地契约 | YAML/PowerShell/Bash/Python 解析与契约通过 |
| Kubernetes API/集群 | Kind v1.37.0 实跑；最终一键版本 `teacher-kind-cicd-final2-20260831`，Metrics API、业务后端、Gateway、Postgres、MinIO Ready |
| 自动扩缩容 | 并发 4、121.187s：Pod 1→4→1；244/244 成功；2.013 req/s；平均 1975.251ms；P95 3802.347ms；错误率 0% |
| HPA/故障复核 | Windows PowerShell 5.1 实跑 121.105s：236/236 成功、0 错误；1.949 req/s，平均 2047.350ms，P95 3904.009ms；HPA 1→4→1；故障 503/200/200，恢复成功；JSON 可由 Python UTF-8 解析 |
| 恢复竞态复验 | 2026-09-01 在 PowerShell 7 与 Windows PowerShell 5.1 各实跑一次：均为 HPA 1→4→1、故障 503/200/200、恢复后跨服务 `/api/live/rooms` 200；随后 API 85/85 |
| 故障处理 | content-service 停止时内容接口返回设计的 503；user/social 均 200；content 恢复成功 |
| 运行可观测性 | Gateway 与 user/content/social 的 health/ready/version 共 12 个端点全部通过精确版本检查，版本 `teacher-kind-cicd-final2-20260831` |
| 性能对比 | 三接口×两版本×3轮；主对比 18/18 测量 0 错误；微服务吞吐分别低 28.99%、33.86%、3.11%，不支持“性能提升” |

## 新鲜证据位置

- 教师终验后端 JUnit：`work/teacher-final-audit/core-final.xml`、`user-final.xml`、`content-final.xml`、`social-final.xml`、`ci-final.xml`。
- E2E JUnit：`.ci-results/microservices-local/teacher-audit-20260831/e2e.xml`；独立复跑：`work/teacher-final-audit/e2e-run-2.xml`。
- 最终本地一键 CI/CD：`.ci-results/kind-cicd/teacher-kind-cicd-final2-20260831/`；其中 Compose 门禁、API 85/85、E2E 3/3、Kind 资源、12 项探针/版本检查和部署诊断均已落盘。
- 零基础启动文档：`docs/getting-started/README.md`，文档契约 5/5、相对链接 0 损坏；隔离读者测试确认随机密码与连接 URL 一致且默认拒绝覆盖已有配置。
- 故障修复记录：首次 E2E 中，39.5MB 投稿被 Nginx 默认 1MB 限制返回 413；直播辅助请求误连单体 8001。上传路由随后限定 512MB、关闭请求缓冲并延长媒体超时；E2E 微服务模式辅助请求改走 8100。先重跑失败两项 2/2，再全量 3/3。
- 首次失败的 Playwright 附件已被后续成功全量运行按默认行为清理，因此不能把本段文字冒充课程所需的持久原始失败证据；第 2 项流水线必须为失败运行使用独立工件目录。
- 前后版本逐文件 SHA-256：`docs/microservices/version-manifest.json`。
- 原目录 `README.md` 在复制后被其他进程修改；清单同时记录当前观察值，并用副本中经哈希验证的复制时文件重建 `5f37…` 冻结基线，没有回滚原目录。
- 云原生报告：`docs/microservices/cloud-native-experiments.md`。
- 教师终验复跑：Windows PowerShell 5.1 下 236/236 成功、0 错误，HPA 1→4→1，故障 503/200/200，证据：`docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/`。该轮修复并验证了 5.1 的 `??`、`-SkipHttpErrorCheck`、重定向进程退出码和 JSON BOM 兼容问题。
- HPA/故障主证据：`docs/microservices/evidence/cloud-native/20260831-103639880/`；并发 12 过载对照：`20260831-103047581-overload/`。
- 2026-09-01 修复后完整门禁：`docs/microservices/evidence/verification/20260901-fix-errors/`；契约 82、三服务 39、公开 API 85/85、E2E 3/3，Compose 8 服务运行，配置 healthcheck 的服务均 healthy。
- 单体复制目录并行启动验证：同一证据目录的 `monolith-copy-validation.md` 与 `monolith-copy-e2e.xml`；备用端口下五服务运行，PostgreSQL/MinIO healthy，其余服务 HTTP 探针 200，UC01–UC08 为 3/3。
- 恢复竞态修复复跑：`docs/microservices/evidence/cloud-native/20260901-193144432-recovery-fix-pwsh7/`、`docs/microservices/evidence/cloud-native/20260901-193650344-recovery-fix-powershell51/`。
- 性能报告：`docs/microservices/performance-comparison.md`；主原始证据：`docs/microservices/evidence/performance/20260831-114658527-main/`；并发 16 过载对照：`20260831-113157084-overload/`。

## 关键风险与未完成项

1. 不能声称“性能提升”。已完成同机、同数据、同脚本各 3 次实测，但三个接口的微服务吞吐均更低，且应用总内存更高。
2. 本次 Kind 为单机本地实验，不能外推为生产容量；Metrics Server 的 insecure Kubelet TLS 参数只允许用于本地实验。
3. Kubernetes 新数据库只初始化角色/Schema/表，不自动注入单体演示数据；现场集群如需完整 UC 回归，必须另做受控数据迁移。
4. 并发 12 的登录压测虽完成 1→4→1，但错误率 78.509%；说明突发流量会在 HPA 生效前压满单 Pod，不能只展示并发 4 的成功结果。
5. `.dockerignore` 已排除依赖、虚拟环境和测试证据，但仓库随代码保留约 464.36 MiB 的 `public/demo-videos`，本轮前端构建上下文实测约 532 MiB。直接排除会丢失课程演示视频；若要降低 CI 时间和镜像体积，应把演示视频改为受控对象存储下载或单独数据包，不能只改忽略规则。
6. 直播 URL 的本地端口为 1936/8081；K8s 需配置 `SRS_PUBLIC_*` 并提供 Ingress/LoadBalancer 或明确的 port-forward。
7. 当前推荐接口为通用随机推荐，没有重建跨服务个性化偏好算法；功能可用，但属于与单体推荐质量可能不同的行为差异。
8. `scripts/run-cloud-native-experiments.ps1` 已由 Windows PowerShell 5.1 实际执行；以后若修改脚本，必须重新跑 5.1 解析和最小实验，不得只用 PowerShell 7。

## 不可混淆的下一步

第 1–4 项的本地实现和证据已固化。远端 GitHub Actions 仍未实跑，不能与本地通过混为一谈。现场展示应使用已保存原始结果；若换机器或改变资源参数，必须重新测试，不能沿用本文数字。

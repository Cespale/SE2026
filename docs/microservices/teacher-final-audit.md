# StreamHub 后 5 天任务：教师级终验报告

验证日期：2026-08-31  
验证目录：`C:\Users\lausu\Desktop\SE2026-microservices`  
原项目：`C:\Users\lausu\Desktop\SE2026`（只读）

## 1. 教师结论

**本地交付判定：通过，具备现场验收条件。**四项任务的实现、自动化门禁、原始结果、失败诊断和演示路径已形成闭环；本轮发现的脚本兼容性问题已修复并通过回归测试。

**远程流水线判定：未执行，不冒充通过。**用户明确要求只在本地操作且不推送，因此 GitHub Actions、GHCR 发布和远程 Runner 内 Kind 部署只能判定为“配置已验证、远程未实跑”。

**评分风险：**主要是远程执行边界、单机实验外推风险、前端构建体积和高并发容量拐点。这些不阻断本地课程演示，但必须在答辩时主动说明。

## 2. 要求追溯矩阵

| 任务书要求 | 实现与证据 | 判定 |
|---|---|---|
| 至少 3 个业务微服务 | user、content、social；职责和拆分理由见 `service-architecture.md` | 通过 |
| 服务独立构建、测试、部署 | 三个 Dockerfile；CI Matrix 独立测试；Compose 镜像与 K8s Deployment 均按服务拆分 | 通过 |
| 每张业务表有唯一归属 | `table-ownership.md`；`database/migrations/001-service-tables.sql`；三个受限数据库角色 | 通过 |
| 禁止跨服务直接读写/联表 | Schema 隔离测试、跨 Schema SQL 静态检查、服务源码检查均通过；跨服务使用内部 HTTP/Outbox | 通过 |
| 跨服务失败处理 | 超时、固定 503、只读降级、Outbox 重试/死信可见性、幂等接收；行为测试覆盖 | 通过 |
| 服务划分图/接口清单/表归属/调用说明 | `service-architecture.md`、`service-api-catalog.md`、`table-ownership.md`、`cross-service-calls.md` | 通过 |
| 改造前后两个代码版本 | 原目录只读；副本保留单体代码并新增三服务；`version-manifest.json` 对逐文件 SHA-256 冻结基线 | 通过 |
| 提交后自动构建测试制品部署 | `.github/workflows/ci.yml`：四门禁、Push/PR 路径、失败阻断、Artifact、SHA 镜像和 Kind Job | 本地配置通过；远程未实跑 |
| 所有后端公开接口有 API 测试 | 85 项清单：83 个 HTTP 网关真实巡检，2 个 WebSocket 由服务行为测试覆盖；85/85 | 通过 |
| UC01–UC08 端到端回归 | Playwright 三个组合场景；本地门禁 3/3，独立目录复跑 3/3 | 通过 |
| 日志、健康、就绪、版本 | Gateway 与三业务服务共 12 个端点全部 200；日志和 JSON 已保存 | 通过 |
| 现场说明部署失败排查 | 缺失不可变镜像受控失败：退出 125、inspect 1；恢复标签存在，运行版本未受影响 | 通过 |
| 自动扩缩容 | Kind HPA user-service：CPU request/limit 100m/500m，min/max 1/4；1→4→1 | 通过 |
| 故障处理 | 停止 content-service 后内容接口 503，user/social 200，恢复 rollout 成功 | 通过 |
| 改造前后性能对比 | categories、videos-latest、login；同机/同数据/同脚本/各 3 次，18/18 测量零错误 | 通过，结论为未测出提升 |

## 3. 服务与数据边界审查

### 3.1 业务服务职责

- **user-service**：认证、用户资料、头像、关注关系、会话/消息、通知。
- **content-service**：分类、视频、上传/媒体范围读取、创作者审核、搜索/Feed。
- **social-service**：点赞/收藏、评论/回复、弹幕、直播房间、举报、敏感词。

这样分是按业务所有权和变化/扩容边界分，不是按 URL 数量硬切。数据库表只由所属服务的受限账号访问；Gateway、注册/配置、前端、PostgreSQL、MinIO 都不计入三项业务服务。

### 3.2 跨服务规则

Gateway 只暴露公开 API 与受控的 `/_services/*/{health,ready,version}`；`/internal` 和 `/internal/*` 对外返回 404。服务间通过内部 HTTP 客户端传递 request-id/身份；写侧事件走 Outbox，接收端幂等。GET 可按策略重试，POST/写操作不自动重试。上游超时或 502/503/504 映射为固定 503 或只读降级，避免级联崩溃。

## 4. 自动构建、部署与可观测性

### 4.1 本地门禁结果

证据目录：

`C:\Users\lausu\Desktop\SE2026-microservices\.ci-results\microservices-local\teacher-audit-20260831`

- 三业务镜像 `streamhub-{user,content,social}-service:teacher-audit-20260831` 均存在；Compose 8 个服务运行且业务服务/Gateway healthy。
- API 巡检 `public-api.xml/json`：85/85。
- E2E `e2e.xml`：3/3；独立复跑 `work/teacher-final-audit/e2e-run-2.xml`：3/3，56.3 s。
- 日志：`service-logs.txt`；观测：`observability.json`；门禁结果：`result.txt` 为 PASS。

最终一键 Docker→Kind 证据：`.ci-results/kind-cicd/teacher-kind-cicd-final2-20260831/`。该轮使用当前代码执行 79 项合同/共享测试、39 项服务测试、85/85 API 与 3/3 E2E，随后把 5 个不可变镜像装入 `streamhub-cicd`，滚动部署成功；12 个 health/ready/version 检查全部通过且版本精确匹配。`kind-result.txt` 为 `KIND_CICD_GATE=PASS`。

### 4.2 失败诊断演示

证据：`.ci-results/deployment-failure-drill/20260831153629676/result.json`。

演示命令：

```powershell
& .\scripts\run-deployment-failure-drill.ps1 -GoodVersion 'teacher-audit-20260831'
```

预期解释链：不存在的 `missing-*` 镜像在 `--pull=never` 下直接得到退出码 125；`docker image inspect` 得到 1；确认正确不可变标签存在；查询运行中的 `/_services/user/version` 仍为正确版本。该操作不重建服务、不停容器、不删数据卷。

## 5. 云原生实验结果

### 5.1 自动扩缩容

Kind 集群：`streamhub-lab`，Kubernetes v1.37.0，Metrics Server v0.8.0，namespace `streamhub-ms`。HPA 目标 user-service，CPU 40%，副本 1–4，资源 request/limit 为 100m/500m CPU、128/512Mi 内存。

主证据：`docs/microservices/evidence/cloud-native/20260831-103639880/`。Windows PowerShell 5.1 终验复跑证据：`docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/`。

最新 PS5 复跑：121.105 s，236 请求，236 成功，0 错误，吞吐 1.949 req/s，平均 2047.350 ms，P95 3904.009 ms；就绪 Pod 1→4→1，最大 4。JSON 已用 Python `utf-8` 正常解析。

### 5.2 故障处理

执行 `kubectl scale deployment/content-service --replicas=0`：内容接口返回 `503 {"detail":"上游服务暂不可用"}`；user/social 健康接口保持 200；恢复 content-service 后 rollout 成功。实现类型是“超时返回 + 故障隔离”，不是熔断器；Gateway 不重试非幂等写请求。

## 6. 性能对比审计

证据：`docs/microservices/evidence/performance/20260831-114658527-main/`，并发 4、预热 5 s、读接口 20 s、登录 30 s、每接口每版本 3 轮、同一台 Docker 主机、同一 PostgreSQL 容器和数据。原始 JSON/CSV、资源采样和汇总均保留。

| 接口 | 单体吞吐 | 微服务吞吐 | 微服务平均/P95 | 错误率 |
|---|---:|---:|---:|---:|
| categories | 68.118 req/s | 48.370 req/s | 82.588 / 183.903 ms | 两版本均 0% |
| videos-latest | 18.579 req/s | 12.288 req/s | 339.155 / 679.057 ms | 两版本均 0% |
| login | 0.933 req/s | 0.904 req/s | 4401.777 / 4699.154 ms | 两版本均 0% |

实测结论是微服务吞吐分别低约 28.99%、33.86%、3.11%，且应用内存约为单体 2.86–2.91 倍；因此只能写“完成同条件对比，未测出性能提升”。高并发 12 的另一次实验错误率 78.509%，也一并保留，不能只展示低并发成功结果。

## 7. 全量验证清单

| 检查 | 结果 |
|---|---|
| 契约/共享 pytest | 79 passed；最终一键 JUnit 位于 `.ci-results/kind-cicd/teacher-kind-cicd-final2-20260831/contracts.xml` |
| user-service pytest | 12 passed，`user-final-rerun.xml` |
| content-service pytest | 14 passed，`content-final-rerun.xml` |
| social-service pytest | 13 passed，`social-final-rerun.xml` |
| CI 契约 pytest | 12 passed，`ci-final-rerun.xml` |
| 合计后端 pytest | **130 passed**（79+12+14+13+12）；Schema 隔离另行 PASS |
| 套件隔离门禁 | 五套 pytest 按独立进程/工作目录运行通过；不要把三个服务在同一 pytest 进程混跑（都使用顶层 `app` 包，混跑会发生模块名冲突） |
| 测试点脚本 | `TEST_CASES_BACKEND=29`、`TEST_CASES_E2E=3`、`POINTS_TOTAL=227` |
| TypeScript/生产构建 | typecheck 和 production build 通过；仅有已记录的 bundle 体积警告 |
| YAML/Kubernetes | 19 个部署/Compose/CI YAML（含多文档）解析通过；Kind API server dry-run 通过 |
| Python/Bash/PowerShell | Python compileall 通过；Bash `bash -n` 通过；全体 PowerShell 脚本经 Windows PowerShell 5.1 解析 |
| Compose 配置 | 微服务配置通过；性能配置在注入临时参数后通过；未输出密钥 |
| 文档本地链接 | 10 个文档、0 个损坏本地链接 |
| 工作区保护 | `WORKSPACE_GUARD=PASS`；原目录未写入 |

本轮修复并加入回归测试的实际缺陷：

1. `run-cloud-native-experiments.ps1` 原含 PowerShell 7 的 `??`、`-SkipHttpErrorCheck`，已改为 5.1 兼容写法。
2. Windows PowerShell 5.1 下 `Start-Process` 重定向时退出码读取不可靠，已改用 .NET `ProcessStartInfo` 并等待进程结束。
3. PowerShell 5.1 的 UTF-8 写出会加 BOM，已改为无 BOM 写入，Python UTF-8 解析实测通过。
4. 干净 Kind 集群的镜像/Secret/Metrics 探针会因预期非零退出被 PowerShell 5.1 中断，已用受控存在性探针修复。
5. MinIO 部分多平台 manifest 无法被 Kind all-platform 导入，改用 digest 固定的 amd64 单平台归档；最小导入实验和回归测试均通过。
6. `BACKEND_ONLY` 模式仍无条件缩容不存在的前端/SRS，已改为存在才缩容；Metrics JSON Patch 改用文件，避免 PowerShell 5.1 丢引号。
7. 投稿/审核 E2E 实测可达 40 秒，已为长流程设置 60 秒显式预算；直播场景在资源回落后先条件等待详情 200，不接受持续 503。
8. 本地门禁失败时原先不保存 Compose 日志，现已保证成功/失败都保存状态、服务日志、附件和结果原因。

## 8. 风险、成本与答辩口径

### 已证实的事实

- 本地副本四项任务均有当前日期证据；三业务服务、数据边界、API、E2E、HPA、故障隔离和性能原始数据可复查。
- 本地脚本可以在 Windows PowerShell 5.1 执行云原生实验。

### 未证实/不能声称

- 没有 GitHub Actions Run、GHCR 发布记录或远程 Runner Kind 记录；不得说“远程流水线已成功”。
- 不得说“微服务性能提升”；本机实测相反。
- 单机 Kind 结果不能外推生产容量；`--kubelet-insecure-tls` 仅为本地实验。

### 主动披露的变量

- `.dockerignore` 已排除依赖、虚拟环境和测试证据；但 `public/demo-videos` 约 464.36 MiB，前端构建上下文实测约 532 MiB。前端镜像约 635 MiB，仍是 CI 时间、Kind 导入和存储的主要成本。
- HPA 受控制周期和 4 Pod 上限约束；并发 12 在扩容生效前出现高错误率。
- K8s 数据库初始化的是 Schema/角色/表，不自动迁移完整单体演示数据；换机器现场需先做受控数据准备。
- 推荐接口当前是通用随机推荐，未重建单体的跨服务个性化偏好算法；这是行为差异而非测试失败。
- 直播 URL 在本地使用 1936/8081；K8s 演示需设置 `SRS_PUBLIC_*` 并提供端口转发或入口。

## 9. 现场演示顺序（建议 8 分钟）

1. 展示 `service-architecture.md`、`table-ownership.md` 和 `cross-service-calls.md`，说明三服务边界和表归属。
2. 展示 `.ci-results/kind-cicd/teacher-kind-cicd-final2-20260831/kind-result.txt`，再用 `kubectl --kubeconfig ... get pods` 展示不可变版本和 Ready 状态。
3. 打开 `service-api-catalog.md`，说明 85/85 API 巡检与 2 个 WebSocket 的真实行为测试口径。
4. 展示 `e2e.xml` 与独立 `e2e-run-2.xml` 的 3/3，任选 UC01–02、UC03–05、UC06–08 代表场景。
5. 展示 `ci.yml` 四门禁和 `needs` 阻断关系；再运行部署失败 drill，解释 125→inspect 1→恢复标签。
6. 使用既有 Kind 证据展示 HPA 时间线 1→4→1 和最新 `experiment-summary.json` 指标。
7. 展示停止 content-service 后 503/200/200，再展示恢复日志。
8. 最后展示性能汇总和风险，明确“本次没有测出性能提升、远程未实跑”。

## 10. 复核入口

- 总验证报告：`docs/microservices/verification-report.md`
- CI/CD：`docs/microservices/ci-cd-and-operations.md`
- 云原生：`docs/microservices/cloud-native-experiments.md`
- 性能：`docs/microservices/performance-comparison.md`
- 版本证据：`docs/microservices/version-manifest.json`、`docs/microservices/monolith-vs-microservices.md`
- 终验原始结果：`work/teacher-final-audit/` 与 `.ci-results/`
- 零基础启动：`docs/getting-started/README.md`

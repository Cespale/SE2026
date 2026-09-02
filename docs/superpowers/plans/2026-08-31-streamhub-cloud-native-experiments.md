# StreamHub Cloud-Native Experiments Implementation Plan

> **For agentic workers:** Execute inline in this task. Do not dispatch subagents and do not commit.

**Goal:** 真实完成 Kind 上的 HPA 与依赖故障处理实验并保存原始证据。

**Architecture:** 复用现有 Kubernetes 清单、镜像和 Gateway 备用结果。新增一个 HPA、一个标准库压测器、Kind 建立脚本和实验编排脚本。

**Tech Stack:** Kubernetes v1.36、Kind v0.33.0、Metrics Server v0.8.0、PowerShell、Python 3 标准库、Nginx。

## Global Constraints

- 只修改 `C:\Users\lausu\Desktop\SE2026-microservices`。
- 不提交、不推送、不删除现有 Compose 容器/卷/证据。
- HPA 必须真实观察到扩容和缩容；失败则报告失败。
- 密钥在运行时生成，不写入证据。

---

### Task 1: 实验契约与 HPA

**Files:**
- Create: `tests/microservices/test_cloud_native_experiments.py`
- Create: `k8s/microservices/user-service-hpa.yaml`

**Interfaces:**
- Produces: `HorizontalPodAutoscaler/user-service`，min 1、max 4、CPU target 40%。

- [ ] 写契约测试，检查 HPA、资源 request/limit、Gateway 503 备用结果、脚本参数和非破坏约束。
- [ ] 运行测试，确认因 HPA/脚本不存在而失败。
- [ ] 添加最小 HPA YAML。
- [ ] 重跑契约，HPA 部分通过；脚本部分继续失败。

### Task 2: 可复跑压测器

**Files:**
- Create: `scripts/cloud_native_load.py`
- Test: `tests/microservices/test_cloud_native_load.py`

**Interfaces:**
- Produces: CLI `--url --username --password --concurrency --duration --json`；JSON 包含 `requests`、`throughput_rps`、`average_ms`、`p95_ms`、`error_rate_percent`。

- [ ] 先写统计计算与 CLI 契约测试并确认失败。
- [ ] 用 `urllib.request`、`ThreadPoolExecutor`、`time.perf_counter` 实现固定时长并发 POST。
- [ ] 以最近秩计算 P95；HTTP 非 2xx 和网络异常计为错误。
- [ ] 重跑测试与 `py_compile`。

### Task 3: Kind 实验环境

**Files:**
- Create: `scripts/setup-kind-lab.ps1`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 本地版本镜像和现有 `scripts/deploy-microservices.sh`。
- Produces: `streamhub-lab`、Metrics API、Ready 的 `streamhub-ms` 栈。

- [ ] 契约先检查固定 Kind/Metrics Server 版本、独立 kubeconfig、镜像加载、Metrics Server patch 和健康等待；确认失败。
- [ ] 下载 Kind v0.33.0 到 `.tools/kind.exe`，校验官方 SHA-256。
- [ ] 创建独立 kubeconfig，不覆盖用户默认 kubeconfig。
- [ ] 加载五个不可变镜像，调用现有部署脚本，安装 Metrics Server v0.8.0 并追加实验 TLS 参数。
- [ ] 验证 node Ready、全部 workload Ready、`kubectl top pods` 有数值。

### Task 4: 两项实验编排

**Files:**
- Create: `scripts/run-cloud-native-experiments.ps1`

**Interfaces:**
- Consumes: Kind kubeconfig、Gateway port-forward、压测器、HPA。
- Produces: `.ci-results/cloud-native/<run-id>/` 内 JSON、CSV、YAML、日志和总结。

- [ ] 契约先检查工作区保护、HPA 扩缩容断言、故障断言、恢复 `finally` 和证据目录；确认失败。
- [ ] 启动 Gateway port-forward 到 18100，创建实验用户，等待 Metrics。
- [ ] 记录基线；运行登录压力；断言 Pod 数至少 2；停止负载后等待回到 1。
- [ ] content-service 缩为 0；断言内容接口 503 且 user/social 为 200；在 `finally` 恢复为 1并等待 Ready。
- [ ] 保存 HPA describe、events、Pod 列表、服务日志和实验摘要。

### Task 5: 实跑、报告与回归

**Files:**
- Create: `docs/microservices/cloud-native-experiments.md`
- Update: `work/task3-cloud-native/*`

- [ ] 运行完整契约、脚本语法和既有 72 项后端/契约测试。
- [ ] 建立 Kind 并执行两项实验；不满足任一断言则保留失败证据并修复根因。
- [ ] 从原始 JSON/CSV 写报告，不手填结果，不声称性能提升。
- [ ] 最终重跑并更新版本哈希清单。

## Self-review

- 覆盖 HPA、指标、压力、扩容、缩容、故障提示、隔离、恢复和证据。
- 无 TBD/TODO、无自定义服务网格、无新 Python 依赖。
- 所有路径、接口和阈值一致。

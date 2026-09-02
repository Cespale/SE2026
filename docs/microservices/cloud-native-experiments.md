# StreamHub 云原生实验报告

## 1. 结论

两项实验均在本机真实 Kind/Kubernetes 集群完成，不是配置截图或人工扩容：

- 自动扩缩容：user-service 在 CPU 压力下从 1 Pod 扩至 4 Pod，停止压力后回到 1 Pod。
- 故障处理：content-service 停止后，内容接口返回预设 HTTP 503；user-service 和 social-service 同时保持 HTTP 200，随后 content-service 自动恢复。

主结果使用并发 4。另保留并发 12 的过载结果，不能据此宣称系统在任意负载下都稳定。

## 2. 实验环境与边界

| 项目 | 实际值 |
|---|---|
| 日期 | 2026-08-31 |
| 集群 | Kind `streamhub-lab`，单控制节点 |
| Kubernetes | v1.37.0 |
| Metrics Server | v0.8.0 |
| Namespace | `streamhub-ms` |
| 应用版本 | `local-ci-20260831-cn1` |
| HPA 目标 | user-service |
| CPU request / limit | 100m / 500m |
| 内存 request / limit | 128Mi / 512Mi |
| HPA 目标值 | CPU request 的 40% |
| 副本范围 | 1–4 |

这是单机本地实验，结果不能外推为生产容量。Metrics Server 的 `--kubelet-insecure-tls` 只用于本地 Kind，不应复制到生产环境。

## 3. 可复现实验

PowerShell：

```powershell
cd C:\Users\lausu\Desktop\SE2026-microservices
.\scripts\setup-kind-lab.ps1 -Version local-ci-20260831-cn1
.\scripts\run-cloud-native-experiments.ps1
```

第二条命令默认使用并发 4、持续 120 秒，并执行以下步骤：

1. 应用 HPA，确认 Metrics API 返回 CPU 指标且基线为 1 Pod。
2. 创建一次性实验用户，并发请求 `/api/auth/login`。
3. 每约 5 秒记录期望/当前/就绪 Pod、CPU 利用率及 `kubectl top`。
4. 负载停止后等待回缩到 1 Pod。
5. 将 content-service 缩为 0，探测内容、用户和社交接口。
6. 恢复 content-service，等待 Deployment 就绪，并确认跨服务接口 `/api/live/rooms` 重新返回 200；只有这一步成功后脚本才写出 PASS。
7. 保存日志、事件、恢复结果和最终状态；异常退出时 `finally` 仍会做一次尽力恢复。

脚本不删除集群、Compose 容器或数据卷；实验使用独立 kubeconfig。

### 3.1 现场同时观察 HPA 和 Pod

先完成 `setup-kind-lab.ps1`。实验脚本占用第一个终端；另外打开两个 PowerShell 终端。不要把 HPA 和 Pod 合并成一个多资源 watch 命令，因为不同资源的 watch 组合在现场环境中并不可靠。

第二个终端观察 HPA（先保证 HPA 对象存在）：

```powershell
cd C:\Users\lausu\Desktop\SE2026-microservices
$kubeconfig = (Resolve-Path '.ci-results\cloud-native\kind-lab-kubeconfig').Path
kubectl --kubeconfig $kubeconfig apply -f .\k8s\microservices\user-service-hpa.yaml
kubectl --kubeconfig $kubeconfig get hpa user-service -n streamhub-ms -w
```

第三个终端观察所有 Pod：

```powershell
cd C:\Users\lausu\Desktop\SE2026-microservices
$kubeconfig = (Resolve-Path '.ci-results\cloud-native\kind-lab-kubeconfig').Path
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms -w
```

正确现象：HPA 的副本数先从 1 增加到 2–4，再回到 1；Pod 终端会看到新的 `user-service` Pod 创建并就绪。故障阶段 `content-service` 会暂时变为 0 个，随后恢复到 1 个 Ready。

## 4. 实验一：自动扩缩容

### 4.1 配置

HPA 使用 `autoscaling/v2`：min=1、max=4、CPU=40%。扩容每 15 秒最多增加 2 Pod；本地演示的缩容稳定窗口为 30 秒。CPU 百分比以 Pod 的 100m request 为分母，不是整机 CPU 百分比。

### 4.2 主结果

| 并发 | 持续时间 | 请求数 | 成功/错误 | 吞吐量 | 平均响应 | P95 | 错误率 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 121.187 s | 244 | 244 / 0 | 2.013 req/s | 1975.251 ms | 3802.347 ms | 0.000% |

Pod 时间线关键点：

| 相对基线时间 | 阶段 | 就绪 Pod | HPA CPU |
|---:|---|---:|---:|
| 0 s | 基线 | 1 | 3% |
| 36 s | 负载 | 3 | 140% |
| 54 s | 负载 | 4 | 500% |
| 114 s | 负载 | 4 | 329% |
| 173 s | 冷却 | 1 | 3% |

因此满足“压力升高后增加、压力下降后减少”。吞吐量不高的主要原因是登录接口含 bcrypt 密码校验，且每个 Pod CPU 上限只有 500m；本实验目标是触发 HPA，不代表普通查询接口容量。

### 4.3 过载对照

| 并发 | 请求数 | 成功/错误 | 吞吐量 | 平均响应 | P95 | 错误率 | Pod |
|---:|---:|---:|---:|---:|---:|---:|---|
| 12 | 805 | 173 / 632 | 6.547 req/s | 1811.601 ms | 5023.936 ms | 78.509% | 1→4→1 |

这是容量拐点，不是“更高并发更好”。Gateway 日志表明 HPA 完成扩容前，单 Pod 的连接队列被压满，出现连接超时和客户端超时。主展示采用并发 4，但过载原始结果仍一并提交，避免选择性汇报。

## 5. 实验二：故障处理

操作：`kubectl scale deployment/content-service --replicas=0`。Gateway 采用 500ms 连接超时、2 秒读取超时，并把 502/503/504 映射到固定 JSON 503。认证路由单独使用 10 秒读取超时，因为受限 CPU 下 bcrypt 可能超过全局 2 秒。

| 探测 | 实际结果 | 判定 |
|---|---|---|
| `GET /api/videos` | 503，`{"detail":"上游服务暂不可用"}` | 预设降级结果生效 |
| `GET /_services/user/health` | 200 | user-service 未被拖垮 |
| `GET /_services/social/health` | 200 | social-service 未被拖垮 |
| content-service 恢复 | rollout success | 实验后恢复成功 |

实现的是“超时返回 + 故障隔离”，不是熔断器。Nginx 不重试非幂等请求，避免故障时放大请求。

## 6. 原始证据

主实验：`docs/microservices/evidence/cloud-native/20260831-103639880/`

- `experiment-summary.json`：机器可读总结果。
- `load-results.json`：请求数、吞吐、平均/P95、错误率和状态码。
- `hpa-timeline.csv`：完整扩缩容时间线。
- `user-service-top.txt`：各采样点的 CPU/内存。
- `hpa-final.yaml`、`hpa-describe.txt`：HPA 状态和事件。
- `fault-results.json`、`gateway.log`：故障响应与网关日志。
- `events.txt`、`pods-final.txt`、`content-recovery.log`：集群事件、Pod 状态和恢复结果。

过载对照：`docs/microservices/evidence/cloud-native/20260831-103047581-overload/`。

## 6.1 教师终验复跑（Windows PowerShell 5.1）

为验证交付脚本能在课程常见的 Windows PowerShell 5.1 中实际执行，使用同一 Kind 集群和并发 4 独立复跑：

| 项目 | 实测结果 |
|---|---:|
| 证据目录 | `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/` |
| 负载 | 121.105 s，236 请求，236 成功，0 错误 |
| 吞吐/平均/P95 | 1.949 req/s；平均 2047.350 ms；P95 3904.009 ms |
| HPA | 1 → 4 → 1，最大就绪 Pod 4 |
| 故障 | content 503；user/social 200；恢复 rollout 成功 |

本轮前曾发现脚本含 PowerShell 7 的 `??`、`-SkipHttpErrorCheck`，且用 `Start-Process` 重定向输出时 5.1 的 `ExitCode` 为空。已增加回归测试，改用显式空值转换、兼容 HTTP 探测、.NET `ProcessStartInfo` 和无 BOM JSON 写出，并在 5.1 下实跑通过。原始运行目录 `.ci-results/cloud-native/20260831-154455611/` 也保留；此前的 217/217 复跑目录同样保留。

## 6.2 恢复验收修复复跑（2026-09-01）

深度巡检曾发现旧脚本先输出 PASS，才在 `finally` 中尽力恢复 content-service；紧接着运行 API 巡检时曾出现 `/api/live/rooms` 503，形成 84/85。现已把恢复变成 PASS 前的硬性验收：等待 Deployment rollout 完成，并持续探测跨服务接口 `/api/live/rooms`，只有返回 200 才生成成功结果；异常退出时 `finally` 仍保留尽力恢复。

| 运行环境 | 负载结果 | HPA | 故障隔离 | 恢复验收 | 证据 |
|---|---|---|---|---|---|
| PowerShell 7 | 122.440 s，227/227，1.854 req/s，平均 2146.300 ms，P95 4115.163 ms，0% 错误 | 1→4→1 | content 503；user/social 200 | `/api/live/rooms` 200 | `docs/microservices/evidence/cloud-native/20260901-193144432-recovery-fix-pwsh7/` |
| Windows PowerShell 5.1 | 121.892 s，224/224，1.838 req/s，平均 2166.248 ms，P95 4140.288 ms，0% 错误 | 1→4→1 | content 503；user/social 200 | `/api/live/rooms` 200 | `docs/microservices/evidence/cloud-native/20260901-193650344-recovery-fix-powershell51/` |

两轮结束后 content-service 均为 1/1 Ready；随后再次执行 85 项公开 API 巡检，结果均为 85/85，不再复现恢复竞态。

## 7. 已发现问题与限制

- 第一次尝试在创建用户时因认证路由继承 2 秒超时而返回 503；该次没有完整压测数据，不能算成功实验。修复为仅 `/api/auth/` 使用 10 秒读取超时。
- HPA 约按控制周期反应，不会在流量出现的瞬间扩容；突发流量仍可能在扩容前失败。
- 4 Pod 达到上限后不会继续扩容；需要结合真实 SLO、节点容量和成本重新设定上限。
- 登录压测会放大 bcrypt CPU 成本；后续容量评估应再覆盖读多、写多和跨服务调用接口。
- 本次故障是“服务停止”，未覆盖网络分区、数据库慢查询、部分实例异常和消息积压。

## 8. 依据

- [Kubernetes Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/)
- [Kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [Metrics Server](https://github.com/kubernetes-sigs/metrics-server)

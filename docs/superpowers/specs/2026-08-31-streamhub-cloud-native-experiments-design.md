# StreamHub 云原生实验设计

## 目标与事实边界

在隔离的本地 Kubernetes 中真实展示两件事：CPU 压力升高后 user-service Pod 增加、压力停止后减少；content-service 停止后 Gateway 返回预设 503，user/social 不随之失效。实验不得修改原项目、现有 Compose 容器或数据卷。

## 方案比较

1. **Kind 单节点集群（采用）**：真实 HPA、Pod、Metrics API；能加载已有本地镜像；额外成本是 Kind 节点与 Metrics Server。
2. Compose 手动扩容：代码最少，但不是 HPA，也没有 Pod，不能满足任务书。
3. 只提交 HPA YAML：能静态审查，不能证明扩缩容发生，证据不足。

## 架构与数据流

- `streamhub-lab` Kind 集群与现有 Compose 隔离。
- 使用 `local-ci-20260831-cn1` 镜像和现有 Kubernetes 清单。
- Metrics Server 提供 `metrics.k8s.io`；本地 Kind 使用 `--kubelet-insecure-tls`，仅限实验环境。
- HPA 目标：user-service，CPU request 100m，target 40%，min 1，max 4，实验缩容稳定窗口 30 秒。
- 压测器先创建专用实验用户，再并发请求登录接口；输出请求总数、吞吐量、平均/P95、错误率。
- 实验脚本每 5 秒记录 HPA、Pod 数量和 CPU，形成时间线。
- 故障实验将 content-service 缩为 0。Gateway 使用 500ms 连接超时、全局 2 秒读取超时和 502/503/504 固定 JSON 备用结果；bcrypt 认证路由单独为 10 秒。验证 content 请求为设计的 503，同时 user/social 健康端点仍为 200；最后恢复 content-service。

## 失败与恢复

- Metrics 不可用：停止实验，保存 APIService、Metrics Server 日志和 HPA describe；不能把 `<unknown>` 当作扩缩容成功。
- 压力不足：调整并发或持续时间，不降低到失真的 1% CPU 阈值。
- content-service 恢复失败：保存 rollout、events、describe、logs；不删除持久卷。
- Kind 资源不足：报告本机限制，不用 Compose 结果替代。

## 验收条件

1. HPA 当前指标不是 `<unknown>`。
2. 基线 1 Pod；负载期间至少 2 Pod；负载停止后回到 1 Pod。
3. 指标文件包含并发、请求数、吞吐量、平均/P95、错误率。
4. content-service 为 0 时，内容接口返回 HTTP 503 和 `上游服务暂不可用`。
5. 同期 user/social 健康端点 HTTP 200；恢复后 content 重新 Ready。
6. 所有 YAML、脚本契约和既有微服务测试通过。

## 依据

- Kubernetes HPA 文档：CPU 利用率以 Pod CPU request 为分母；HPA 控制循环默认约 15 秒；Metrics Server 通常提供 `metrics.k8s.io`。
- Kind Quick Start：支持加载本地非 `latest` 镜像，并建议 `IfNotPresent`。
- Metrics Server 官方说明：自签名 Kubelet 证书的测试集群可使用 `--kubelet-insecure-tls`，但不适用于生产。

设计无 TBD/TODO；实验和生产边界明确。用户已要求直接继续，视为批准此最小方案；不执行 Git commit。

# 测试、证据与故障排查

这份文档回答三个问题：失败发生在哪一步、去哪里看证据、怎样在不删除数据的前提下恢复。

## 1. 先认识成功标志

完整本地门禁应出现：

```text
PUBLIC_API_SMOKE=PASS total=85 passed=85 failed=0 http=83 websocket=2
3 passed
LOCAL_MICROSERVICES_GATE=PASS
MICROSERVICES_HEALTH_CHECK=PASS
KIND_CICD_GATE=PASS
```

缺少最后一行或出现 `KIND_CICD_GATE=FAIL`，都表示流水线未完成。不要只根据“Pod 创建了”就宣布部署成功。

## 2. 单独运行不同层级测试

静态、合同和服务测试：

```powershell
.\.venv-ms\Scripts\python.exe -m pytest -q tests\microservices shared\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\user-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\content-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\social-service\tests
npm run typecheck
```

一次完成 Compose 构建、85 个 API 测试、3 个 E2E 和可观测性检查：

```powershell
$version = "local-gate-$(Get-Date -Format 'yyyyMMddHHmmss')"
.\scripts\run-local-microservices-gate.ps1 -Version $version
```

运行前必须已有 `.env.microservices`。失败证据位于 `.ci-results\microservices-local\<版本号>`。

## 3. Compose 排查

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices ps
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 200 gateway user-service content-service social-service postgres-ms minio-ms
```

常见问题：

| 现象 | 检查 | 处理 |
|---|---|---|
| Cannot connect to Docker daemon | `docker version` | 启动 Docker Desktop，等待 Engine running |
| 端口已占用 | `Get-NetTCPConnection -LocalPort 5273,8100,5434,9100,9101 -ErrorAction SilentlyContinue` | 停止占用端口的旧程序，再启动 Compose |
| 数据库认证失败 | 检查 `.env.microservices` | 用初始化脚本生成一致配置；已有卷不要直接更换密码 |
| 容器 unhealthy | `docker compose ... logs <服务名>` | 从第一条异常向前查依赖，不要反复盲目重启 |

普通清理只用 `docker compose ... down`。不要使用 `down -v`，否则数据库和对象存储数据会被删除。

## 4. Kind 排查

先固定 kubeconfig，避免误查其他集群：

```powershell
$kubeconfig = (Resolve-Path '.ci-results\cloud-native\kind-lab-kubeconfig').Path
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms -o wide
kubectl --kubeconfig $kubeconfig get events -n streamhub-ms --sort-by=.metadata.creationTimestamp
kubectl --kubeconfig $kubeconfig describe pod -n streamhub-ms <Pod名称>
kubectl --kubeconfig $kubeconfig logs -n streamhub-ms deployment/user-service --tail=200
```

也可替换为 `content-service`、`social-service` 或 `gateway`。重点状态：

- `ImagePullBackOff`：镜像没有装入 Kind 或标签与 Deployment 不一致；重新运行完整 CI/CD 脚本，不要把标签改成 `latest`。
- `CrashLoopBackOff`：容器已经启动但程序退出；查看 `kubectl logs` 和 `kubectl describe` 的退出码。
- `0/1 Ready`：就绪探针失败；查看 `/ready` 依赖的数据库或其他服务。
- `Pending`：查看事件中的资源不足、PVC 或调度原因。

## 5. 自动诊断证据

完整流水线无论成功或失败都会尝试收集：

```text
.ci-results\kind-cicd\<版本号>\kind-result.txt
.ci-results\kind-cicd\<版本号>\kind-resources.txt
.ci-results\kind-cicd\<版本号>\kind-diagnostics\
```

`kind-diagnostics` 中包含资源、事件、rollout、describe 和各 Deployment 日志。先看 `kind-result.txt`，再看 `events.txt`，最后看失败服务的 `*-describe.txt` 与 `*-logs.txt`。

手工重新收集：

```powershell
$env:KUBECONFIG = $kubeconfig
& 'C:\Program Files\Git\bin\bash.exe' scripts/collect-deployment-diagnostics.sh .ci-results/manual-kind-diagnostics
```

## 6. 版本不一致

如果 `/version` 返回的值不是本次 `$version`，说明旧 Pod 或旧镜像仍在运行。检查：

```powershell
kubectl --kubeconfig $kubeconfig get deployment -n streamhub-ms -o custom-columns='NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image'
kubectl --kubeconfig $kubeconfig rollout status deployment/user-service -n streamhub-ms --timeout=120s
```

不要把 `latest` 当成修复方法。应使用新版本号重跑流水线，让镜像标签、Deployment 和 `/version` 三者一致。

## 7. Secret 与提交安全

不要把 `.env.microservices`、Kubernetes Secret 内容、访问令牌或密码放进报告、截图、日志附件和版本库。报告中只需要展示变量名、Secret 对象存在以及服务正常使用，不需要展示真实值。

# 用 Docker、Kubernetes 和 Kind 运行本地 CI/CD

本方法模拟“提交代码后自动测试、构建镜像和部署”的完整门禁。它先在 Docker Compose 中做回归，再把同一版本的镜像装入本机 Kind Kubernetes 集群。

## 1. 安装并检查依赖

需要以下工具：

- Docker Desktop，使用 Linux containers；
- Python 3.11 或兼容版本；
- Node.js 22.15 或更高版本和 npm；
- Git for Windows，默认安装到 `C:\Program Files\Git`；
- `kubectl`；
- PowerShell 5.1 或更高版本。

检查命令：

```powershell
docker version
docker compose version
python --version
node --version
npm --version
kubectl version --client
Test-Path 'C:\Program Files\Git\bin\bash.exe'
```

Kind 可执行文件由部署脚本下载到项目的 `.tools` 目录，并校验 SHA-256，不要求全局安装。

## 2. 准备项目依赖

从项目根目录执行：

```powershell
python -m venv .venv-ms
.\.venv-ms\Scripts\python.exe -m pip install -r requirements-microservices-test.txt
npm ci
npx playwright install chromium
```

若 `.env.microservices` 不存在，生成一份本地配置：

```powershell
.\scripts\init-microservices-env.ps1
```

## 3. 一条命令执行完整门禁

每次部署使用新的不可变版本号。不要使用 `latest`，否则无法证明现场运行的是哪份代码。

```powershell
$version = "local-kind-$(Get-Date -Format 'yyyyMMddHHmmss')"
.\scripts\run-kind-cicd-gate.ps1 -Version $version -ClusterName streamhub-cicd
```

脚本依次执行：

1. 工作区边界检查；
2. 合同测试、3 个业务服务各自测试和前端类型检查；
3. 构建 5 个带版本标签的镜像；
4. Compose 全栈部署、85 个公开 API 测试和 3 个代表性 E2E 流程；
5. 关闭 Compose 容器但保留数据卷；
6. 创建或复用 `streamhub-cicd` Kind 集群并装载镜像；
7. 部署数据库、MinIO、3 个业务服务、网关、HPA 和 Metrics Server，并在 schema 创建后还原并迁移单体演示数据（演示账号在 Kind 同样可用）；
8. 验证网关及 3 个业务服务的健康、就绪和精确版本；
9. 保存资源快照、日志、事件和失败诊断。

最终必须同时看到：

```text
LOCAL_MICROSERVICES_GATE=PASS
MICROSERVICES_HEALTH_CHECK=PASS
KIND_CICD_GATE=PASS
```

出现 `KIND_CICD_GATE=FAIL` 不能算部署成功，应按排障文档检查证据。

## 4. 查看 Kubernetes 结果

```powershell
$kubeconfig = (Resolve-Path '.ci-results\cloud-native\kind-lab-kubeconfig').Path
kubectl --kubeconfig $kubeconfig get nodes -o wide
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms -o wide
kubectl --kubeconfig $kubeconfig get deployment,service,hpa -n streamhub-ms
kubectl --kubeconfig $kubeconfig top pods -n streamhub-ms
```

业务 Pod 应为 `Running` 且 `READY` 为 `1/1`；`schema-migration` 应为 `Completed`。默认 Kind 路线只部署后端，因此看不到 `frontend-ms` 和 `srs-ms` 是正常设计，不是漏部署。

重新执行 12 个健康、就绪和版本检查：

```powershell
$env:KUBECONFIG = $kubeconfig
$env:EXPECTED_VERSION = $version
$env:APP_VERSION = $version
$env:NAMESPACE = 'streamhub-ms'
& 'C:\Program Files\Git\bin\bash.exe' scripts/health-check-microservices.sh
```

## 5. 临时访问网关

在一个 PowerShell 窗口执行：

```powershell
kubectl --kubeconfig $kubeconfig -n streamhub-ms port-forward service/gateway 8100:80
```

保持窗口运行，在另一个窗口访问 `http://127.0.0.1:8100/health`。按 `Ctrl+C` 结束端口转发，不会停止集群。

## 6. 暂停、恢复和删除

非破坏性暂停与恢复：

```powershell
docker stop streamhub-cicd-control-plane
docker start streamhub-cicd-control-plane
```

只有明确不要集群内资源和持久卷时，才执行：

```powershell
.\.tools\kind.exe delete cluster --name streamhub-cicd
```

删除 Kind 集群不可恢复。日常完成实验后可以直接保留集群，下一次脚本会复用它。

失败处理见 [README-Testing-Troubleshooting.md](README-Testing-Troubleshooting.md)。

## 7. 使用队友的 self-hosted GitHub Actions

当前 `.github/workflows/ci.yml` 已接入队友仓库提交
`76b18e947342fcb459e3ef7c008e4c0f53aa108b` 的 self-hosted 运行方式。没有原样复制其单体流水线：原文件只构建单体后端和前端，原样覆盖会漏掉 user、content、social 三个业务服务、Gateway、MinIO、85 项公开 API 回归和微服务 Kind 清单。

整合后的事件与 Runner：

| 事件 | Runner | 原因 |
|---|---|---|
| `push` 到 `main` | `self-hosted` | 使用队友的本地 Runner 完成全部测试、镜像和 Kind 部署 |
| `pull_request` 到 `main` | `ubuntu-latest` | 公共仓库的未合并代码不进入长期存在的自托管机器 |

self-hosted 机器必须是 **Linux x64**，并满足：Docker Engine 与 Compose 可用、至少 **8 GiB** 可用内存（推荐 12 GiB）、至少约 20 GiB 可用空间、可以访问 GitHub/容器镜像仓库、Runner 服务在线。Python 3.11、Node.js 22、Kind 和 kubectl 由工作流或 Action 准备；Docker 必须由机器管理员预装并允许 Runner 用户使用。

在 GitHub 仓库进入 `Settings → Actions → Runners → New self-hosted runner`，选择 Linux x64，严格执行页面为该仓库生成的安装命令。注册令牌是临时密钥，不要写进 README、截图或提交记录。Runner 上线后，向 `main` 推送才会使用它；没有在线且标签匹配的 Runner 时，任务会保持排队。

本次只改本地副本，没有 commit、push 或触发 GitHub Actions，因此结论仍是“本地配置和本地 Kind 已验证，**远程未实跑**”。远程是否成功必须以新提交产生的 Actions Run、Artifact 和日志为准。

## 8. 自托管机器资源不足时怎么做

不要同时运行多个 Kind 集群再执行完整门禁。多个 Kubernetes 控制面会持续占用 CPU 和内存，可能让本来正确的登录、上传或查询在网关超时。本机实测 Docker 仅分配 7.46 GiB、同时运行多个 Kind 时，E2E 会在不同步骤随机超时；暂停额外集群后，85 项 API 和 3 组 E2E 均通过。

暂停不会删除集群和数据：

```powershell
docker stop desktop-control-plane streamhub-lab-control-plane
# 门禁结束后恢复
docker start desktop-control-plane streamhub-lab-control-plane
```

一键脚本会自动设置镜像标签。若你手工复用某个已构建版本，变量名必须是 `IMAGE_TAG` 和 `APP_VERSION`，不是 `VERSION`：

```powershell
$version = '你的不可变版本号'
$env:IMAGE_TAG = $version
$env:APP_VERSION = $version
docker compose -f docker-compose.microservices.yml --env-file .env.microservices up -d --no-build --wait
```

遗漏这两个变量时，Compose 会尝试使用默认 `local-ms` 镜像；如果该镜像不存在，会报 `No such image`。优先使用第 3 节的一键脚本，可避免这个人工错误。

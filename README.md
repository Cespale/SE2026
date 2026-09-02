# StreamHub：从拿到代码到完整运行与课程验收

StreamHub 是一个视频、互动与直播平台。本仓库同时保留改造前的单体后端和改造后的微服务实现；课程“后 5 天”主要使用微服务版本。微服务版本包含 React 前端、API Gateway、3 个业务微服务、PostgreSQL、MinIO、SRS，以及 Docker Compose、Kubernetes、Kind、GitHub Actions、API/E2E 测试、HPA、故障实验和性能对比脚本。

本文写给第一次接触项目的人。照顺序执行，不需要事先理解代码。

> 路径约定：代码目录统一命名为 `SE2026-microservices`。本文出现的项目文件路径全部从 `SE2026-microservices` 开始，不包含任何人的电脑用户名或桌面路径。进入项目根目录后，命令中的 `.` 就代表 `SE2026-microservices`。

全部课程任务、项目设计、实施内容和实测结论见 [SE2026-microservices\项目说明.md](项目说明.md)。

## 1. 先选择你要做什么

| 目标 | 推荐入口 | 最终应该看到什么 |
| --- | --- | --- |
| 最快打开网页并体验功能 | 第 5 节 Docker Compose | 8 个服务运行，浏览器打开 `http://127.0.0.1:5273` |
| 一条命令完成本地测试、镜像和 Kind 部署 | 第 6 节 Kind CI/CD | `KIND_CICD_GATE=PASS` |
| 完成课程四项现场验收 | 第 7 节完整验收 | 微服务、CI/CD、云原生实验、性能对比均有结果和证据 |
| 查看 Kubernetes 服务 | 第 8 节手工核验 | Node 为 `Ready`，业务 Pod 为 `Running 1/1` |
| 排查失败 | 第 11 节 | 找到失败阶段、服务日志和证据目录 |

如果只是想确认项目可以运行，先做第 2～5 节。如果要交课程作业，做完第 2～9 节。

## 2. 新电脑需要准备什么

### 2.1 推荐环境

- Windows 10/11，64 位；
- Docker Desktop，使用 Linux containers；
- Git for Windows，默认包含 Git Bash；
- Python 3.11；
- Node.js 22 和 npm；
- `kubectl`；
- Windows PowerShell 5.1 或更高版本；
- PowerShell 7，仅性能对比脚本需要；
- 至少 12 GB 可用磁盘空间，建议预留 20 GB；
- 建议整机 12 GB 以上内存，Docker Desktop 至少分配 4 CPU、8 GB 内存。

Kind 不要求全局安装：`SE2026-microservices\scripts\setup-kind-lab.ps1` 会下载经过 SHA-256 校验的 Kind 到 `SE2026-microservices\.tools`。

官方安装入口：

- Docker Desktop：https://docs.docker.com/desktop/setup/install/windows-install/
- Python：https://www.python.org/downloads/windows/
- Node.js：https://nodejs.org/en/download
- kubectl：https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/
- Kind：https://kind.sigs.k8s.io/docs/user/quick-start/
- PowerShell 7：https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-windows

### 2.2 检查工具

打开 PowerShell，执行：

```powershell
git --version
docker version
docker compose version
python --version
node --version
npm --version
kubectl version --client
pwsh --version
Test-Path 'C:\Program Files\Git\bin\bash.exe'
```

正确结果：

- 每个版本命令都能输出版本号；
- `docker version` 同时出现 Client 和 Server；
- Git Bash 检查返回 `True`；
- 如果只有 `pwsh` 不存在，仍可启动 Compose 和运行 Kind 门禁，但不能执行性能对比。

Docker 出现 `Cannot connect to the Docker daemon` 时，先启动 Docker Desktop并等待 Engine Running，不要修改项目代码。

## 3. 获取代码

### 3.1 从 GitHub clone

在准备存放项目的目录打开 PowerShell：

```powershell
git clone https://github.com/Cespale/SE2026.git SE2026-microservices
Set-Location SE2026-microservices
```

`git clone` 最后的 `SE2026-microservices` 很重要，它保证目录名称与本文一致。

### 3.2 从 ZIP 获取

1. 解压 ZIP；
2. 把解压出来的最外层目录重命名为 `SE2026-microservices`；
3. 确认里面直接能看到 `README.md`、`package.json`、`services`、`scripts`，而不是再套一层同名目录；
4. 在 `SE2026-microservices` 的父目录打开 PowerShell，执行：

```powershell
Set-Location SE2026-microservices
```

ZIP 可能带有别人电脑生成的 `SE2026-microservices\.venv-ms`、`SE2026-microservices\node_modules` 和 `SE2026-microservices\.ci-results`。前两项是可重新生成的依赖，不能保证跨电脑可用；`.ci-results` 是历史证据，不是运行依赖。

打包 ZIP 时不要包含 `SE2026-microservices\.env`、`SE2026-microservices\.env.microservices` 或任何 Token；可以保留 `SE2026-microservices\docs\microservices\evidence` 中的课程证据。是否附带体积较大的本机 `.ci-results` 应由交付要求决定。

### 3.3 确认目录正确

```powershell
Get-ChildItem README.md, package.json, docker-compose.microservices.yml, services, scripts, k8s
```

六个目标都能找到才继续。如果找不到，通常是 ZIP 多套了一层目录或当前终端位置错误。

## 4. 第一次安装项目依赖

以下命令都在 `SE2026-microservices` 根目录运行。

### 4.1 Python 微服务测试环境

如果复制来的虚拟环境无法使用，只删除可再生成的 `SE2026-microservices\.venv-ms`，不要删除源码或数据目录：

```powershell
if (Test-Path .venv-ms) { Remove-Item -LiteralPath .venv-ms -Recurse -Force }
python -m venv .venv-ms
.\.venv-ms\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ms\Scripts\python.exe -m pip install -r requirements-microservices-test.txt
```

### 4.2 前端与浏览器测试环境

```powershell
npm ci
npx playwright install chromium
```

`npm ci` 以 `SE2026-microservices\package-lock.json` 为准重新安装依赖，适合 clone 或 ZIP 后的干净复现。

### 4.3 生成本机微服务配置

```powershell
if (-not (Test-Path .env.microservices)) {
    .\scripts\init-microservices-env.ps1
}
```

脚本会生成随机数据库密码、服务数据库 URL、JWT 密钥和 MinIO 密码，并默认拒绝覆盖已经存在的 `SE2026-microservices\.env.microservices`。

安全规则：

- 不要把 `SE2026-microservices\.env.microservices`、`SE2026-microservices\.env`、Token 或密码提交到 GitHub；
- 不要把自己电脑的真实 `.env` 放进要发给别人的 ZIP；
- 收到未知来源 ZIP 时，应检查其中是否包含真实密钥。

## 5. 最快启动完整微服务网页

### 5.1 构建并启动

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices up -d --build --wait --wait-timeout 240
docker compose -f docker-compose.microservices.yml --env-file .env.microservices ps
```

第一次运行需要下载基础镜像并构建前端，可能需要数分钟。不要因为一段时间没有新输出就关闭终端。

正常情况下共 8 个服务：

| 服务 | 用途 | 本机入口 |
| --- | --- | --- |
| `frontend-ms` | React 前端 | http://127.0.0.1:5273 |
| `gateway` | API 统一入口 | http://127.0.0.1:8100 |
| `user-service` | 用户、认证、关注、聊天、通知 | 仅容器内部 8000 |
| `content-service` | 视频、分类、投稿、审核、媒体 | 仅容器内部 8000 |
| `social-service` | 点赞、收藏、评论、弹幕、直播、举报 | 仅容器内部 8000 |
| `postgres-ms` | 三个服务 Schema 的 PostgreSQL | 127.0.0.1:5434 |
| `minio-ms` | 用户上传媒体对象存储 | http://127.0.0.1:9101 |
| `srs-ms` | 本地直播流服务 | 1936 / http://127.0.0.1:8081 |

`docker compose ps` 中带健康检查的服务应为 `healthy`，其他服务应为 `running`。

### 5.2 打开网页和登录

浏览器打开 `http://127.0.0.1:5273`。

| 角色 | 账号 | 密码 |
| --- | --- | --- |
| 普通用户 | `user` | `user123` |
| 创作者 | `creator` | `creator123` |
| 管理员 | `admin` | `admin123` |

可以现场体验搜索与播放、点赞/收藏、评论、弹幕、投稿、审核、创作者中心、创建直播、直播聊天和结束直播。

### 5.3 验证网关和服务

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8100/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8100/ready'
Invoke-RestMethod -Uri 'http://127.0.0.1:8100/version'
Invoke-RestMethod -Uri 'http://127.0.0.1:8100/_services/user/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8100/_services/content/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:8100/_services/social/health'
```

正确结果：网关和三个业务服务分别返回 `ok`，版本接口返回当前 `APP_VERSION`。

### 5.4 查看日志

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 gateway
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 user-service
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 content-service
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 social-service
```

### 5.5 安全停止

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices down
```

不要执行 `docker compose down -v`。`-v` 会删除 PostgreSQL 和 MinIO 数据卷。

## 6. 一条命令完成 Docker、测试、镜像和 Kind 部署

这条路线模拟代码提交后的完整 CI/CD 门禁。它会先运行本地回归，再把同一不可变版本部署到本机 Kind Kubernetes。

### 6.1 运行完整门禁

```powershell
$version = "manual-$(Get-Date -Format 'yyyyMMddHHmmss')"
.\scripts\run-kind-cicd-gate.ps1 -Version $version -ClusterName streamhub-cicd
```

脚本依次完成：

1. 检查工作区、服务边界、Schema、网关、Kubernetes 和 CI/CD 契约；
2. 分别测试 user、content、social 三个业务服务；
3. 执行 TypeScript 类型检查；
4. 构建 user、content、social、Gateway、前端共 5 个版本镜像；
5. 启动 Compose 微服务测试栈；
6. 从 Gateway 巡检 85 个公开接口；
7. 运行 3 个 Playwright 场景，覆盖 UC01～UC08；
8. 停止临时 Compose 容器但保留数据卷；
9. 创建或复用 `streamhub-cicd` Kind 集群；
10. 载入版本镜像，部署 PostgreSQL、MinIO、3 个业务服务、Gateway、HPA 和 Metrics Server；
11. 检查日志、健康、就绪、版本和 Kubernetes 资源；
12. 保存成功或失败证据。

为避免多个 Kubernetes 控制面抢占 CPU 和内存，脚本会临时暂停所有正在运行的 Kind control-plane，并记录精确名单；门禁结束后逐个恢复。不会删除集群或数据。

### 6.2 成功标准

终端必须同时出现：

```text
PUBLIC_API_SMOKE=PASS total=85 passed=85 failed=0 http=83 websocket=2
3 passed
LOCAL_MICROSERVICES_GATE=PASS
MICROSERVICES_HEALTH_CHECK=PASS
KIND_CICD_GATE=PASS
```

没有最后一行 `KIND_CICD_GATE=PASS` 就不能算完整成功。

本机 2026-09-02 最新人工复跑版本 `manual-20260902110259` 的结果：

- 契约/共享测试 85 项通过；
- user、content、social 分别 12、14、13 项通过；
- 公开接口 85/85；
- Playwright 3/3；
- Gateway 与三个业务服务 12 个 health/ready/version 检查通过；
- Kind 中 3 个业务服务、Gateway、PostgreSQL、MinIO 均 Ready；
- `LOCAL_MICROSERVICES_GATE=PASS` 与 `KIND_CICD_GATE=PASS` 同时存在。

对应证据目录：`SE2026-microservices\.ci-results\kind-cicd\manual-20260902110259`。

`SE2026-microservices\.ci-results` 是本机运行产物，已被 Git 忽略，因此从 GitHub clone 后通常看不到上述本机目录；接收的 ZIP 只有在打包者主动保留时才会带上它。无论历史证据是否存在，接收者都应在自己的电脑重新运行门禁，生成属于本机和本次版本的新证据。仓库中随代码保留的课程原始报告位于 `SE2026-microservices\docs\microservices\evidence`。

## 7. 课程四项完整验收流程

### 7.1 第一项：三个业务微服务和数据边界

材料：

- `SE2026-microservices\docs\microservices\service-architecture.md`
- `SE2026-microservices\docs\microservices\service-api-catalog.md`
- `SE2026-microservices\docs\microservices\table-ownership.md`
- `SE2026-microservices\docs\microservices\cross-service-calls.md`
- `SE2026-microservices\docs\microservices\monolith-vs-microservices.md`
- `SE2026-microservices\docs\microservices\version-manifest.json`

运行边界与契约检查：

```powershell
.\.venv-ms\Scripts\python.exe scripts\check_microservices_workspace.py
.\.venv-ms\Scripts\python.exe -m pytest -q tests\microservices shared\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\user-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\content-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\social-service\tests
```

当前参考结果：85、12、14、13 项分别通过。

### 7.2 第二项：自动构建、测试和部署

完整 Kind 门禁已包含本地构建、85 个公开接口、UC01～UC08、版本镜像、部署和观测检查，执行第 6 节命令即可。

现场演示一次“部署失败怎么查”时，先保持本地 Compose 门禁运行：

```powershell
$localVersion = "failure-demo-$(Get-Date -Format 'yyyyMMddHHmmss')"
.\scripts\run-local-microservices-gate.ps1 -Version $localVersion
.\scripts\run-deployment-failure-drill.ps1 -GoodVersion $localVersion
```

正确结果：

```text
DEPLOYMENT_FAILURE_DRILL=EXPECTED_FAILURE
```

这里的 `EXPECTED_FAILURE` 是实验成功：脚本故意使用不存在的不可变镜像标签，保留失败输出，并证明当前正确版本仍在运行。它不会删除容器、数据库或数据卷。

### 7.3 第三项：HPA 自动扩缩容和故障处理

先保证第 6 节 Kind 门禁通过。建议打开三个 PowerShell。

终端 A：

```powershell
.\scripts\run-cloud-native-experiments.ps1
```

终端 B 观察 HPA：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig apply -f k8s\microservices\user-service-hpa.yaml
kubectl --kubeconfig $kubeconfig get hpa user-service -n streamhub-ms -w
```

终端 C 观察 Pod：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms -w
```

正确结果：

- user-service 从 1 个 Pod 扩到 2～4 个，再缩回 1 个；
- 压测记录吞吐量、平均响应、P95 和错误率；
- content-service 停止期间内容接口返回预设 503；
- user-service 和 social-service 健康接口仍为 200；
- content-service 恢复到 1/1 Ready，`/api/live/rooms` 恢复为 200；
- 最后一行是 `CLOUD_NATIVE_EXPERIMENTS=PASS`。

主实验实测：并发 4、244/244 成功、错误率 0%，吞吐量 2.013 req/s，平均 1975.251 ms，P95 3802.347 ms，HPA 1→4→1。高并发 12 过载对照错误率为 78.509%，必须如实保留。

### 7.4 第四项：单体与微服务性能对比

该脚本要求 PowerShell 7：

```powershell
pwsh -NoProfile -File .\scripts\run-performance-comparison.ps1 -Runs 3 -ReadConcurrency 4
```

正确结果：

```text
PERFORMANCE_COMPARISON=PASS
```

脚本在同一台机器、同一 PostgreSQL、同一批数据和同一压力脚本下，对分类列表、最新视频列表、登录分别运行单体和微服务各 3 次，并记录吞吐量、平均响应、P95、错误率、CPU 和内存。

本次实际没有测出微服务更快：三个接口的微服务吞吐量都更低，应用内存约为单体的 2.86～2.91 倍。正确结论是“完成公平对比，但未测出性能提升；微服务收益主要是边界、独立部署、故障隔离和扩缩容”。

## 8. 手工查看真实 Kubernetes 环境

### 8.1 查看节点和 Pod

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig get nodes
kubectl --kubeconfig $kubeconfig get deployments -n streamhub-ms
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms
kubectl --kubeconfig $kubeconfig get services -n streamhub-ms
kubectl --kubeconfig $kubeconfig get hpa -n streamhub-ms
kubectl --kubeconfig $kubeconfig top pods -n streamhub-ms
```

正确结果：

- control-plane 为 `Ready`；
- user、content、social、gateway、postgres、minio Deployment 为 `1/1`；
- 业务 Pod 为 `Running 1/1`；
- `schema-migration` 为 `Completed`；
- 不应出现 `CrashLoopBackOff` 或 `ImagePullBackOff`。

Kind 门禁默认重点部署后端，不提供可直接访问的前端页面和 SRS；网页功能演示使用第 5 节 Compose。这个范围差异是设计选择，不是漏部署业务微服务。

### 8.2 临时访问 Kind Gateway

新开一个终端并保持运行：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig port-forward service/gateway 18100:80 -n streamhub-ms
```

正确输出：

```text
Forwarding from 127.0.0.1:18100 -> 80
Forwarding from [::1]:18100 -> 80
```

再开一个终端：

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:18100/health'
Invoke-RestMethod -Uri 'http://127.0.0.1:18100/ready'
Invoke-RestMethod -Uri 'http://127.0.0.1:18100/version'
Invoke-RestMethod -Uri 'http://127.0.0.1:18100/_services/user/version'
Invoke-RestMethod -Uri 'http://127.0.0.1:18100/_services/content/version'
Invoke-RestMethod -Uri 'http://127.0.0.1:18100/_services/social/version'
```

四个版本号必须与本次 `$version` 一致。完成后在端口转发终端按 `Ctrl+C`，不会停止集群。

### 8.3 日志和事件

```powershell
kubectl --kubeconfig $kubeconfig logs deployment/gateway -n streamhub-ms --tail=100
kubectl --kubeconfig $kubeconfig logs deployment/user-service -n streamhub-ms --tail=100
kubectl --kubeconfig $kubeconfig logs deployment/content-service -n streamhub-ms --tail=100
kubectl --kubeconfig $kubeconfig logs deployment/social-service -n streamhub-ms --tail=100
kubectl --kubeconfig $kubeconfig get events -n streamhub-ms --sort-by=.metadata.creationTimestamp
```

## 9. GitHub Actions 自动 CI/CD

工作流位于 `SE2026-microservices\.github\workflows\ci.yml`，分四层：

1. `contract-tests`：微服务架构、数据边界、接口与流水线契约；
2. `service-tests`：user、content、social Matrix 独立测试；
3. `microservices-regression`：Compose、85 个公开接口、UC01～UC08；
4. `build-deploy`：仅 main push 且前三层通过后执行，制作 Git SHA 镜像、推送 GHCR、部署 Kind、保存诊断。

运行模型：

- Pull Request 到 main：隔离的 `ubuntu-latest`；
- Push 到 main：队友方案整合后的 Linux x64 `self-hosted` Runner；
- 前置门禁失败：镜像发布和部署不会执行；
- JUnit、日志、事件和诊断 Artifact 保留 30 天。

本地 `KIND_CICD_GATE=PASS` 不能自动证明某次远程 GitHub Actions 成功。远程验收必须打开仓库 `Actions → StreamHub Microservices CI/CD`，确认对应提交的 Job 全绿、Runner 在线、Artifact 可下载、GHCR 镜像存在。

## 10. 可选：运行改造前单体版本

仓库保留 `SE2026-microservices\backend` 和 `SE2026-microservices\docker-compose.yml`，用于展示改造前版本和做公平性能对比。

```powershell
Copy-Item .env.example .env
notepad .env
```

把 `SE2026-microservices\.env` 中所有 `CHANGE_ME` 换成本机专用强密码，再启动：

```powershell
docker compose up -d --build --wait --wait-timeout 240
docker compose ps
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health'
Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing
```

安全停止：

```powershell
docker compose down
```

单体测试会重建测试 Schema，只能连接专用 `streamhub_test`。完整安全命令见 `SE2026-microservices\TESTING.md` 第十节。

## 11. 常见问题与排查顺序

### 11.1 Docker 无法启动或拉取镜像

```powershell
docker version
docker pull hello-world
```

- `x509: certificate signed by unknown authority`：通常是代理或证书信任问题；
- `timeout`：通常是 Docker Desktop 到镜像仓库的网络问题；
- 不能直接把这两类问题归因于 Dockerfile。

### 11.2 端口已被占用

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -In 5273,8100,5434,9100,9101,18100
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

不要未经确认删除其他项目的容器或卷。18100 被占用时，结束旧 port-forward，或改用 18101。

### 11.3 Pod 启动失败

```powershell
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms
kubectl --kubeconfig $kubeconfig describe pod <Pod名称> -n streamhub-ms
kubectl --kubeconfig $kubeconfig logs <Pod名称> -n streamhub-ms --previous
kubectl --kubeconfig $kubeconfig get events -n streamhub-ms --sort-by=.metadata.creationTimestamp
```

- `ImagePullBackOff`：查镜像名称、标签和权限；
- `CrashLoopBackOff`：查日志、环境变量和数据库连接；
- `Readiness probe failed`：进程可能已启动但还未准备好服务请求。

### 11.4 E2E 随机超时

```powershell
docker ps --filter 'label=io.x-k8s.kind.role=control-plane' --format '{{.Names}} {{.Status}}'
docker stats --no-stream
```

不要盲目增加 Playwright 超时掩盖 503。先查 `SE2026-microservices\.ci-results\...\service-logs.txt`、Playwright Trace 和网关上游超时。完整 Kind 门禁会临时暂停所有 Kind 控制节点并在结束后恢复。

### 11.5 PowerShell 出现 `>` 提示符

`>` 通常表示 PowerShell 等待续行，不是要复制的命令。不要复制聊天记录里的 `PS ...>` 或 `>>`。按 `Ctrl+C` 退出未完成命令，再复制代码块中的完整命令。

### 11.6 证据目录

| 阶段 | 证据目录 |
| --- | --- |
| 本地微服务门禁 | `SE2026-microservices\.ci-results\microservices-local\<版本>` |
| Kind 完整门禁 | `SE2026-microservices\.ci-results\kind-cicd\<版本>` |
| 部署失败实验 | `SE2026-microservices\.ci-results\deployment-failure-drill\<时间戳>` |
| HPA/故障实验 | `SE2026-microservices\.ci-results\cloud-native\<时间戳>` |
| 性能对比 | `SE2026-microservices\.ci-results\performance\<时间戳>` |

详细排障：`SE2026-microservices\docs\getting-started\README-Testing-Troubleshooting.md`。

## 12. 数据安全和停止规则

| 数据 | 位置 |
| --- | --- |
| 用户、视频元数据、审核状态、评论等 | PostgreSQL 数据卷和三个服务 Schema |
| 用户上传的视频、封面、头像 | MinIO 的 `streamhub-media` Bucket |
| 固定演示素材 | `SE2026-microservices\public\demo-videos`、`SE2026-microservices\public\demo-covers` |
| 测试证据 | `SE2026-microservices\.ci-results` |
| 代码和部署配置 | GitHub/ZIP 中的 `SE2026-microservices` |

MinIO 是对象存储，不是第二个关系数据库。PostgreSQL 保存业务信息和媒体 URL，MinIO 保存媒体文件本体。

不要随便执行：

- `docker compose down -v`：删除 Compose 数据卷；
- `kind delete cluster`：删除 Kind 集群和集群内持久数据；
- 对业务数据库运行测试：单体测试只允许连接 `streamhub_test`；
- 删除 `SE2026-microservices\.ci-results`：会丢失课程原始证据；
- 上传 `.env`、`.env.microservices` 或 Token。

普通 `docker compose down`、停止 port-forward、关闭观察命令不会删除数据。

## 13. 目录导航

| 路径 | 内容 |
| --- | --- |
| `SE2026-microservices\src` | React/TypeScript 前端 |
| `SE2026-microservices\backend` | 改造前单体 FastAPI 后端 |
| `SE2026-microservices\services\user-service` | 用户业务微服务 |
| `SE2026-microservices\services\content-service` | 内容业务微服务 |
| `SE2026-microservices\services\social-service` | 社交与直播业务微服务 |
| `SE2026-microservices\shared` | 服务共享的有限基础能力 |
| `SE2026-microservices\gateway` | Nginx API Gateway |
| `SE2026-microservices\database` | Schema、账号和迁移脚本 |
| `SE2026-microservices\k8s\microservices` | 微服务 Kubernetes 清单 |
| `SE2026-microservices\scripts` | 构建、测试、部署、实验和诊断脚本 |
| `SE2026-microservices\tests\microservices` | 架构、Schema、接口、K8s、CI/CD 契约测试 |
| `SE2026-microservices\e2e` | UC01～UC08 Playwright 测试 |
| `SE2026-microservices\docs\microservices` | 四项课程任务设计、报告和原始证据 |
| `SE2026-microservices\.github\workflows\ci.yml` | GitHub Actions 流水线 |
| `SE2026-microservices\TESTING.md` | 更细的完整测试顺序 |
| `SE2026-microservices\项目说明.md` | 全部课程任务、项目改造、结果和限制 |

## 14. 最终验收清单

- [ ] 工具可用，依赖安装完成，本机配置已生成；
- [ ] Compose 8 个服务启动，网页能登录；
- [ ] 85 个公开接口全部通过；
- [ ] UC01～UC08 的 3 个 E2E 场景全部通过；
- [ ] Kind Node 为 Ready，业务 Pod 为 Running 1/1；
- [ ] 12 个健康、就绪、版本检查通过；
- [ ] `LOCAL_MICROSERVICES_GATE=PASS`；
- [ ] `KIND_CICD_GATE=PASS`；
- [ ] HPA 出现 1→多→1，故障实验出现 503/200/200 并恢复；
- [ ] 性能脚本每个版本每个接口至少运行 3 次；
- [ ] 没有把“本地通过”写成“远程 GitHub Actions 已通过”；
- [ ] 没有在无数据支持时声称“微服务性能提升”。

完成后保留 `SE2026-microservices\.ci-results` 和 `SE2026-microservices\docs\microservices\evidence`，它们是报告和现场答辩的原始证据。

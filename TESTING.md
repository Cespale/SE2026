# StreamHub 从获取代码到课程验收：完整测试过程

这份文档写给第一次接触项目的人。除特别说明外，所有命令都在 **Windows PowerShell** 中执行，并且终端当前位置必须是项目根目录。

测试不是只看网页能不能打开。完整验收分为六层：静态检查、本地微服务全回归、部署失败演练、Kind Kubernetes 部署、云原生实验、单体与微服务性能对比。

## 一、先看安全边界

- 不要执行 `docker compose down -v`。`-v` 会删除 PostgreSQL 和 MinIO 数据卷。
- 不要在有用数据的环境执行 `kind delete cluster`。
- 不要把 `.env`、`.env.microservices`、密码、Token 或私钥提交到 GitHub。
- 后端单体测试只允许连接专用的 `streamhub_test` 数据库，不能连接保存业务数据的数据库。
- 性能结果只能按实际测量结果描述；微服务更慢也属于有效实验，不能没有证据就写“性能提升”。
- 每次测试使用新的不可变版本号，不能使用 `latest`。

## 二、准备一台新电脑

### 1. 安装工具

需要：

- Git
- Docker Desktop，并启用 Linux containers
- Python 3.11 或兼容版本
- Node.js 22
- PowerShell 7（性能对比脚本需要；其他主要脚本兼容 Windows PowerShell 5.1）
- Git for Windows（提供 Git Bash）
- `kubectl` 和 `kind`

在终端逐项检查：

```powershell
git --version
docker version
docker compose version
python --version
node --version
npm --version
pwsh --version
kubectl version --client
kind version
```

正确结果：每条命令都显示版本，不出现“无法识别命令”；Docker 同时显示 Client 和 Server。Docker Desktop 建议分配至少 4 个 CPU、8 GB 内存和 12 GB 可用磁盘空间。

### 2. 模拟从 GitHub 获取代码

真实新电脑执行：

```powershell
git clone https://github.com/Cespale/SE2026.git
Set-Location SE2026
```

如果代码已经在本机，不必再次 clone，只需进入项目根目录：

```powershell
Set-Location 'C:\你的路径\SE2026-microservices'
```

确认位置正确：

```powershell
Get-ChildItem README.md, package.json, docker-compose.microservices.yml, scripts
```

正确结果：四个目标都能找到。

### 3. 安装测试依赖

```powershell
python -m venv .venv-ms
.\.venv-ms\Scripts\python.exe -m pip install --upgrade pip
.\.venv-ms\Scripts\python.exe -m pip install -r requirements-microservices-test.txt
npm ci
npx playwright install chromium
.\scripts\init-microservices-env.ps1
```

正确结果：命令正常结束，根目录出现 `.venv-ms` 和 `.env.microservices`。`.env.microservices` 是本机配置，不应提交。

## 三、推荐测试顺序

| 顺序 | 测试 | 证明什么 | 最终标志 |
| --- | --- | --- | --- |
| 1 | 快速静态检查 | 架构、测试、前端依赖和代码可构建 | 所有命令退出码为 0 |
| 2 | 本地微服务全回归 | 三个业务服务、85 个公开 API、UC01–UC08 | `LOCAL_MICROSERVICES_GATE=PASS` |
| 3 | 部署失败演练 | 能定位错误镜像且线上服务不受影响 | `EXPECTED_FAILURE` |
| 4 | Kind CI/CD 门禁 | 镜像可部署到本机 Kubernetes | `KIND_CICD_GATE=PASS` |
| 5 | HPA 与故障处理 | 自动扩缩容、服务隔离和恢复 | `CLOUD_NATIVE_EXPERIMENTS=PASS` |
| 6 | 性能对比 | 同机、同数据、同脚本、每版至少 3 次 | `PERFORMANCE_COMPARISON=PASS` |

前五层建议连续执行。第 2 层结束后立即做第 3 层，因为失败演练需要正在运行的本地微服务和刚制作的版本镜像。第 4 层会重新执行完整本地门禁，然后把微服务部署到 Kind。

## 四、第一层：快速静态检查

在项目根目录依次执行：

```powershell
.\.venv-ms\Scripts\python.exe scripts\check_microservices_workspace.py
.\.venv-ms\Scripts\python.exe -m pytest -q tests\microservices shared\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\user-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\content-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q services\social-service\tests
.\.venv-ms\Scripts\python.exe -m pytest -q tests\microservices\test_ci_cd_contract.py
npm audit --registry=https://registry.npmjs.org
npm run typecheck
npm run build
.\.venv-ms\Scripts\python.exe scripts\test_point_report.py --min-total 200 --min-e2e 60 --output .ci-results\test-points.md
```

当前版本的参考正确结果：

- 架构/共享契约：85 项通过。
- user、content、social 三个业务服务：分别 12、14、13 项通过。
- CI/CD 契约：17 项通过。
- `npm audit`：0 个漏洞。
- TypeScript 检查成功；Webpack 显示 `compiled successfully`，没有 warning。
- 测试点报告总计 227：单元 60、API/集成 107、E2E 60、失败/异常路径 29。

这些数字是当前代码版本的基线。以后若有意增加测试，数量可以增加；无代码变更却减少时必须调查。

## 五、第二层：本地微服务全回归

先创建本次唯一版本号，再运行一键门禁：

```powershell
$testVersion = "manual-$(Get-Date -Format 'yyyyMMddHHmmss')"
.\scripts\run-local-microservices-gate.ps1 -Version $testVersion
```

首次构建会下载镜像，时间较长。不要因为一段时间没有新文字就关闭终端。

正确结果应同时满足：

- 85/85 个公开 API 通过。
- Playwright 显示 3 个场景通过，这 3 个场景共同覆盖 UC01–UC08。
- 最后一行包含 `LOCAL_MICROSERVICES_GATE=PASS`。
- 浏览器可打开前端 `http://127.0.0.1:5273`。
- Gateway 健康、就绪、版本接口可访问：

```powershell
Invoke-RestMethod http://127.0.0.1:8100/health
Invoke-RestMethod http://127.0.0.1:8100/ready
Invoke-RestMethod http://127.0.0.1:8100/version
docker compose -f docker-compose.microservices.yml --env-file .env.microservices ps
```

`ps` 中业务容器应为 `running` 或 `healthy`。证据保存在 `.ci-results\microservices-local\<版本号>\`，主要文件是：

- `public-api.json` / `public-api.xml`：85 个公开接口。
- `e2e.xml` 和 `playwright-artifacts`：UC01–UC08 端到端回归。
- `user-service.xml`、`content-service.xml`、`social-service.xml`：服务独立测试。
- `probes.json`：健康、就绪、版本接口。
- `result.txt`：本层最终结果。

查看日志：

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 gateway
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 user-service
```

## 六、第三层：受控部署失败演练

保持上一层服务运行，在同一个终端继续：

```powershell
.\scripts\run-deployment-failure-drill.ps1 -GoodVersion $testVersion
```

正确结果是：

```text
DEPLOYMENT_FAILURE_DRILL=EXPECTED_FAILURE
```

这里的 `EXPECTED_FAILURE` 是实验成功，不是项目坏了。脚本故意请求一个不存在且禁止自动拉取的镜像，证明能够定位“不可变镜像标签不存在”，同时验证当前 user-service 版本仍然可用。它不停止容器、不修改数据库、不删除数据卷。

证据位于 `.ci-results\deployment-failure-drill\<时间戳>\`：

- `deploy-attempt.txt`：部署失败原始输出。
- `missing-image-inspect.txt`：错误镜像不存在。
- `good-image-inspect.txt`：正确镜像存在。
- `result.json` / `report.md`：根因、处理方案和当前运行版本。

## 七、第四层：Docker + Kind Kubernetes CI/CD 门禁

运行：

```powershell
$kindVersion = "kind-manual-$(Get-Date -Format 'yyyyMMddHHmmss')"
.\scripts\run-kind-cicd-gate.ps1 -Version $kindVersion
```

脚本会重新完成本地测试、构建镜像、停止本地微服务测试栈、创建/更新 Kind 环境、加载镜像、部署并检查健康/就绪/版本。正确结果包含：

```text
LOCAL_MICROSERVICES_GATE=PASS
MICROSERVICES_HEALTH_CHECK=PASS
KIND_CICD_GATE=PASS
```

检查真实 Kubernetes 环境：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig get nodes
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms
kubectl --kubeconfig $kubeconfig get deployments -n streamhub-ms
kubectl --kubeconfig $kubeconfig get services -n streamhub-ms
kubectl --kubeconfig $kubeconfig logs deployment/user-service -n streamhub-ms --tail=100
```

正确结果：节点为 `Ready`；Pod 为 `Running` 且就绪列为 `1/1`；user、content、social 和 gateway Deployment 的可用副本符合期望。Kind 门禁证据位于 `.ci-results\kind-cicd\<版本号>\`。

若要从浏览器/本机直接访问 Kind Gateway，在一个新终端保持下面命令运行：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig port-forward service/gateway 18100:80 -n streamhub-ms
```

然后另一个终端执行：

```powershell
Invoke-RestMethod http://127.0.0.1:18100/health
Invoke-RestMethod http://127.0.0.1:18100/ready
Invoke-RestMethod http://127.0.0.1:18100/version
```

完成后可按 `Ctrl+C` 只停止端口转发，不会停止 Kubernetes 服务。

## 八、第五层：HPA 自动扩缩容和故障处理

确保上一层 Kind 门禁已通过。为了现场看见 Pod 数量变化，准备三个终端。先启动终端 2 和终端 3 的观察命令，最后才在终端 1 启动实验。

终端 2 观察 HPA：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig apply -f k8s\microservices\user-service-hpa.yaml
kubectl --kubeconfig $kubeconfig get hpa user-service -n streamhub-ms -w
```

终端 3 观察 Pod：

```powershell
$kubeconfig = '.ci-results\cloud-native\kind-lab-kubeconfig'
kubectl --kubeconfig $kubeconfig get pods -n streamhub-ms -w
```

终端 1 运行实验：

```powershell
.\scripts\run-cloud-native-experiments.ps1
```

不要把 HPA 和 Pod 合并成一个 `get hpa,pods -w` 命令；分开观察更清楚，也避免资源类型输出混乱。

正确结果：

- HPA 完整变化为 **1→2–4→1**（基线 1 个、压力下扩容、压力下降后缩回 1 个）。
- 压力前 user-service 为 1 个副本。
- 压力升高后扩到 2–4 个副本。
- 压力结束并经过稳定窗口后回到 1 个副本。
- 压测结果记录吞吐量、平均响应时间、P95 响应时间和错误率。
- 停止 content-service 后，依赖它的接口返回预设 503；user-service、social-service 仍返回 200，没有级联崩溃。
- content-service 被恢复并重新就绪；`/api/live/rooms` 再次返回 200。
- 终端 1 最后一行包含 `CLOUD_NATIVE_EXPERIMENTS=PASS`。

证据位于 `.ci-results\cloud-native\<时间戳>\`：

- `hpa-timeline.csv`：扩缩容时间线。
- `load-results.json`：吞吐量、平均/P95、错误率。
- `fault-results.json`：故障隔离结果。
- `content-recovery-results.json`：依赖服务恢复后的 200 证据。
- `experiment-summary.json`：本次实验汇总。

终端 2、3 看完后按 `Ctrl+C` 停止观察即可，不会删除环境。

## 九、第六层：单体与微服务性能对比

公平性要求：同一台机器、同一份数据、同一份压力脚本、相同并发；单体和微服务各至少运行 3 次。测试时不要同时下载大文件、运行其他压测或启动无关重型容器。

该脚本需要 **PowerShell 7**。在项目根目录运行：

```powershell
pwsh -NoProfile -File .\scripts\run-performance-comparison.ps1 -Runs 3 -ReadConcurrency 4
```

课程主结果使用 `ReadConcurrency 4`。默认高并发参数主要用于观察过载，不应用来替代公平的主对比。

正确结果：最后一行包含 `PERFORMANCE_COMPARISON=PASS`。证据位于 `.ci-results\performance\<时间戳>\`，其中应包含原始多轮结果、汇总数据和报告。检查三类主要接口：分类列表、最新视频列表、登录；记录并发数、吞吐量、平均响应时间、P95、错误率、CPU 和内存。

结论必须按数据写，例如“微服务 P95 增加，可能来自 Gateway 和跨服务调用开销”。只有测量值确实更好时才能写“性能提升”。

## 十、可选：验证改造前的单体版本

这一步用于证明“改造前代码仍可运行”，不是微服务门禁的替代品。

### 1. 启动单体 Compose

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d --build --wait --wait-timeout 240
docker compose ps
```

先把 `.env` 中所有 `CHANGE_ME` 换成仅用于本机的强密码。如果端口被另一份 StreamHub 占用，按根目录 README 修改 `*_HOST_PORT`。默认情况下验证：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-WebRequest http://127.0.0.1:5173 -UseBasicParsing
```

### 2. 安全运行单体后端测试

下列测试会重建测试数据库中的 Schema，所以必须先创建独立的 `streamhub_test`，绝不能把 `DATABASE_URL` 指向业务数据库：

```powershell
$postgresPasswordLine = Get-Content .env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' } | Select-Object -First 1
$postgresPassword = (($postgresPasswordLine -replace '^POSTGRES_PASSWORD=', '').Trim()).Trim('"').Trim("'")
$postgresPort = '5433'
$postgresPortLine = Get-Content .env | Where-Object { $_ -match '^POSTGRES_HOST_PORT=' } | Select-Object -First 1
if ($postgresPortLine) { $postgresPort = ($postgresPortLine -replace '^POSTGRES_HOST_PORT=', '').Trim() }
$testDbExists = (docker compose exec -T postgres psql -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='streamhub_test'" | Out-String).Trim()
if ($testDbExists -ne '1') { docker compose exec -T postgres psql -U postgres -d postgres -c 'CREATE DATABASE streamhub_test' }
$encodedPassword = [Uri]::EscapeDataString($postgresPassword)
$env:DATABASE_URL = "postgresql+psycopg2://postgres:${encodedPassword}@127.0.0.1:${postgresPort}/streamhub_test"
.\.venv-ms\Scripts\python.exe -m pytest backend\tests -q -W error::DeprecationWarning
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

当前正确结果为 38 项通过。若数据库名不是 `streamhub_test`，立即停止，不要继续测试。

普通停止单体环境：

```powershell
docker compose down
```

不要加 `-v`。

## 十一、GitHub Actions 远程 CI/CD 怎么验证

本地全部通过不等于 GitHub 已部署。只有代码实际 push 到 GitHub 后，远程流水线才会运行。

1. 打开 GitHub 仓库的 `Actions`。
2. 选择 `StreamHub Microservices CI/CD`。
3. Pull Request 应完成契约检查、三个业务服务独立测试和完整回归。
4. push 到 `main` 后才继续制作不可变版本镜像、推送 GHCR，并部署到 Kind。Runner 由仓库变量 `USE_SELF_HOSTED` 选择：默认 GitHub 自带 `ubuntu-latest`；设为 `true` 时使用队友的 Linux x64 `self-hosted`。
5. 所有 Job 应为绿色；失败时下载该次运行保留的日志、事件、JUnit 和部署诊断 Artifact。

远程部署默认走 GitHub 自带 runner，无需预配；若设 `USE_SELF_HOSTED=true`，远程部署前必须确认 self-hosted Runner 在线。Runner 的完整配置见 [Kind CI/CD 操作手册](docs/getting-started/README-Kind-CICD.md)。本地脚本成功只能证明代码和部署流程可执行，不能替代“GitHub Runner 在线、权限正确、实际工作流绿色”的远程证据。

## 十二、失败时先去哪里看

| 失败阶段 | 首要证据 |
| --- | --- |
| 架构/契约 | 终端错误，以及 `.ci-results\test-points.md` |
| 本地公开 API | `.ci-results\microservices-local\<版本>\public-api.json` |
| E2E | 同目录 `e2e.xml`、`playwright-artifacts` |
| Compose 启动 | `docker compose ... ps` 和 `docker compose ... logs --tail 200 <服务>` |
| 预期部署失败 | `.ci-results\deployment-failure-drill\<时间戳>` |
| Kind 部署 | `.ci-results\kind-cicd\<版本>` 及其中的 diagnostics |
| HPA/故障恢复 | `.ci-results\cloud-native\<时间戳>` |
| 性能对比 | `.ci-results\performance\<时间戳>` |
| GitHub Actions | 对应运行的 Job 日志与 Artifacts |

更细的排障步骤见 [测试与故障排查](docs/getting-started/README-Testing-Troubleshooting.md)。

## 十三、课程四项要求的最终证据清单

| 课程要求 | 现场操作 | 应提交的证据 |
| --- | --- | --- |
| 至少 3 个业务微服务 | 查看 user/content/social 独立目录、测试和 Deployment | `docs/microservices` 中的服务划分图、接口清单、数据表归属、跨服务说明；单体与微服务两版代码 |
| 自动构建部署和全回归 | 跑本地门禁和 Kind 门禁，查看日志/健康/就绪/版本 | 85/85 API、UC01–UC08、三个服务 JUnit、Kind 诊断、受控部署失败报告 |
| 两项云原生实验 | 三终端观察 HPA；停止依赖服务并恢复 | HPA 1→多→1、压测四指标、故障隔离 503/200/200、恢复 200 |
| 改造前后性能 | PowerShell 7 运行 3 轮公平对比 | 测试条件、每轮原始数据、汇总、CPU/内存、诚实差异解释 |

只有上表四行都有“命令结果 + 原始文件 + 可解释结论”，才算完成课程验收。仓库内已有一次完整验证报告可作为格式参考：[微服务验证报告](docs/microservices/verification-report.md)，但你自己的现场演示仍应重新运行并保存本次时间戳证据。

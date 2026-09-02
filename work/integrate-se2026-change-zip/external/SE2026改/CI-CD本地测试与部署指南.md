# StreamHub CI/CD 本地测试与部署指南

> 本文档是「在**自己的电脑**上完整复现 GitHub Actions 流水线（CI），并完成 Kubernetes 部署（CD）」的操作指导。
> 覆盖：3 个流水线 job 的本地逐条复现、镜像构建/载入、K8s 部署、健康检查，以及实践中踩过的全部坑。
>
> 配套文档：[README.md](README.md)（系统运行与三类测试总纲）、[P5工作记录与使用说明.md](P5工作记录与使用说明.md)（CI/CD 搭建记录）。

---

## 一、CI 流水线长什么样

流水线定义在 [.github/workflows/ci.yml](.github/workflows/ci.yml)，严格按「取代码 → 装依赖 → 编译 → 单测 → 集成 → 镜像 → 部署 → 健康检查」执行，拆成 3 个 job，用 `needs` 串联：

| Job | 名字 | 做什么 | 失败时 |
|---|---|---|---|
| `test-backend` | 1 · 后端单元测试 + 集成测试 | 装依赖 → 契约检查 → 测试点门槛 → pytest 单测/集成 | 流水线停 |
| `test-frontend` | 2 · 前端编译 + 系统测试 | `npm ci` → typecheck → build → Playwright E2E | 流水线停 |
| `build-deploy` | 3 · 版本镜像 + K8s 部署 + 健康检查 | **只有 job1、job2 全绿才执行** → 打镜像 → kind 部署 → 健康检查 | 随测试 |

**本地等价目标**：把 job1、job2、job3 各自的命令，在你机器上逐个跑通即可。

> 镜像版本号用 git 短 SHA，禁止 `latest`。CI 只监听 `main` 分支的 push/PR。

---

## 二、本地环境准备

### 1. 前置条件

| 工具 | 版本 | 用途 |
|---|---|---|
| Python | 3.11（虚拟环境） | 后端测试 |
| Node.js | 20 + npm | 前端编译与 E2E |
| Docker Desktop | 最新 | 容器 / kind 节点 |
| kubectl | 与集群匹配 | K8s 操作 |
| kind | 最新 | 本地单节点集群 |
| PostgreSQL（docker） | postgres:16 | 测试库 |

本项目已就绪的本地环境：`backend/.venv`、`node_modules`、`.env`。

### 2. 准备 `.env`

```bash
# 首次：从模板复制（.env 已被 gitignore，不会提交）
cp .env.example .env        # Windows cmd 用：copy .env.example .env
```

把 `CHANGE_ME` 换成自己的值：

```env
POSTGRES_PASSWORD=123456
SECRET_KEY=随便一串字符
MINIO_ROOT_USER=streamhub
MINIO_ROOT_PASSWORD=随便一串字符
```

> ⚠️ **重要：`.env` 里只能放 `键=值`，绝不能粘贴命令。**
> 曾有人把 `bash scripts/deploy.sh` 误粘贴到某行行尾，导致 `deploy.sh` source `.env` 时无限递归——bash 进程层层 fork，`shell level (1000) too high` 警告刷屏，**内存逼近 100%**（详见第六章坑 1）。

### 3. 启动依赖服务（本地测试用）

后端单测/集成只依赖 PostgreSQL；E2E 额外依赖 MinIO：

```bash
docker compose up -d postgres minio
docker compose ps        # 两个容器 healthy 即可
```

> 端口注意：compose 把 postgres 映射到宿主 **5433**（不是 5432），MinIO 到 9000/9001。

---

## 三、Job 1：后端测试（本地复现）

[conftest.py](backend/tests/conftest.py) 默认连 `postgresql+psycopg2://postgres:123456@127.0.0.1:5433/streamhub_test`。

> ⚠️ **测试库名是 `streamhub_test`，compose 只建了 `streamhub` 一个库**，本地跑前先建库，或显式指定 `DATABASE_URL`：
> ```bash
> # 方式 A：建测试库
> docker exec streamhub-postgres psql -U postgres -c "CREATE DATABASE streamhub_test;"
> # 方式 B：直接指定（conftest 用 setdefault，不会被覆盖）
> export DATABASE_URL=postgresql+psycopg2://postgres:123456@127.0.0.1:5433/streamhub
> ```

### 1) 流水线契约检查
校验 ci.yml 符合任务书要求（3 级测试、镜像不带 latest、部署有门禁等）：

```bash
python scripts/test_ci_contract.py -v
```

### 2) 测试点数量与用例稳定性门槛
统计全部可执行断言，要求 **≥200 个测试点、≥60 个 E2E 点**，且 29 个后端用例 + 3 个 E2E 场景不允许增删：

```bash
python scripts/test_point_report.py --min-total 200 --min-e2e 60 --output .ci-results/backend/test-points.md
```

### 3) 单元测试
```bash
cd backend
python -m pytest -q tests/test_audit_rules_unit.py tests/test_object_storage_unit.py tests/test_security_unit.py
```

### 4) 集成/API 测试
```bash
python -m pytest -q tests/test_live_api.py tests/test_media_storage_api.py tests/test_video_consumption_api.py tests/test_video_flow_api.py
```

> 集成测试会连真实 PostgreSQL 和 MinIO（走对象存储），必须先把第二节第 3 步的服务拉起来。

---

## 四、Job 2：前端编译 + 系统测试（本地复现）

```bash
npm ci                      # 按 lockfile 装依赖
npm run typecheck           # tsc --noEmit
npm run build               # webpack 生产构建
npx playwright install chromium   # 首次装浏览器
npm test                    # = playwright test
```

[playwright.config.ts](playwright.config.ts) 会**自动拉起**后端（uvicorn，端口 8001）和前端（webpack dev，端口 3267），并自动注入 `CORS_ORIGINS`、MinIO 凭据等。所以 `npm test` 前只需要：

- postgres、minio 已 healthy（见第二节第 3 步）
- `.env` 里 `E2E_BACKEND_PYTHON` 指向正确解释器（Windows 默认 `backend/.venv/Scripts/python.exe`）

报告输出到 `reports/e2e-tests.xml`，失败痕迹在 `test-results/`。

---

## 五、Job 3：版本镜像 + K8s 部署 + 健康检查（本地复现）

### 第 0 步：准备 kind 集群

```bash
kind create cluster
```

### 第 1 步：构建镜像

```bash
docker build -f backend/Dockerfile -t streamhub-backend:test .
docker build -f Dockerfile.frontend -t streamhub-frontend:test .
```

### 第 2 步：把镜像载入集群（⚠️ 最容易踩坑）

**只载入自家两个镜像是不够的**，`deploy.sh` 应用的清单里还有 postgres、MinIO 和 SRS（直播推流/播放的媒体服务器）：

```bash
# 全部 5 个都要载入
kind load docker-image streamhub-backend:test
kind load docker-image streamhub-frontend:test
kind load docker-image postgres:16
kind load docker-image quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z
kind load docker-image ossrs/srs:5
```

> ⚠️ **postgres:16 必须本地载入**。kind 节点从 Docker Hub 直接拉 `postgres:16` 大概率 `EOF`/超时失败（国内网络），导致 Pod `ImagePullBackOff`、deploy 卡在 `rollout status` 报 `timed out waiting for the condition`。MinIO 一般能从 quay.io 拉到，但网络不稳时也会挂，一并载入最稳。**SRS（`ossrs/srs:5`）同样来自 Docker Hub，也必须本地载入。**

**方法 A：先直接 `kind load` 全部 5 个（最快，能通则通）**

`postgres:16`、minio 和 srs 都是**多平台镜像**，在 Docker Desktop 上 `kind load` **可能**报 `ctr: content digest ... not found`。没报错就是成功；报错的那几个改用下面的方法 B 单独导入。

**方法 B：`kind load` 报 `content digest ... not found` 时的替代导入**

> **为什么失败**：`kind load` 在节点内执行 `ctr images import --all-platforms --digests`，强制校验多平台 manifest 引用的**所有** layer blob。Docker Desktop `docker save` 导出的多平台 tar 里不含全部平台对应的层，containerd 按 digest 找不到 → 报错。

绕开它，用 `docker save` + `docker cp` + 节点内 `ctr import`（只导入当前可用层）：

```bash
# ── postgres:16 ──
docker save postgres:16 -o /tmp/pg.tar
docker cp /tmp/pg.tar kind-control-plane:/pg.tar
MSYS_NO_PATHCONV=1 docker exec kind-control-plane ctr --namespace=k8s.io images import /pg.tar

# ── MinIO ──
MINIO_IMAGE="quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
docker save ${MINIO_IMAGE} -o /tmp/minio.tar
docker cp /tmp/minio.tar kind-control-plane:/minio.tar
MSYS_NO_PATHCONV=1 docker exec kind-control-plane ctr --namespace=k8s.io images import /minio.tar

# ── SRS（直播媒体服务器，同样多平台）──
SRS_IMAGE="ossrs/srs:5"
docker save ${SRS_IMAGE} -o /tmp/srs.tar
docker cp /tmp/srs.tar kind-control-plane:/srs.tar
MSYS_NO_PATHCONV=1 docker exec kind-control-plane ctr --namespace=k8s.io images import /srs.tar

# ── 验证（用 CRI 视角 crictl，kubelet 认的是这个）──
docker exec kind-control-plane crictl images | grep -E 'postgres|minio|srs'
```

三个关键点：
1. **`MSYS_NO_PATHCONV=1` 必须加**（仅在 Git Bash）——否则 Git Bash 会把 `/pg.tar` 转成 Windows 路径（如 `D:/Tools/Git/pg.tar`），节点内找不到文件。
2. **验证用 `crictl images`**（CRI 视角）而不是 `ctr images list`——kubelet 认 CRI 视图，两者可能不一致。
3. 镜像本地没有就先 `docker pull` 再 save。

> ⚠️ **shell 环境提示**：上面的命令是 **Git Bash** 语法。如果你在 **PowerShell** 里跑，会报「`\tmp` 路径不存在」「不认识 `MSYS_NO_PATHCONV=1`」。两种解决：
> - 项目目录右键 → **Git Bash Here**，再照抄命令（推荐）；
> - 或在 PowerShell 用替代版（无需 `MSYS_NO_PATHCONV=1`，路径用 `$env:TEMP`）：
> ```powershell
> # postgres:16
> docker save postgres:16 -o "$env:TEMP\pg.tar"
> docker cp "$env:TEMP\pg.tar" kind-control-plane:/pg.tar
> docker exec kind-control-plane ctr --namespace=k8s.io images import /pg.tar
>
> # MinIO
> $MINIO_IMAGE = "quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
> docker save $MINIO_IMAGE -o "$env:TEMP\minio.tar"
> docker cp "$env:TEMP\minio.tar" kind-control-plane:/minio.tar
> docker exec kind-control-plane ctr --namespace=k8s.io images import /minio.tar
>
> # SRS（直播媒体服务器）
> $SRS_IMAGE = "ossrs/srs:5"
> docker save $SRS_IMAGE -o "$env:TEMP\srs.tar"
> docker cp "$env:TEMP\srs.tar" kind-control-plane:/srs.tar
> docker exec kind-control-plane ctr --namespace=k8s.io images import /srs.tar
>
> # 验证
> docker exec kind-control-plane crictl images | Select-String "postgres|minio|srs"
> ```

> **导入后 Pod 还卡 `ImagePullBackOff`？** 旧 Pod 不一定自动重试，强制重启让它用本地镜像：
> ```bash
> kubectl -n streamhub rollout restart deploy/streamhub-postgres
> kubectl -n streamhub rollout status deploy/streamhub-postgres --timeout=120s
> ```

### 第 3 步：部署

```bash
export VERSION=test
bash scripts/deploy.sh
```

`deploy.sh` 会：source `.env` → 建 namespace `streamhub` → 生成 Secret/ConfigMap → 逐个应用 [k8s/](k8s/) 五个清单（postgres / minio / backend / frontend / **srs**）→ 等 5 个 Deployment rollout。

### 第 4 步：健康检查

```bash
bash scripts/health-check.sh
```

输出 `==> 全部健康检查通过` 即成功。它会依次 port-forward 并 curl 后端 `/openapi.json`、前端 `/`、前端→后端链路 `/api/health`、MinIO `/minio/health/live`、SRS `/api/v1/versions`。

### 第 5 步：从浏览器访问

Windows 下 kind 的 NodePort(30000) 绑在 Docker 内网节点 IP 上，**宿主机无法直连 `localhost:30000`**，需要端口转发。一键脚本会拉起全部 4 个转发（前端页面 / SRS 推流 / SRS 拉流 / SRS API）：

```bash
bash scripts/port-forward.sh
```

输出 `[OK]` 即全部就绪，随后：
- 浏览器打开 **http://127.0.0.1:13266**
- OBS 服务器填 **rtmp://127.0.0.1:1935/live**，串流密钥填页面「直播中」显示的那个 key
- 直播间的 flv.js 播放器自动走 8080，无需手动配

> ⚠️ **每次重建集群后端口转发全部失效，必须重跑本脚本**——这是最容易漏的一步：页面能开（转发了 13266）但 OBS 推流和浏览器播放连不上（没转 1935/8080）。
>
> 停止转发：`bash scripts/port-forward.sh --stop`。本脚本会自动跳过已被占用的端口（比如你手动转过的），可反复执行。

**不想用脚本时**，手动等价命令如下：

```bash
# ① 前端页面（浏览器访问）
kubectl -n streamhub port-forward svc/streamhub-frontend 13266:3266
# 浏览器打开 http://127.0.0.1:13266

# ② SRS RTMP（OBS 推流端口 1935）
kubectl -n streamhub port-forward svc/streamhub-srs 1935:1935
# OBS 服务器填 rtmp://127.0.0.1:1935/live，串流密钥填页面上的 streamKey

# ③ SRS HTTP-FLV（观众播放端口 8080）
kubectl -n streamhub port-forward svc/streamhub-srs 8080:8080
# 直播间的 flv.js 播放器依赖它

# ④（可选）SRS API，诊断用
kubectl -n streamhub port-forward svc/streamhub-srs 1985:1985
```

> ⚠️ **不开直播功能就不需要 ②③**；但要测「开播」必须有 ②（OBS 才能推上来），要测「观看直播」必须有 ③。
>
> ⚠️ **OBS 的串流密钥必须填页面「直播中」显示的那个 key**（它 = 房间的 `streamKey`，观众拉流的 `pullUrl` 就是按它生成的）。手动改 key 会导致「OBS 推流成功但观众端看不到内容」（详见第六章坑 11）。

---

## 六、踩坑汇总（按破坏力排序）

| # | 现象 | 根因 | 解法 |
|---|---|---|---|
| 1 | `bash: warning: shell level (1000) too high` + **内存逼近 100%** | `.env` 某行被粘贴了 `bash scripts/deploy.sh`，source 时无限递归 fork bash | 删掉 `.env` 里的命令残留，只留 `键=值`；用 `tr -d '\r'` 顺手去 CRLF |
| 2 | 重建集群后部署卡住，postgres Pod `ImagePullBackOff`，报 `timed out waiting for the condition` | 只 load 了自家镜像，postgres:16 从 Docker Hub 拉取失败 | 重建集群后 5 个镜像全部载入（自家 2 个 + postgres/minio/srs）；已拉不动的用 `ctr import`（见第五节第 2 步） |
| 3 | `kind load docker-image` 报 `ctr: content digest ... not found`（postgres/minio/srs 多平台镜像） | `kind load` 在节点内用 `--all-platforms --digests` 导入，强制校验所有平台层，而 Docker Desktop 导出的多平台 tar 不含全部平台的层 | 改 `docker save` + `docker cp` + 节点内 `ctr images import`（只导当前平台）；`MSYS_NO_PATHCONV=1` 防路径转换；用 `crictl images` 验证；导入后 `rollout restart` 让旧 Pod 用本地镜像 |
| 4 | 前端 Pod 健康检查通过，但 `curl localhost:30000` 连不上 | Windows/kind 下 NodePort 在 Docker 内网，宿主机路由不到 | 用 `kubectl port-forward`（健康检查脚本就是这个原理） |
| 5 | 本地 `pytest` 连库失败 | 测试库名应为 `streamhub_test`，compose 只建了 `streamhub`；且端口是 5433 不是 5432 | 建库或导出 `DATABASE_URL`；连接串端口用 5433 |
| 6 | `.env` 是 CRLF 时变量值带 `\r`（如密码尾部） | Windows 换行符被 bash source 时计入值 | `tr -d '\r' < .env > .env.new && mv .env.new .env` |
| 7 | CI 的 `npm test` 报 Missing script | 旧版没加 test 脚本 | 确认 `package.json` 有 `"test": "playwright test"` |
| 8 | 部署后 OBS 推流连不上（`rtmp://127.0.0.1:1935` 连接被拒），只有本地 docker 能用 | k8s 清单漏了直播媒体服务器 SRS（docker-compose 里有 `srs`、k8s 完全没有） | 新增 [k8s/srs.yaml](k8s/srs.yaml)（RTMP 1935 + HTTP-FLV 8080 + API 1985），`deploy.sh`/CI 一并部署；本地 load `ossrs/srs:5` 镜像，并 port-forward `1935`（推流）/`8080`（播放） |
| 9 | 前端页面能打开，但所有 API 请求失败（后端连不上） | 旧版 `src/api.ts` 兜底硬编码 `http://127.0.0.1:8000`，且 k8s 清单未注入 `REACT_APP_API_BASE_URL`；port-forward 模式下宿主机没有 127.0.0.1:8000 在监听 | `src/api.ts` 改为同源兜底（`__STREAMHUB_API_BASE_URL__ || ''`），webpack dev-server 加 `/api`、`/uploads`、`/avatars` 代理到后端；k8s 下页面与后端同源，天然连通 |
| 10 | 前端控制台持续报 `WebSocket connection to 'ws://127.0.0.1:3266/ws' failed: ERR_CONNECTION_REFUSED`（HMR 热更新） | webpack-dev-server 注入给浏览器的 HMR WebSocket 端口默认取 `devServer.port`（3266），与页面实际访问端口（如 port-forward 的 13266）不一致；早期还曾硬编码 `webSocketURL.port=5173` | [webpack.config.js](webpack.config.js) `client.webSocketURL.port` 设为 `0`，客户端会自动跟随页面实际端口（`location.port`）——K8s port-forward / compose / 本地 dev 都适配 |
| 11 | OBS 能连上服务器并推流，但观众端看不到直播内容 | 推流密钥用了「登录用户」的 `stream_key`，观众拉流的 `pullUrl` 却按「房间」的 `stream_key` 生成——两者不一致（种子演示房最典型：用户 key 是后端随机生成的 6 位数字，房间 key 是固定的 `stream_demo_XXX`） | 前端「直播中」页显示推流密钥时以 `existingRoom.streamKey` 为准（与 pullUrl 同源）；新建房间时后端本就用 `user.stream_key`，天然一致 |

---

## 七、停止与清理

按「从轻到重」选择：

| 目的 | 命令 | 数据 |
|---|---|---|
| 暂时停跑，保留数据 | `kubectl -n streamhub scale deploy --all --replicas=0` | 全部保留，`--replicas=1` 即恢复 |
| 只停端口转发 | `bash scripts/port-forward.sh --stop` | 只杀 `port-forward.sh` 拉起的 kubectl，集群不受影响 |
| 卸载应用，保留集群 | `kubectl delete ns streamhub` | ⚠️ postgres/minio 的 PVC 数据会删 |
| 连集群一起删 | `kind delete cluster` | 全部清除（含已导入镜像） |
| 连 Docker 也停 | 退出 Docker Desktop 或 `wsl --shutdown` | kind 数据在 volume 里，重启后通常还在 |

---

## 八、一句话速查

```bash
# 后端测试
docker compose up -d postgres minio
python scripts/test_ci_contract.py -v
python scripts/test_point_report.py --min-total 200 --min-e2e 60 --output .ci-results/backend/test-points.md
cd backend && python -m pytest -q tests/test_audit_rules_unit.py tests/test_object_storage_unit.py tests/test_security_unit.py
python -m pytest -q tests/test_live_api.py tests/test_media_storage_api.py tests/test_video_consumption_api.py tests/test_video_flow_api.py

# 前端 + E2E
npm ci && npm run typecheck && npm run build
npx playwright install chromium && npm test

# K8s 部署
kind create cluster
docker build -f backend/Dockerfile -t streamhub-backend:test .
docker build -f Dockerfile.frontend -t streamhub-frontend:test .
# 自家两个单平台镜像用 kind load
kind load docker-image streamhub-backend:test streamhub-frontend:test
# postgres/minio/srs 多平台镜像：Docker Desktop 上 kind load 会报 content digest not found，改用 tar+ctr
docker save postgres:16 -o /tmp/pg.tar && docker cp /tmp/pg.tar kind-control-plane:/pg.tar
MSYS_NO_PATHCONV=1 docker exec kind-control-plane ctr --namespace=k8s.io images import /pg.tar
MINIO_IMAGE="quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z"
docker save ${MINIO_IMAGE} -o /tmp/minio.tar && docker cp /tmp/minio.tar kind-control-plane:/minio.tar
MSYS_NO_PATHCONV=1 docker exec kind-control-plane ctr --namespace=k8s.io images import /minio.tar
SRS_IMAGE="ossrs/srs:5"
docker save ${SRS_IMAGE} -o /tmp/srs.tar && docker cp /tmp/srs.tar kind-control-plane:/srs.tar
MSYS_NO_PATHCONV=1 docker exec kind-control-plane ctr --namespace=k8s.io images import /srs.tar
VERSION=test bash scripts/deploy.sh
bash scripts/health-check.sh
bash scripts/port-forward.sh              # 一键转发：13266 页面 / 1935 OBS 推流 / 8080 播放 / 1985 诊断；重建集群后必重跑
bash scripts/port-forward.sh --stop       # 停止转发
```

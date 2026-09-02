# StreamHub 交接文档

> **最新入口（2026-08-28）：当前唯一主项目是 `C:\Users\lausu\Desktop\SE2026-main`。请优先阅读文档末尾“2026-08-28 新会话交接”章节；下面较早日期中的路径、测试数字和“最新”字样均为历史快照。**

更新时间：2026-08-24  
项目目录：`C:\Users\lausu\Desktop\大三上学期\大作业\StreamHub`

## 任务目标

完成课程前三项：补齐文档和图；完成可断言的单元、API、E2E 测试；后续完成容器化、CI/CD、Kubernetes 部署。

## 已完成内容

### 业务范围和文档

已按实际代码确认 8 个业务用例：UC01 发现并播放视频、UC02 视频互动、UC03 创作者投稿、UC04 管理员审核、UC05 创作者管理作品、UC06 创建直播间、UC07 进入直播实时互动、UC08 结束直播。

`C:\Users\lausu\Desktop\大三上学期\大作业` 已有：

- `第9组-StreamHub-需求说明书.md`
- `第9组-StreamHub-概要设计说明书.md`
- `第9组-StreamHub-详细设计说明书.md`
- `第9组-StreamHub-交付说明.md`
- `第9组-StreamHub-测试报告.md`
- `第9组-StreamHub-图\`：共 28 张 PNG，含用例图、概念类图、组件图、类图及 UC01—UC08 三层图。
- `第9组-StreamHub-基线检查与追溯表.xlsx`：基线、需求追溯、测试编号三张工作表。
- `第9组-StreamHub基线验收记录.xlsx`：11 条验收项，均已勾选通过。

### 测试

最终结果：14/14 通过，0 失败。

| 类型 | 数量 | 结果 | 证据 |
|---|---:|---|---|
| 单元测试 | 3 | 3/3 通过 | `backend/reports/unit-tests.xml` |
| API 集成测试 | 8 | 8/8 通过 | `backend/reports/all-backend-tests.xml` |
| E2E 测试 | 3 | 3/3 通过 | `reports/e2e-tests.xml` |

后端命令：`cd C:\Users\lausu\Desktop\大三上学期\大作业\StreamHub\backend`，再执行 `.\.venv\Scripts\python.exe -m pytest tests -v --junitxml=reports\all-backend-tests.xml`。

前端命令：`cd C:\Users\lausu\Desktop\大三上学期\大作业\StreamHub`，再执行 `npm run test:e2e`。

E2E：`E2E-TC01-02` 搜索播放评论弹幕；`E2E-TC03-05` 投稿审核结果；`E2E-TC06-08` 直播创建、消息和结束。

### 已修复真实问题

文件：`StreamHub\src\stores\liveStore.ts`。

旧 WebSocket 的异步 `onclose` 会误清空新连接，出现“聊天已连接”但消息无法发送。现有修复必须保留：`if (get().ws === ws) { set({ isConnected: false, ws: null }); }`。

## 当前运行状态

- PostgreSQL Compose 服务 `postgres` 已运行，宿主机端口 `5433`；`streamhub_test` 已创建。
- 后端：`http://127.0.0.1:8000`。
- 前端：`http://127.0.0.1:3266`。
- 账号：`user/user123`、`creator/creator123`、`admin/admin123`。

启动数据库：在项目根目录执行 `docker compose up -d postgres`。

启动后端：在 `backend` 执行 `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000`。

启动前端：在项目根目录执行 `npm run dev`。

`Errno 10048` 表示已有后端占用 8000，不能再启动一个。

## 当前问题

完整 Compose 未跑通，根因是 Docker Desktop 到 Docker Hub 的网络/证书，不是项目 Dockerfile：

- 代理开启时：`x509: certificate signed by unknown authority`。
- 关闭代理后：直连 `registry-1.docker.io:443` 超时。
- 用户已确认 Docker Desktop 是 IPv4 only。

`postgres:16` 已成功拉取；`node:20-alpine` 和 `python:3.11-slim` 未成功拉取，所以完整前后端镜像尚未构建。

后端最终运行有 66 条弃用警告：FastAPI `on_event`、Pydantic `.dict()`。不影响 14 条断言通过。

## 下一步计划

1. 在可访问 Docker Hub 的网络下解决 Docker Desktop 代理/证书/直连，再依次执行 `docker pull node:20-alpine`、`docker pull python:3.11-slim`、`docker compose up --build -d`、`docker compose ps`、`Invoke-RestMethod http://localhost:8000/api/health`。
2. 新建 GitHub Actions：检出、装依赖、后端测试、E2E、构建版本号镜像、推送；测试失败必须阻断后续步骤。
3. 新建 Kubernetes Deployment、Service、ConfigMap/Secret、迁移和测试数据脚本；部署后做健康检查。
4. 若教师强制要求每个业务用例均有独立单元测试，再补 `UNIT-TC01`—`UNIT-TC08`。当前认证单元测试有 3 条，UC01—UC08 均已有 API 和 E2E 覆盖。

## 踩过的坑

- 本地后端依旧依赖 PostgreSQL；`127.0.0.1:5433 connection refused` 是 DB 未运行。
- API WebSocket 首条消息是 `online`，不可假定首条为 `join_ack`。
- Playwright 文本可能重复：审核状态要限定表格行；直播消息要限定“直播间聊天”面板。
- 只清 `localStorage` 不会清 Zustand 内存态；切账号需清 `auth-storage`、`goto`、`reload` 并等待登录按钮。
- Docker TLS 报错先验证代理、证书和直连，不改项目代码、不反复 Compose。

---

# 2026-08-25 新会话交接：SE2026-main 本地启动与 Docker 排障

## 任务目标

让本机目录 `C:\Users\lausu\Desktop\大三上学期\大二小学期\SE2026-main` 的 StreamHub 项目能正常启动；优先跑通本地前后端，Docker 全量启动作为后续目标。

## 已完成内容

- 已检查项目的启动配置：Docker Compose 包含 PostgreSQL、后端、前端和 SRS 流媒体服务；后端本地端口为 8000，前端本地开发地址为 `http://localhost:3266`。
- 已确认新项目目录下目前存在 `backend\.env`、`backend\.venv` 和 `node_modules`。但本次尚未得到一次完整的前后端成功启动结果，因此不要直接当成“项目已跑通”。
- 已定位 `start.bat` 报出 `'StreamHub' is not recognized`、`'er' is not recognized` 等错误的原因：文件是 UTF-8 编码，CMD 按本地代码页错误解析其中的中文输出文字。直接运行 Docker 命令可绕开该脚本问题。
- 已确认 Docker 不能正常从 Docker Hub 拉镜像，且这不是项目 Compose 文件本身的问题：
  - 先是 `x509: certificate signed by unknown authority`；
  - 切到 No proxy 后，变为连接 Docker Hub 的 IPv6 地址超时；
  - `docker pull hello-world` 同样失败，说明在它成功前，完整 Compose 也不会成功。
- 已确认本机已有一个可用的 PostgreSQL 容器 `streamhub-postgres`，状态为 healthy，使用 `postgres:16`，宿主机端口为 5433，数据库为 `streamhub`。它属于旧项目目录 `C:\Users\lausu\Desktop\大三上学期\大作业\StreamHub`。
- 新项目执行 `docker compose up -d postgres` 失败的原因已定位：Compose 固定使用容器名 `streamhub-postgres`，与上述旧项目正在运行的数据库容器重名；不是 PostgreSQL 服务损坏。

## 当前问题

1. Docker Desktop 仍无法直接访问 Docker Hub：即使已选 No proxy，拉取镜像仍会走 IPv6 地址并超时。因此 `ossrs/srs:5` 等未缓存镜像无法下载，不能执行 `docker compose up --build -d` 跑完整容器化系统。
2. 新项目不应再次启动名为 `streamhub-postgres` 的数据库容器；当前应复用旧项目已运行的 PostgreSQL。复用会共享同一份数据库数据。
3. 还需要实际启动本地后端和前端并检查页面/接口，才能确认 `.env` 的数据库连接和依赖安装都正确。

## 下一步计划

1. 先不要执行 `docker compose up -d postgres`，也不要删除旧的 `streamhub-postgres` 容器。
2. 开两个 PowerShell 窗口，启动本地服务：

   后端（在 `C:\Users\lausu\Desktop\大三上学期\大二小学期\SE2026-main\backend`）：

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

   前端（在 `C:\Users\lausu\Desktop\大三上学期\大二小学期\SE2026-main`）：

   ```powershell
   npm run dev
   ```

3. 后端启动后先打开 `http://localhost:8000/docs`；前端启动后打开 `http://localhost:3266`。若后端数据库连接失败，检查 `backend\.env` 是否使用宿主机数据库地址 `127.0.0.1:5433`，且用户名、密码、数据库名与 Compose 中 PostgreSQL 配置一致；不要把 `.env.example` 中的 5432/默认密码直接照搬。
4. Docker 问题先单独验证：每次网络或 Docker 设置调整后，仅执行 `docker pull hello-world`。它成功后，再执行 `docker compose up --build -d`。
5. 若仍然是 IPv6 超时，优先换一个能访问 Docker Hub 的网络（例如手机热点）验证；或按学校/网络环境提供的有效 HTTPS 代理配置 Docker Desktop。不要为了绕过问题关闭 TLS 校验或配置不安全镜像仓库。
6. 若将来必须让新旧两个项目各自拥有独立数据库，再由新会话先修改 Compose 的容器名、端口和数据库卷配置；不要直接删除现有容器或数据卷。

## 踩过的坑

- PowerShell 相对路径要写 `.\.venv\Scripts\python.exe`，不能写成 `..venv\Scripts\python.exe`；后者少了反斜杠，指向的不是当前目录下的虚拟环境。
- Windows 的 `.bat` 文件即使内容看起来正确，也可能因 UTF-8/本地代码页不匹配而被 CMD 误解析。遇到中文提示被当作命令执行时，先怀疑编码；可直接运行脚本里的实际命令，或将批处理另存为 ANSI/GBK。
- `x509` 证书错误和 No proxy 下的 IPv6 超时不是同一种问题：前者偏向证书/代理信任，后者是 Docker Desktop 到 Docker Hub 的网络连通性问题。
- Docker Desktop 的 DNS/IPv6 过滤设置未必能影响“拉取镜像”这条由 Containers Proxy 处理的路径。不能仅因界面显示已过滤 IPv6，就假定 `docker pull` 会改走 IPv4；必须以实际 `docker pull hello-world` 输出为准。
- Compose 使用固定 `container_name` 时，两个不同项目目录也会发生容器名冲突。启动前先查已有容器和端口，决定复用、改名还是另建隔离环境。
- 课程原项目的测试也有一个重要教训：单独执行的 3 个端到端测试可以分别通过，但完整 `npx playwright test` 曾出现第 3 组超时失败。因此“逐个通过”不能写成“整套 E2E 已稳定通过”；提交前必须跑完整命令并据此更新测试报告。

---

# 2026-08-26 新会话交接：三层测试补齐与可交付材料

> **先读本节。**上面 `大作业\StreamHub` 的旧测试数字和旧启动状态是历史记录；本次实际测试源码目录为 `C:\Users\lausu\Desktop\大三上学期\大二小学期\StreamHub`，不要混用两份项目或两个运行时。

## 任务目标

按《软件工程基础实践-2026夏》中的测试要求，完成并留存三类测试材料：

1. 单元测试：关键规则、异常分支、断言。
2. 集成/API 测试：权限、接口、数据库和 WebSocket。
3. 端到端测试：从页面或接口入口完成已确认业务流程。

所有报告和证据均应放在：

`C:\Users\lausu\Desktop\大三上学期\大二小学期\0826测试报告`

用户要求：每完成一类先让其查看，再继续下一类；前一类材料必须保留；每类要有正式报告和一份小白能看懂的白话说明。

## 已完成内容

### 1. 单元测试：审核状态规则

- 目录：`0826测试报告\UNIT-TC04-01-审核状态规则`。
- 测试规则：视频审核只允许 `通过(1)`、`驳回(2)`；`审核中(0)` 和其他非法数字必须被拒绝。
- 代码：
  - 测试：`StreamHub\backend\tests\test_audit_rules_unit.py`。
  - 规则：`StreamHub\backend\app\schemas.py`，`AuditIn.auditStatus` 为 `Literal[1, 2]`。
- 最终单测：1/1 通过；当时后端回归 15/15 通过。后续全量回归已为 18/18 通过。
- 证据和说明：该目录中的 `测试报告.md`、`测试说明.md`、`给小白看的测试说明.md`、`流水线门禁记录.md` 和 `证据\`。

### 2. API / 集成测试：视频审核、权限和数据库

- 目录：`0826测试报告\API-TC04-审核接口集成测试`。
- 测试内容：创作者投稿、管理员通过/驳回、普通用户越权审核、非法审核状态、审核不存在的视频；另有直播创建/结束/消息的 API 覆盖。
- 新增 API 测试：`StreamHub\backend\tests\test_video_flow_api.py:137-187`。
- API 组最终：6/6 通过；当时完整后端回归 17/17 通过，之后已升级为 18/18 通过。
- 使用 `streamhub_test` 测试库；fixture 会重建表，不应污染演示库。
- 做过受控失败：临时去掉状态校验后，非法 `0` 被接受，测试失败且门禁退出 1；已立即恢复生产规则。它是门禁有效性证据，不是最终失败。
- 材料同样完整保存在该目录：正式报告、白话说明、门禁记录和 `证据\`。

### 3. E2E：UC01–UC08 完整业务流程

- 目录：`0826测试报告\E2E-TC01-08-完整业务流程`。
- 有效范围是当前已实现、已确认的 UC01–UC08：看视频、互动、投稿、审核、创作者管理、创建直播、直播聊天、结束直播。
- UC09–UC19 未实现、静态模拟或待教师确认，**不得**写成已覆盖。
- 三条流程：
  - `E2E-TC01-02`：用户搜索、播放视频、评论、视频弹幕。
  - `E2E-TC03-05`：创作者投稿、管理员审核、创作者查看“已通过”。
  - `E2E-TC06-08`：创建直播、观众聊天/弹幕、结束直播后页面显示“已结束”。
- 修复后完整 E2E 连续两轮均为 3/3 通过、0 失败、0 错误：
  - `证据\e2e-post-fix-full-run-1.xml`
  - `证据\e2e-post-fix-full-run-2.xml`
- 后续完整后端回归：18/18 通过、0 失败、0 错误：`证据\backend-regression-after-e2e.xml`。
- 已执行 `npm run typecheck`，通过。

### 本次发现并修复的真实问题

1. **测试运行时指向错项目。**本机 `3266/8000` 是另一份 `SE2026-main`/旧服务，浏览器从 `3266` 调旧 `8000` 被 CORS 拦截；不能把登录失败归因于账号。
2. **E2E 结束直播写死旧后端。**`e2e/streamhub.spec.ts` 原先请求 `8000`，即使 Playwright 启动当前项目 `8001`，该步骤仍会误调旧服务。已改为 `E2E_BACKEND_URL`，最终有效运行真实调用 `8001`。
3. **WebSocket 断线竞态。**初次隔离 E2E 虽 3/3 通过，但后端出现“close 后仍发送 join_ack”ASGI 异常。先在 `backend/tests/test_live_api.py:128-141` 写回归测试复现失败，再在 `backend/app/main.py:951-969` 清理连接阶段断线。修复后两轮 E2E 日志无此异常。
4. **Windows 控制台编码。**Playwright 启动 Uvicorn 时，中文 `print` 在 cp1252 下触发 `UnicodeEncodeError`。`playwright.config.ts` 的后端子进程已设置 `PYTHONIOENCODING=utf-8`。

### E2E 关键运行配置

- `StreamHub\playwright.config.ts:3-56`：E2E 前端 `3267`、后端 `8001`，不复用用户正在运行的 `3266/8000`；JUnit 和 artifacts 由环境变量写到报告目录。
- `StreamHub\src\api.ts:1-6`、`StreamHub\webpack.config.js:103-108`：编译时注入 E2E API 地址；非 E2E 默认仍为 `8000`。
- `StreamHub\e2e\streamhub.spec.ts:3,171-176`：结束直播调用当前 E2E 后端。
- `E2E...\run-e2e-tc01-08-gate.ps1:21-33`：本地门禁。Playwright 非零时输出 `E2E_TEST=FAILED`、`PUBLISH_IMAGE=SKIPPED`、`DEPLOY=SKIPPED` 并以非零退出。

## 当前问题 / 真实边界

1. **CI/CD 尚未搭建，但这不是本次测试失败。**用户明确说明将在下午搭建 CI/CD。当前已经有本地门禁失败记录；没有 GitHub Actions、GitLab CI 或 Jenkins 定义/运行记录，所以不能写“远端镜像发布、部署已被验证阻断”。
2. **E2E 使用演示库 `streamhub`。**每次会新增评论、弹幕、投稿和直播记录。后续若频繁运行，应建设独立 E2E 数据库与清理策略。
3. **维护警告。**最新后端完整回归有 59 个弃用警告：FastAPI `on_event`、Pydantic `.dict()`。不影响 18/18 通过，但后续应迁移 lifespan 和 `model_dump()`。
4. 工作树本来就有用户未提交文件和历史报告，例如 `public.zip`、多份课程文档、旧 `reports/e2e-tests.xml`、根目录 `test-results`。不要使用 reset/checkout/delete 清理；只处理明确授权的文件。

## 下一步计划

### 用户下午搭建 CI/CD 时

1. 新建真实 CI 配置，顺序必须为：依赖安装 → 单元/API 测试 → E2E 测试 → 构建镜像 → 推送镜像 → 部署。
2. 在构建镜像前调用测试门禁，或让每个测试命令失败即退出。失败时后续 build/push/deploy step 必须没有执行。
3. 留两份远端记录：一次全部通过；一次故意失败，证明镜像构建、推送、部署都跳过。
4. 不要把本地 `8000/3266` 当 CI 的服务；CI 应按工作流启动自己的 PostgreSQL、后端和前端。

### 后续交付核验

1. 使用三类目录中的正式报告和白话说明准备答辩材料。
2. 若教师把 UC09–UC19 明确纳入评分，先确认需求和实现，再补测试；不能只补“空壳测试”。
3. 若需要清理 E2E 演示数据，先让用户确认删除范围；不要直接清 `streamhub`。

## 踩过的坑 / 有效方法

- 用户提到多个项目目录或报告目录时，先逐个检查。`SE2026-main`、`StreamHub`、`大作业\StreamHub` 可以同时存在，端口相同不代表源码相同。
- E2E 通过不能只看 JUnit 绿灯；还要确认浏览器请求的后端地址、数据库和服务进程确实属于当前源码。此次错误端口能让测试表面通过却调用旧后端。
- 受控失败应保留，但必须恢复生产代码并重新跑完整测试。不要把受控失败计入最终失败数。
- 完整套件至少连续跑两轮；单独跑每个用例通过，不代表组合后稳定。
- 课程测试材料不仅要有代码，还要有：测试总数/通过/失败/原因/环境、代码地址、原始 JUnit/日志，以及小白说明。

## 本次协作中用户纠正 / 补充的约束

| 修改内容 | 错误归因 | 下次指令建议 |
|---|---|---|
| 开始前必须读取 `HANDOFF.md` 和 `错题本.md` | 信息不足：没有先恢复历史上下文，容易重复劳动或用旧路径 | `开始前先完整读取 HANDOFF.md 和错题本.md，并以最新交接为准。` |
| 不能迎合结论；要区分事实、推测和主观判断，并核验关键数字、人物、路径和运行时 | 判断方法未前置，容易把“测试绿灯”直接等同于“当前项目有效通过” | `先检查错误前提、逻辑跳跃和信息缺失；输出时标注【事实】【推测】【判断】，关键结论给出可复查证据。` |
| 测试结果还可能在 `StreamHub` 报告目录，不能只看一个文件夹 | 信息收集不完整 | `判断测试完成度前，逐个检查我列出的所有项目和报告目录。` |
| 第一类材料必须保留；后续类放进新的子目录 | 交付范围遗漏，不是技术判断错误 | `新增测试只能新增目录和文件，不得覆盖或移动已验收测试材料。` |
| 测试报告必须列出被测、新增和门禁代码地址 | 交付元数据遗漏 | `每份报告必须列：被测代码、新增代码、测试代码、门禁脚本的绝对路径和行号。` |
| 每完成一类先停下给用户审阅 | 阶段顺序遗漏 | `按“单元 → 等我确认 → API → 等我确认 → E2E”推进。` |
| CI/CD 是后续下午任务，不能把尚未搭建的远端流水线误说成当前测试缺陷 | 阶段信息不足；测试结论与未来交付阶段混淆 | `按当前阶段评价：说明未完成的后续工作，但不要把已排期的下一阶段写成当前任务失败。` |
| 三类目录都要有小白说明 | 受众要求遗漏 | `除正式报告外，每类测试额外生成一份非技术读者说明：测什么、为何测、结果和边界。` |

---

## 2026-08-26 提交目录同步（最新）

### 交付目录

- 用户最终提交目录改为：`C:\Users\lausu\Desktop\大三上学期\大二小学期\SE2026-main`。
- 已将当前有效的 `StreamHub` 源码、单元/API/E2E 测试、测试配置、演示视频和 `0826测试报告` **复制并合并**到该目录；原 `StreamHub` 和原报告目录均保留，未删除。
- 提交时以 `SE2026-main` 为准。报告 Markdown 中的代码地址已改为从 `SE2026-main\` 开始，不再引用旧的绝对 `StreamHub` 地址。

### 迁移后重新核验（均在 `SE2026-main` 执行）

- `npm run typecheck`：通过。
- 后端完整回归：18/18 通过、0 失败、0 错误；证据：`SE2026-main\0826测试报告\E2E-TC01-08-完整业务流程\证据\backend-regression-se2026-main.xml`。
- E2E 完整流程连续两轮：各 3/3 通过、0 失败、0 错误；证据：同目录 `e2e-se2026-main-run-1.xml`、`e2e-se2026-main-run-2.xml`。
- 受控门禁失败：将 E2E 后端临时指向不可连接的 `127.0.0.1:9`，得到 1/1 失败，门禁记录 `E2E_TEST=FAILED`、`PUBLISH_IMAGE=SKIPPED`、`DEPLOY=SKIPPED`、退出码 1；证据：`pipeline-se2026-main-controlled-unreachable-backend.log` 和对应 JUnit XML。此为预期失败，不计入最终版本测试失败。

### 迁移后注意

- 目标目录新增 `backend\requirements-test.txt`，用于在 `requirements.txt` 基础上安装 `pytest==9.1.1`、`httpx==0.28.1`；它是重新执行后端测试所需依赖。
- 历史上 `8000` 端口的 CORS 受控失败已不再能复现：迁移后该端口由当前 `SE2026-main` 后端占用，且允许 E2E 前端源。不能沿用旧失败结论，已改用不可连接后端作为无副作用的门禁失败证据。
- 若打包提交，保留 `0826测试报告` 和 `public\demo-videos`；可排除可重装的 `node_modules` 与 `backend\.venv`，以降低压缩包体积。

---

# 2026-08-28 新会话交接：UC09—UC18 三层测试完成与 Windows 门禁修复

> **新会话先读本节，再按需回看上面的历史记录。** 当前唯一主项目是 `C:\Users\lausu\Desktop\SE2026-main`。上文出现的 `大作业\StreamHub`、`大二小学期\StreamHub` 等路径均为历史副本，不要再作为当前源码目录。

## 任务目标

1. 依据根目录 `第9组-StreamHub-业务场景确认与基线验收表.xlsx`，补测原前八个业务以外的 UC09—UC18。
2. 依次完成单元测试、API 集成测试和 E2E 浏览器测试，保留可复跑门禁、正式报告、日志和 JUnit 证据。
3. 用户后续明确取消由助手制作截图：测试可靠通过即可，截图由用户自己完成。
4. 新测试的报告、门禁和证据分别归档到 `0826测试报告` 下的三个新目录；旧 UC01—UC08 测试材料不得覆盖、移动或删除。
5. E2E 必须使用独立测试库，不得清空演示主库；README1 要写清今天的结果和复跑方法。

## 已完成内容

### 1. 今日最终测试结果

| 测试阶段 | 最终结果 | 主要证据 |
| --- | ---: | --- |
| UC09—UC18 单元测试 | 21/21 通过 | `0826测试报告\UNIT-TC09-18-剩余业务规则\证据\unit-tc09-18.xml` |
| UC09—UC18 API 集成测试 | 10/10 通过 | `0826测试报告\API-TC09-18-剩余业务集成测试\证据\api-tc09-18.xml` |
| UC09—UC18 新 E2E | 8/8 通过 | 包含在两轮完整套件 XML 中；每轮均有 `remaining-business.spec.ts` 的 8 条用例 |
| UC01—UC18 完整 E2E 第 1 轮 | 11/11 通过 | `0826测试报告\E2E-TC09-18-剩余业务流程\证据\full-suite-run-1.xml` |
| UC01—UC18 完整 E2E 第 2 轮 | 11/11 通过 | `0826测试报告\E2E-TC09-18-剩余业务流程\证据\full-suite-run-2.xml` |
| 后端最终完整回归 | 50/50 通过 | `0826测试报告\E2E-TC09-18-剩余业务流程\证据\backend-regression.xml` |
| 前端 TypeScript | 通过，退出码 0 | `0826测试报告\E2E-TC09-18-剩余业务流程\证据\frontend-typecheck.log` |

JUnit 已复核：以上最终 XML 均为 0 failures、0 errors。完整 E2E 连续两轮通过，不是把单条成功拼成整套成功。

### 2. 三个今日交付目录

- `0826测试报告\UNIT-TC09-18-剩余业务规则`
- `0826测试报告\API-TC09-18-剩余业务集成测试`
- `0826测试报告\E2E-TC09-18-剩余业务流程`

三个目录内均有门禁脚本、测试报告、测试说明、白话说明和证据。测试源码与生产修复按项目结构放在源码目录，并不位于报告目录：

- 单元测试：`backend\unit_tests\test_remaining_business_rules_unit.py`
- API 测试：`backend\tests\test_remaining_business_api.py`
- E2E 测试：`e2e\remaining-business.spec.ts`
- UC14 并发回归：`backend\tests\test_chat_concurrency.py`
- UC14 生产修复：`backend\app\main.py` 的 `get_or_create_conversation`
- E2E 运行配置：`playwright.config.ts`

### 3. 修复的真实生产缺陷

UC14 双方几乎同时打开私信时，两个请求可能同时判断会话不存在并插入同一用户对，触发 `uq_conversation_pair` 唯一约束，令其中一个请求返回 500。已先增加确定性并发回归，再在 `get_or_create_conversation` 捕获 `IntegrityError`、回滚并读取并发赢家创建的会话。修复后并发回归、后端 50/50 和完整 E2E 两轮均通过。

### 4. 数据库隔离与门禁

- UC09—UC18 单元测试使用 Mock 隔离，不启动 Web 服务，也不访问真实数据库。
- 普通后端启动依赖 `backend\.env` 中的 `DATABASE_URL`；当前 `.env` 已存在，包含 `DATABASE_URL`、`SECRET_KEY`、`CORS_ORIGINS`，不得把密码写入报告或提交到公开仓库。
- API 测试使用 `streamhub_test`，fixture 会验证库名并重建测试库 schema。
- 今日 E2E 门禁会从 `streamhub-postgres` 容器读取现有 PostgreSQL 账号和密码，URL 编码后仅注入当前进程；它创建或重置专用库 `streamhub_e2e_test`，不会重置 `streamhub`。
- 今日三个门禁已修正为 ASCII 源码并通过 Windows PowerShell 5.1 解析；单元/API 门禁还避免了 `$ErrorActionPreference='Stop'` 把 pytest/OpenCV 的原生 stderr 误当终止异常。

复跑命令均从项目根目录执行：

```powershell
& ".\0826测试报告\UNIT-TC09-18-剩余业务规则\run-unit-tc09-18-gate.ps1"
& ".\0826测试报告\API-TC09-18-剩余业务集成测试\run-api-tc09-18-gate.ps1"
& ".\0826测试报告\E2E-TC09-18-剩余业务流程\run-e2e-tc09-18-gate.ps1"
```

其中 E2E 会自行启动 3267/8001，不要提前手动占用这两个端口。完整说明见 `0826测试报告\README1.md` 的“2026-08-28 今日最终测试汇总”。
今日 `run-e2e-tc09-18-gate.ps1` 默认运行新旧完整套件，正确结果是 **11 passed**（其中 `remaining-business.spec.ts` 为新增 8 条，旧 `streamhub.spec.ts` 为 3 条）。

### 5. README1 更新

`0826测试报告\README1.md` 已追加今天的最终结果、三类复跑命令、正确输出、数据库隔离和证据链接。旧 2026-08-27 的 1/1、6/6、3/3 已明确标成历史阶段；旧 `E2E-TC01-08` 的复跑命令增加 `-TestArgs "e2e/streamhub.spec.ts"`，避免新增 spec 后意外执行全部 11 条测试。

## 当前运行状态

以下仅为 2026-08-28 会话结束时的快照；新会话应重新执行端口、容器和目录检查，不能永久沿用：

- `streamhub-postgres`：healthy，宿主机端口 5433。
- 前端 3266：当前有 Node 进程监听。
- 后端 8000：当前有进程监听。
- E2E 专用端口 3267/8001：当前未监听，属于正常状态，门禁运行时临时启动。
- 根目录当前不是 Git 仓库，无法提供分支、未提交修改、未推送提交或 stash 状态。
- 根目录没有 `AGENTS.md`，也没有 `scripts/codex_hook_emulation.py`；本次无需更新代理规则，无法运行 SessionEnd 钩子。

## 当前问题

1. **UC19 仍无可测试定义。**工作簿追溯矩阵出现 UC19，但业务清单没有名称、前置条件、步骤和预期结果；不能猜测补测。
2. **存在历史乱码证据目录，尚未删除。**当前有三个名为 `è¯æ®` 的目录：今日 UNIT 2 个文件、今日 API 2 个文件、旧 `E2E-TC01-08` 12 个调试文件（约 14.8 MB）。这是旧 PowerShell 编码问题留下的重复产物；正确 `证据` 目录仍在。用户未授权删除，因此本次保留。
3. **E2E 报告的截图描述已被后续状态改变。**`E2E-TC09-18-剩余业务流程\测试报告.md` 写的是生成报告时递归审计 0 张图片，但当前 `证据` 目录已有 `img.png`、`img_1.png`、`img_2.png`。推测为用户后来自行截图；若最终交付要求报告与目录现状完全一致，应先向用户确认后更新该段文字。
4. **阶段报告是历史快照。**UNIT 报告仍写 API/E2E 未开始，API 报告仍写 E2E 未开始；这是各阶段生成时的真实状态。当前最终状态以 README1 和本节为准。若要统一最终口径，可在原报告增加“后续阶段已完成”的附注，但不要篡改当时门禁输出。
5. **旧 E2E 门禁有主库与范围风险。**`E2E-TC01-08` 按旧设计使用 `backend\.env` 的演示主库，而且默认不限定 spec 时会执行当前全部 11 条 E2E。不要裸跑旧门禁；README1 中已给出带 `-TestArgs` 的历史复跑命令。未经用户批准，不要改造或删除旧测试。
6. **非阻断维护项仍在。**后端存在 FastAPI `on_event`、Pydantic `.dict()`、SQLAlchemy 查询写法警告；Git LFS 演示视频占位文件会输出 `moov atom not found`。测试断言通过不等于真实 MP4 已成功解码播放。
7. **远程 CI、镜像发布和部署仍未在本次执行。**本次只验证本地门禁，不能写成远程流水线已通过。

## 下一步计划

1. 新会话先完整读取本节、`错题本.md` 和 `0826测试报告\README1.md`，以 `SE2026-main` 为唯一主项目。
2. 若只是复验，直接运行上面的三个今日门禁；E2E 无需提前启动前后端，也不要使用旧 UC01—UC08 门禁代替完整门禁。
3. 向用户确认后再清理三个乱码 `è¯æ®` 目录；删除前逐个核对绝对路径，不能碰正确 `证据` 目录和历史正式报告。
4. 向用户确认 `img*.png` 是否为最终截图；若是，更新 E2E 报告中“0 张图片”的旧描述。截图仍由用户负责，助手不要自动生成。
5. 若教师要求 UC19，先取得完整业务定义再设计单元/API/E2E，不能用推测补齐。
6. 若继续课程交付，再单独建设并实跑远程 CI/CD、镜像与部署；保留一次通过和一次受控失败的远程证据。

## 踩过的坑与有效方法

- 在 `backend` 中启动虚拟环境解释器必须写 `& ".\.venv\Scripts\python.exe"`；`..venv` 少了反斜杠和当前目录前缀，会被 PowerShell 当成不存在的命令。
- 后端导入阶段报“没有找到 DATABASE_URL”不是 Uvicorn 故障。先确认 `backend\.env`，必要时从正在运行的 PostgreSQL 容器读取真实配置；密码必须 URL 编码且不能输出到日志。
- Windows PowerShell 5.1 对 UTF-8 无 BOM 的中文脚本字面量和路径可能乱码甚至 ParserError。门禁尽量使用 ASCII 源码；需要中文目录名时可运行时由 Unicode 码点构造，并用真实 PowerShell 5.1 Parser 做静态检查。
- PowerShell 5.1 在 `$ErrorActionPreference='Stop'` 下可能把原生程序写入 stderr 的非致命信息包装为 `NativeCommandError`。执行 pytest 等原生命令时临时使用 `Continue`、保存 `$LASTEXITCODE`，随后恢复原设置。
- 新增 E2E spec 后，旧脚本中的裸 `npx playwright test` 会把新旧 spec 全部执行。历史复跑必须指定 spec；最终验收应明确是“旧 3 条”还是“完整 11 条”。
- 报告数字必须从最新 JUnit/日志核验，并注明日期和阶段；阶段性 1/1、6/6、3/3 与最终 21/21、10/10、11/11 不矛盾，但不标日期会误导新读者。
- 用户一旦说“截图我自己来”和“直接继续下一个测试”，后续同类阶段应自动沿用，不应继续生成截图或每阶段重复等待确认；只有遇到权限扩大、破坏性操作或真实阻断才暂停。
- “所有材料在三个文件夹”只能指报告、门禁和证据；测试源码与生产修复必须留在正常源码目录。说明范围时要明确，不能为了迎合而说“所有东西都在”。
- 旧测试的核心文件没有被覆盖，但旧 E2E 目录里存在调试时新增的乱码证据目录。回答“之前测试有没有动”前必须做文件审计，并区分“未覆盖旧文件”和“目录中新增了文件”。

## 本次协作中用户纠正 / 更新的内容

| 修改内容 | 错误归因 | 下次指令建议 |
| --- | --- | --- |
| 开始任务前先读 `HANDOFF.md` 和 `错题本.md`，以最新主项目为准 | 信息不足：不恢复历史上下文会误用旧路径和旧测试结论 | `开始前完整读取 HANDOFF.md 和错题本.md；先复述当前主项目、不可触碰目录和最新测试状态，再执行。` |
| 后端命令从错误的 `..venv\Scripts\python.exe` 改为 `.\.venv\Scripts\python.exe` | 判断逻辑问题：没有按当前工作目录解析并验证相对路径 | `给出命令前先确认当前目录并用 Test-Path 验证解释器路径；Windows PowerShell 命令必须可直接复制。` |
| E2E 启动前补齐 `DATABASE_URL`，并要求自动读取现有数据库密码生成配置 | 判断逻辑问题：只给启动命令，未检查应用导入期的必需配置和现有容器真实参数 | `启动前检查 backend/.env 和必需环境变量；缺失时从现有容器安全读取、URL 编码并生成，不显示密码。` |
| 原先要求测试截图，后续改为“截图不用了，我自己来” | 信息不足／需求更新：用户在执行中收窄了交付范围 | `从现在起所有后续测试只交付结果、日志和报告，不生成截图；截图由我负责。` |
| 后续阶段要求“直接做下一个测试”“继续”，不再每类都停下等待 | 判断逻辑问题：没有把最新授权推广到剩余同类任务，仍沿用旧交接中的逐阶段暂停 | `完成当前阶段后自动继续全部剩余测试，不要逐项请求确认；仅在破坏性操作或真实阻断时停下。` |
| Windows PowerShell 运行 E2E 门禁出现乱码和第 17 行 ParserError | 判断逻辑问题：脚本未用用户真实的 Windows PowerShell 5.1 做解析与执行验证 | `交付 .ps1 前必须用 Windows PowerShell 5.1 ParseFile 检查且实际冒烟；门禁源码尽量只含 ASCII。` |
| 新测试的报告、门禁和证据要集中到三个对应报告目录，测试源码仍留在源码目录，且之前的测试材料不能被改坏 | 信息不足（交付范围／需求边界补充）：此前没有明确归档范围与历史材料保护边界 | `新报告、门禁、证据只新增到三个新目录；测试源码按项目结构存放；不得覆盖、移动、删除旧测试；完成后列出新旧目录审计差异。` |
| README1 必须补今天的测试内容和实际运行方法 | 信息不足：原 README1 只有历史阶段说明，缺最终总览与复跑入口 | `收尾时更新 README1：写日期、最终数字、可复制命令、预期输出、数据库隔离和证据链接，并做无上下文读者检查。` |

## 会话收尾状态

### 📋 本次操作回顾

1. 完成 UC09—UC18 单元、API、E2E 测试及全量回归。
2. 修复 UC14 私信会话并发 500，并增加确定性回归测试。
3. 修复 Windows PowerShell 5.1 门禁编码和原生 stderr 兼容问题。
4. 更新 `0826测试报告\README1.md`，并为本次会话追加本交接章节。

### 📊 当前状态

- Git：项目根目录不是 Git 仓库，无法检查分支、未提交或未推送状态。
- Tests：最终证据为单元 21/21、API 10/10、完整 E2E 两轮各 11/11、后端 50/50，均 0 failures、0 errors。
- Build：只执行并通过 TypeScript 类型检查；本次没有执行远程 CI、镜像构建或部署。
- Cleanup：未发现根目录 `temp`、`plan`、`test-results`、`playwright-report`；发现三个历史乱码证据目录，等待用户授权后再删除。

### 💡 下一步建议

优先确认并处理乱码证据目录与 E2E 报告截图描述，再根据课程要求决定是否补 UC19 或进入 CI/CD 与部署阶段。

---

# 2026-08-29 新会话交接：中期检查材料与远程仓库复核

> **本节是当前最新入口，并覆盖上方历史章节中的冲突结论。**本次中期检查只确认 `UC01–UC08`。用户已明确说明：`UC09–UC18` 不需要，也不存在这些正式用例。上方 2026-08-28 章节中关于“补 UC09–UC18 测试”“完整 11 条 E2E”等内容仅是历史会话产物，不得再用于当前中期检查结论。

## 任务目标

1. 仅以远程仓库 `https://github.com/Cespale/SE2026/tree/main` 为验收代码依据，检查前 5 天到中期检查的课程材料是否齐全。
2. 说明单元测试、集成/API 测试、端到端测试分别验证什么，以及它们与 CI/CD 的关系。
3. 核查容器化、流水线、Kubernetes、数据库脚本、测试脚本、部署脚本、镜像版本号和 README 启动说明。
4. 审阅老师即将查看的中期检查 PDF，指出必须修正的内容和现场说明口径。

## 已完成内容

### 1. 当前业务范围已重新冻结

- 当前正式范围只有 `UC01–UC08`：发现/播放视频、视频互动、创作者投稿、管理员审核、创作者作品管理、创建直播间、进入直播并实时互动、结束直播。
- 追溯表当前最新内容只到 `UC08`，这是正常且完整的当前范围；不存在“还欠 UC09–UC18”的结论。
- 用例数量是否足够应以老师确认的业务范围、追溯完整性和可运行证据判断，不能因为历史材料曾出现 18 个编号就要求补到 18 个。

### 2. 三类测试与 CI/CD 的关系已说明

- 单元测试：验证单个规则和异常分支，例如审核状态是否合法。
- 集成/API 测试：验证接口、权限、数据库和多个模块协作。
- E2E 测试：从页面入口验证一个完整用户流程。
- CI/CD 不是“第四种测试”。流水线负责自动依次运行上述测试，再制作镜像、部署 Kubernetes 和健康检查。测试失败时后续部署必须停止。

### 3. 远程仓库交付物已复核

远程仓库中已看到以下类别的材料：

- `.github/workflows/ci.yml`：提交流水线配置。
- `Dockerfile.frontend`、`backend/Dockerfile`、`docker-compose.yml`：前端、后端和数据库容器化；数据库使用官方 PostgreSQL 镜像。
- `docker-init/`、`migrations/`：建表、迁移及初始化相关脚本。
- `k8s/`：前端、后端、PostgreSQL 的 Kubernetes 部署文件。
- `scripts/deploy.sh`、`scripts/health-check.sh`：部署和健康检查脚本。
- `backend/tests/`、`e2e/`、测试门禁脚本：测试代码与脚本。
- `README.md`：包含环境文件、Compose 启动、服务地址、Kubernetes 部署和健康检查说明。
- Git 标签 `monolith-start`：原单体系统基线标签。

流水线使用 Git 提交短 SHA 作为正式镜像版本，不是只使用 `latest`；本地 Docker Compose 截图中出现的 `latest` 属于本地构建标签，不能单独据此判断正式流水线不合格。

截至本节写入时，GitHub API 显示远程 `main` 为提交 `ccca387101f716a1551365308d3cab8991ed6b07`，最新 `StreamHub CI/CD` 运行编号为 `33228415069`，状态 `completed/success`，共 10 次运行。动态状态以后必须重新查询，不能永久沿用本段数字。

### 4. 三个黄色警告已解释

- 三个黄色标记不是三项测试失败；最新流水线结论为成功。
- 警告来自部分 GitHub Actions 仍声明旧的 Node.js 20 内部运行环境，GitHub 将其强制迁移到 Node.js 24。
- 现场先看每个 job 的绿色成功结论；若老师追问，再说明这是 Action 运行时升级提醒，不影响本次测试、构建和部署结果。

### 5. 中期检查 PDF 复核结果

已完整检查：

- `C:\Users\lausu\OneDrive\桌面\文档\xwechat_files\wxid_bt1hgi0a85vm12_3c2a\temp\RWTemp\2026-08\aeb46df8a3572e2e5366105747c17080\中期检查(1).pdf`
- `C:\Users\lausu\OneDrive\桌面\文档\xwechat_files\wxid_bt1hgi0a85vm12_3c2a\temp\RWTemp\2026-08\aeb46df8a3572e2e5366105747c17080\中期检查(2).pdf`

第二版已经把流水线截图换成成功记录，也把 `like_rooms` 改成了 `live_rooms`。整体可用于检查，但仍有以下问题：

1. 第 7 页“内容服务”中间列仍写成 `User Service`，应改为 `Content Service`。
2. 第 8 页“社交服务”中间列仍写成 `User Service`，应改为 `Social Service`。
3. 第 7 页使用 `audit_tags`，第 18 页使用 `audit_logs`，应统一为 `audit_logs`。
4. 微服务章节包含私信、关注、举报、敏感词等当前范围外能力，必须在章节前注明这是“下一阶段目标设计”，不是当前已经实现的 UC。
5. 第二项目前主要展示文件夹缩略图，追溯关系不可读；最好增加一张清晰的 UC01–UC08 追溯表或完成情况表。
6. Docker Desktop 截图可见本地 `latest`；最好补充正式 CI 使用短 SHA 版本号的证据或现场说明。

建议增加的范围说明：

> 本节为下一阶段微服务拆分目标设计，不代表当前功能已经全部实现；本次中期检查确认的业务范围为 UC01–UC08。

## 当前问题

1. `C:\Users\lausu\Desktop\SE2026` 本地检出停在 `b083a95d572712c47dd3ae21b6a525515698ef51`，明显落后于远程 `main`；本次用户又明确要求只看远程仓库。因此不要用这个本地副本判断当前代码是否存在，除非用户以后明确授权同步。
2. 本地 `HANDOFF.md` 和 `错题本.md` 是未跟踪文件；本次只按用户要求更新，不提交、不推送。
3. `中期检查(2).pdf` 的上述文字和图表笔误尚未由助手修改；本次任务只是审阅。
4. 远程 Actions、提交和文件会继续变化。用户说“现在再看”或表示刚上传后，必须重新读取远程 `main` 和最新运行，不能复述缓存结论。
5. 中期材料的微服务部分是设计方案，不能把 API 清单里的规划功能表述成当前已经实现。

## 下一步计划

1. 在老师检查前至少完成四项：修正两个 `User Service`；统一 `audit_logs`；加入 UC01–UC08/下一阶段设计说明；保留最新成功流水线截图。
2. 有时间则补充一张清晰追溯表，以及短 SHA 镜像版本证据。
3. 现场按顺序展示：系统运行 → `monolith-start` 标签 → UC01–UC08 图和追溯表 → 三类测试 → 成功流水线 → Docker/Kubernetes/部署文件 → 微服务目标设计。
4. 若后续继续审查仓库，首先查询远程最新 commit SHA 和 Actions run；不要默认本地副本已经同步。

## 踩过的坑与有效方法

- 历史交接、旧测试目录和微服务规划出现 UC09–UC18，不代表它们仍是正式用例。当前用户明确确认和最新追溯表优先。
- 用户限定“只看仓库”时，范围是远程 GitHub `main`；不能混入桌面旧副本、另一份克隆或历史运行状态。
- GitHub 是动态状态。用户上传新文件后要重新取远程 HEAD、文件树和最新 Actions，不能沿用几分钟前的“没有 README”等结论。
- 黄色 annotation 与失败 conclusion 不同。判断流水线时先看 run/job conclusion，再解释 warning。
- 本地 Compose 镜像的 `latest` 与 CI/Kubernetes 正式镜像标签要分开检查。
- 测试属于 CI 的质量门禁；CI/CD 是编排和交付流程，不应把“CI/CD 测试”误当成另一套独立测试。
- 展示证据要让老师一眼能读懂。文件夹缩略图只能证明文件存在，不能证明 UC01–UC08 的追溯关系完整。
- 微服务接口清单属于下一阶段目标设计时必须明确标注，否则会被理解为当前功能承诺。

## 本次协作中用户纠正 / 更新的内容

| 修改内容 | 错误归因 | 下次指令建议 |
| --- | --- | --- |
| 追溯表最新内容只有 UC01–UC08，后面没有 | 信息不足：历史材料包含更多编号，未先以当前追溯表确认正式范围 | `先以当前追溯表和我确认的用例清单冻结范围；未出现在正式清单中的编号不要当成缺失项。` |
| UC09–UC18 不需要，也不存在这些正式用例 | 判断逻辑问题：把历史测试、旧计划或微服务接口中的功能误当成当前正式用例，没有让最新明确指令覆盖旧交接 | `当前唯一正式业务范围是 UC01–UC08；忽略所有历史 UC09–UC18 结论，不要补测、统计或评价它们。` |
| 后续审查只看远程仓库，不看本地副本 | 信息不足／范围更新：此前同时存在多个本地项目副本，混用会产生过期结论 | `本次只以 https://github.com/Cespale/SE2026 的远程 main 为事实来源；除保存交接外，不使用本地副本判断项目状态。` |
| 用户上传或修改仓库后要求“现在再看” | 信息变化：仓库在会话中继续更新，旧的文件清单和流水线状态已过期 | `每次我说“已经上传/现在再看”，都重新获取远程 HEAD、文件树和最新 Actions，并注明检查时的 commit SHA。` |

## 会话收尾状态

### 📋 本次操作回顾

1. 阅读课程要求、远程仓库结构、CI/CD、Docker/Kubernetes/脚本和 README。
2. 明确当前只有 UC01–UC08，并解释三类测试及其与 CI/CD 的关系。
3. 核查成功流水线与三个非阻断警告。
4. 完整审阅两版中期检查 PDF，给出现场说明口径和剩余修改项。
5. 追加本交接章节，并把新纠错去重录入错题本。

### 📊 当前状态

- Git：本地 `main` 为 `b083a95`，远程 `main` 为 `ccca387`；本地代码落后。`HANDOFF.md`、`错题本.md` 为未跟踪文件。
- Tests：本次没有重新执行本地测试；远程最新 CI/CD 运行 `33228415069` 为成功。
- Build/Deploy：本次没有本地构建或部署；只审查远程流水线记录和仓库文件。
- AGENTS/Hook：仓库中没有 `AGENTS.md`，也没有 `scripts/codex_hook_emulation.py`，无需更新代理规则，无法运行 SessionEnd 钩子。
- Cleanup：没有删除用户文件；本次 PDF 渲染临时文件位于 Codex 会话工作区，不属于项目交付物。

### 💡 下一步建议

优先修正中期 PDF 的服务名称、数据表名称和范围说明；现场以远程成功流水线、UC01–UC08 追溯证据及“微服务是下一阶段目标设计”作为统一口径。

---

# 2026-08-30 新会话交接：MinIO 持久化、CI/CD 重构与 227 测试点本地验收

> **本节是当前最新入口，并覆盖上方历史章节中的冲突结论。** 当前用户授权操作的唯一项目是 `C:\Users\lausu\Desktop\SE2026`，不是 `SE2026-main` 或其他历史副本。正式业务范围仍只有 `UC01–UC08`，不再考虑 `UC09–UC18`。本次用户明确要求所有改动只保留在本地，不提交、不推送；未经新的明确授权，不得执行 commit、push、创建远程运行或修改其他文件。

## 任务目标

1. 解决“持久化媒体不能放在 GitHub”问题：用户上传的视频、封面和头像改存 MinIO，PostgreSQL 只保存业务字段和媒体 URL；旧文件必须保留，并支持换机按 README 启动。
2. 按老师要求重构本地 CI/CD 配置：Push `main` 后依次取代码、装依赖、编译、单元测试、集成测试、E2E、制作版本镜像、部署 Kubernetes、健康检查；失败阻断部署，并保存成功/失败记录。
3. 保持测试用例清单不变，只增加“测试点”；失败路径也计入测试点，前端/E2E 测试点不少于 60，总测试点不少于 200。
4. 在本机逐项完成 Compose、MinIO、数据库、后端、前端、E2E、测试点和流水线配置验收，生成可复查证据。

## 已完成内容

### 1. 媒体持久化改为 MinIO

- `docker-compose.yml` 已包含 PostgreSQL、MinIO、后端、前端和 SRS 五个服务；MinIO 使用固定版本 `quay.io/minio/minio:RELEASE.2025-09-07T16-13-09Z`，数据卷为 `streamhub_minio_data`。
- 新增 `backend/app/object_storage.py`，后端上传、读取视频/封面/头像时使用 MinIO；PostgreSQL 中继续保存 `/uploads/...`、`/avatars/...` 形式的 URL，页面调用方式不变。
- 后端启动迁移是幂等复制：旧 `public/uploads` 和 `public/avatars` 文件会复制到 MinIO，已存在对象会跳过；原本地文件不删除。
- `.gitignore` 已忽略运行时媒体目录；52 个历史头像/封面已从 Git 索引移除，但只是不再被 Git 跟踪。经逐个检查，52/52 文件仍实际存在于本机。
- 用户已真实上传 `beihang2025`，PostgreSQL 中出现：
  - 视频：`/uploads/videos/3931ea83-5e99-47d3-a38b-ba96e9ed59e2_a189cb7e150f2a52.mp4`
  - 封面：`/uploads/covers/3931ea83-5e99-47d3-a38b-ba96e9ed59e2_f45e9b2755ce8c82.jpg`
- 已在 MinIO 中看到对应对象，并验证容器重启后仍存在。早先查询 `/uploads/%` 得到 0 行只是因为当时没有任何真实用户上传，并非迁移失败。
- 新增 README，说明换机启动、服务地址、数据位置、旧数据迁移、Kubernetes 和 CI/CD。不要执行 `docker compose down -v`，否则会删除 PostgreSQL 和 MinIO 数据卷。

### 2. CI/CD 与 Kubernetes 配置完成

- 本地 `.github/workflows/ci.yml` 使用 GitHub Actions，触发条件为 Push/PR 到 `main`。
- 三个任务：
  1. 后端单元测试和集成测试；
  2. 前端类型检查、编译和 Playwright E2E；
  3. 仅在前两项成功且事件是 Push `main` 时制作镜像、部署和健康检查。
- 部署运行位置是 GitHub 提供的临时 `ubuntu-latest` Runner，Runner 内通过 `helm/kind-action` 创建临时 Kind Kubernetes 集群。Kind 是老师允许的工具，但任务结束后集群会销毁，不是长期在线服务器，也没有永久访问链接。
- 前端和后端镜像同时标记为 Git 提交短 SHA（`${GITHUB_SHA:0:8}`），推送到 GHCR；流水线没有用 `latest` 作为正式部署版本。
- Kubernetes 清单：`k8s/postgres.yaml`、`k8s/minio.yaml`、`k8s/backend.yaml`、`k8s/frontend.yaml`。PostgreSQL 和 MinIO 均有 PVC；后端/前端有 readiness probe，MinIO 有 readiness/liveness probe。
- 部署脚本 `scripts/deploy.sh` 会创建 namespace、Secret、数据库初始化 ConfigMap，应用四份清单并等待 Deployment 就绪；`scripts/health-check.sh` 检查后端、前端和 MinIO。PostgreSQL 由自身 `pg_isready` readiness probe 检查。
- `backend/docker-init/01_streamhub_backup.sql` 同时包含建表和 `COPY` 测试/初始数据；后端启动还会执行 `create_all` 和已有字段迁移。
- `build-deploy` 明确依赖两个测试任务；任何依赖安装、编译或测试失败都会停止后续部署。三阶段均通过 `if: always()` 上传日志/JUnit/阶段结果，保留 30 天。
- `scripts/test_ci_contract.py -v`：12/12 通过，覆盖分支触发、三类测试、失败阻断、版本镜像、GHCR、Kind、MinIO、健康检查、记录保留和 Node 24 兼容 Action 版本。

### 3. 数据库和对象存储的正确口径

- 运行时只有一个关系数据库：PostgreSQL 的 `streamhub`，保存用户、标题、审核状态、媒体 URL 等。
- MinIO 保存视频、封面和头像文件本体；MinIO 是对象存储，不是“第二个数据库”。
- 本地自动测试使用独立 PostgreSQL 数据库 `streamhub_test`。更换 PostgreSQL 容器后该库消失，已重新创建。测试 fixture 会反复删除并重建 `public` schema，因此绝不能把本地测试指向演示库 `streamhub`。
- GitHub Actions 的每个测试 job 都有自己一次性的 PostgreSQL Service，数据库名虽为 `streamhub`，但与本地和 Kubernetes 正式数据完全隔离。
- Kubernetes 部署后端连接 `streamhub-postgres:5432/streamhub`，同时连接 `streamhub-minio:9000`；它不会同时连接两个正式 PostgreSQL 数据库。

### 4. 测试用例保持不变，测试点增至 227

- 测试用例基线未增加：后端测试函数 29 个，pytest 实际收集 38 项；E2E 仍为 3 个完整业务场景。
- 测试点按一个用例中的独立输入、断言、权限、状态和失败路径拆分：

| 类别 | 测试点 |
| --- | ---: |
| 单元测试点 | 60 |
| API/集成测试点 | 107 |
| 前端/E2E 测试点 | 60 |
| 其中失败路径测试点 | 29 |
| 总测试点 | 227 |

- 新增 `scripts/test_point_report.py`，门禁要求总测试点至少 200、E2E 至少 60，并校验测试用例基线没有变化。
- `.ci-results/test-points.md` 已生成，脚本输出：`TEST_CASES_BACKEND=29 TEST_CASES_E2E=3 POINTS_UNIT=60 POINTS_API=107 POINTS_E2E=60 POINTS_FAILURE=29 POINTS_TOTAL=227`。

### 5. 本地验收结果

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| Docker Compose | PostgreSQL、MinIO、后端、前端、SRS 共 5 个服务运行；PostgreSQL/MinIO healthy | `docker compose ps` |
| MinIO 真实上传与持久化 | 通过 | PostgreSQL `/uploads/...` URL、MinIO 对象及重启后对象仍存在 |
| 后端完整测试 | 38 passed，50 warnings | `.ci-results/backend-tests.xml` |
| 前端类型检查 | 通过 | `npm run typecheck` 退出码 0 |
| 前端生产构建 | 通过，3 个 bundle-size 警告；`bundle.js` 约 793 KiB | `npm run build` |
| Playwright E2E | 3 passed，约 45.7 秒 | `.ci-results/frontend-e2e.xml` |
| 测试点门禁 | 227，总数与 E2E 下限均通过 | `.ci-results/test-points.md` |
| CI/CD 配置契约 | 12/12 通过 | `scripts/test_ci_contract.py -v` 输出 |
| 暂存内容格式 | 通过 | `git diff --cached --check` 无输出 |

- 三份 `.ci-results` 报告都存在且被 `.gitignore` 忽略，不会混入代码提交。
- 后端 50 条警告主要是 FastAPI `on_event` 与 Pydantic `.dict()` 弃用；前端 3 条警告是 bundle 超出推荐大小；E2E 有依赖的 `util._extend` 弃用提醒。它们不是测试失败，但属于后续维护项。

## 当前运行和 Git 状态

- 当前项目：`C:\Users\lausu\Desktop\SE2026`。
- 分支：`main`；HEAD：`b083a95d572712c47dd3ae21b6a525515698ef51`；跟踪 `origin/main`，当前没有本地提交领先远程。
- 代码改动已经被本地暂存：21 个修改、7 个新增、52 个媒体文件索引删除。`git add` 只改变本地暂存区，不代表提交或上传。
- `HANDOFF.md` 和 `错题本.md` 是未跟踪文件，用户要求保留，但不要自动加入代码提交。
- 当前没有 commit，也没有 push；远程 GitHub 仍看不到本次 MinIO、227 测试点和新版 CI/CD 改动。
- 五个 Compose 服务在会话结束时仍运行：PostgreSQL、MinIO、后端、前端、SRS。MinIO 容器名带临时前缀 `3c40c70a0faa_streamhub-minio`，但 Compose service 是 `minio` 且状态 healthy；需要查询时使用 `docker compose ps -q minio`，不要硬编码容器名。
- `.ci-results` 和 `test-results` 是本地生成证据；本次没有清理。
- 仓库没有 `AGENTS.md`，也没有 `scripts/codex_hook_emulation.py`；无需更新代理规则，无法运行 SessionEnd 钩子。

## 当前问题 / 尚未完成的真实边界

1. **新版远程 CI/CD 尚未真正运行。**本地 12/12 契约检查只能证明配置结构符合预期，不能证明 GitHub Runner、GHCR、Kind 和部署脚本实际成功。因为用户明确不要 Push，所以老师要求的“Push 一次后流水线自动完成”和新版成功/失败远程记录尚未产生。
2. **Kind 是临时部署。**它符合老师允许使用 Kind 的要求，适合课程流水线验收；但流水线结束后集群和 PVC 一起消失。如果老师要求长期在线服务或公开链接，需要另行部署到持久 Kubernetes 环境。
3. **远程运行前需要 GitHub Secrets。**至少配置 `POSTGRES_PASSWORD` 和 `SECRET_KEY`；缺失时 `deploy.sh` 会按 fail-fast 设计停止。
4. **还没有真实新版成功/失败记录。**工作流已配置 `always()` 保存两类记录，但只有实际运行后才会产生 Artifact。最终按老师要求验收时应保留一次成功运行和一次受控失败运行。
5. **技术债警告尚未处理。**FastAPI/Pydantic 弃用和前端 bundle 体积不会阻断当前验收，但不能永久忽略。

## 下一步计划

1. 新会话开始先完整读取本节和 `错题本.md`，复述：当前路径、UC01–UC08、只允许本地、不得自动 commit/push、媒体原件不得删除。
2. 如果用户继续只做本地测试，当前可以停止；不要再执行 Git 操作，也不要清理数据卷或测试证据。
3. 如果用户以后明确授权完成老师的远程 CI/CD 验收：
   - 先审查暂存差异和秘密信息；明确排除 `HANDOFF.md`、`错题本.md`、`.env` 和 `.ci-results`；
   - 配置 GitHub Secrets；
   - 经用户确认后 commit/push；
   - 观察新版 GitHub Actions 全流程，下载 Artifact，确认 SHA 镜像进入 GHCR；
   - 经用户单独确认后制造一次安全、可恢复的受控失败，证明后续部署被阻断，再恢复并保留两类记录。
4. 若老师要求证明 Kubernetes 本身已跑通而又暂时不 Push，可另行得到用户授权后在本地 Kind/Minikube 实跑部署脚本；这不能替代老师要求的 Push 自动触发记录。

## 踩过的坑与有效方法

- Docker 报 `ossrs/srs:5 ... x509` 时，失败发生在拉取镜像阶段，与数据库在本机还是组长机器无关。先看报错点名的镜像/服务，再判断证书、网络或容器冲突。
- 固定容器名会与旧项目冲突。此次旧 `streamhub-postgres` 占名，删除旧容器后 Compose 正常重建；任何时候都不要顺手删除数据卷。
- `localhost:5173` 与 `127.0.0.1:5173` 是不同的 CORS Origin。后端允许前者而未允许后者时，浏览器预检会失败，前端却可能显示“账号或密码错误”。应看控制台 CORS 报错并直接请求后端确认，不要先改账号密码。
- PostgreSQL 只存媒体 URL；查询 `/uploads/%` 为 0 行只能证明当前没有用户上传，不能证明 MinIO 失败。验收应完成一次真实上传，再同时检查数据库 URL、MinIO 对象和重启持久化。
- 更换 PostgreSQL 容器后，本地 `streamhub_test` 需要重新创建。测试 fixture 会 DROP/CREATE schema，绝不能为了省事改连 `streamhub`。
- 测试用例数与测试点数不是一回事。用户明确要求用例不变、失败路径计入、前端测试点增加；不能通过虚构新用例凑到 200。
- PowerShell 粘贴多行命令时，多余的 `>` 会被解释为重定向，曾误生成 `--min-total` 空文件和 `erslausuDesktopSE2026` 输出文件。后续提供可复制命令应优先使用单行；不要复制 `PS C:\...>` 提示符和续行提示符。发现陌生文件先检查内容和大小，再精确删除。
- `git diff --check` 的 `LF will be replaced by CRLF` 是 Windows 换行提醒；是否存在格式错误要看命令退出码及最终是否有实际错误输出。
- `git rm --cached`/索引删除不会删除工作区原件。此次 52 个 `D` 已验证全部仍在本机；解释 Git 状态时必须区分“Git 不再跟踪”和“磁盘文件被删除”。
- MinIO Compose 容器名可能带临时哈希；查询环境和状态用 `docker compose ps -q minio`，不要假设固定名称。
- 本地测试、契约检查和暂存均不等于 commit、push 或远程 CI/CD 跑通。用户说“我自己测试，不推”后必须立即停止向提交/推送方向推进。

## 本次协作中用户纠正 / 更新的内容

| 修改内容 | 错误归因 | 下次指令建议 |
| --- | --- | --- |
| 操作范围从旧远程仓库审查改为只修改本地 `C:\Users\lausu\Desktop\SE2026` | 信息不足／范围更新：上一节以远程 `main` 为唯一事实源，用户随后明确授权了新的本地项目范围 | `本次唯一操作目录是 C:\Users\lausu\Desktop\SE2026；先复述实际路径，禁止混用 SE2026-main、远程 main 或其他副本。` |
| 先只解决媒体数据问题，不得顺带修改其他问题；旧数据必须保留 | 判断逻辑问题：任务存在多个待办时容易主动扩大实现范围，没有把“当前只做数据问题”设成硬边界 | `当前只处理用户上传媒体改存 MinIO；除完成该闭环必需文件外不改其他模块，旧文件只复制不删除。` |
| 写交接时只能修改 `HANDOFF.md` 和 `错题本.md` | 判断逻辑问题：收尾动作可能顺手清理临时文件或更新其他规则文件，超出授权 | `本轮只允许写 HANDOFF.md 与错题本.md；其他文件仅可只读检查，不清理、不格式化、不提交。` |
| 用户问的是“用户上传的视频或照片”存在哪里，不是演示视频在哪里 | 信息不足：没有先区分仓库内演示资源与运行时用户上传内容 | `回答媒体存储前分别列出演示资源、用户上传文件、数据库元数据三类位置，不得混为一谈。` |
| 查询不到 `/uploads/%` 记录是因为当时没有用户上传，不代表迁移失败 | 判断逻辑问题：把空查询结果直接解释为存储链路问题，缺少业务前提核对 | `看到 0 rows 时先确认是否发生过真实上传；用一次真实上传同时验证 DB URL、MinIO 对象和重启持久化。` |
| 测试用例保持不变，只增加测试点；失败测试点必须计入，前端测试点还要增加 | 信息不足／指标口径更新：先按“增加测试数量”理解，没有区分 case 与 point，也遗漏失败路径和前端下限 | `固定后端 29 个测试函数和 E2E 3 个场景；只拆分可验证测试点，失败路径计入，E2E 至少 60，总数至少 200。` |
| 用户说“停止”时必须立即停止当前操作 | 判断逻辑问题：持续排查容易忽略即时停止指令 | `我说“停止”后立即终止当前命令和修改，只报告已发生的状态，等待下一条指令。` |
| 用户没有要推送，只想自己本地测试 | 判断逻辑问题：从“最终检查/暂存”错误推断出用户准备 commit 或 push；暂存不代表授权远程操作 | `所有工作只保留本地；除非我明确说“提交并推送”，不得 commit、push、创建远程运行或继续做推送准备。` |
| 不能把本地 12/12 CI 契约检查说成完整 CI/CD 已跑通 | 判断逻辑问题：把配置静态验证、Compose 本地运行和真实 GitHub Runner/Kind 执行混为一谈 | `完成结论必须分开写：本地配置检查、实际本地运行、远程流水线运行；没有新版 Actions run 和 Artifact 时只能说“已配置，未远程实跑”。` |
| PostgreSQL 测试库与正式库要说明清楚，MinIO不能叫第二数据库 | 信息不足：没有先区分关系数据库、测试环境和对象存储的角色 | `说明数据连接时固定列出：正式 PostgreSQL、隔离测试 PostgreSQL、MinIO 对象存储；明确后端不会同时连接两个正式数据库。` |

## 会话收尾状态

### 📋 本次操作回顾

1. 将用户上传媒体持久化改为 MinIO，并保留旧媒体原件和 URL 兼容。
2. 重构 GitHub Actions、Kind/Kubernetes、版本镜像、失败门禁、Artifact 和部署/健康检查脚本。
3. 在不增加测试用例的前提下把测试点扩充到 227，并完成后端、前端、E2E 和 CI 契约本地验收。
4. 逐项指导用户完成 Compose、MinIO、数据库与测试证据核验。
5. 只更新本交接文档和错题本，没有提交或推送。

### 📊 当前状态

- Git：`main`，HEAD `b083a95`，跟踪 `origin/main`；21 个修改、7 个新增和 52 个索引删除已暂存，2 份交接文档未跟踪；没有新提交和未推送提交。
- Tests：后端 38/38、E2E 3/3、CI 契约 12/12 通过；测试点 227；三份 `.ci-results` 报告存在。
- Build：TypeScript 类型检查和前端生产构建通过，存在非阻断体积警告。
- Deploy：本地 Docker Compose 五个服务运行；新版远程 GitHub Actions/Kind 尚未执行。
- Cleanup：保留 `.ci-results`、`test-results`、本地媒体和数据卷；没有删除临时/历史证据。

### 💡 下一步建议

保持本地现状即可。只有用户明确授权完成远程课程验收时，才审查暂存内容、配置 Secrets、提交推送并取得一次成功和一次受控失败的真实 GitHub Actions 记录。

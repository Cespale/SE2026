# StreamHub 三类测试说明

本目录包含课程要求的三类测试：单元测试、API 集成测试和端到端（E2E）测试。每类测试均由门禁脚本运行：测试失败时脚本以非零退出，并显示 `PUBLISH_IMAGE=SKIPPED`、`DEPLOY=SKIPPED`；测试通过时显示 `PUBLISH_IMAGE=NOT_RUN`、`DEPLOY=NOT_RUN`。目前没有远端 CI/CD，因此这些是本地门禁记录，不代表已经实际发布镜像或部署。

## 运行前准备（首次一次即可）

以下命令均在项目根目录 `SE2026-main` 的 PowerShell 中执行。

1. 启动 PostgreSQL：

```powershell
docker compose up -d postgres
```

若出现 `streamhub-postgres is already in use`，不要删除容器或数据；表示已有同名容器。先运行：

```powershell
docker start streamhub-postgres
```

2. 创建仅供 API 测试使用的测试库：

```powershell
docker compose exec postgres createdb -U postgres streamhub_test
```

如果提示 `database "streamhub_test" already exists`，表示已创建，可继续。API 测试会清空并重建**测试库**的 `public` schema，不会使用主库 `streamhub`。

3. 安装 Python 测试依赖：

```powershell
cd backend
py -3.11 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-test.txt
cd ..
```

4. 安装前端和浏览器测试依赖：

```powershell
npm install
npx playwright install chromium
```

5. E2E 需要连接主库 `streamhub`。当前目录没有 `backend/.env` 时，在运行 E2E 前设置：

```powershell
$env:DATABASE_URL = 'postgresql+psycopg2://postgres:123456@127.0.0.1:5433/streamhub'
$env:SECRET_KEY = 'streamhub-demo-secret-key'
```

> 不需要手动启动前端或后端再运行 E2E。E2E 会自动在 `8001` 启动后端、在 `3267` 启动前端；手动占用这些端口可能导致失败。

## 1. 单元测试：审核状态规则

### 测什么

只测试“管理员审核视频时，审核状态是否合法”这个小规则，不启动 Web 服务、不访问数据库。

- 允许：`1`（通过）、`2`（拒绝）。
- 拒绝：`0`、`3` 等非法状态。
- 每个结果都由断言判断，不是只看程序有没有报错。

### 如何运行

```powershell
cd backend
& "..\0826测试报告\UNIT-TC04-01-审核状态规则\run-unit-tc04-gate.ps1" `
  -Python ".\.venv\Scripts\python.exe" `
  -TestPath "tests\test_audit_rules_unit.py"
```

### 正确结果

终端应显示：`1 passed`、`UNIT_TEST=PASSED`、`PUBLISH_IMAGE=NOT_RUN`、`DEPLOY=NOT_RUN`。

![终端截图-单元测试-20260827.png](UNIT-TC04-01-%E5%AE%A1%E6%A0%B8%E7%8A%B6%E6%80%81%E8%A7%84%E5%88%99/%E8%AF%81%E6%8D%AE/%E7%BB%88%E7%AB%AF%E6%88%AA%E5%9B%BE-%E5%8D%95%E5%85%83%E6%B5%8B%E8%AF%95-20260827.png)![单元测试终端通过证据](<UNIT-TC04-01-审核状态规则/证据/终端截图-单元测试-20260827.png>)

详细报告：[UNIT-TC04-01-审核状态规则/测试报告.md](<UNIT-TC04-01-审核状态规则/测试报告.md>)。

## 2. API 集成测试：投稿、审核、权限与数据库

### 测什么

测试前端以外的完整 HTTP API 调用链：登录认证、创作者投稿、管理员审核、权限校验、请求参数校验，以及 PostgreSQL 数据写入和查询。

6 个用例覆盖：

- 创作者投稿后管理员通过；
- 普通用户不能投稿；
- 管理员拒绝投稿；
- 普通用户不能审核；
- 管理员不能把投稿退回非法的“待审核”状态；
- 管理员审核不存在的视频会得到 `404`。

### 如何运行

```powershell
cd backend
& "..\0826测试报告\API-TC04-审核接口集成测试\run-api-tc04-gate.ps1" `
  -Python ".\.venv\Scripts\python.exe" `
  -TestPath "tests\test_video_flow_api.py"
```

### 正确结果

终端应显示：`6 passed`、`API_TEST=PASSED`、`PUBLISH_IMAGE=NOT_RUN`、`DEPLOY=NOT_RUN`。

![终端截图-API测试-20260827 （1）.png](API-TC04-%E5%AE%A1%E6%A0%B8%E6%8E%A5%E5%8F%A3%E9%9B%86%E6%88%90%E6%B5%8B%E8%AF%95/%E8%AF%81%E6%8D%AE/%E7%BB%88%E7%AB%AF%E6%88%AA%E5%9B%BE-API%E6%B5%8B%E8%AF%95-20260827%20%EF%BC%881%EF%BC%89.png)
![终端截图-API测试-20260827（2）.png](API-TC04-%E5%AE%A1%E6%A0%B8%E6%8E%A5%E5%8F%A3%E9%9B%86%E6%88%90%E6%B5%8B%E8%AF%95/%E8%AF%81%E6%8D%AE/%E7%BB%88%E7%AB%AF%E6%88%AA%E5%9B%BE-API%E6%B5%8B%E8%AF%95-20260827%EF%BC%882%EF%BC%89.png)

详细报告：[API-TC04-审核接口集成测试/测试报告.md](<API-TC04-审核接口集成测试/测试报告.md>)。

## 3. E2E 测试：从浏览器入口完成业务流程

### 测什么

由 Playwright 像真实用户一样操作页面，覆盖 3 条完整流程：

- 普通用户搜索视频，进入详情页，发表评论并发送弹幕；
- 创作者投稿，管理员审核，创作者查看审核结果；
- 创作者创建直播间，观众发送弹幕，最后通过接口结束直播。

它验证页面、前端请求、后端 API、数据库和 WebSocket 的协作结果。

### 如何运行

先确认已完成“运行前准备”第 5 步，然后在项目根目录运行：

```powershell
& ".\0826测试报告\E2E-TC01-08-完整业务流程\run-e2e-tc01-08-gate.ps1"
```

### 正确结果

终端应显示 3 条用例均为 `ok`，最后显示：`3 passed`、`E2E_TEST=PASSED`、`PUBLISH_IMAGE=NOT_RUN`、`DEPLOY=NOT_RUN`。

![终端截图-E2E测试-20260827 （1.1）.png](E2E-TC01-08-%E5%AE%8C%E6%95%B4%E4%B8%9A%E5%8A%A1%E6%B5%81%E7%A8%8B/%E8%AF%81%E6%8D%AE/%E7%BB%88%E7%AB%AF%E6%88%AA%E5%9B%BE-E2E%E6%B5%8B%E8%AF%95-20260827%20%EF%BC%881.1%EF%BC%89.png)![E2E 测试终端通过证据](<E2E-TC01-08-完整业务流程/证据/终端截图-E2E测试-20260827（2.1）.png>)
![终端截图-E2E测试-20260827（2.1）.png](E2E-TC01-08-%E5%AE%8C%E6%95%B4%E4%B8%9A%E5%8A%A1%E6%B5%81%E7%A8%8B/%E8%AF%81%E6%8D%AE/%E7%BB%88%E7%AB%AF%E6%88%AA%E5%9B%BE-E2E%E6%B5%8B%E8%AF%95-20260827%EF%BC%882.1%EF%BC%89.png)

详细报告：[E2E-TC01-08-完整业务流程/测试报告.md](<E2E-TC01-08-完整业务流程/测试报告.md>)。

## 结果怎么看

- 出现 `passed` 和对应的 `*_TEST=PASSED`：本类测试通过。
- 出现 `FAILED`、`SKIPPED` 或 PowerShell 非零退出：测试失败；门禁已阻止后续发布和部署步骤。
- 三类测试的最终记录分别为：单元 `1/1` 通过、API `6/6` 通过、E2E `3/3` 通过。

## 已知边界

- E2E 会向演示主库写入投稿、评论、弹幕和直播记录；重复运行会留下部分演示数据。
- 当前 E2E 确认视频页面存在和业务流程可通，**不证明本地 MP4 已成功解码播放**。`public/demo-videos` 使用 Git LFS；必须取得真实 LFS 视频文件后，才能验证实际播放。

# 第9组-StreamHub 测试报告

测试日期：2026-08-24  
项目：StreamHub

## 1. 执行结果

| 类型 | 测试数 | 通过 | 失败 | 结果文件 |
|---|---:|---:|---:|---|
| 单元测试 | 3 | 3 | 0 | `backend/reports/unit-tests.xml` |
| API 集成测试 | 8 | 8 | 0 | `backend/reports/all-backend-tests.xml` |
| E2E 测试 | 3 | 3 | 0 | `reports/e2e-tests.xml` |
| 合计 | **14** | **14** | **0** | — |

最终执行失败原因：无。所有断言通过。

## 2. 运行环境

- Windows 本机开发环境
- Python 3.11.9、pytest 9.1.1、FastAPI TestClient / WebSocket TestClient
- PostgreSQL 16 Docker 容器；测试数据库：`streamhub_test`，主机端口：5433
- 前端：React + Playwright Chromium 151.0.7922.34
- 本地服务：前端 `http://127.0.0.1:3266`；后端 `http://127.0.0.1:8000`

## 3. 单元测试（3/3）

命令：

```powershell
cd StreamHub\backend
.\.venv\Scripts\python.exe -m pytest tests\test_security_unit.py -v --junitxml=reports\unit-tests.xml
```

| 编号 | 断言内容 | 结果 |
|---|---|---|
| UNIT-TC09-01 | 密码哈希后可验证，错误密码被拒绝 | 通过 |
| UNIT-TC09-02 | 令牌可还原为正确用户 ID | 通过 |
| UNIT-TC09-03 | 无效令牌返回 HTTP 401 | 通过 |

## 4. API 集成测试（8/8）

命令：

```powershell
cd StreamHub\backend
.\.venv\Scripts\python.exe -m pytest tests -v --junitxml=reports\all-backend-tests.xml
```

| 编号 | 覆盖用例 | 断言内容 | 结果 |
|---|---|---|---|
| INT-TC01 | UC01 | 搜索、详情、可播放地址 | 通过 |
| INT-TC02 | UC02 | 点赞、收藏、评论、视频弹幕 | 通过 |
| INT-TC03 | UC03 | 创作者投稿进入审核中 | 通过 |
| INT-TC04 | UC04 | 管理员审核更新视频状态 | 通过 |
| INT-TC05 | UC05 | 创作者只能读取本人作品 | 通过 |
| INT-TC06 | UC06、UC08 | 创建并结束本人直播间 | 通过 |
| INT-TC07 | UC07 | WebSocket 直播消息发送 | 通过 |
| INT-TC08 | UC08 | 普通用户无权结束直播间 | 通过 |

## 5. E2E 测试（3/3）

命令：

```powershell
cd StreamHub
npm run test:e2e
```

| 编号 | 完整业务流程 | 执行时间 | 结果 |
|---|---|---:|---|
| E2E-TC01-02 | 用户搜索、播放视频、发表评论和弹幕 | 4.237 秒 | 通过 |
| E2E-TC03-05 | 创作者投稿，管理员审核，创作者查看结果 | 11.049 秒 | 通过 |
| E2E-TC06-08 | 创建直播、观众发弹幕、接口结束直播 | 18.064 秒 | 通过 |

E2E JUnit 汇总：3 tests、0 failures、0 skipped、0 errors、34.688543 秒。

## 6. 覆盖结论

- UC01—UC08 都有 API 与 E2E 覆盖，主成功流程、关键权限分支和直播 WebSocket 互动已验证。
- 认证与授权由 3 条单元测试覆盖。
- 后端最终全量运行显示 11 passed；其中包含上述 3 条单元测试和 8 条 API 集成测试。
- 本次后端运行有 66 条弃用警告：FastAPI `on_event` 与 Pydantic `.dict()`。它们不影响本次断言结果，后续可改为 `lifespan` 和 `model_dump()`。
- 若教师要求“每个业务用例均有独立单元测试”，可继续将业务状态转换拆为可独立测试的服务函数；当前各用例已由 API 与 E2E 实测通过。

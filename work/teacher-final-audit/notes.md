# 教师终验审计笔记

## 已冻结事实

- 审查目录：`C:\Users\lausu\Desktop\SE2026-microservices`。
- 原项目：`C:\Users\lausu\Desktop\SE2026`，只读。
- 正式用例仅 UC01—UC08；历史 UC09—UC18 不计入当前范围。
- 本地修改获得授权；远程提交、推送和 Actions 运行未获授权。
- PostgreSQL 是关系数据库；MinIO 是对象存储，不能混称第二数据库。

## 已完成核验

- 四项 30 分要求已逐条映射到实现、测试、原始证据、报告和现场演示入口；详见 `docs/microservices/teacher-final-audit.md`。
- user/content/social 三服务职责、表归属、Schema 权限、HTTP/Outbox 边界和失败策略一致；Schema 隔离与源码静态检查通过。
- 公开 API 清单 85/85；WebSocket 不以普通 HTTP 巡检冒充，真实行为由服务测试覆盖；UC01—UC08 两轮 E2E 各 3/3。
- Kind HPA/故障脚本在 Windows PowerShell 5.1 实际跑通：236/236、0 错误、1→4→1、503/200/200；JSON 可由 Python UTF-8 解析。
- 性能报告按同机、同数据、同脚本、每接口每版本 3 轮生成，结论只写“未测出提升”。

## 本轮发现并修复

1. 云原生脚本含 PowerShell 7 专属语法/参数；改为 5.1 兼容实现并加入源代码回归测试。
2. 5.1 下 `Start-Process` 重定向会导致退出码读取不可靠；改用 .NET `ProcessStartInfo`、等待进程后读取退出码。
3. 5.1 `Set-Content -Encoding utf8` 写 JSON 会带 BOM；增加无 BOM 写出，Python UTF-8 解析回归通过。
4. 报告测试计数从旧的 115 修正为当前 130（契约/共享 79、CI 12、服务 39）。
5. 尝试把所有服务放进一个 pytest 进程时复现顶层 `app` 包冲突（content 错导入 user 的模型）；这不是服务运行缺陷，而是测试隔离要求。按 CI Matrix/独立进程重跑五套，79+12+14+13+12 全部通过。
6. 最终本地一键 CI/CD 已用 `teacher-kind-cicd-final2-20260831` 实跑通过；期间修复 PS5 预期非零、MinIO 多平台导入、可选 Deployment、JSON Patch 引号、长 E2E 预算与失败日志留存。
7. 已新增 4 份零基础 README 和安全 `.env` 初始化脚本；隔离读者测试与链接检查通过。

## 保留的风险边界

- 远程 GitHub Actions、GHCR 和远程 Runner Kind 未执行，因为本任务限定本地操作；不得写成远程通过。
- 单机 Kind、HPA 上限 4、并发 12 的高错误率、前端约 635 MiB 镜像和推荐算法行为差异均已写入报告。

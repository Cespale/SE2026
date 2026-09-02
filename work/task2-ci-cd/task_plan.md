# Task Plan: 微服务自动构建、部署与可观测验收

## Goal
在本地副本中完成课程第 2 项所需的微服务 CI/CD、API/E2E 回归、日志/健康/就绪/版本证据和一次可复现的部署失败排查；不提交、不推送。

## Phases
- [x] Phase 1: 审计现有流水线、脚本、测试和运行状态
- [x] Phase 2: 先写并运行失败的 CI/CD 契约测试
- [x] Phase 3: 最小实现微服务构建、测试、制镜像和部署流水线
- [x] Phase 4: 实跑本地成功门禁与受控失败门禁
- [x] Phase 5: 验证 API/E2E、日志、健康、就绪和版本号
- [x] Phase 6: 固化原始证据、正式报告和最终边界

## Key Questions
1. 如何只处理受代码变更影响的业务微服务，同时保证共享代码变更触发全部服务？
2. 如何在不推送的前提下真实证明门禁、镜像和本地部署，而不虚报远端 Actions？
3. 如何制造安全、可恢复且不破坏数据卷的部署失败？

## Decisions Made
- 只修改 `C:\Users\lausu\Desktop\SE2026-microservices`。
- 不执行 commit、push、远程 Actions 或数据卷删除。
- 生产行为代码遵循 RED → GREEN；YAML/文档以契约测试先行。

## Errors Encountered
- RED: `test_ci_cd_contract.py` 7/7 failed as expected because the existing workflow targets the monolith and the new smoke/diagnostic/version contracts do not exist.
- First GREEN run exposed two false-negative string assertions (workflow env and PowerShell native argument splatting); assertions were corrected to inspect semantics. Contract then passed 8/8.
- Legacy `scripts/test_ci_contract.py` still asserted monolith job names; its old run produced 4 failures and 4 errors. It was updated to the microservice pipeline and passed 12/12.
- Final rerun: API 85/85 passed, but E2E TC01 timed out. Preserved Trace showed first navigation took 34.96s because Compose had no frontend healthcheck and started E2E during Webpack startup. A failing contract reproduced the missing healthcheck; Compose now waits for frontend HTTP readiness. Failure evidence remains under the original result directory.
- Final audit command initially used underscore service paths and found no files; corrected to the repository's hyphenated directories. This was a verification-command typo, not a product failure. Corrected runs passed user 12/12, content 14/14, and social 13/13.

## Status
**Complete** - 第 2 项本地实现、运行证据、失败排查和事实边界均已固化；远端 Actions/GHCR/Kind 仍明确标为未实跑。

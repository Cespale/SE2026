# 深度测试问题修复报告

日期：2026-09-01。范围：仅 `C:\Users\lausu\Desktop\SE2026-microservices`，未提交、未推送、未删除数据卷或历史证据。

## 修复结果

| 问题 | 根因 | 修复 |
|---|---|---|
| 云原生实验后出现 API 84/85 | 脚本先输出 PASS，`finally` 才用允许失败方式恢复 content-service | PASS 前强制 scale/rollout，并等待跨服务 `/api/live/rooms` 返回 200；单独保存恢复 JSON |
| HPA 现场观察命令易误用 | HPA 和 Pod 被合并为多资源 watch，且观察对象容易混淆 | 文档改为两个终端分别 watch `user-service` HPA 和全部 Pod，明确故障对象是 `content-service` |
| 复制目录争用 `streamhub-*` 容器名 | 单体 Compose 固定 5 个全局 `container_name` | 删除固定名称，恢复 Compose 项目隔离；7 个宿主机端口全部可由 `.env` 配置 |
| 备用端口下前后端不能正确联动 | 前端 API 基址和后端 CORS 没有跟随自定义端口 | Compose 同时设置 `REACT_APP_API_BASE_URL` 与 `CORS_ORIGINS` |
| 缺少密钥时 Compose 静默使用空值 | 环境变量没有 required 约束 | `POSTGRES_PASSWORD`、`SECRET_KEY` 改为缺失即明确失败 |
| npm 生产依赖含 1 high、3 moderate | Router、ws 等旧依赖；开发服务器又通过 sockjs 引入旧 uuid | Router 升级 7.18.3，webpack-dev-server 升级 6.0.0，Node 基线升级 22；完整 audit 0 |
| 前端生产构建 810 KiB 单包并有 3 个警告 | 所有页面、动画、直播播放器和管理图表同步进入首包 | 路由、布局、鉴权和弹窗按需加载；首包 238906 bytes，构建 0 警告 |
| FastAPI/Pydantic 弃用警告 | 使用 `on_event` 和 Pydantic v1 的 `.dict()` | 改为 lifespan 和 `model_dump()` |
| 根 README 的 CI/CD 描述仍是单体旧流程 | 文档未随三服务流水线更新 | 改为契约→三服务独测→85 API/E2E→SHA 镜像→Kind→诊断的真实流程 |

## 验证结果

| 验证 | 结果 |
|---|---|
| 工作区保护 | PASS |
| 微服务/共享契约 | 82 passed |
| 三服务独立测试 | user 12、content 14、social 13，合计 39 passed |
| 单体后端，弃用警告视为错误 | 38 passed |
| CI 契约脚本 | 12 passed |
| 测试口径 | 后端 29 个测试函数、E2E 3 个场景、227 个测试点，未增删用例 |
| 微服务 Compose | 8 服务运行，需健康检查的服务均 healthy |
| 微服务公开接口 | 85/85，两次云原生实验后复查仍为 85/85 |
| 微服务 UC01–UC08 | 3/3 passed |
| 单体副本备用端口 | 五服务运行；PostgreSQL/MinIO healthy，后端/前端/SRS 探针 200；UC01–UC08 3/3 |
| PowerShell 7 云原生实跑 | 227/227，HPA 1→4→1，故障 503/200/200，恢复接口 200 |
| Windows PowerShell 5.1 云原生实跑 | 224/224，HPA 1→4→1，故障 503/200/200，恢复接口 200 |
| npm audit | 完整依赖 0 vulnerabilities |
| 前端 | typecheck PASS；production build PASS、0 warning |
| 单体 Compose 配置 | `.env.example` 下解析成功；无密钥时退出 1 并指出缺失变量 |

## 证据

- 完整微服务门禁：`docs/microservices/evidence/verification/20260901-fix-errors/`。
- 单体并行副本：同目录 `monolith-copy-validation.md`、`monolith-copy-e2e.xml`。
- PowerShell 7 云原生：`docs/microservices/evidence/cloud-native/20260901-193144432-recovery-fix-pwsh7/`。
- Windows PowerShell 5.1 云原生：`docs/microservices/evidence/cloud-native/20260901-193650344-recovery-fix-powershell51/`。

## 仍需如实说明

- 远端 GitHub Actions 本轮没有 push，因此没有远端运行记录；本地 CI/CD 等价门禁和真实 Kind 已通过。
- 前端首包已低于默认 244 KiB 阈值，但全部异步 chunk 合计仍约 922 KiB；不能写成“整个前端只有 233 KiB”。
- Docker 构建上下文约 532 MiB，主要是 464.36 MiB 的课程演示视频。若要继续优化，应迁移为对象存储或独立数据包，不能直接忽略后破坏播放。
- Docker Desktop 直连 Docker Hub 曾因本机证书链失败；使用 DaoCloud 镜像源取得同一 `node:22-alpine` 后构建成功。换机必须保证能访问可信镜像仓库。
- 现有旧失败留下的 `streamhub-minio` Created 容器没有擅自删除；它不占端口。以后确认不再需要时可由用户自行清理，数据卷仍应保留。

# Notes: 深度测试问题修复

## Confirmed Findings

- 云原生脚本在 `finally` 恢复 `content-service` 之前就写出 PASS；恢复使用 `-AllowFailure`，而且没有验证跨服务接口重新返回 200，存在“实验通过但下一轮 API 巡检 84/85”的竞态窗口。
- 原单体 `docker-compose.yml` 固定了 5 个 `container_name`，复制目录与旧副本并行启动时仍争用全局容器名，破坏 Compose 的项目级隔离。
- 根目录没有 `.env` 时，单体 Compose 把数据库密码和 `SECRET_KEY` 解析为空；README 虽要求复制示例文件，但配置没有快速失败保护。
- HPA 目标是 `user-service`，故障注入目标是 `content-service`。项目中没有错误的多资源 watch 命令，但缺少两个终端分别观察 HPA 和 Pod 的现场步骤。
- `npm audit`（官方 registry）确认 4 个生产依赖漏洞：1 high、3 moderate；兼容升级即可修复，不需要 `--force`。
- 后端 Pydantic `.dict()` 和 FastAPI `on_event` 是弃用警告，不是本轮功能失败的根因；在主要运行错误修复后再单独评估，避免扩大回归面。

## Safety Decisions

- 不运行 `docker compose down -v`，不删除 Kind 集群，不覆盖历史证据。
- 不更改 UC01–UC08 或 85 个公开接口的统计口径；只增强现有契约测试中的断言。
- 原单体缺少必填密钥时应明确失败，不允许静默使用空值。

## Verification Evidence

- 新增回归断言先得到 2 个预期失败，修复后 3 个针对性测试通过。
- 单体 Compose 使用 `.env.example` 时配置解析成功；缺少根 `.env` 时退出码 1，并明确报告 `POSTGRES_PASSWORD`/`SECRET_KEY` 缺失。
- 单体后端 38 项在 `DeprecationWarning` 视为错误的模式下全部通过，0 个弃用警告。
- 前端生产依赖审计和完整依赖审计均为 0 漏洞。
- 前端类型检查通过；生产构建由 810 KiB 单包、3 个性能警告降为首包 238906 bytes、0 警告。
- webpack-dev-server 6 在本机实启成功，主页返回 200，媒体代理请求实际转发到 8100 并返回预期 404。
- 完整本地微服务门禁 `fix-errors-20260901-r2` 通过：82 项契约、user 12、content 14、social 13、85/85 公开接口、UC01–UC08 三组 E2E 全部成功；Node 22 前端容器健康。
- 第一次门禁 `fix-errors-20260901` 因 Docker Hub 的本机证书链无法拉取 `node:22-alpine` 而失败；从本机既有的 DaoCloud 镜像源拉取同一官方镜像并本地标记后，第二次构建成功。该失败属于环境网络，不是代码回归，失败证据仍保留。
- Docker 前端构建上下文约 532 MB，复核后其中约 464.36 MiB 是 `public/demo-videos` 的 11 个课程演示视频；`.dockerignore` 已正确排除 `node_modules`、`.ci-results`、虚拟环境等。当前不能直接排除视频，否则本地演示播放会丢失。
- 单体 Compose 的所有宿主机端口已参数化；以 5435/9200/9201/8200/5373/1937/8082 与原项目并行实启，五服务均运行，PostgreSQL/MinIO healthy，后端/前端/SRS HTTP 探针 200，UC01–UC08 3/3。为支持备用前端端口，补充了 CORS 和前端 API 基址联动。
- 单体前端首次 15 秒探针在 Webpack 27.322 秒冷编译完成前超时；编译完成后复测 200。应以 health 状态为启动完成条件，而不是固定等待时间。

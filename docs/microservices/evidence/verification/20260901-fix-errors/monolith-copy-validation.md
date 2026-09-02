# 单体副本并行启动验证

验证日期：2026-09-01。

为确认复制目录不会再与原项目争用固定容器名，同时不停止或删除原项目，使用 Compose 项目名 `se2026-copy-validation` 和一组备用宿主机端口启动单体版。数据库与 MinIO 使用该项目自己的命名卷，验证过程没有执行 `down -v`。

| 服务 | 验证地址/端口 | 结果 |
|---|---|---|
| PostgreSQL | `127.0.0.1:5435` | healthy |
| MinIO API / Console | `127.0.0.1:9200` / `9201` | health 200 |
| 单体后端 | `http://127.0.0.1:8200` | running，业务探针 200 |
| 前端 | `http://127.0.0.1:5373` | running，200 且包含 `#root` |
| SRS | `127.0.0.1:1937` / `http://127.0.0.1:8082` | running，HTTP 200 |

业务探针：

- `GET /api/health`：200。
- `GET /api/videos`：200。
- `GET /api/live/rooms`：200。
- UC01–UC08 Playwright：3/3 通过，JUnit 见同目录 `monolith-copy-e2e.xml`。

前端首次请求的 15 秒探针发生在 Webpack 冷编译期间，编译实际耗时 27.322 秒，因此客户端先超时；编译完成后立即复测为 200。这不是运行失败，但现场冷启动应等待容器 health 为 healthy，再打开浏览器。

本次验证同时确认：PostgreSQL 与 MinIO 的容器级 healthcheck 为 healthy，另外三个服务处于 running 且实际 HTTP 探针成功；固定 `container_name` 已移除；7 个宿主机端口可由 `.env` 配置；后端 CORS 会包含所选前端端口；前端会使用所选后端端口。

# StreamHub 业务微服务拆分设计

日期：2026-08-30  
状态：用户已批准设计，尚未实施代码拆分  
操作目录：`C:\Users\lausu\Desktop\SE2026-microservices`  
单体基线：`C:\Users\lausu\Desktop\SE2026`（只读）

## 1. 目标与边界

把现有 FastAPI 单体后端拆成三个业务微服务：用户服务、内容服务、社交服务。API 网关、前端、PostgreSQL、MinIO、SRS 不计入三个业务服务。

正式端到端业务范围仍为 UC01–UC08。关注、私信、通知、举报、敏感词等现有公开功能继续保留并迁移，但不虚构为新的正式用例。后续所有真实公开后端接口均进入 API 测试清单。

本阶段只完成课程第 1 项：服务拆分、数据归属、跨服务通信、独立构建/测试/部署基础和四类说明材料。本阶段不执行远程 CI/CD、HPA 实验、故障现场实验或性能对比；这些内容分别属于后续第 2–4 项。

## 2. 已核实的基线问题

- 当前业务代码主要集中在 `backend/app/main.py`，约 3200 行，认证、视频、互动、直播、私信和管理功能共用一个 SQLAlchemy Session。
- 当前 ORM 存在大量跨领域外键和 relationship。拆到不同 Schema 后继续使用这些关系会违反“其他服务不能直接读写该表”和“不能跨服务联表查询”的要求。
- 旧 `微服务划分.md` 可保留三服务名称，但不能原样作为实施依据：它包含已废止的 UC09–UC18、当前不存在的表和接口，并遗漏若干真实表。
- 当前收藏接口没有收藏明细表，只会重复增加 `videos.favorite_count`。设计新增 `video_favorites`，使收藏可去重、可取消、可审计。
- 当前 token 仅包含用户 ID，有效期 7 天。其他服务若只本地解析 token，无法及时得知封禁和角色变更。因此采用用户服务在线校验，不能假定 JWT 本地验证等价于现有权限语义。

## 3. 总体架构

```text
Browser / Frontend
        |
        v
API Gateway :8100
   |           |           |
   v           v           v
User        Content      Social
Service     Service      Service
   |           |           |
user_service content_service social_service
      \          |          /
       PostgreSQL instance :5434

Content/User services also access owned MinIO prefixes.
Social service cooperates with SRS for live interactions.
```

网关保留现有 `/api/*`、`/ws/*`、`/uploads/*`、`/avatars/*` 对外路径。前端不因后端拆分修改业务 URL。网关只负责路由、请求 ID 和统一错误格式，不保存业务状态。限流属于后续故障处理实验，不在本阶段提前实现。

复制版使用独立 Compose 名称、容器、端口和 Volume，不占用单体当前端口：

| 组件 | 复制版宿主机端口 |
| --- | ---: |
| API 网关 | 8100 |
| 前端 | 5273 |
| PostgreSQL | 5434 |
| MinIO API / Console | 9100 / 9101 |
| SRS RTMP / HTTP | 1936 / 8081 |

业务服务内部统一监听 8000。需要本地单独调试时再映射诊断端口，不作为公开入口。

## 4. 服务职责

### 4.1 用户服务

负责注册、登录、token 校验、用户资料、头像、角色和封禁、关注关系、私信、通知。

主要公开路径：

- `/api/auth/*`
- `/api/users/*` 中用户资料和关系接口
- `/api/chat/*`、`/ws/chat`
- `/api/notifications/*`
- `/api/admin/users/*`

内部接口包括 token 校验、批量用户摘要、幂等创建通知。

### 4.2 内容服务

负责分类、视频发现、投稿、审核、创作者作品管理、视频/封面对象、视频元数据和统计快照。

主要公开路径：

- `/api/categories`
- `/api/videos` 中视频查询、投稿和媒体接口
- `/api/creator/videos*`
- `/api/admin/videos*`
- `/uploads/*`

内部接口包括视频存在性/状态校验、批量视频摘要、幂等更新互动统计。

### 4.3 社交服务

负责评论、回复、提及、点赞、收藏、视频弹幕、直播间、直播 WebSocket、举报和敏感词。

主要公开路径：

- `/api/videos/{id}/like*`
- `/api/videos/{id}/favorite*`
- `/api/videos/{id}/comments*`
- `/api/comments/*`
- `/api/videos/{id}/danmaku`
- `/api/live/*`、`/ws/live/*`
- `/api/reports`、`/api/admin/reports*`
- `/api/admin/sensitive-words*`
- `/api/admin/live-rooms*`

## 5. 数据表归属

同一 PostgreSQL 实例内使用三个 Schema 和三个受限账号。账号默认只拥有本 Schema 的 USAGE、SELECT、INSERT、UPDATE、DELETE 和序列权限。

| Schema / 服务 | 归属表 |
| --- | --- |
| `user_service` / 用户服务 | `users`、`follows`、`conversations`、`messages`、`notifications`、`processed_events` |
| `content_service` / 内容服务 | `categories`、`videos`、`integration_outbox`、`processed_events` |
| `social_service` / 社交服务 | `comments`、`comment_mentions`、`video_likes`、`video_favorites`、`video_interaction_baselines`、`danmaku`、`live_rooms`、`reports`、`sensitive_words`、`integration_outbox`、`processed_events` |

`integration_outbox` 保存待投递事件；`processed_events` 保存已处理事件 ID，保证接收幂等。它们是各服务自己的技术表，不共享。

`video_interaction_baselines` 保存迁移时旧聚合计数减去可迁移明细后的非负残差。新绝对计数等于该基线加当前社交明细数，避免第一次互动把历史种子计数覆盖成 1。

跨服务引用只保存 UUID 或整数 ID，不建立跨 Schema 外键，不声明跨服务 ORM relationship。例如：

- `social_service.comments.user_id` 只保存用户 ID，通过用户服务获取昵称和头像。
- `social_service.comments.video_id` 只保存视频 ID，通过内容服务校验视频状态。
- `social_service.live_rooms.category_id` 只保存分类 ID，通过内容服务获取分类。
- `content_service.videos.uploader_id` 只保存用户 ID，通过用户服务获取创作者摘要。

Schema 内部外键继续保留，例如 `messages.conversation_id`、`comment_mentions.comment_id`、`videos.category_id`。

## 6. MinIO 对象归属

MinIO 不是业务服务，也不是数据库。对象按前缀划分管理权：

- 用户服务：`avatars/`
- 内容服务：`videos/`、`covers/`

服务使用独立 MinIO 凭据和前缀策略。社交服务不直接读写媒体对象，只消费公开 URL。

## 7. 跨服务调用

仅使用内部 HTTP 和数据库 Outbox，不引入 RabbitMQ、Kafka、Redis 或 Celery。题目允许通过接口、事件或消息协作；当前规模下新增消息基础设施只会增加部署、监控和故障面。

### 7.1 同步读取

- 内容、社交服务调用用户服务批量获取用户摘要。
- 社交服务调用内容服务校验视频存在且可互动。
- 社交服务调用内容服务获取分类或视频摘要。
- 用户服务聚合用户视频/互动统计时调用内容、社交服务。

批量接口用于避免逐行 N+1 调用。

### 7.2 身份与权限

用户服务负责验证现有 Bearer token，并返回用户 ID、角色和状态。内容、社交服务通过共享 HTTP 客户端调用该内部接口。

- token 无效、用户封禁：返回 401/403。
- 用户服务超时：受保护写操作返回 503，不写本地业务表。
- 公开视频和直播查询不依赖登录；资料补全失败时可降级。

默认连接超时 0.5 秒，总超时 1.5 秒，均可由环境变量校准。

### 7.3 互动计数和通知

点赞、取消点赞、收藏、评论等操作先在社交服务本地事务内写业务表和 Outbox。请求返回社交服务的权威计数。后台把“绝对计数”事件投递到内容服务，避免重复投递造成重复加减。

审核结果通知由内容服务写入本服务 Outbox，再幂等投递到用户服务。评论、提及等通知由社交服务采用相同模式。

## 8. 失败处理

| 场景 | 策略 |
| --- | --- |
| 身份校验失败/超时 | 失败关闭；受保护写操作返回明确 401/403/503，不落库 |
| 写前视频校验失败 | 返回 404；内容服务超时则返回 503，不写互动数据 |
| 用户资料补全超时 | 公开视频/评论读取返回匿名占位信息和降级标记 |
| 事件投递失败 | Outbox 指数退避重试；保留次数、下次执行时间和最后错误 |
| 重复事件 | 目标服务按 `event_id` 查询 `processed_events`，重复请求直接返回成功 |
| 非幂等 POST 超时 | 不盲目自动重试；客户端使用幂等键后才能安全重放 |
| 达到最大重试次数 | 默认 10 次后标记 `dead`，健康/运维接口暴露积压并记录结构化日志；次数可配置 |

GET 最多重试两次。日志记录 `request_id`、目标服务、方法、耗时、状态、重试次数和错误类型，不记录密码、token 或数据库连接串。

## 9. 代码结构

```text
services/
  user-service/
    app/
    tests/
    Dockerfile
    requirements.txt
  content-service/
    app/
    tests/
    Dockerfile
    requirements.txt
  social-service/
    app/
    tests/
    Dockerfile
    requirements.txt
gateway/
shared/
  auth_context/
  service_client/
```

`shared` 只允许放 Authorization 头转发、认证结果类型、请求 ID、HTTP 客户端、统一错误结构等无业务状态代码。token 真伪、用户状态和角色仍由用户服务校验。禁止共享 SQLAlchemy 业务模型、Session 或跨服务数据库工具。

每个服务提供：

- `/health`：进程存活。
- `/ready`：本服务数据库及必要依赖可用。
- `/version`：返回构建版本。
- 独立 Dockerfile、依赖文件、pytest 命令、Deployment 和 Service。

## 10. 渐进改造顺序

1. 复制实际工作区到隔离目录，排除 Git 元数据、可重建依赖、秘密配置和缓存。
2. 建立复制版独立 Compose、端口、Volume 和配置。
3. 只读导出单体 PostgreSQL、MinIO 数据，导入复制版；不修改源数据。
4. 建立三个 Schema、受限账号和迁移脚本。
5. 抽离用户服务；网关切换相关路由；运行回归。
6. 抽离内容服务；网关切换相关路由；运行回归。
7. 抽离社交服务；网关切换相关路由；运行回归。
8. 验证所有公开路由均由新服务处理后，删除复制版单体运行入口。
9. 运行服务测试、跨服务失败测试、Schema 权限测试、镜像构建、Compose 冒烟和现有 E2E。
10. 生成课程要求的四类说明材料和改造差异清单。

## 11. 测试与验收

每个服务必须单独完成：依赖安装、pytest、Docker build、启动、健康/就绪/版本检查。

必须验证：

- 三个数据库账号无法直接读写其他 Schema。
- 代码不存在跨服务 ORM relationship、跨 Schema join 或他方数据库连接。
- 跨服务成功、超时、失败关闭、读取降级、Outbox 重试和幂等。
- 网关路由覆盖现有全部公开 API 与 WebSocket。
- 迁移后的现有后端回归通过。
- 现有 3 条 E2E 通过网关运行，继续覆盖正式 UC01–UC08。
- 三个业务镜像分别构建成功。
- Compose 中网关、三个服务、前端、PostgreSQL、MinIO、SRS 达到预期状态。

所有测试数字只能来自本次真实日志和 JUnit。现有单体的 38/38、E2E 3/3、227 测试点是历史基线，不能自动写成微服务结果。

## 12. 交付物

- 服务划分图。
- 服务接口清单。
- 数据表归属表。
- 跨服务调用及失败处理说明。
- 单体目录与微服务目录差异清单及关键文件哈希。
- 三服务独立构建、测试、部署配置。
- 原始测试日志和 JUnit。
- 改造前目录 `SE2026` 与改造后目录 `SE2026-microservices`。

因当前明确禁止 commit 和 push，本设计不创建 Git 提交。两个目录、差异清单和文件哈希用于本地版本证明；其证据强度弱于 Git tag，此限制需在最终说明中如实标注。

## 13. 已知成本与风险

- 在线鉴权增加一次内部调用，微服务延迟可能高于单体；后续性能对比必须实测。
- Schema 隔离仍共享 PostgreSQL 实例，数据库实例故障会影响三个服务；它满足课程允许条件，但不是物理隔离。
- Outbox 避免事件丢失，但带来最终一致性和积压监控成本。
- 网关路由中 `/api/videos/{id}/comments|like|favorite|danmaku` 必须优先于通用 `/api/videos/*`，否则会误路由。
- 数据导出导入必须包含 PostgreSQL 业务数据和 MinIO 对象；只复制项目文件不等于复制运行时数据。
- 复制版需避免固定 `container_name` 和源项目端口/Volume，防止误操作主项目。

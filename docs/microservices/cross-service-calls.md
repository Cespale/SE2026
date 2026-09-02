# StreamHub 跨服务调用与失败处理

## 统一约束

- 同步客户端连接超时 0.5 秒、总超时 1.5 秒。
- GET/HEAD 最多 3 次尝试（首次 + 2 次退避重试）；POST/PUT/PATCH/DELETE 每轮只尝试 1 次，避免重复写。
- Gateway 普通 HTTP 连接超时 500ms、读取超时 2s；媒体上传单独允许 30/120s，WebSocket 读取 1h。
- 每次调用携带 `X-Request-ID`。Gateway 隐藏上游重复响应头后只返回一个请求 ID。
- 受保护写操作的依赖校验失败时返回 503，不写本地业务表。公开读可降级，但必须返回 `X-StreamHub-Degraded`。

## 同步 HTTP

| 调用方 | 被调用方/接口 | 目的 | 尝试 | 失败结果 | 本地数据影响 |
|---|---|---|---|---|---|
| user | content `GET /internal/users/{id}/received-like-count` | 用户主页收到的点赞数 | 最多 3 次 | `likeCount=0`，响应头标记 content 降级 | user 本地关注统计照常返回，不写数据 |
| content | user `POST /internal/auth/introspect` | 投稿、审核等鉴权 | 1 次 | 对外 401 或 503 | 依赖失败时不创建/修改视频 |
| content | user `POST /internal/users/batch` | 视频列表补充作者资料 | 1 次 | 作者显示“用户”，响应头标记 user 降级 | 视频读取仍成功 |
| social | user `POST /internal/auth/introspect` | 点赞、收藏、评论、直播、举报鉴权 | 1 次 | 对外 401 或 503 | 不写互动/直播/举报表，不产生 Outbox |
| social | user `POST /internal/users/batch` | 评论/直播/点赞列表补用户资料 | 1 次 | 使用“匿名用户/主播”等备用值并标记降级 | 主数据读取继续 |
| social | content `GET /internal/videos/{id}/interaction-target` | 写互动前确认视频存在且可互动 | 最多 3 次 | 404 原样返回；超时/5xx 返回 503 | 不写互动表、不产生 Outbox |
| social | content `GET /api/categories` | 验证/显示直播分类 | 最多 3 次 | 使用空分类映射；创建时无法确认的分类不做跨库查询 | 不访问 content Schema |
| Gateway | user/content/social 公开接口 | 单一入口与路由隔离 | Nginx 不重试写 | 502/503/504 统一为 503 JSON | 其他服务不级联退出 |

## Outbox 异步写

| 生产者 | 事件/接收接口 | 接收者 | 幂等方式 | 失败与恢复 |
|---|---|---|---|---|
| content | `notification.created` → user `POST /internal/notifications` | user | `user_service.processed_events.event_id` | 原视频事务先提交；Outbox 指数退避，最多 10 次 |
| content | `video.deleted` → social `POST /internal/events/video-deleted` | social | `social_service.processed_events.event_id` | 重复删除返回 `duplicate=true`；互动清理不会重复产生副作用 |
| social | `video.interaction-counts.changed` → content `PUT /internal/videos/{id}/interaction-counts` | content | content processed event + 绝对计数覆盖 | 不发送增量，重复投递不会二次累加；失败继续重试 |
| social | `notification.created` → user `POST /internal/notifications` | user | user processed event | 通知失败不回滚评论/直播管理事务 |

Outbox 状态为 `pending → processing → sent`。失败增加 `attempts`、记录 `last_error` 和下一次时间；第 10 次失败进入 `dead`。content/social 各提供 `GET /internal/outbox/dead?limit=20` 诊断，但 Gateway 对全部 `/internal/*` 返回 404，因此该接口只在集群/Compose 内部可见。

## 已验证故障契约

- content 无法鉴权时投稿返回 503，视频数量不变。
- social 无法校验视频时点赞/收藏返回 404/503，互动表和 Outbox 均不新增。
- user/content/social 的公开补充资料读取失败时返回备用值和降级响应头。
- Outbox 首次失败保留事件并安排重试；达到上限进入 dead 且内部接口可见。
- 视频删除和互动绝对计数接收端记录事件 ID，重复事件只处理一次。

这些是自动化契约测试；课程要求的“现场主动停止依赖服务”属于后续云原生故障实验，不能用本契约测试冒充现场实验结果。

# StreamHub 数据表归属

## 强制规则

数据库 `streamhub` 内使用三个 Schema 和三个登录账号。账号只能访问本服务 Schema；跨服务 ID 只保存为普通 UUID/整数，不建立跨 Schema 外键。`scripts/verify_schema_isolation.py` 已验证每个账号能读自有表且不能读另外两个 Schema。

| 完整表名 | 来源 | 唯一归属 | 允许账号 | 外部 ID/含义 | 其他服务禁止行为 |
|---|---|---|---|---|---|
| `user_service.users` | 单体迁移 | user | `streamhub_user_service` | 无；用户主数据 | content/social 禁止直接查用户、密码、角色 |
| `user_service.follows` | 单体迁移 | user | `streamhub_user_service` | 两端均为本 Schema 用户 ID | 其他服务禁止统计关注关系 |
| `user_service.conversations` | 单体迁移 | user | `streamhub_user_service` | 两端均为本 Schema 用户 ID | 其他服务禁止读取会话 |
| `user_service.messages` | 单体迁移 | user | `streamhub_user_service` | 会话/发送者/接收者均属 user | 其他服务禁止读取或写聊天内容 |
| `user_service.notifications` | 单体迁移 | user | `streamhub_user_service` | `target_id` 是不透明外部对象 ID | 其他服务通过通知接口/Outbox 创建，禁止直接 INSERT |
| `user_service.processed_events` | 新增 | user | `streamhub_user_service` | 外部事件 `event_id` | 其他服务禁止修改幂等记录 |
| `content_service.categories` | 单体迁移 | content | `streamhub_content_service` | 无 | 其他服务通过分类接口读取 |
| `content_service.videos` | 单体迁移 | content | `streamhub_content_service` | `uploader_id` 是 user ID | user/social 禁止直接读取或更新视频/计数 |
| `content_service.integration_outbox` | 新增 | content | `streamhub_content_service` | payload 含 user/video/event ID | 其他服务禁止确认或删除事件 |
| `content_service.processed_events` | 新增 | content | `streamhub_content_service` | social 发来的 `event_id` | social 禁止直接写幂等状态 |
| `social_service.comments` | 单体迁移 | social | `streamhub_social_service` | `video_id` 属 content；`user_id` 属 user | user/content 禁止联表或删除评论 |
| `social_service.comment_mentions` | 单体迁移 | social | `streamhub_social_service` | `mentioned_user_id` 属 user | user 禁止直接写提及记录 |
| `social_service.video_likes` | 单体迁移 | social | `streamhub_social_service` | user ID + content video ID | content 禁止直接统计明细 |
| `social_service.video_favorites` | 新增 | social | `streamhub_social_service` | user ID + content video ID | content/user 禁止直接读写收藏 |
| `social_service.video_interaction_baselines` | 新增 | social | `streamhub_social_service` | content video ID；历史残差计数 | content 禁止直接改基线 |
| `social_service.danmaku` | 单体迁移 | social | `streamhub_social_service` | user ID + video/直播目标 ID | content 禁止直接读取或清理 |
| `social_service.live_rooms` | 单体迁移 | social | `streamhub_social_service` | `anchor_id` 属 user；`category_id` 属 content | user/content 禁止直接改直播状态 |
| `social_service.reports` | 单体迁移 | social | `streamhub_social_service` | reporter/target 为外部 ID | 其他服务禁止直接审核举报 |
| `social_service.sensitive_words` | 单体迁移 | social | `streamhub_social_service` | 无 | 其他服务禁止直接维护词库 |
| `social_service.integration_outbox` | 新增 | social | `streamhub_social_service` | payload 含 user/video/event ID | 其他服务禁止确认或删除事件 |
| `social_service.processed_events` | 新增 | social | `streamhub_social_service` | content 发来的 `event_id` | content 禁止直接写幂等状态 |

## 对象存储归属

MinIO 桶可以共用，但前缀仍有唯一写入者：user 只写/读 `avatars/*`；content 只写/读 `uploads/videos/*` 与 `uploads/covers/*`；social 不直接读写媒体对象。删除视频时 content 只清理 content 前缀，并用 Outbox 通知 social 清理互动数据。

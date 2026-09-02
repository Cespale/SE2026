# StreamHub 微服务公开接口与 API 测试清单

本清单由三个服务源码装饰器生成；`tests/microservices/test_public_api_catalog.py` 会逐项校验归属和单体兼容性。`scripts/public_api_smoke.py` 按测试 ID 从网关巡检全部 85 项：83 个 HTTP 接口真实请求，2 个 WebSocket 接口由服务行为测试建立真实连接。业务成功和失败路径由对应服务 pytest 与 UC01–UC08 E2E 补足。

公开接口总数：**85**。另有网关兼容接口 `GET /api/health`；内部 `/internal/*` 不公开。单体头像参数名 `media_path` 在用户服务中改名为 `avatar_path`，URL 语义不变。微服务新增 `DELETE /api/videos/{video_id}/favorite`，补齐取消收藏。

| 方法 | 路径 | 归属 | 鉴权 | 内部依赖/失败策略 | API 测试 ID |
|---|---|---|---|---|---|
| GET | `/api/admin/users` | user | 管理员 | 无 | API-U001 |
| PATCH | `/api/admin/users/{user_id}/ban` | user | 管理员 | 无 | API-U002 |
| PATCH | `/api/admin/users/{user_id}/type` | user | 管理员 | 无 | API-U003 |
| PUT | `/api/auth/change-password` | user | 登录用户 | 无 | API-U004 |
| POST | `/api/auth/login` | user | 公开 | 无 | API-U005 |
| GET | `/api/auth/me` | user | 登录用户 | 无 | API-U006 |
| PATCH | `/api/auth/me` | user | 登录用户 | 无 | API-U007 |
| POST | `/api/auth/register` | user | 公开 | 无 | API-U008 |
| POST | `/api/auth/upgrade-to-creator` | user | 登录用户 | 无 | API-U009 |
| POST | `/api/auth/upload-avatar` | user | 登录用户 | 无 | API-U010 |
| GET | `/api/chat/conversations` | user | 登录用户 | 无 | API-U011 |
| POST | `/api/chat/conversations` | user | 登录用户 | 无 | API-U012 |
| GET | `/api/chat/conversations/{conv_id}/messages` | user | 登录用户 | 无 | API-U013 |
| POST | `/api/chat/conversations/{conv_id}/messages` | user | 登录用户 | 无 | API-U014 |
| POST | `/api/chat/conversations/{conv_id}/read` | user | 登录用户 | 无 | API-U015 |
| POST | `/api/chat/messages/{msg_id}/recall` | user | 登录用户 | 无 | API-U016 |
| GET | `/api/creator/fans` | user | 创作者 | 无 | API-U017 |
| GET | `/api/notifications` | user | 登录用户 | 无 | API-U018 |
| POST | `/api/notifications/read-all` | user | 登录用户 | 无 | API-U019 |
| GET | `/api/notifications/unread-count` | user | 登录用户 | 无 | API-U020 |
| POST | `/api/notifications/{notif_id}/read` | user | 登录用户 | 无 | API-U021 |
| GET | `/api/users/{user_id}` | user | 公开 | 无 | API-U022 |
| DELETE | `/api/users/{user_id}/follow` | user | 登录用户 | 无 | API-U023 |
| POST | `/api/users/{user_id}/follow` | user | 登录用户 | 无 | API-U024 |
| GET | `/api/users/{user_id}/followers` | user | 公开 | 无 | API-U025 |
| GET | `/api/users/{user_id}/following` | user | 公开 | 无 | API-U026 |
| GET | `/api/users/{user_id}/relation` | user | 登录用户 | 无 | API-U027 |
| GET | `/api/users/{user_id}/stats` | user | 公开 | content（降级为 0） | API-U028 |
| GET | `/avatars/{avatar_path:path}` | user | 公开 | 无 | API-U029 |
| WEBSOCKET | `/ws/chat` | user | 查询参数 token | 无 | API-U030 |
| POST | `/api/admin/cleanup-uploads` | content | 管理员 | user 鉴权 | API-C001 |
| POST | `/api/admin/local-videos/sync` | content | 管理员 | user 鉴权 | API-C002 |
| GET | `/api/admin/videos` | content | 管理员 | user 鉴权；user 批量资料（可降级）；outbox→user/social | API-C003 |
| GET | `/api/admin/videos/pending` | content | 管理员 | user 鉴权；user 批量资料（可降级）；outbox→user/social | API-C004 |
| PATCH | `/api/admin/videos/{video_id}/audit` | content | 管理员 | user 鉴权；user 批量资料（可降级）；outbox→user/social | API-C005 |
| POST | `/api/admin/videos/{video_id}/unapprove` | content | 管理员 | user 鉴权；outbox→user/social | API-C006 |
| POST | `/api/admin/videos/{video_id}/warn` | content | 管理员 | user 鉴权；outbox→user/social | API-C007 |
| GET | `/api/categories` | content | 公开 | 无 | API-C008 |
| GET | `/api/creator/videos` | content | 创作者 | user 鉴权；user 批量资料（可降级）；outbox→user/social | API-C009 |
| GET | `/api/creator/videos/{status}` | content | 创作者 | user 鉴权；user 批量资料（可降级）；outbox→user/social | API-C010 |
| DELETE | `/api/creator/videos/{video_id}` | content | 创作者 | user 鉴权；outbox→user/social | API-C011 |
| PUT | `/api/creator/videos/{video_id}` | content | 创作者 | user 鉴权；user 批量资料（可降级）；outbox→user/social | API-C012 |
| GET | `/api/creator/week-stats` | content | 创作者 | user 鉴权 | API-C013 |
| GET | `/api/feed` | content | 登录用户 | user 鉴权；user 批量资料（可降级） | API-C014 |
| GET | `/api/users/{user_id}/videos` | content | 公开 | user 批量资料（可降级） | API-C015 |
| GET | `/api/videos` | content | 公开 | user 批量资料（可降级） | API-C016 |
| POST | `/api/videos` | content | 创作者 | user 鉴权；user 批量资料（可降级） | API-C017 |
| GET | `/api/videos/recommended` | content | 公开 | user 批量资料（可降级） | API-C018 |
| POST | `/api/videos/upload-cover` | content | 创作者 | user 鉴权 | API-C019 |
| POST | `/api/videos/upload-file` | content | 创作者 | user 鉴权 | API-C020 |
| GET | `/api/videos/{video_id}` | content | 公开 | user 批量资料（可降级） | API-C021 |
| GET | `/api/videos/{video_id}/related` | content | 公开 | user 批量资料（可降级） | API-C022 |
| GET | `/uploads/{media_path:path}` | content | 公开 | 无 | API-C023 |
| GET | `/api/admin/live-rooms` | social | 管理员 | user 鉴权；outbox→user | API-S001 |
| POST | `/api/admin/live-rooms/{room_id}/close` | social | 管理员 | user 鉴权；outbox→user | API-S002 |
| POST | `/api/admin/live-rooms/{room_id}/warn` | social | 管理员 | user 鉴权；outbox→user | API-S003 |
| GET | `/api/admin/reports` | social | 管理员 | user 鉴权 | API-S004 |
| PATCH | `/api/admin/reports/{report_id}/handle` | social | 管理员 | user 鉴权 | API-S005 |
| PATCH | `/api/admin/reports/{report_id}/ignore` | social | 管理员 | user 鉴权 | API-S006 |
| GET | `/api/admin/sensitive-words` | social | 管理员 | user 鉴权 | API-S007 |
| POST | `/api/admin/sensitive-words` | social | 管理员 | user 鉴权 | API-S008 |
| DELETE | `/api/admin/sensitive-words/{word_id}` | social | 管理员 | user 鉴权 | API-S009 |
| DELETE | `/api/comments/{comment_id}` | social | 登录用户 | user 鉴权 | API-S010 |
| GET | `/api/comments/{comment_id}/replies` | social | 公开 | user 批量资料（可降级） | API-S011 |
| GET | `/api/creator/active-room` | social | 创作者 | user 鉴权；content 分类；user 主播资料 | API-S012 |
| GET | `/api/creator/comments` | social | 创作者 | user 鉴权；user 批量资料（可降级） | API-S013 |
| DELETE | `/api/creator/comments/{comment_id}` | social | 创作者 | user 鉴权 | API-S014 |
| GET | `/api/live/rooms` | social | 公开 | content 分类；user 主播资料 | API-S015 |
| POST | `/api/live/rooms` | social | 创作者 | user 鉴权；content 分类；user 主播资料 | API-S016 |
| GET | `/api/live/rooms/{room_id}` | social | 公开 | content 分类；user 主播资料 | API-S017 |
| POST | `/api/live/rooms/{room_id}/end` | social | 创作者 | user 鉴权；content 分类；user 主播资料 | API-S018 |
| POST | `/api/live/rooms/{room_id}/stop` | social | 创作者 | user 鉴权；content 分类；user 主播资料 | API-S019 |
| POST | `/api/live/{room_id}/danmaku` | social | 登录用户 | user 鉴权；content 分类；user 主播资料 | API-S020 |
| POST | `/api/reports` | social | 登录用户 | user 鉴权；content 校验 | API-S021 |
| GET | `/api/users/{user_id}/likes` | social | 登录用户 | user 鉴权 | API-S022 |
| GET | `/api/videos/{video_id}/comments` | social | 公开 | content 校验；user 批量资料（可降级） | API-S023 |
| POST | `/api/videos/{video_id}/comments` | social | 登录用户 | user 鉴权；content 校验；user 批量资料（可降级） | API-S024 |
| GET | `/api/videos/{video_id}/danmaku` | social | 公开 | content 校验；user 批量资料（可降级） | API-S025 |
| POST | `/api/videos/{video_id}/danmaku` | social | 登录用户 | user 鉴权；content 校验；user 批量资料（可降级） | API-S026 |
| DELETE | `/api/videos/{video_id}/favorite` | social | 登录用户 | user 鉴权；content 校验 | API-S027 |
| POST | `/api/videos/{video_id}/favorite` | social | 登录用户 | user 鉴权；content 校验 | API-S028 |
| DELETE | `/api/videos/{video_id}/like` | social | 登录用户 | user 鉴权；content 校验 | API-S029 |
| POST | `/api/videos/{video_id}/like` | social | 登录用户 | user 鉴权；content 校验 | API-S030 |
| GET | `/api/videos/{video_id}/like-status` | social | 登录用户 | user 鉴权；content 校验 | API-S031 |
| WEBSOCKET | `/ws/live/{room_id}` | social | 公开 | 无 | API-S032 |

## 内部接口

内部接口总数：**11**。Gateway 对 `/internal` 和 `/internal/*` 固定返回 404。

| 方法 | 路径 | 归属 | 调用方/用途与失败语义 | 测试 ID |
|---|---|---|---|---|
| POST | `/internal/auth/introspect` | user | content/social：鉴权；失败时调用方不得写业务数据 | INT-U001 |
| POST | `/internal/notifications` | user | content/social Outbox：幂等创建通知 | INT-U002 |
| POST | `/internal/users/batch` | user | content/social：批量用户资料；读场景可降级 | INT-U003 |
| GET | `/internal/users/{user_id}/following-ids` | user | content：关注 ID；用户不存在返回 404 | INT-U004 |
| GET | `/internal/outbox/dead` | content | 运维：查看 dead 事件；Gateway 不公开 | INT-C001 |
| GET | `/internal/users/{user_id}/received-like-count` | content | user：主页收到点赞数 | INT-C002 |
| POST | `/internal/videos/batch` | content | social：批量视频摘要 | INT-C003 |
| PUT | `/internal/videos/{video_id}/interaction-counts` | content | social Outbox：幂等覆盖绝对计数 | INT-C004 |
| GET | `/internal/videos/{video_id}/interaction-target` | content | social：互动前验证视频和作者 | INT-C005 |
| POST | `/internal/events/video-deleted` | social | content Outbox：幂等清理视频互动 | INT-S001 |
| GET | `/internal/outbox/dead` | social | 运维：查看 dead 事件；Gateway 不公开 | INT-S002 |

## 验证口径

- 全量归属/兼容：`test_public_api_catalog.py`，自动比较单体与三服务路由。
- API 行为：user/content/social 各自 pytest；受保护接口同时验证鉴权失败和成功路径。
- 网关运行时巡检：`public_api_smoke.py`；5xx、405、网关未知接口 404 均失败，并输出 JUnit/JSON。
- 端到端：UC01–UC08 合并为 3 个 Playwright 场景，经 5273→8100 网关执行。
- WebSocket：聊天与直播分别在服务测试中建立真实 TestClient WebSocket。

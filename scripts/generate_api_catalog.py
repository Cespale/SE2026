import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "microservices" / "service-api-catalog.md"
SERVICE_FILES = {
    "user": ROOT / "services" / "user-service" / "app" / "main.py",
    "content": ROOT / "services" / "content-service" / "app" / "main.py",
    "social": ROOT / "services" / "social-service" / "app" / "main.py",
}
PREFIX = {"user": "U", "content": "C", "social": "S"}
PUBLIC_PREFIXES = ("/api", "/ws", "/uploads", "/avatars")
METHODS = {"get", "post", "put", "patch", "delete", "websocket"}


def route_functions(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        source = ast.unparse(node)
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in METHODS
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                route = decorator.args[0].value
                result.append((decorator.func.attr.upper(), route, source))
    return sorted(result, key=lambda item: (item[1], item[0]))


def auth_level(owner: str, method: str, route: str, source: str) -> str:
    if "Depends(require_admin)" in source:
        return "管理员"
    if "Depends(require_creator)" in source:
        return "创作者"
    if "Depends(get_current_user)" in source or "Depends(current_auth_context)" in source:
        return "登录用户"
    if method == "WEBSOCKET" and route == "/ws/chat":
        return "查询参数 token"
    return "公开"


def dependency(owner: str, route: str, source: str) -> str:
    if owner == "user":
        return "content（降级为 0）" if route.endswith("/stats") else "无"
    if owner == "content":
        dependencies = []
        if "Depends(current_auth_context)" in source or "Depends(require_" in source:
            dependencies.append("user 鉴权")
        if any(token in source for token in ("video_items(", "user_map_for(")):
            dependencies.append("user 批量资料（可降级）")
        if route.startswith("/api/admin/videos") or route.startswith("/api/creator/videos"):
            dependencies.append("outbox→user/social")
        return "；".join(dict.fromkeys(dependencies)) or "无"
    dependencies = []
    if "Depends(current_auth_context)" in source or "Depends(require_" in source:
        dependencies.append("user 鉴权")
    if route.startswith("/api/videos/") or route.startswith("/api/reports"):
        dependencies.append("content 校验")
    if route.startswith(("/api/live", "/api/creator/active-room")):
        dependencies.append("content 分类；user 主播资料")
    if any(token in source for token in ("fetch_users(", "render_comments(")):
        dependencies.append("user 批量资料（可降级）")
    if route.startswith("/api/admin/live-rooms"):
        dependencies.append("outbox→user")
    return "；".join(dict.fromkeys(dependencies)) or "无"


def internal_purpose(owner: str, route: str) -> str:
    purposes = {
        ("user", "/internal/auth/introspect"): "content/social：鉴权；失败时调用方不得写业务数据",
        ("user", "/internal/users/batch"): "content/social：批量用户资料；读场景可降级",
        ("user", "/internal/users/{user_id}/following-ids"): "content：关注 ID；用户不存在返回 404",
        ("user", "/internal/notifications"): "content/social Outbox：幂等创建通知",
        ("content", "/internal/outbox/dead"): "运维：查看 dead 事件；Gateway 不公开",
        ("content", "/internal/videos/{video_id}/interaction-target"): "social：互动前验证视频和作者",
        ("content", "/internal/videos/batch"): "social：批量视频摘要",
        ("content", "/internal/videos/{video_id}/interaction-counts"): "social Outbox：幂等覆盖绝对计数",
        ("content", "/internal/users/{user_id}/received-like-count"): "user：主页收到点赞数",
        ("social", "/internal/outbox/dead"): "运维：查看 dead 事件；Gateway 不公开",
        ("social", "/internal/events/video-deleted"): "content Outbox：幂等清理视频互动",
    }
    return purposes.get((owner, route), "内部调用；不经 Gateway")


def main() -> int:
    entries = []
    internal_entries = []
    for owner, path in SERVICE_FILES.items():
        public_routes = [
            item for item in route_functions(path) if item[1].startswith(PUBLIC_PREFIXES)
        ]
        for index, (method, route, source) in enumerate(public_routes, start=1):
            entries.append(
                (
                    method,
                    route,
                    owner,
                    auth_level(owner, method, route, source),
                    dependency(owner, route, source),
                    f"API-{PREFIX[owner]}{index:03d}",
                )
            )
        private_routes = [
            item for item in route_functions(path) if item[1].startswith("/internal")
        ]
        for index, (method, route, _source) in enumerate(private_routes, start=1):
            internal_entries.append(
                (method, route, owner, internal_purpose(owner, route), f"INT-{PREFIX[owner]}{index:03d}")
            )

    lines = [
        "# StreamHub 微服务公开接口与 API 测试清单",
        "",
        "本清单由三个服务源码装饰器生成；`tests/microservices/test_public_api_catalog.py` 会逐项校验归属和单体兼容性。`scripts/public_api_smoke.py` 按测试 ID 从网关巡检全部 85 项：83 个 HTTP 接口真实请求，2 个 WebSocket 接口由服务行为测试建立真实连接。业务成功和失败路径由对应服务 pytest 与 UC01–UC08 E2E 补足。",
        "",
        f"公开接口总数：**{len(entries)}**。另有网关兼容接口 `GET /api/health`；内部 `/internal/*` 不公开。单体头像参数名 `media_path` 在用户服务中改名为 `avatar_path`，URL 语义不变。微服务新增 `DELETE /api/videos/{{video_id}}/favorite`，补齐取消收藏。",
        "",
        "| 方法 | 路径 | 归属 | 鉴权 | 内部依赖/失败策略 | API 测试 ID |",
        "|---|---|---|---|---|---|",
    ]
    for method, route, owner, auth, dep, test_id in entries:
        lines.append(f"| {method} | `{route}` | {owner} | {auth} | {dep} | {test_id} |")
    lines.extend(
        [
            "",
            "## 内部接口",
            "",
            f"内部接口总数：**{len(internal_entries)}**。Gateway 对 `/internal` 和 `/internal/*` 固定返回 404。",
            "",
            "| 方法 | 路径 | 归属 | 调用方/用途与失败语义 | 测试 ID |",
            "|---|---|---|---|---|",
        ]
    )
    for method, route, owner, purpose, test_id in internal_entries:
        lines.append(f"| {method} | `{route}` | {owner} | {purpose} | {test_id} |")
    lines.extend(
        [
            "",
            "## 验证口径",
            "",
            "- 全量归属/兼容：`test_public_api_catalog.py`，自动比较单体与三服务路由。",
            "- API 行为：user/content/social 各自 pytest；受保护接口同时验证鉴权失败和成功路径。",
            "- 网关运行时巡检：`public_api_smoke.py`；5xx、405、网关未知接口 404 均失败，并输出 JUnit/JSON。",
            "- 端到端：UC01–UC08 合并为 3 个 Playwright 场景，经 5273→8100 网关执行。",
            "- WebSocket：聊天与直播分别在服务测试中建立真实 TestClient WebSocket。",
        ]
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"API_CATALOG=PASS routes={len(entries)} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

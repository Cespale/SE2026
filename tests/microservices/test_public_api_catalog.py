import ast
import re
from pathlib import Path


MONOLITH = Path("backend/app/main.py")
SERVICE_FILES = {
    "user": Path("services/user-service/app/main.py"),
    "content": Path("services/content-service/app/main.py"),
    "social": Path("services/social-service/app/main.py"),
}
CATALOG = Path("docs/microservices/service-api-catalog.md")
PUBLIC_PREFIXES = ("/api", "/ws", "/uploads", "/avatars")
METHODS = {"get", "post", "put", "patch", "delete", "websocket"}


def routes(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr in METHODS
                and decorator.args
                and isinstance(decorator.args[0], ast.Constant)
            ):
                method = decorator.func.attr.upper()
                route = decorator.args[0].value
                found.add((method, route))
    return found


def normalized(route):
    method, path = route
    return method, re.sub(r"\{[^}]+\}", "{}", path)


def test_every_monolith_public_route_has_an_equivalent_owner():
    monolith = {
        normalized(item)
        for item in routes(MONOLITH)
        if item[1].startswith(PUBLIC_PREFIXES)
    }
    owned = {}
    for owner, path in SERVICE_FILES.items():
        for item in routes(path):
            if not item[1].startswith(PUBLIC_PREFIXES):
                continue
            key = normalized(item)
            assert key not in owned, f"duplicate owner for {key}: {owned[key]} and {owner}"
            owned[key] = owner

    assert monolith - {("GET", "/api/health")} <= set(owned)
    assert set(owned) - monolith == {("DELETE", "/api/videos/{}/favorite")}
    gateway = Path("gateway/nginx.conf").read_text(encoding="utf-8")
    assert "location = /api/health" in gateway


def test_catalog_lists_every_public_service_route_with_test_id():
    catalog = CATALOG.read_text(encoding="utf-8")
    count = 0
    for owner, path in SERVICE_FILES.items():
        for method, route in sorted(routes(path)):
            if not route.startswith(PUBLIC_PREFIXES):
                continue
            assert f"| {method} | `{route}` | {owner} |" in catalog
            count += 1
    assert f"公开接口总数：**{count}**" in catalog
    assert "API-U" in catalog and "API-C" in catalog and "API-S" in catalog


def test_catalog_lists_every_internal_service_route():
    catalog = CATALOG.read_text(encoding="utf-8")
    count = 0
    for owner, path in SERVICE_FILES.items():
        for method, route in sorted(routes(path)):
            if not route.startswith("/internal"):
                continue
            assert f"| {method} | `{route}` | {owner} |" in catalog
            count += 1
    assert f"内部接口总数：**{count}**" in catalog

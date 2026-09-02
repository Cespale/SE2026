import asyncio
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from shared.streamhub_common.auth_context import AuthContext
from shared.streamhub_common.request_id import RequestIdMiddleware
from shared.streamhub_common.service_client import ServiceClient, ServiceUnavailable


def test_auth_context_exposes_active_roles() -> None:
    user_id = uuid4()

    assert AuthContext(user_id, user_type=0, status=0).is_creator is False
    assert AuthContext(user_id, user_type=1, status=0).is_creator is True
    assert AuthContext(user_id, user_type=2, status=0).is_admin is True
    assert AuthContext(user_id, user_type=2, status=1).is_admin is False


def test_request_id_middleware_preserves_or_generates_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/")
    def read_root(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    with TestClient(app) as client:
        supplied = client.get("/", headers={"X-Request-ID": "req-fixed"})
        generated = client.get("/")

    assert supplied.json() == {"request_id": "req-fixed"}
    assert supplied.headers["X-Request-ID"] == "req-fixed"
    assert generated.json()["request_id"]
    assert generated.headers["X-Request-ID"] == generated.json()["request_id"]


def test_get_retries_twice_and_forwards_request_id() -> None:
    async def run() -> None:
        attempts: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(request.headers["X-Request-ID"])
            if len(attempts) < 3:
                return httpx.Response(503, json={"detail": "busy"})
            return httpx.Response(200, json={"ok": True})

        client = ServiceClient(
            "http://user-service:8000",
            transport=httpx.MockTransport(handler),
        )

        try:
            result = await client.request_json(
                "GET",
                "/internal/users",
                request_id="req-1",
            )
        finally:
            await client.aclose()

        assert result == {"ok": True}
        assert attempts == ["req-1", "req-1", "req-1"]

    asyncio.run(run())


def test_post_is_not_retried() -> None:
    async def run() -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(503, json={"detail": "busy"})

        client = ServiceClient(
            "http://content-service:8000",
            transport=httpx.MockTransport(handler),
        )

        try:
            with pytest.raises(ServiceUnavailable, match="upstream status 503"):
                await client.request_json(
                    "POST",
                    "/internal/events",
                    request_id="req-2",
                )
        finally:
            await client.aclose()

        assert attempts == 1

    asyncio.run(run())

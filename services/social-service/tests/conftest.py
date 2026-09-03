import os
import sys
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT))

os.environ["SOCIAL_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SERVICE_VERSION"] = "test-version"
os.environ["USER_SERVICE_URL"] = "http://user-service:8000"
os.environ["CONTENT_SERVICE_URL"] = "http://content-service:8000"
os.environ["OUTBOX_WORKER_ENABLED"] = "false"
os.environ["SRS_PUBLIC_RTMP_BASE"] = "rtmp://localhost:1936/live"
os.environ["SRS_PUBLIC_HTTP_BASE"] = "http://localhost:8081/live"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LiveRoom  # noqa: E402
from shared.streamhub_common.service_client import ServiceUnavailable  # noqa: E402


CREATOR_ID = UUID("10000000-0000-0000-0000-000000000001")
ADMIN_ID = UUID("10000000-0000-0000-0000-000000000002")
VIEWER_ID = UUID("10000000-0000-0000-0000-000000000003")
VIDEO_ID = UUID("20000000-0000-0000-0000-000000000001")


class FakeUserClient:
    def __init__(self):
        self.fail_batch = False
        self.notifications = []

    async def request_json(self, method, path, request_id, **kwargs):
        if path == "/internal/auth/introspect":
            authorization = kwargs.get("headers", {}).get("Authorization")
            roles = {
                "Bearer creator-token": (CREATOR_ID, 1),
                "Bearer admin-token": (ADMIN_ID, 2),
                "Bearer viewer-token": (VIEWER_ID, 0),
            }
            if authorization not in roles:
                response = httpx.Response(401, request=httpx.Request("POST", path))
                raise httpx.HTTPStatusError("unauthorized", request=response.request, response=response)
            user_id, user_type = roles[authorization]
            return {"user_id": str(user_id), "user_type": user_type, "status": 0}
        if path.endswith("/stream-key"):
            return {"streamKey": "streamkey-abcdef0123"}
        if path == "/internal/users/batch":
            if self.fail_batch:
                raise ServiceUnavailable("user batch unavailable")
            names = {
                str(CREATOR_ID): "Creator",
                str(ADMIN_ID): "Admin",
                str(VIEWER_ID): "Viewer",
            }
            return [
                {
                    "id": user_id,
                    "account": names.get(user_id, "user").lower(),
                    "nickname": names.get(user_id, "用户"),
                    "avatar": f"/{user_id}.png",
                    "bio": "",
                    "userType": 0,
                    "status": 0,
                }
                for user_id in kwargs["json"]["ids"]
            ]
        if path == "/internal/notifications":
            self.notifications.append(kwargs["json"])
            return {"ok": True, "duplicate": False}
        raise AssertionError(f"unexpected user call: {method} {path}")


class FakeContentClient:
    def __init__(self):
        self.validation = "ok"
        self.count_events = []

    async def request_json(self, method, path, request_id, **kwargs):
        if path.endswith("/interaction-target"):
            if self.validation == "timeout":
                raise ServiceUnavailable("content unavailable")
            if self.validation == "missing":
                response = httpx.Response(404, request=httpx.Request("GET", path))
                raise httpx.HTTPStatusError("missing", request=response.request, response=response)
            return {"id": str(VIDEO_ID), "uploaderId": str(CREATOR_ID)}
        if path == "/internal/videos/batch":
            return [
                {
                    "id": video_id,
                    "title": "Video",
                    "coverUrl": "/cover.jpg",
                    "categoryId": "1",
                    "uploaderId": str(CREATOR_ID),
                    "status": 0,
                    "auditStatus": 1,
                }
                for video_id in kwargs["json"]["ids"]
            ]
        if path.endswith("/interaction-counts"):
            self.count_events.append(kwargs["json"])
            return kwargs["json"]
        if path == "/api/categories":
            return [{"id": "1", "name": "游戏", "type": 1}]
        raise AssertionError(f"unexpected content call: {method} {path}")


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def fake_user_client(monkeypatch):
    client = FakeUserClient()
    monkeypatch.setattr("app.main.get_user_client", lambda: client)
    monkeypatch.setattr("app.outbox.get_user_client", lambda: client)
    return client


@pytest.fixture
def fake_content_client(monkeypatch):
    client = FakeContentClient()
    monkeypatch.setattr("app.main.get_content_client", lambda: client)
    monkeypatch.setattr("app.outbox.get_content_client", lambda: client)
    return client


@pytest.fixture
def client(fake_user_client, fake_content_client):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ids():
    return {
        "creator": str(CREATOR_ID),
        "admin": str(ADMIN_ID),
        "viewer": str(VIEWER_ID),
        "video": str(VIDEO_ID),
    }


@pytest.fixture
def auth_headers():
    return lambda role: {"Authorization": f"Bearer {role}-token"}

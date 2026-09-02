import os
import sys
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT))

os.environ["CONTENT_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SERVICE_VERSION"] = "test-version"
os.environ["USER_SERVICE_URL"] = "http://user-service:8000"
os.environ["SOCIAL_SERVICE_URL"] = "http://social-service:8000"
os.environ["OUTBOX_WORKER_ENABLED"] = "false"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Category, Video  # noqa: E402
from shared.streamhub_common.service_client import ServiceUnavailable  # noqa: E402


CREATOR_ID = UUID("10000000-0000-0000-0000-000000000001")
ADMIN_ID = UUID("10000000-0000-0000-0000-000000000002")
VIEWER_ID = UUID("10000000-0000-0000-0000-000000000003")
VIDEO_ID = UUID("20000000-0000-0000-0000-000000000001")
PENDING_VIDEO_ID = UUID("20000000-0000-0000-0000-000000000002")


class FakeUserClient:
    def __init__(self):
        self.fail_auth = False
        self.fail_batch = False
        self.following_ids = [str(CREATOR_ID)]
        self.notification_events = []

    async def request_json(self, method, path, request_id, **kwargs):
        if path == "/internal/auth/introspect":
            if self.fail_auth:
                raise ServiceUnavailable("auth unavailable")
            authorization = kwargs.get("headers", {}).get("Authorization", "")
            roles = {
                "Bearer creator-token": (CREATOR_ID, 1),
                "Bearer admin-token": (ADMIN_ID, 2),
                "Bearer viewer-token": (VIEWER_ID, 0),
            }
            if authorization not in roles:
                raise ServiceUnavailable("invalid test token")
            user_id, user_type = roles[authorization]
            return {
                "user_id": str(user_id),
                "user_type": user_type,
                "status": 0,
            }
        if path == "/internal/users/batch":
            if self.fail_batch:
                raise ServiceUnavailable("batch unavailable")
            names = {
                str(CREATOR_ID): ("creator", "Creator"),
                str(ADMIN_ID): ("admin", "Admin"),
                str(VIEWER_ID): ("viewer", "Viewer"),
            }
            return [
                {
                    "id": user_id,
                    "account": names.get(user_id, ("user", "用户"))[0],
                    "nickname": names.get(user_id, ("user", "用户"))[1],
                    "avatar": f"/{user_id}.png",
                    "bio": "",
                    "userType": 1,
                    "status": 0,
                }
                for user_id in kwargs["json"]["ids"]
            ]
        if path.endswith("/following-ids"):
            return {"ids": self.following_ids}
        if path == "/internal/notifications":
            self.notification_events.append(kwargs["json"])
            return {"ok": True, "duplicate": False}
        raise AssertionError(f"unexpected user call: {method} {path}")


class FakeSocialClient:
    def __init__(self):
        self.events = []
        self.fail = False

    async def request_json(self, method, path, request_id, **kwargs):
        if self.fail:
            raise ServiceUnavailable("social unavailable")
        self.events.append(kwargs["json"])
        return {"ok": True, "duplicate": False}


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add_all(
            [
                Category(id=1, name="推荐", type=0, sort_order=1),
                Category(id=2, name="科技", type=0, sort_order=2),
                Video(
                    id=VIDEO_ID,
                    title="Approved",
                    description="video",
                    tags=["test"],
                    category_id=2,
                    uploader_id=CREATOR_ID,
                    audit_status=1,
                    status=0,
                    like_count=4,
                    comment_count=2,
                    favorite_count=1,
                ),
                Video(
                    id=PENDING_VIDEO_ID,
                    title="Pending",
                    description="pending",
                    tags=[],
                    category_id=1,
                    uploader_id=CREATOR_ID,
                    audit_status=0,
                    status=0,
                ),
            ]
        )
        db.commit()
    yield


@pytest.fixture
def fake_user_client(monkeypatch):
    client = FakeUserClient()
    monkeypatch.setattr("app.main.get_user_client", lambda: client)
    monkeypatch.setattr("app.outbox.get_user_client", lambda: client)
    return client


@pytest.fixture
def fake_social_client(monkeypatch):
    client = FakeSocialClient()
    monkeypatch.setattr("app.outbox.get_social_client", lambda: client)
    return client


@pytest.fixture
def client(fake_user_client):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def ids():
    return {
        "creator": str(CREATOR_ID),
        "admin": str(ADMIN_ID),
        "viewer": str(VIEWER_ID),
        "video": str(VIDEO_ID),
        "pending": str(PENDING_VIDEO_ID),
    }


@pytest.fixture
def auth_headers():
    return lambda role: {"Authorization": f"Bearer {role}-token"}

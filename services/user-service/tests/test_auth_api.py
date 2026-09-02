from datetime import timedelta

from app.database import SessionLocal
from app.models import User
from app.security import create_token


class FakeAvatarObject:
    def stream(self, _chunk_size):
        yield b"avatar-bytes"

    def close(self):
        pass

    def release_conn(self):
        pass


class FakeAvatarStorage:
    def stat_object(self, bucket, object_name):
        assert bucket == "streamhub-media"
        assert object_name == "avatars/alice.png"
        return type("Metadata", (), {"content_type": "image/png"})()

    def get_object(self, bucket, object_name):
        assert bucket == "streamhub-media"
        assert object_name == "avatars/alice.png"
        return FakeAvatarObject()


def test_avatar_media_is_served_by_user_service(client, monkeypatch):
    monkeypatch.setattr(
        "app.main.get_avatar_storage", lambda: FakeAvatarStorage()
    )
    response = client.get("/avatars/alice.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"avatar-bytes"


def test_login_register_profile_password_and_avatar_contract(
    client, auth_headers, monkeypatch
):
    login = client.post(
        "/api/auth/login",
        json={"account": "alice", "password": "alice123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["account"] == "alice"
    assert client.post(
        "/api/auth/login",
        json={"account": "alice", "password": "wrong"},
    ).status_code == 400

    registered = client.post(
        "/api/auth/register",
        json={"account": "new-user", "password": "secret12", "nickname": "New"},
    )
    assert registered.status_code == 200
    assert client.post(
        "/api/auth/register",
        json={"account": "new-user", "password": "secret12", "nickname": "Again"},
    ).status_code == 400

    headers = auth_headers("alice")
    assert client.get("/api/auth/me", headers=headers).json()["nickname"] == "Alice"
    updated = client.patch(
        "/api/auth/me",
        headers=headers,
        json={"nickname": "Alice 2", "bio": "updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["nickname"] == "Alice 2"

    wrong_old = client.put(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "wrong", "new_password": "newpass1"},
    )
    assert wrong_old.status_code == 400

    uploaded = {}

    def fake_upload(file, object_name, length):
        uploaded.update(object_name=object_name, length=length)

    monkeypatch.setattr("app.main.upload_avatar_object", fake_upload)
    avatar = client.post(
        "/api/auth/upload-avatar",
        headers=headers,
        files={"file": ("avatar.png", b"image-bytes", "image/png")},
    )
    assert avatar.status_code == 200
    assert avatar.json()["data"]["avatar"].startswith("/avatars/")
    assert uploaded["object_name"].startswith("avatars/")


def test_upgrade_and_admin_guards(client, auth_headers, users):
    upgraded = client.post(
        "/api/auth/upgrade-to-creator",
        headers=auth_headers("alice"),
    )
    assert upgraded.status_code == 200
    assert upgraded.json()["data"]["userType"] == 1

    cannot_ban_admin = client.patch(
        f"/api/admin/users/{users['admin']}/ban",
        headers=auth_headers("admin"),
        json={"status": 1},
    )
    assert cannot_ban_admin.status_code == 403

    listing = client.get("/api/admin/users", headers=auth_headers("admin"))
    assert listing.status_code == 200
    assert listing.json()["total"] == 3

    changed = client.patch(
        f"/api/admin/users/{users['alice']}/type",
        headers=auth_headers("admin"),
        json={"userType": 1},
    )
    assert changed.status_code == 200
    assert changed.json()["userType"] == 1


def test_introspection_rejects_expired_bad_and_banned_tokens(client, auth_headers):
    valid = client.post("/internal/auth/introspect", headers=auth_headers("alice"))
    assert valid.status_code == 200
    assert valid.json()["user_type"] == 0

    with SessionLocal() as db:
        user = db.query(User).filter(User.account == "alice").one()
        expired = create_token(user, expires_delta=timedelta(seconds=-1))
    assert client.post(
        "/internal/auth/introspect",
        headers={"Authorization": f"Bearer {expired}"},
    ).status_code == 401
    assert client.post(
        "/internal/auth/introspect",
        headers={"Authorization": "Bearer broken.token"},
    ).status_code == 401

    with SessionLocal() as db:
        user = db.query(User).filter(User.account == "alice").one()
        banned_token = create_token(user)
        user.status = 1
        db.commit()
    assert client.post(
        "/internal/auth/introspect",
        headers={"Authorization": f"Bearer {banned_token}"},
    ).status_code == 401


def test_internal_user_batch_is_bounded(client, users):
    response = client.post(
        "/internal/users/batch",
        json={"ids": [users["alice"], users["creator"]]},
    )
    assert response.status_code == 200
    assert {item["account"] for item in response.json()} == {"alice", "creator"}

    too_many = client.post(
        "/internal/users/batch",
        json={"ids": [users["alice"]] * 201},
    )
    assert too_many.status_code == 422

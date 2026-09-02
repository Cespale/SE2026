from app.database import SessionLocal
from app.models import Follow, Notification
from shared.streamhub_common.service_client import ServiceUnavailable


def test_follow_relation_lists_and_creator_fans(client, auth_headers, users):
    headers = auth_headers("alice")
    assert client.post(
        f"/api/users/{users['alice']}/follow", headers=headers
    ).status_code == 400

    followed = client.post(
        f"/api/users/{users['creator']}/follow", headers=headers
    )
    assert followed.json() == {"ok": True, "isFollowing": True}
    assert client.post(
        f"/api/users/{users['creator']}/follow", headers=headers
    ).status_code == 200

    relation = client.get(
        f"/api/users/{users['creator']}/relation", headers=headers
    ).json()
    assert relation["isFollowing"] is True
    assert relation["followerCount"] == 1
    assert len(client.get(f"/api/users/{users['creator']}/followers").json()) == 1
    assert len(client.get(f"/api/users/{users['alice']}/following").json()) == 1
    internal_ids = client.get(
        f"/internal/users/{users['alice']}/following-ids"
    )
    assert internal_ids.status_code == 200
    assert internal_ids.json() == {"ids": [users["creator"]]}

    fans = client.get("/api/creator/fans", headers=auth_headers("creator"))
    assert fans.status_code == 200
    assert fans.json()["total"] == 1

    with SessionLocal() as db:
        assert db.query(Follow).count() == 1
        assert db.query(Notification).count() == 1

    unfollowed = client.delete(
        f"/api/users/{users['creator']}/follow", headers=headers
    )
    assert unfollowed.json()["isFollowing"] is False


def test_public_profile_and_admin_ban(client, auth_headers, users):
    profile = client.get(f"/api/users/{users['alice']}")
    assert profile.status_code == 200
    assert profile.json()["account"] == "alice"

    banned = client.patch(
        f"/api/admin/users/{users['alice']}/ban",
        headers=auth_headers("admin"),
        json={"status": 1},
    )
    assert banned.status_code == 200
    assert banned.json()["status"] == 1


def test_user_stats_uses_content_api_and_degrades_safely(
    client, users, monkeypatch
):
    class ContentClient:
        async def request_json(self, method, path, request_id):
            assert method == "GET"
            assert path.endswith("/received-like-count")
            assert request_id
            return {"likeCount": 12}

    monkeypatch.setattr("app.main.get_content_client", lambda: ContentClient())
    response = client.get(f"/api/users/{users['creator']}/stats")
    assert response.status_code == 200
    assert response.json() == {
        "followerCount": 0,
        "followingCount": 0,
        "likeCount": 12,
    }

    class UnavailableContentClient:
        async def request_json(self, method, path, request_id):
            raise ServiceUnavailable("content unavailable")

    monkeypatch.setattr(
        "app.main.get_content_client", lambda: UnavailableContentClient()
    )
    degraded = client.get(f"/api/users/{users['creator']}/stats")
    assert degraded.status_code == 200
    assert degraded.json()["likeCount"] == 0
    assert degraded.headers["X-StreamHub-Degraded"] == "content-service"

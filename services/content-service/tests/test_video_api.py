from app.database import SessionLocal
from app.models import ProcessedEvent, Video


def test_public_video_routes_enrich_users_and_increment_views(
    client, ids, fake_user_client
):
    assert client.get("/api/categories").status_code == 200
    listing = client.get("/api/videos?sort=latest")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["uploaderName"] == "Creator"
    assert client.get("/api/videos/recommended").status_code == 200
    detail = client.get(f"/api/videos/{ids['video']}")
    assert detail.status_code == 200
    assert detail.json()["viewCount"] == 1
    assert client.get(f"/api/videos/{ids['video']}/related").status_code == 200


def test_public_read_degrades_when_user_batch_fails(client, fake_user_client):
    fake_user_client.fail_batch = True
    response = client.get("/api/videos")
    assert response.status_code == 200
    assert response.json()["items"][0]["uploaderName"] == "用户"
    assert response.headers["X-StreamHub-Degraded"] == "user-service"


def test_auth_timeout_prevents_create_write(
    client, auth_headers, fake_user_client
):
    with SessionLocal() as db:
        before = db.query(Video).count()
    fake_user_client.fail_auth = True
    response = client.post(
        "/api/videos",
        headers=auth_headers("creator"),
        json={
            "title": "New video",
            "description": "desc",
            "tags": [],
            "categoryId": "1",
        },
    )
    assert response.status_code == 503
    with SessionLocal() as db:
        assert db.query(Video).count() == before


def test_create_creator_and_user_video_routes(client, auth_headers, ids):
    created = client.post(
        "/api/videos",
        headers=auth_headers("creator"),
        json={
            "title": "New video",
            "description": "desc",
            "tags": ["new"],
            "categoryId": "1",
        },
    )
    assert created.status_code == 200
    assert created.json()["auditStatus"] == 0
    assert client.get(
        "/api/creator/videos", headers=auth_headers("creator")
    ).status_code == 200
    assert client.get(f"/api/users/{ids['creator']}/videos").status_code == 200


def test_internal_targets_batches_counts_and_received_likes(client, ids):
    assert client.get(
        f"/internal/videos/{ids['video']}/interaction-target"
    ).status_code == 200
    assert client.get(
        f"/internal/videos/{ids['pending']}/interaction-target"
    ).status_code == 404
    assert client.post(
        "/internal/videos/batch", json={"ids": [ids["video"]]}
    ).status_code == 200

    event = {
        "eventId": "30000000-0000-0000-0000-000000000001",
        "likeCount": 8,
        "commentCount": 5,
        "favoriteCount": 3,
    }
    first = client.put(
        f"/internal/videos/{ids['video']}/interaction-counts", json=event
    )
    second = client.put(
        f"/internal/videos/{ids['video']}/interaction-counts", json=event
    )
    assert first.status_code == second.status_code == 200
    assert second.json()["likeCount"] == 8
    with SessionLocal() as db:
        assert db.query(ProcessedEvent).count() == 1

    likes = client.get(
        f"/internal/users/{ids['creator']}/received-like-count"
    )
    assert likes.json() == {"likeCount": 8}

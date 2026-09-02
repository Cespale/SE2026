from uuid import UUID

from app.database import SessionLocal
from app.models import (
    Comment,
    IntegrationOutbox,
    ProcessedEvent,
    VideoFavorite,
    VideoInteractionBaseline,
    VideoLike,
)


def test_like_and_favorite_are_unique_and_emit_absolute_counts(
    client, auth_headers, ids
):
    headers = auth_headers("viewer")
    assert client.post(f"/api/videos/{ids['video']}/like", headers=headers).status_code == 200
    assert client.post(f"/api/videos/{ids['video']}/like", headers=headers).status_code == 400
    assert client.get(f"/api/videos/{ids['video']}/like-status", headers=headers).json()["liked"] is True
    assert client.delete(f"/api/videos/{ids['video']}/like", headers=headers).status_code == 200
    assert client.delete(f"/api/videos/{ids['video']}/like", headers=headers).status_code == 400

    assert client.post(f"/api/videos/{ids['video']}/favorite", headers=headers).status_code == 200
    assert client.post(f"/api/videos/{ids['video']}/favorite", headers=headers).status_code == 400
    assert client.delete(f"/api/videos/{ids['video']}/favorite", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.query(VideoLike).count() == 0
        assert db.query(VideoFavorite).count() == 0
        assert db.query(IntegrationOutbox).count() == 4


def test_content_missing_or_timeout_prevents_local_write(
    client, auth_headers, ids, fake_content_client
):
    fake_content_client.validation = "missing"
    assert client.post(
        f"/api/videos/{ids['video']}/like", headers=auth_headers("viewer")
    ).status_code == 404
    fake_content_client.validation = "timeout"
    assert client.post(
        f"/api/videos/{ids['video']}/favorite", headers=auth_headers("viewer")
    ).status_code == 503
    with SessionLocal() as db:
        assert db.query(VideoLike).count() == 0
        assert db.query(VideoFavorite).count() == 0
        assert db.query(IntegrationOutbox).count() == 0


def test_legacy_counter_baseline_is_preserved(client, auth_headers, ids):
    with SessionLocal() as db:
        db.add(
            VideoInteractionBaseline(
                video_id=UUID(ids["video"]),
                like_count=100,
                comment_count=200,
                favorite_count=300,
            )
        )
        db.commit()
    response = client.post(
        f"/api/videos/{ids['video']}/like", headers=auth_headers("viewer")
    )
    assert response.status_code == 200
    assert response.json()["likeCount"] == 101
    with SessionLocal() as db:
        event = db.query(IntegrationOutbox).one()
        assert event.payload["commentCount"] == 200
        assert event.payload["favoriteCount"] == 300


def test_comment_reply_danmaku_enrichment_and_degraded_read(
    client, auth_headers, ids, fake_user_client
):
    created = client.post(
        f"/api/videos/{ids['video']}/comments",
        headers=auth_headers("viewer"),
        json={"content": "hello", "parentId": "0", "replyToUserId": ""},
    )
    assert created.status_code == 200
    comment_id = created.json()["id"]
    reply = client.post(
        f"/api/videos/{ids['video']}/comments",
        headers=auth_headers("creator"),
        json={"content": "reply", "parentId": comment_id, "replyToUserId": ids["viewer"]},
    )
    assert reply.status_code == 200
    assert len(client.get(f"/api/comments/{comment_id}/replies").json()) == 1
    assert client.post(
        f"/api/videos/{ids['video']}/danmaku",
        headers=auth_headers("viewer"),
        json={"content": "danmaku", "videoTime": 3},
    ).status_code == 200
    assert len(client.get(f"/api/videos/{ids['video']}/danmaku").json()) == 1

    fake_user_client.fail_batch = True
    degraded = client.get(f"/api/videos/{ids['video']}/comments")
    assert degraded.status_code == 200
    assert degraded.json()[0]["username"] == "匿名用户"
    assert degraded.headers["X-StreamHub-Degraded"] == "user-service"


def test_video_deleted_event_is_idempotent(client, auth_headers, ids):
    client.post(
        f"/api/videos/{ids['video']}/like", headers=auth_headers("viewer")
    )
    client.post(
        f"/api/videos/{ids['video']}/favorite", headers=auth_headers("viewer")
    )
    event = {
        "eventId": "50000000-0000-0000-0000-000000000001",
        "videoId": ids["video"],
    }
    first = client.post("/internal/events/video-deleted", json=event)
    second = client.post("/internal/events/video-deleted", json=event)
    assert first.status_code == second.status_code == 200
    assert second.json()["duplicate"] is True
    with SessionLocal() as db:
        assert db.query(VideoLike).count() == 0
        assert db.query(VideoFavorite).count() == 0
        assert db.query(ProcessedEvent).count() == 1

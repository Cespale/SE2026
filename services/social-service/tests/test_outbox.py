import asyncio

from app.database import SessionLocal
from app.models import IntegrationOutbox
from app.outbox import MAX_ATTEMPTS, drain_outbox_once, enqueue_outbox


def test_count_outbox_delivers_absolute_values(fake_content_client, fake_user_client):
    with SessionLocal() as db:
        event = enqueue_outbox(
            db,
            "video.interaction-counts.changed",
            {
                "videoId": "20000000-0000-0000-0000-000000000001",
                "likeCount": 2,
                "commentCount": 3,
                "favoriteCount": 1,
            },
        )
        db.commit()
        event_id = event.id
    assert asyncio.run(drain_outbox_once()) is True
    with SessionLocal() as db:
        assert db.get(IntegrationOutbox, event_id).status == "sent"
    assert fake_content_client.count_events[0]["likeCount"] == 2


def test_notification_outbox_delivers_to_user(fake_content_client, fake_user_client):
    with SessionLocal() as db:
        event = enqueue_outbox(
            db,
            "notification.created",
            {
                "recipientId": "10000000-0000-0000-0000-000000000001",
                "senderId": "10000000-0000-0000-0000-000000000003",
                "notifType": 1,
                "targetType": 0,
                "targetId": "20000000-0000-0000-0000-000000000001",
                "content": "comment",
            },
        )
        db.commit()
    assert asyncio.run(drain_outbox_once()) is True
    assert len(fake_user_client.notifications) == 1


def test_dead_outbox_event_is_visible_through_internal_diagnostics(
    client, fake_content_client, fake_user_client
):
    with SessionLocal() as db:
        event = enqueue_outbox(db, "unsupported.event", {})
        event.attempts = MAX_ATTEMPTS - 1
        db.commit()
        event_id = str(event.id)

    assert asyncio.run(drain_outbox_once()) is True
    response = client.get("/internal/outbox/dead")
    assert response.status_code == 200
    assert response.json()[0]["id"] == event_id
    assert response.json()[0]["attempts"] == MAX_ATTEMPTS

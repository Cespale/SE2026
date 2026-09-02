import asyncio

from app.database import SessionLocal
from app.models import IntegrationOutbox
from app.outbox import MAX_ATTEMPTS, drain_outbox_once, enqueue_outbox


def test_outbox_delivery_marks_sent(fake_user_client, fake_social_client):
    with SessionLocal() as db:
        event = enqueue_outbox(
            db,
            "notification.created",
            {
                "eventId": "40000000-0000-0000-0000-000000000001",
                "recipientId": "10000000-0000-0000-0000-000000000001",
                "senderId": None,
                "notifType": 4,
                "targetType": 0,
                "targetId": None,
                "content": "done",
            },
        )
        db.commit()
        event_id = event.id

    assert asyncio.run(drain_outbox_once()) is True
    with SessionLocal() as db:
        assert db.get(IntegrationOutbox, event_id).status == "sent"
    assert len(fake_user_client.notification_events) == 1


def test_outbox_failure_is_retried_without_losing_event(
    fake_user_client, fake_social_client
):
    fake_social_client.fail = True
    with SessionLocal() as db:
        event = enqueue_outbox(
            db,
            "video.deleted",
            {
                "eventId": "40000000-0000-0000-0000-000000000002",
                "videoId": "20000000-0000-0000-0000-000000000001",
            },
        )
        db.commit()
        event_id = event.id

    assert asyncio.run(drain_outbox_once()) is True
    with SessionLocal() as db:
        event = db.get(IntegrationOutbox, event_id)
        assert event.status == "pending"
        assert event.attempts == 1
        assert event.last_error


def test_dead_outbox_event_is_visible_through_internal_diagnostics(
    client, fake_user_client, fake_social_client
):
    fake_social_client.fail = True
    with SessionLocal() as db:
        event = enqueue_outbox(
            db,
            "video.deleted",
            {
                "eventId": "40000000-0000-0000-0000-000000000003",
                "videoId": "20000000-0000-0000-0000-000000000001",
            },
        )
        event.attempts = MAX_ATTEMPTS - 1
        db.commit()
        event_id = str(event.id)

    assert asyncio.run(drain_outbox_once()) is True
    response = client.get("/internal/outbox/dead")
    assert response.status_code == 200
    assert response.json()[0]["id"] == event_id
    assert response.json()[0]["attempts"] == MAX_ATTEMPTS

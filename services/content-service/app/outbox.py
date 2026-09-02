import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from .clients import get_social_client, get_user_client
from .database import SessionLocal
from .models import IntegrationOutbox


MAX_ATTEMPTS = 10


def enqueue_outbox(db, event_type: str, payload: dict) -> IntegrationOutbox:
    event_id = uuid.uuid4()
    body = dict(payload)
    body.setdefault("eventId", str(event_id))
    event = IntegrationOutbox(
        id=event_id,
        event_type=event_type,
        payload=body,
        status="pending",
        attempts=0,
    )
    db.add(event)
    return event


async def deliver(event: IntegrationOutbox) -> None:
    request_id = f"outbox-{event.id}"
    if event.event_type == "notification.created":
        await get_user_client().request_json(
            "POST",
            "/internal/notifications",
            request_id,
            json=event.payload,
        )
        return
    if event.event_type == "video.deleted":
        await get_social_client().request_json(
            "POST",
            "/internal/events/video-deleted",
            request_id,
            json=event.payload,
        )
        return
    raise RuntimeError(f"unsupported outbox event: {event.event_type}")


async def drain_outbox_once() -> bool:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        statement = (
            select(IntegrationOutbox)
            .where(
                IntegrationOutbox.status == "pending",
                or_(
                    IntegrationOutbox.next_attempt_at.is_(None),
                    IntegrationOutbox.next_attempt_at <= now,
                ),
            )
            .order_by(IntegrationOutbox.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        event = db.execute(statement).scalar_one_or_none()
        if event is None:
            return False
        event.status = "processing"
        try:
            await deliver(event)
        except Exception as exc:
            event.attempts += 1
            event.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            if event.attempts >= MAX_ATTEMPTS:
                event.status = "dead"
            else:
                event.status = "pending"
                event.next_attempt_at = now + timedelta(
                    seconds=min(300, 2**event.attempts)
                )
            db.commit()
            return True
        event.status = "sent"
        event.sent_at = datetime.now(timezone.utc)
        event.last_error = None
        db.commit()
        return True

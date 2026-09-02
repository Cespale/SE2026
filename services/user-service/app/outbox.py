from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Notification, ProcessedEvent
from .schemas import InternalNotificationIn


def record_notification_once(
    db: Session,
    event: InternalNotificationIn,
) -> bool:
    if db.get(ProcessedEvent, event.eventId):
        return True

    db.add(
        ProcessedEvent(
            event_id=event.eventId,
            event_type="notification.created",
        )
    )
    if event.senderId != event.recipientId:
        db.add(
            Notification(
                recipient_id=event.recipientId,
                sender_id=event.senderId,
                notif_type=event.notifType,
                target_type=event.targetType,
                target_id=event.targetId,
                content=event.content[:500],
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(ProcessedEvent, event.eventId):
            return True
        raise
    return False

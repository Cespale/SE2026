import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from .database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    user_id = Column(Uuid(as_uuid=True), nullable=False)
    video_id = Column(Uuid(as_uuid=True), nullable=False)
    parent_id = Column(Uuid(as_uuid=True), nullable=True)
    reply_to_user_id = Column(Uuid(as_uuid=True), nullable=True)
    like_count = Column(Integer, default=0)
    is_top = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommentMention(Base):
    __tablename__ = "comment_mentions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(Uuid(as_uuid=True), ForeignKey("comments.id"), nullable=False)
    mentioned_user_id = Column(Uuid(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("comment_id", "mentioned_user_id", name="uq_comment_mention"),
        Index("ix_mention_user", "mentioned_user_id"),
    )


class VideoLike(Base):
    __tablename__ = "video_likes"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), nullable=False)
    video_id = Column(Uuid(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_user_video_like"),
        Index("ix_video_likes_user", "user_id"),
        Index("ix_video_likes_video", "video_id"),
    )


class VideoFavorite(Base):
    __tablename__ = "video_favorites"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), nullable=False)
    video_id = Column(Uuid(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "video_id", name="uq_user_video_favorite"),
        Index("ix_video_favorites_user", "user_id"),
        Index("ix_video_favorites_video", "video_id"),
    )


class VideoInteractionBaseline(Base):
    __tablename__ = "video_interaction_baselines"

    video_id = Column(Uuid(as_uuid=True), primary_key=True)
    like_count = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    favorite_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Danmaku(Base):
    __tablename__ = "danmaku"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    color = Column(String(20), default="#FFFFFF")
    position = Column(SmallInteger, default=0)
    user_id = Column(Uuid(as_uuid=True), nullable=False)
    target_id = Column(Uuid(as_uuid=True), nullable=False)
    target_type = Column(SmallInteger, default=0)
    video_time = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LiveRoom(Base):
    __tablename__ = "live_rooms"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(120), nullable=False)
    description = Column(Text, default="")
    category_id = Column(Integer, nullable=True)
    cover = Column(Text, default="")
    stream_key = Column(String(80), unique=True, nullable=False)
    push_url = Column(Text, default="")
    pull_url = Column(Text, default="")
    anchor_id = Column(Uuid(as_uuid=True), nullable=False)
    online_count = Column(Integer, default=0)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(Uuid(as_uuid=True), nullable=False)
    target_type = Column(SmallInteger, nullable=False)
    target_id = Column(Uuid(as_uuid=True), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(SmallInteger, default=0)
    handler_id = Column(Uuid(as_uuid=True), nullable=True)
    handled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_reports_target", "target_type", "target_id"),
        Index("ix_reports_status", "status"),
    )


class SensitiveWord(Base):
    __tablename__ = "sensitive_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IntegrationOutbox(Base):
    __tablename__ = "integration_outbox"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_social_outbox_pending", "status", "next_attempt_at"),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id = Column(Uuid(as_uuid=True), primary_key=True)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

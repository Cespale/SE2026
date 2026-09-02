import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from .database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    type = Column(SmallInteger, default=0)
    sort_order = Column(Integer, default=0)


class Video(Base):
    __tablename__ = "videos"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(120), nullable=False)
    description = Column(Text, default="")
    tags = Column(ARRAY(String).with_variant(JSON, "sqlite"), default=list)
    cover_url = Column(Text, default="")
    video_url = Column(Text, default="")
    duration = Column(Integer, default=0)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0)
    uploader_id = Column(Uuid(as_uuid=True), nullable=False)
    audit_status = Column(SmallInteger, default=0)
    status = Column(SmallInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    reject_reason = Column(Text, nullable=True)


class IntegrationOutbox(Base):
    __tablename__ = "integration_outbox"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_content_outbox_pending", "status", "next_attempt_at"),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id = Column(Uuid(as_uuid=True), primary_key=True)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

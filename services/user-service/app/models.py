import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    avatar = Column(Text, default="")
    bio = Column(Text, default="")
    user_type = Column(SmallInteger, default=0)
    status = Column(SmallInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    stream_key = Column(String(20), unique=True, nullable=True)


class Follow(Base):
    __tablename__ = "follows"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_id = Column(Uuid(as_uuid=True), nullable=False)
    followee_id = Column(Uuid(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("follower_id", "followee_id", name="uq_follow_pair"),
        Index("ix_follows_follower", "follower_id"),
        Index("ix_follows_followee", "followee_id"),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_a_id = Column(Uuid(as_uuid=True), nullable=False)
    user_b_id = Column(Uuid(as_uuid=True), nullable=False)
    last_message_id = Column(Uuid(as_uuid=True), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_a_id", "user_b_id", name="uq_conversation_pair"),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        Uuid(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    sender_id = Column(Uuid(as_uuid=True), nullable=False)
    receiver_id = Column(Uuid(as_uuid=True), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(SmallInteger, default=0)
    is_recalled = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    recalled_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation")

    __table_args__ = (
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
        Index("ix_messages_receiver_unread", "receiver_id", "is_read"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    sender_id = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notif_type = Column(SmallInteger, default=0)
    target_type = Column(SmallInteger, default=0)
    target_id = Column(Uuid(as_uuid=True), nullable=True)
    content = Column(Text, default="")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender = relationship("User", foreign_keys=[sender_id])

    __table_args__ = (
        Index(
            "ix_notif_recipient_unread",
            "recipient_id",
            "is_read",
            "created_at",
        ),
    )


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    event_id = Column(Uuid(as_uuid=True), primary_key=True)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

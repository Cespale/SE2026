from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
import uuid
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=False)
    avatar = Column(Text, default='')
    bio = Column(Text, default='')
    user_type = Column(SmallInteger, default=0)  # 0普通，1创作者，2管理员
    status = Column(SmallInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    type = Column(SmallInteger, default=0)  # 0视频，1直播
    sort_order = Column(Integer, default=0)

class Video(Base):
    __tablename__ = 'videos'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(120), nullable=False)
    description = Column(Text, default='')
    tags = Column(ARRAY(String), default=list)
    cover_url = Column(Text, default='')
    video_url = Column(Text, default='')
    duration = Column(Integer, default=0)
    category_id = Column(Integer, ForeignKey('categories.id'))
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0)
    uploader_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    audit_status = Column(SmallInteger, default=0)  # 0待审核，1通过，2驳回
    status = Column(SmallInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    uploader = relationship('User')
    category = relationship('Category')

class Comment(Base):
    __tablename__ = 'comments'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    video_id = Column(UUID(as_uuid=True), ForeignKey('videos.id'))
    parent_id = Column(UUID(as_uuid=True), nullable=True)
    reply_to_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    like_count = Column(Integer, default=0)
    is_top = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User', foreign_keys=[user_id])
    reply_to_user = relationship('User', foreign_keys=[reply_to_user_id])

class Danmaku(Base):
    __tablename__ = 'danmaku'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    color = Column(String(20), default='#FFFFFF')
    position = Column(SmallInteger, default=0)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    target_id = Column(UUID(as_uuid=True), nullable=False)
    target_type = Column(SmallInteger, default=0)  # 0视频，1直播
    video_time = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship('User')

class LiveRoom(Base):
    __tablename__ = 'live_rooms'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(120), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    cover = Column(Text, default='')
    stream_key = Column(String(80), unique=True, nullable=False)
    push_url = Column(Text, default='')
    pull_url = Column(Text, default='')
    anchor_id = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    online_count = Column(Integer, default=0)
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    anchor = relationship('User')
    category = relationship('Category')


class Follow(Base):
    __tablename__ = 'follows'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    followee_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    follower = relationship('User', foreign_keys=[follower_id])
    followee = relationship('User', foreign_keys=[followee_id])

    __table_args__ = (
        UniqueConstraint('follower_id', 'followee_id', name='uq_follow_pair'),
        Index('ix_follows_follower', 'follower_id'),
        Index('ix_follows_followee', 'followee_id'),
    )


class Conversation(Base):
    """1对1 私聊会话。user_a_id < user_b_id 强制排序,避免同一对用户出现两条会话。"""
    __tablename__ = 'conversations'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_a_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    user_b_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    last_message_id = Column(UUID(as_uuid=True), nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_a = relationship('User', foreign_keys=[user_a_id])
    user_b = relationship('User', foreign_keys=[user_b_id])

    __table_args__ = (
        UniqueConstraint('user_a_id', 'user_b_id', name='uq_conversation_pair'),
    )


class Message(Base):
    __tablename__ = 'messages'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.id'), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    content = Column(Text, nullable=False)
    message_type = Column(SmallInteger, default=0)  # 0文本 1图片 2表情
    is_recalled = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    recalled_at = Column(DateTime(timezone=True), nullable=True)

    sender = relationship('User', foreign_keys=[sender_id])
    receiver = relationship('User', foreign_keys=[receiver_id])

    __table_args__ = (
        Index('ix_messages_conv_created', 'conversation_id', 'created_at'),
        Index('ix_messages_receiver_unread', 'receiver_id', 'is_read'),
    )


class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)  # 系统通知时为空
    notif_type = Column(SmallInteger, default=0)  # 0点赞 1评论 2关注 3@提及 4系统
    target_type = Column(SmallInteger, default=0)  # 0视频 1评论 2直播
    target_id = Column(UUID(as_uuid=True), nullable=True)
    content = Column(Text, default='')
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    recipient = relationship('User', foreign_keys=[recipient_id])
    sender = relationship('User', foreign_keys=[sender_id])

    __table_args__ = (
        Index('ix_notif_recipient_unread', 'recipient_id', 'is_read', 'created_at'),
    )


class CommentMention(Base):
    """评论正文中 @用户名 被解析后的索引,用于'有人@我'通知和聚合查询。"""
    __tablename__ = 'comment_mentions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id = Column(UUID(as_uuid=True), ForeignKey('comments.id'), nullable=False)
    mentioned_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    comment = relationship('Comment')
    mentioned_user = relationship('User')

    __table_args__ = (
        UniqueConstraint('comment_id', 'mentioned_user_id', name='uq_comment_mention'),
        Index('ix_mention_user', 'mentioned_user_id'),
    )

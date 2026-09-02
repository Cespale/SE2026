from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    account: str
    password: str


class RegisterIn(BaseModel):
    account: str
    password: str
    nickname: str


class UserOut(BaseModel):
    id: str
    account: str
    nickname: str
    avatar: str
    bio: str
    userType: int
    status: int
    streamKey: Optional[str] = None


class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserBrief(BaseModel):
    id: str
    account: str
    nickname: str
    avatar: str
    bio: str = ""


class FollowListItem(UserBrief):
    isMutual: bool = False
    followedAt: str = ""


class RelationOut(BaseModel):
    isFollowing: bool
    isFollowedBy: bool
    isMutual: bool
    followerCount: int
    followingCount: int


class ConversationOut(BaseModel):
    id: str
    peerId: str
    peerName: str
    peerAvatar: str
    lastMessage: str = ""
    lastMessageType: int = 0
    lastMessageAt: str = ""
    unreadCount: int = 0


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    messageType: int = 0


class MessageOut(BaseModel):
    id: str
    conversationId: str
    senderId: str
    senderName: str
    senderAvatar: str
    receiverId: str
    content: str
    messageType: int
    isRecalled: bool
    isRead: bool
    createTime: str


class NotificationOut(BaseModel):
    id: str
    notifType: int
    targetType: int
    targetId: str = ""
    senderId: str = ""
    senderName: str = ""
    senderAvatar: str = ""
    content: str
    isRead: bool
    createTime: str


class UnreadCountOut(BaseModel):
    total: int
    chat: int
    notification: int


class IntrospectionOut(BaseModel):
    user_id: str
    user_type: int
    status: int


class UserBatchIn(BaseModel):
    ids: list[UUID] = Field(max_length=200)


class InternalUserOut(BaseModel):
    id: str
    account: str
    nickname: str
    avatar: str
    bio: str
    userType: int
    status: int


class InternalNotificationIn(BaseModel):
    eventId: UUID
    recipientId: UUID
    senderId: UUID | None = None
    notifType: int
    targetType: int
    targetId: UUID | None = None
    content: str = ""

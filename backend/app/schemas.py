from pydantic import BaseModel, Field
from typing import List, Optional

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

class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None

class CategoryOut(BaseModel):
    id: str
    name: str
    type: int

class VideoCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = ''
    tags: List[str] = []
    coverUrl: str = ''
    videoUrl: str = ''
    duration: int = 300
    categoryId: str

class VideoOut(BaseModel):
    id: str
    title: str
    description: str
    tags: List[str]
    coverUrl: str
    videoUrl: str
    duration: int
    categoryId: str
    categoryName: str
    viewCount: int
    likeCount: int
    commentCount: int
    favoriteCount: int
    uploaderId: str
    uploaderName: str
    uploaderAvatar: str
    uploadTime: str
    auditStatus: int

class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    parentId: str = '0'

class CommentOut(BaseModel):
    id: str
    content: str
    userId: str
    username: str
    userAvatar: str
    videoId: str
    parentId: str
    likeCount: int
    isTop: bool
    createTime: str

class DanmakuCreate(BaseModel):
    content: str = Field(min_length=1, max_length=80)
    color: str = '#FFFFFF'
    position: int = 0
    videoTime: int = 0

class DanmakuOut(BaseModel):
    id: str
    content: str
    color: str
    position: int
    userId: str
    username: str
    videoTime: int
    sendTime: str

class LiveRoomCreate(BaseModel):
    title: str
    categoryId: str
    cover: str = ''

class LiveRoomOut(BaseModel):
    id: str
    title: str
    categoryId: str
    categoryName: str
    cover: str
    streamKey: str
    pushUrl: str
    pullUrl: str
    anchorId: str
    anchorName: str
    anchorAvatar: str
    onlineCount: int
    startTime: str
    endTime: str
    status: int

class AuditIn(BaseModel):
    auditStatus: int


# ---------- 社区互动:关注 / 粉丝 ----------

class UserBrief(BaseModel):
    """用户简要信息(粉丝列表/关注列表/消息发送者等场景复用)"""
    id: str
    account: str
    nickname: str
    avatar: str
    bio: str = ''


class FollowListItem(UserBrief):
    isMutual: bool = False
    followedAt: str = ''


class RelationOut(BaseModel):
    isFollowing: bool
    isFollowedBy: bool
    isMutual: bool
    followerCount: int
    followingCount: int


# ---------- 社区互动:私聊 ----------

class ConversationOut(BaseModel):
    id: str
    peerId: str
    peerName: str
    peerAvatar: str
    lastMessage: str = ''
    lastMessageType: int = 0
    lastMessageAt: str = ''
    unreadCount: int = 0


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    messageType: int = 0  # 0文本 1图片 2表情


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


# ---------- 社区互动:通知 ----------

class NotificationOut(BaseModel):
    id: str
    notifType: int        # 0点赞 1评论 2关注 3@提及 4系统
    targetType: int       # 0视频 1评论 2直播
    targetId: str = ''
    senderId: str = ''
    senderName: str = ''
    senderAvatar: str = ''
    content: str
    isRead: bool
    createTime: str


class UnreadCountOut(BaseModel):
    total: int
    chat: int
    notification: int


# ---------- 社区互动:评论二级回复增强 ----------

class CommentCreateV2(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    parentId: str = '0'
    replyToUserId: str = ''


class CommentOutV2(CommentOut):
    replyToUserId: str = ''
    replyToUsername: str = ''
    replyCount: int = 0

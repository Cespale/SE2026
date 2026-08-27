from pydantic import BaseModel, Field
from typing import List, Literal, Optional

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
    auditStatus: Literal[1, 2]

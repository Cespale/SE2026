from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    parentId: str = "0"
    replyToUserId: str = ""


class DanmakuCreate(BaseModel):
    content: str = Field(min_length=1, max_length=80)
    color: str = "#FFFFFF"
    position: int = 0
    videoTime: int = 0


class LiveRoomCreate(BaseModel):
    title: str
    categoryId: str
    cover: str = ""
    description: Optional[str] = None


class ReportCreate(BaseModel):
    target_type: int
    target_id: UUID
    reason: str


class VideoDeletedEvent(BaseModel):
    eventId: UUID
    videoId: UUID

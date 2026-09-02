from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VideoCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = ""
    tags: list[str] = []
    coverUrl: str = ""
    videoUrl: str = ""
    duration: int = 300
    categoryId: str


class VideoUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None


class AuditIn(BaseModel):
    auditStatus: Literal[1, 2]
    rejectReason: Optional[str] = None


class VideoBatchIn(BaseModel):
    ids: list[UUID] = Field(max_length=200)


class InteractionCountsIn(BaseModel):
    eventId: UUID
    likeCount: int = Field(ge=0)
    commentCount: int = Field(ge=0)
    favoriteCount: int = Field(ge=0)

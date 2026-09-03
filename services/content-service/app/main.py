import io
import asyncio
import os
import random
import re
import secrets
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

import cv2
import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_, text
from sqlalchemy.orm import Session

from shared.streamhub_common.auth_context import AuthContext
from shared.streamhub_common.request_id import RequestIdMiddleware
from shared.streamhub_common.service_client import ServiceUnavailable

from .clients import close_clients, get_user_client
from .config import OUTBOX_WORKER_ENABLED, SERVICE_VERSION
from .database import get_db
from .models import Category, IntegrationOutbox, ProcessedEvent, Video
from .object_storage import ContentObjectStorage
from .outbox import drain_outbox_once, enqueue_outbox
from .schemas import (
    AuditIn,
    InteractionCountsIn,
    VideoBatchIn,
    VideoCreate,
    VideoUpdateRequest,
)


_media_storage: ContentObjectStorage | None = None


def get_media_storage() -> ContentObjectStorage:
    global _media_storage
    if _media_storage is None:
        _media_storage = ContentObjectStorage.from_env()
    return _media_storage


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = None
    if OUTBOX_WORKER_ENABLED:
        async def run_outbox_worker() -> None:
            while True:
                processed = await drain_outbox_once()
                await asyncio.sleep(0.2 if processed else 1.0)

        worker = asyncio.create_task(run_outbox_worker())
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        await close_clients()


app = FastAPI(
    title="StreamHub Content Service",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)


@app.get("/health")
def health():
    return {"status": "ok", "service": "content"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "service": "content"}


@app.get("/version")
def version():
    return {"service": "content", "version": SERVICE_VERSION}


@app.get("/internal/outbox/dead")
def dead_outbox_events(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(IntegrationOutbox)
        .filter(IntegrationOutbox.status == "dead")
        .order_by(desc(IntegrationOutbox.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(row.id),
            "eventType": row.event_type,
            "attempts": row.attempts,
            "lastError": row.last_error or "",
            "createdAt": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


def parse_range_header(header: str, object_size: int) -> tuple[int, int]:
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if object_size <= 0 or not match or "," in header:
        raise ValueError("invalid byte range")
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        raise ValueError("invalid byte range")
    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            raise ValueError("invalid byte range")
        return max(object_size - suffix, 0), object_size - 1
    start = int(start_text)
    end = int(end_text) if end_text else object_size - 1
    if start >= object_size or end < start:
        raise ValueError("invalid byte range")
    return start, min(end, object_size - 1)


@app.get("/uploads/{media_path:path}")
def get_uploaded_media(media_path: str, request: Request):
    object_name = f"uploads/{media_path}"
    try:
        metadata = get_media_storage().stat_object(object_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="媒体文件不存在") from exc
    object_size = int(metadata.size)
    start = 0
    end = object_size - 1
    status_code = 200
    if request.headers.get("range"):
        try:
            start, end = parse_range_header(request.headers["range"], object_size)
        except ValueError as exc:
            raise HTTPException(
                status_code=416,
                detail="无效的媒体范围",
                headers={"Content-Range": f"bytes */{object_size}"},
            ) from exc
        status_code = 206
    length = end - start + 1

    def stream_object():
        result = get_media_storage().get_object(
            object_name, offset=start, length=length
        )
        try:
            yield from result.stream(64 * 1024)
        finally:
            result.close()
            result.release_conn()

    headers = {"Accept-Ranges": "bytes", "Content-Length": str(length)}
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{object_size}"
    return StreamingResponse(
        stream_object(),
        status_code=status_code,
        media_type=metadata.content_type or "application/octet-stream",
        headers=headers,
    )


async def current_auth_context(
    request: Request,
    authorization: str | None = Header(None),
) -> AuthContext:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        result = await get_user_client().request_json(
            "POST",
            "/internal/auth/introspect",
            request.state.request_id,
            headers={"Authorization": authorization},
        )
        context = AuthContext(
            user_id=UUID(result["user_id"]),
            user_type=int(result["user_type"]),
            status=int(result["status"]),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise HTTPException(status_code=401, detail="登录状态已失效") from exc
        raise HTTPException(status_code=503, detail="用户服务暂不可用") from exc
    except (ServiceUnavailable, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="用户服务暂不可用") from exc
    if context.status != 0:
        raise HTTPException(status_code=401, detail="用户不存在或已被封禁")
    return context


async def require_creator(
    context: AuthContext = Depends(current_auth_context),
) -> AuthContext:
    if not context.is_creator:
        raise HTTPException(status_code=403, detail="需要创作者权限")
    return context


async def require_admin(
    context: AuthContext = Depends(current_auth_context),
) -> AuthContext:
    if not context.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return context


async def user_map_for(
    user_ids: list[UUID],
    request: Request,
    response: Response,
) -> dict[str, dict]:
    unique_ids = list(dict.fromkeys(str(user_id) for user_id in user_ids))
    if not unique_ids:
        return {}
    try:
        rows = await get_user_client().request_json(
            "POST",
            "/internal/users/batch",
            request.state.request_id,
            json={"ids": unique_ids},
        )
        return {str(row["id"]): row for row in rows}
    except (ServiceUnavailable, httpx.HTTPError, KeyError, TypeError):
        response.headers["X-StreamHub-Degraded"] = "user-service"
        return {}


def video_payload(video: Video, db: Session, users: dict[str, dict]) -> dict:
    category = db.get(Category, video.category_id) if video.category_id else None
    uploader = users.get(str(video.uploader_id), {})
    return {
        "id": str(video.id),
        "title": video.title,
        "description": video.description or "",
        "tags": video.tags or [],
        "coverUrl": video.cover_url or "",
        "videoUrl": video.video_url or "",
        "duration": video.duration or 0,
        "categoryId": str(video.category_id or ""),
        "categoryName": category.name if category else "",
        "viewCount": video.view_count or 0,
        "likeCount": video.like_count or 0,
        "commentCount": video.comment_count or 0,
        "favoriteCount": video.favorite_count or 0,
        "uploaderId": str(video.uploader_id),
        "uploaderName": uploader.get("nickname", "用户"),
        "uploaderAvatar": uploader.get("avatar", ""),
        "uploadTime": video.created_at.isoformat() if video.created_at else "",
        "auditStatus": video.audit_status or 0,
        "rejectReason": video.reject_reason or "",
    }


async def video_items(
    videos: list[Video],
    db: Session,
    request: Request,
    response: Response,
) -> list[dict]:
    users = await user_map_for(
        [video.uploader_id for video in videos], request, response
    )
    return [video_payload(video, db, users) for video in videos]


@app.get("/api/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(Category).order_by(Category.type, Category.sort_order).all()
    return [{"id": "0", "name": "推荐", "type": 0}] + [
        {"id": str(row.id), "name": row.name, "type": row.type or 0}
        for row in rows
    ]


@app.get("/api/videos")
async def list_videos(
    request: Request,
    response: Response,
    category_id: Optional[str] = None,
    keyword: Optional[str] = None,
    sort: str = "comprehensive",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Video).filter(Video.status == 0, Video.audit_status == 1)
    if category_id and category_id != "0":
        query = query.filter(Video.category_id == int(category_id))
    if keyword:
        query = query.filter(
            or_(
                Video.title.ilike(f"%{keyword}%"),
                Video.description.ilike(f"%{keyword}%"),
            )
        )
    if sort == "latest":
        query = query.order_by(desc(Video.created_at))
    elif sort == "hottest":
        query = query.order_by(desc(Video.view_count), desc(Video.like_count))
    else:
        query = query.order_by(func.random())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": await video_items(rows, db, request, response),
        "hasMore": page * page_size < total,
    }


@app.get("/api/videos/recommended")
async def recommended_videos(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    rows = db.query(Video).filter(
        Video.status == 0, Video.audit_status == 1
    ).all()
    random.shuffle(rows)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    return {
        "items": await video_items(page_rows, db, request, response),
        "hasMore": start + page_size < len(rows),
    }


@app.get("/api/videos/{video_id}")
async def get_video(
    video_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    video.view_count = (video.view_count or 0) + 1
    db.commit()
    db.refresh(video)
    return (await video_items([video], db, request, response))[0]


@app.get("/api/videos/{video_id}/related")
async def related_videos(
    video_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if not video:
        return {"items": []}
    rows = db.query(Video).filter(
        Video.id != video_id,
        Video.category_id == video.category_id,
        Video.status == 0,
        Video.audit_status == 1,
        Video.video_url.like("/demo-videos/%"),
    ).order_by(func.random()).limit(5).all()
    return {"items": await video_items(rows, db, request, response)}


@app.post("/api/videos")
async def create_video(
    data: VideoCreate,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    video_url = (data.videoUrl or "").strip()
    cover_url = (data.coverUrl or "").strip()
    if not video_url or ".mp4" not in video_url.lower():
        video_url = "/demo-videos/video1.mp4"
    if not cover_url:
        cover_url = "https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop"
    category_id = int(data.categoryId or 1)
    if not db.get(Category, category_id):
        category_id = 1
    video = Video(
        title=data.title or "未命名视频",
        description=data.description or "这是一个由创作者上传的视频。",
        tags=data.tags or ["投稿", "视频", "StreamHub"],
        cover_url=cover_url,
        video_url=video_url,
        duration=data.duration or 596,
        category_id=category_id,
        uploader_id=context.user_id,
        audit_status=0,
        status=0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return (await video_items([video], db, request, response))[0]


@app.get("/api/creator/videos")
async def creator_videos(
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    rows = db.query(Video).filter(Video.uploader_id == context.user_id).order_by(
        desc(Video.created_at)
    ).all()
    return {"items": await video_items(rows, db, request, response)}


@app.get("/api/users/{user_id}/videos")
async def user_videos(
    user_id: UUID,
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    query = db.query(Video).filter(
        Video.uploader_id == user_id,
        Video.audit_status == 1,
        Video.status == 0,
    ).order_by(desc(Video.created_at))
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": await video_items(rows, db, request, response),
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < total,
    }


def notification_payload(video: Video, content: str) -> dict:
    return {
        "recipientId": str(video.uploader_id),
        "senderId": None,
        "notifType": 4,
        "targetType": 0,
        "targetId": str(video.id),
        "content": content,
    }


@app.get("/api/admin/videos/pending")
async def pending_videos(
    request: Request,
    response: Response,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(Video).filter(Video.audit_status == 0).order_by(
        desc(Video.created_at)
    ).all()
    return {"items": await video_items(rows, db, request, response)}


@app.patch("/api/admin/videos/{video_id}/audit")
async def audit_video(
    video_id: UUID,
    data: AuditIn,
    request: Request,
    response: Response,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    video.audit_status = data.auditStatus
    video.reject_reason = data.rejectReason or None
    if data.auditStatus == 1:
        content = f'您的视频 "{video.title}" 已通过审核'
    else:
        content = f'您的视频 "{video.title}" 未通过审核，理由：{data.rejectReason or "未填写具体原因"}'
    enqueue_outbox(db, "notification.created", notification_payload(video, content))
    db.commit()
    db.refresh(video)
    return (await video_items([video], db, request, response))[0]


@app.get("/api/feed")
async def get_feed(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    try:
        result = await get_user_client().request_json(
            "GET",
            f"/internal/users/{context.user_id}/following-ids",
            request.state.request_id,
        )
        following_ids = [UUID(value) for value in result["ids"]]
    except (ServiceUnavailable, httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="用户服务暂不可用") from exc
    query = db.query(Video).filter(
        Video.uploader_id.in_(following_ids),
        Video.status == 0,
        Video.audit_status == 1,
    ).order_by(desc(Video.created_at))
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": await video_items(rows, db, request, response),
        "hasMore": page * page_size < total,
    }


@app.get("/api/creator/week-stats")
def creator_week_stats(_: AuthContext = Depends(require_creator)):
    today = datetime.now().date()
    labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return [
        {"day": labels[index], "views": 0}
        for index, _ in enumerate(today - timedelta(days=value) for value in range(6, -1, -1))
    ]


@app.get("/api/creator/videos/{status}")
async def creator_videos_by_status(
    status: int,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    rows = db.query(Video).filter(
        Video.uploader_id == context.user_id,
        Video.audit_status == status,
    ).order_by(desc(Video.created_at)).all()
    return {"items": await video_items(rows, db, request, response)}


@app.delete("/api/creator/videos/{video_id}")
def delete_video(
    video_id: UUID,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.uploader_id == context.user_id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在或无权限删除")
    enqueue_outbox(
        db,
        "video.deleted",
        {"videoId": str(video.id)},
    )
    db.delete(video)
    db.commit()
    return {"code": 0, "message": "删除成功"}


@app.put("/api/creator/videos/{video_id}")
async def update_video(
    video_id: UUID,
    data: VideoUpdateRequest,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.uploader_id == context.user_id,
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在或无权限编辑")
    if data.title is not None:
        video.title = data.title
    if data.description is not None:
        video.description = data.description
    if data.category_id is not None and db.get(Category, data.category_id):
        video.category_id = data.category_id
    db.commit()
    db.refresh(video)
    payload = (await video_items([video], db, request, response))[0]
    return {"code": 0, "message": "更新成功", "data": payload}


@app.get("/api/admin/videos")
async def admin_videos(
    request: Request,
    response: Response,
    page: int = 1,
    limit: int = 20,
    keyword: Optional[str] = None,
    audit_status: Optional[int] = None,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Video).filter(Video.status == 0)
    if keyword:
        query = query.filter(Video.title.ilike(f"%{keyword}%"))
    if audit_status is not None:
        query = query.filter(Video.audit_status == audit_status)
    total = query.count()
    rows = query.order_by(desc(Video.created_at)).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": await video_items(rows, db, request, response),
        "total": total,
        "page": page,
        "hasMore": page * limit < total,
    }


@app.post("/api/admin/videos/{video_id}/warn")
def warn_video(
    video_id: UUID,
    data: dict,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    reason = data.get("reason", "管理员警告")
    enqueue_outbox(
        db,
        "notification.created",
        notification_payload(video, f'您的视频 "{video.title}" 收到管理员警告：{reason}'),
    )
    db.commit()
    return {"code": 0, "message": "警告已发送"}


@app.post("/api/admin/videos/{video_id}/unapprove")
def unapprove_video(
    video_id: UUID,
    data: dict,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    reason = data.get("reason", "管理员将视频设为待审核状态")
    video.audit_status = 0
    video.reject_reason = reason
    enqueue_outbox(
        db,
        "notification.created",
        notification_payload(video, f'您的视频 "{video.title}" 已被设为待审核，理由：{reason}'),
    )
    db.commit()
    return {"code": 0, "message": "已设为待审核"}


def upload_length(file: UploadFile) -> int:
    if file.size is not None:
        return int(file.size)
    current = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    length = file.file.tell()
    file.file.seek(current)
    return int(length)


def safe_extension(filename: str | None, default: str) -> str:
    candidate = (filename or "").rsplit(".", 1)[-1].lower()
    return candidate if re.fullmatch(r"[a-z0-9]{1,10}", candidate) else default


@app.post("/api/videos/upload-cover")
async def upload_video_cover(
    file: UploadFile = File(...),
    context: AuthContext = Depends(require_creator),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")
    length = upload_length(file)
    if length > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过5MB")
    filename = f"cover_{context.user_id}_{secrets.token_hex(8)}.{safe_extension(file.filename, 'jpg')}"
    object_name = f"uploads/covers/{filename}"
    file.file.seek(0)
    get_media_storage().upload_stream(
        file.file,
        object_name,
        length,
        file.content_type,
    )
    return {
        "code": 0,
        "message": "封面上传成功",
        "data": {"coverUrl": f"/{object_name}"},
    }


@app.post("/api/videos/upload-file")
async def upload_video_file(
    file: UploadFile = File(...),
    context: AuthContext = Depends(require_creator),
):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="只支持视频文件")
    if file.size is not None and file.size > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过500MB")
    extension = safe_extension(file.filename, "mp4")
    filename = f"{context.user_id}_{secrets.token_hex(8)}.{extension}"
    object_name = f"uploads/videos/{filename}"
    temp_path: Path | None = None
    try:
        file.file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)
        if temp_path.stat().st_size > 500 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件大小不能超过500MB")
        get_media_storage().upload_path(temp_path, object_name, file.content_type)
        cover_url = ""
        duration = 0
        capture = cv2.VideoCapture(str(temp_path))
        try:
            if capture.isOpened():
                success, frame = capture.read()
                if success:
                    encoded, image = cv2.imencode(".jpg", frame)
                    if encoded:
                        cover_name = f"uploads/covers/{context.user_id}_{secrets.token_hex(8)}.jpg"
                        cover_bytes = image.tobytes()
                        get_media_storage().upload_stream(
                            io.BytesIO(cover_bytes),
                            cover_name,
                            len(cover_bytes),
                            "image/jpeg",
                        )
                        cover_url = f"/{cover_name}"
                fps = capture.get(cv2.CAP_PROP_FPS)
                frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                if fps > 0:
                    duration = int(frames / fps)
        finally:
            capture.release()
        return {
            "code": 0,
            "message": "上传成功",
            "data": {
                "videoUrl": f"/{object_name}",
                "duration": duration,
                "coverUrl": cover_url,
            },
        }
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


@app.post("/api/admin/local-videos/sync")
def sync_local_videos(
    context: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    directory = Path(os.getenv("LOCAL_VIDEO_DIR", "/app/public/demo-videos"))
    if not directory.is_dir():
        return {"message": "本地视频同步完成", "created": 0, "updated": 0}
    category = db.get(Category, 1)
    if not category:
        db.add(Category(id=1, name="推荐", type=0, sort_order=1))
        db.flush()
    created = 0
    updated = 0
    for path in sorted(directory.glob("*.mp4")):
        video_url = f"/demo-videos/{path.name}"
        video = db.query(Video).filter(Video.video_url == video_url).first()
        if video:
            video.status = 0
            video.audit_status = 1
            updated += 1
        else:
            db.add(
                Video(
                    title=path.stem.replace("-", " ").replace("_", " ").title(),
                    description=f"本地演示视频：{path.name}",
                    tags=["本地视频", "自动导入", "演示"],
                    video_url=video_url,
                    category_id=1,
                    uploader_id=context.user_id,
                    audit_status=1,
                    status=0,
                )
            )
            created += 1
    db.commit()
    return {"message": "本地视频同步完成", "created": created, "updated": updated}


@app.post("/api/admin/cleanup-uploads")
def cleanup_uploads(
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    used_urls = {
        row[0]
        for row in db.query(Video.video_url)
        .filter(Video.video_url.like("/uploads/videos/%"))
        .all()
    }
    deleted: list[str] = []
    try:
        storage = get_media_storage()
        for object_name in storage.iter_names("uploads/videos/"):
            if f"/{object_name}" not in used_urls:
                storage.remove_object(object_name)
                deleted.append(Path(object_name).name)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="对象存储清理失败") from exc
    return {
        "code": 0,
        "message": f"已清理 {len(deleted)} 个残留文件",
        "deleted": deleted,
    }


@app.get("/internal/videos/{video_id}/interaction-target")
def interaction_target(video_id: UUID, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video or video.status != 0 or video.audit_status != 1:
        raise HTTPException(status_code=404, detail="视频不存在或不可互动")
    return {"id": str(video.id), "uploaderId": str(video.uploader_id)}


@app.post("/internal/videos/batch")
async def batch_videos(
    data: VideoBatchIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    rows = db.query(Video).filter(Video.id.in_(data.ids)).all() if data.ids else []
    by_id = {row.id: row for row in rows}
    videos = [
        video
        for video_id in data.ids
        if (video := by_id.get(video_id)) is not None
    ]
    # 复用完整的视频序列化（含作者信息、播放量等），
    # 供跨服务的用户喜欢列表等场景直接返回给前端。
    return await video_items(videos, db, request, response)


@app.put("/internal/videos/{video_id}/interaction-counts")
def update_interaction_counts(
    video_id: UUID,
    data: InteractionCountsIn,
    db: Session = Depends(get_db),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="视频不存在")
    if not db.get(ProcessedEvent, data.eventId):
        db.add(
            ProcessedEvent(
                event_id=data.eventId,
                event_type="video.interaction-counts.changed",
            )
        )
        video.like_count = data.likeCount
        video.comment_count = data.commentCount
        video.favorite_count = data.favoriteCount
        db.commit()
        db.refresh(video)
    return {
        "likeCount": video.like_count or 0,
        "commentCount": video.comment_count or 0,
        "favoriteCount": video.favorite_count or 0,
    }


@app.get("/internal/users/{user_id}/received-like-count")
def received_like_count(user_id: UUID, db: Session = Depends(get_db)):
    count = db.query(func.sum(Video.like_count)).filter(
        Video.uploader_id == user_id,
        Video.status == 0,
        Video.audit_status == 1,
    ).scalar() or 0
    return {"likeCount": int(count)}

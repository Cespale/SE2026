import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import desc, or_, text
from sqlalchemy.orm import Session

from shared.streamhub_common.auth_context import AuthContext
from shared.streamhub_common.request_id import RequestIdMiddleware
from shared.streamhub_common.service_client import ServiceUnavailable

from .clients import close_clients, get_content_client, get_user_client
from .config import (
    OUTBOX_WORKER_ENABLED,
    SERVICE_VERSION,
    SRS_PUBLIC_HTTP_BASE,
    SRS_PUBLIC_RTMP_BASE,
)
from .database import SessionLocal, get_db
from .models import (
    Comment,
    CommentMention,
    Danmaku,
    IntegrationOutbox,
    LiveRoom,
    ProcessedEvent,
    Report,
    SensitiveWord,
    VideoFavorite,
    VideoInteractionBaseline,
    VideoLike,
)
from .outbox import drain_outbox_once, enqueue_outbox
from .schemas import (
    CommentCreate,
    DanmakuCreate,
    LiveRoomCreate,
    ReportCreate,
    VideoDeletedEvent,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = None
    if OUTBOX_WORKER_ENABLED:
        async def run_worker() -> None:
            while True:
                processed = await drain_outbox_once()
                await asyncio.sleep(0.2 if processed else 1.0)

        worker = asyncio.create_task(run_worker())
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
    title="StreamHub Social Service",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)


@app.get("/health")
def health():
    return {"status": "ok", "service": "social"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready", "service": "social"}


@app.get("/version")
def version():
    return {"service": "social", "version": SERVICE_VERSION}


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


async def validate_video(video_id: UUID, request_id: str) -> dict:
    try:
        return await get_content_client().request_json(
            "GET",
            f"/internal/videos/{video_id}/interaction-target",
            request_id,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=404, detail="视频不存在或不可互动") from exc
        raise HTTPException(status_code=503, detail="内容服务暂不可用") from exc
    except ServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail="内容服务暂不可用") from exc


async def fetch_users(
    ids: list[UUID], request: Request, response: Response
) -> dict[str, dict]:
    unique = list(dict.fromkeys(str(value) for value in ids))
    if not unique:
        return {}
    try:
        rows = await get_user_client().request_json(
            "POST",
            "/internal/users/batch",
            request.state.request_id,
            json={"ids": unique},
        )
        return {str(row["id"]): row for row in rows}
    except (ServiceUnavailable, httpx.HTTPError, KeyError, TypeError):
        response.headers["X-StreamHub-Degraded"] = "user-service"
        return {}


def counts_for(db: Session, video_id: UUID) -> dict[str, int]:
    baseline = db.get(VideoInteractionBaseline, video_id)
    return {
        "likeCount": (baseline.like_count if baseline else 0)
        + db.query(VideoLike).filter(VideoLike.video_id == video_id).count(),
        "commentCount": (baseline.comment_count if baseline else 0)
        + db.query(Comment).filter(Comment.video_id == video_id).count(),
        "favoriteCount": (baseline.favorite_count if baseline else 0)
        + db.query(VideoFavorite).filter(VideoFavorite.video_id == video_id).count(),
    }


def enqueue_counts(db: Session, video_id: UUID) -> None:
    db.flush()
    enqueue_outbox(
        db,
        "video.interaction-counts.changed",
        {"videoId": str(video_id), **counts_for(db, video_id)},
    )


@app.post("/api/videos/{video_id}/like")
async def like_video(
    video_id: UUID,
    request: Request,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    await validate_video(video_id, request.state.request_id)
    if db.query(VideoLike).filter(
        VideoLike.user_id == context.user_id,
        VideoLike.video_id == video_id,
    ).first():
        raise HTTPException(status_code=400, detail="已经点赞")
    db.add(VideoLike(user_id=context.user_id, video_id=video_id))
    enqueue_counts(db, video_id)
    db.commit()
    return {"ok": True, "liked": True, **counts_for(db, video_id)}


@app.delete("/api/videos/{video_id}/like")
async def unlike_video(
    video_id: UUID,
    request: Request,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    await validate_video(video_id, request.state.request_id)
    row = db.query(VideoLike).filter(
        VideoLike.user_id == context.user_id,
        VideoLike.video_id == video_id,
    ).first()
    if not row:
        raise HTTPException(status_code=400, detail="尚未点赞")
    db.delete(row)
    enqueue_counts(db, video_id)
    db.commit()
    return {"ok": True, "liked": False, **counts_for(db, video_id)}


@app.get("/api/videos/{video_id}/like-status")
def like_status(
    video_id: UUID,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    liked = db.query(VideoLike).filter(
        VideoLike.user_id == context.user_id,
        VideoLike.video_id == video_id,
    ).first() is not None
    return {"liked": liked}


@app.post("/api/videos/{video_id}/favorite")
async def favorite_video(
    video_id: UUID,
    request: Request,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    await validate_video(video_id, request.state.request_id)
    if db.query(VideoFavorite).filter(
        VideoFavorite.user_id == context.user_id,
        VideoFavorite.video_id == video_id,
    ).first():
        raise HTTPException(status_code=400, detail="已经收藏")
    db.add(VideoFavorite(user_id=context.user_id, video_id=video_id))
    enqueue_counts(db, video_id)
    db.commit()
    return {"ok": True, "favorited": True, **counts_for(db, video_id)}


@app.delete("/api/videos/{video_id}/favorite")
async def unfavorite_video(
    video_id: UUID,
    request: Request,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    await validate_video(video_id, request.state.request_id)
    row = db.query(VideoFavorite).filter(
        VideoFavorite.user_id == context.user_id,
        VideoFavorite.video_id == video_id,
    ).first()
    if not row:
        raise HTTPException(status_code=400, detail="尚未收藏")
    db.delete(row)
    enqueue_counts(db, video_id)
    db.commit()
    return {"ok": True, "favorited": False, **counts_for(db, video_id)}


def comment_payload(comment: Comment, users: dict[str, dict], reply_count: int = 0) -> dict:
    user = users.get(str(comment.user_id), {})
    reply_user = users.get(str(comment.reply_to_user_id), {}) if comment.reply_to_user_id else {}
    return {
        "id": str(comment.id),
        "content": comment.content,
        "userId": str(comment.user_id),
        "username": user.get("nickname", "匿名用户"),
        "userAvatar": user.get("avatar", ""),
        "videoId": str(comment.video_id),
        "parentId": str(comment.parent_id) if comment.parent_id else "0",
        "likeCount": comment.like_count or 0,
        "isTop": bool(comment.is_top),
        "createTime": comment.created_at.isoformat() if comment.created_at else "",
        "replyToUserId": str(comment.reply_to_user_id) if comment.reply_to_user_id else "",
        "replyToUsername": reply_user.get("nickname", ""),
        "replyCount": reply_count,
    }


async def render_comments(
    rows: list[Comment], db: Session, request: Request, response: Response
) -> list[dict]:
    user_ids = [row.user_id for row in rows] + [
        row.reply_to_user_id for row in rows if row.reply_to_user_id
    ]
    users = await fetch_users(user_ids, request, response)
    return [
        comment_payload(
            row,
            users,
            db.query(Comment).filter(Comment.parent_id == row.id).count(),
        )
        for row in rows
    ]


@app.get("/api/videos/{video_id}/comments")
async def list_comments(
    video_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    rows = db.query(Comment).filter(
        Comment.video_id == video_id,
        Comment.parent_id.is_(None),
    ).order_by(desc(Comment.is_top), desc(Comment.created_at)).all()
    return await render_comments(rows, db, request, response)


@app.get("/api/comments/{comment_id}/replies")
async def list_replies(
    comment_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    rows = db.query(Comment).filter(Comment.parent_id == comment_id).order_by(
        Comment.created_at
    ).all()
    return await render_comments(rows, db, request, response)


def mask_sensitive(db: Session, content: str) -> str:
    """敏感词替换为等长 *号(与单体一致), 而不是拒绝发送。"""
    words = [row[0] for row in db.query(SensitiveWord.word).all() if row[0]]
    result = content
    for word in words:
        if word in result:
            result = result.replace(word, "*" * len(word))
    return result


@app.post("/api/videos/{video_id}/comments")
async def create_comment(
    video_id: UUID,
    data: CommentCreate,
    request: Request,
    response: Response,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    target = await validate_video(video_id, request.state.request_id)
    content = mask_sensitive(db, data.content)
    parent_id = None if data.parentId in {"", "0"} else UUID(data.parentId)
    reply_to = None if not data.replyToUserId else UUID(data.replyToUserId)
    if parent_id and not db.get(Comment, parent_id):
        raise HTTPException(status_code=404, detail="父评论不存在")
    comment = Comment(
        content=content,
        user_id=context.user_id,
        video_id=video_id,
        parent_id=parent_id,
        reply_to_user_id=reply_to,
    )
    db.add(comment)
    db.flush()
    enqueue_counts(db, video_id)
    recipient = reply_to or UUID(target["uploaderId"])
    if recipient != context.user_id:
        enqueue_outbox(
            db,
            "notification.created",
            {
                "recipientId": str(recipient),
                "senderId": str(context.user_id),
                "notifType": 1,
                "targetType": 0,
                "targetId": str(video_id),
                "content": "有人评论了视频",
            },
        )
    db.commit()
    db.refresh(comment)
    return (await render_comments([comment], db, request, response))[0]


@app.delete("/api/comments/{comment_id}")
async def delete_comment(
    comment_id: UUID,
    request: Request,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    target = await validate_video(comment.video_id, request.state.request_id)
    if context.user_id not in {comment.user_id, UUID(target["uploaderId"])} and not context.is_admin:
        raise HTTPException(status_code=403, detail="无权删除评论")
    db.query(Comment).filter(Comment.parent_id == comment.id).delete()
    db.delete(comment)
    enqueue_counts(db, comment.video_id)
    db.commit()
    return {"code": 0, "message": "删除成功"}


def danmaku_payload(row: Danmaku, users: dict[str, dict]) -> dict:
    user = users.get(str(row.user_id), {})
    return {
        "id": str(row.id),
        "content": row.content,
        "color": row.color,
        "position": row.position,
        "userId": str(row.user_id),
        "username": user.get("nickname", "匿名用户"),
        "videoTime": row.video_time or 0,
        "sendTime": row.created_at.isoformat() if row.created_at else "",
    }


@app.get("/api/videos/{video_id}/danmaku")
async def list_danmaku(
    video_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    rows = db.query(Danmaku).filter(
        Danmaku.target_id == video_id,
        Danmaku.target_type == 0,
    ).order_by(Danmaku.created_at).all()
    users = await fetch_users([row.user_id for row in rows], request, response)
    return [danmaku_payload(row, users) for row in rows]


@app.post("/api/videos/{video_id}/danmaku")
async def create_danmaku(
    video_id: UUID,
    data: DanmakuCreate,
    request: Request,
    response: Response,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    await validate_video(video_id, request.state.request_id)
    content = mask_sensitive(db, data.content)
    row = Danmaku(
        content=content,
        color=data.color,
        position=data.position,
        user_id=context.user_id,
        target_id=video_id,
        target_type=0,
        video_time=data.videoTime,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    users = await fetch_users([context.user_id], request, response)
    return danmaku_payload(row, users)


class LiveHub:
    def __init__(self) -> None:
        self.rooms: dict[str, list[WebSocket]] = {}

    async def connect(self, room_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.rooms.setdefault(room_id, []).append(websocket)
        await self.broadcast(room_id, {"type": "online", "count": len(self.rooms[room_id])})

    def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        connections = self.rooms.get(room_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: str, payload: dict) -> None:
        for websocket in self.rooms.get(room_id, []).copy():
            try:
                await websocket.send_json(payload)
            except Exception:
                self.disconnect(room_id, websocket)


live_hub = LiveHub()


async def category_names(request_id: str) -> dict[int, str]:
    try:
        rows = await get_content_client().request_json(
            "GET", "/api/categories", request_id
        )
        return {int(row["id"]): row["name"] for row in rows if row["id"] != "0"}
    except (ServiceUnavailable, httpx.HTTPError, KeyError, ValueError):
        return {}


async def render_rooms(
    rows: list[LiveRoom], request: Request, response: Response
) -> list[dict]:
    users = await fetch_users([row.anchor_id for row in rows], request, response)
    categories = await category_names(request.state.request_id)
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "description": row.description or "",
            "categoryId": str(row.category_id or ""),
            "categoryName": categories.get(row.category_id, ""),
            "cover": row.cover or "",
            "streamKey": row.stream_key,
            "pushUrl": f"{SRS_PUBLIC_RTMP_BASE}/{row.stream_key}",
            "pullUrl": f"{SRS_PUBLIC_HTTP_BASE}/{row.stream_key}.flv",
            "anchorId": str(row.anchor_id),
            "anchorName": users.get(str(row.anchor_id), {}).get("nickname", "主播"),
            "anchorAvatar": users.get(str(row.anchor_id), {}).get("avatar", ""),
            "onlineCount": len(live_hub.rooms.get(str(row.id), [])),
            "startTime": row.start_time.isoformat() if row.start_time else "",
            "endTime": row.end_time.isoformat() if row.end_time else "",
            "status": row.status or 0,
        }
        for row in rows
    ]


@app.get("/api/live/rooms")
async def list_live_rooms(
    request: Request,
    response: Response,
    category_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(LiveRoom).filter(LiveRoom.status == 1)
    if category_id:
        try:
            query = query.filter(LiveRoom.category_id == int(category_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="分类编号无效") from exc
    rows = query.order_by(desc(LiveRoom.created_at)).all()
    return {"items": await render_rooms(rows, request, response)}


@app.get("/api/live/rooms/{room_id}")
async def get_live_room(
    room_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="直播间不存在")
    return (await render_rooms([room], request, response))[0]


@app.post("/api/live/rooms")
async def create_live_room(
    data: LiveRoomCreate,
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    existing = db.query(LiveRoom).filter(
        LiveRoom.anchor_id == context.user_id,
        LiveRoom.status == 1,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="你已有一个正在直播的房间，请先结束当前直播")
    db.query(LiveRoom).filter(
        LiveRoom.anchor_id == context.user_id,
        LiveRoom.status == 2,
    ).delete(synchronize_session=False)
    categories = await category_names(request.state.request_id)
    category_id = int(data.categoryId)
    if categories and category_id not in categories:
        raise HTTPException(status_code=400, detail="分类不存在")
    # 复用创作者账号的稳定推流密钥(与开播页 OBS 配置一致), 而不是每次随机生成,
    # 否则按开播页第一次显示的密钥推流, 永远对不上新建房间的拉流地址。
    stream_key = None
    try:
        key_resp = await get_user_client().request_json(
            "GET",
            f"/internal/users/{context.user_id}/stream-key",
            request.state.request_id,
        )
        stream_key = key_resp.get("streamKey")
    except (ServiceUnavailable, httpx.HTTPError, KeyError, TypeError):
        pass
    if not stream_key:
        stream_key = secrets.token_hex(12)
    room = LiveRoom(
        title=data.title,
        description=data.description or "",
        category_id=category_id,
        cover=data.cover,
        stream_key=stream_key,
        push_url=f"{SRS_PUBLIC_RTMP_BASE}/{stream_key}",
        pull_url=f"{SRS_PUBLIC_HTTP_BASE}/{stream_key}.flv",
        anchor_id=context.user_id,
        status=1,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return (await render_rooms([room], request, response))[0]


def stop_room(room_id: UUID, context: AuthContext, db: Session):
    room = db.get(LiveRoom, room_id)
    if not room or (room.anchor_id != context.user_id and not context.is_admin):
        raise HTTPException(status_code=404, detail="直播间不存在或无权限")
    room.status = 2
    room.end_time = datetime.now(timezone.utc)
    db.commit()
    return {"code": 0, "message": "直播已结束"}


@app.post("/api/live/rooms/{room_id}/end")
def end_live_room(
    room_id: UUID,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    return stop_room(room_id, context, db)


@app.post("/api/live/rooms/{room_id}/stop")
def stop_live_room(
    room_id: UUID,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    return stop_room(room_id, context, db)


@app.websocket("/ws/live/{room_id}")
async def live_websocket(websocket: WebSocket, room_id: str):
    # 解析登录态(前端通过 ?token= 携带 JWT), 进入提示应显示真实昵称而不是"游客"
    nickname = "游客"
    user_avatar = ""
    user_id = ""
    token = websocket.query_params.get("token")
    if token:
        try:
            introspect = await get_user_client().request_json(
                "POST",
                "/internal/auth/introspect",
                "ws-live",
                headers={"Authorization": f"Bearer {token}"},
            )
            users = await get_user_client().request_json(
                "POST",
                "/internal/users/batch",
                "ws-live",
                json={"ids": [introspect["user_id"]]},
            )
            if users:
                user_id = str(users[0].get("id", introspect["user_id"]))
                nickname = users[0].get("nickname") or nickname
                user_avatar = users[0].get("avatar") or ""
        except Exception:
            # 解析失败时退回"游客", 不影响观看
            pass
    try:
        await live_hub.connect(room_id, websocket)
        await websocket.send_json(
            {"type": "join_ack", "onlineCount": len(live_hub.rooms.get(room_id, []))}
        )
        await live_hub.broadcast(
            room_id,
            {
                "type": "system",
                "content": f"{nickname} 进入直播间",
                "userId": user_id,
                "username": nickname,
                "userAvatar": user_avatar,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        while True:
            data = json.loads(await websocket.receive_text())
            if data.get("type") == "heartbeat":
                await websocket.send_json(
                    {"type": "online", "count": len(live_hub.rooms.get(room_id, []))}
                )
            elif data.get("type") == "danmaku":
                await live_hub.broadcast(room_id, {"type": "danmaku", **data})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        live_hub.disconnect(room_id, websocket)


@app.post("/api/live/{room_id}/danmaku")
async def send_live_danmaku(
    room_id: UUID,
    data: dict,
    request: Request,
    response: Response,
    context: AuthContext = Depends(current_auth_context),
):
    # 带上发送者昵称/头像, 否则前端聊天室所有消息都只能显示"观众"
    users = await fetch_users([context.user_id], request, response)
    user = users.get(str(context.user_id), {})
    await live_hub.broadcast(
        str(room_id),
        {
            "type": "danmaku",
            "content": data.get("content", ""),
            "color": data.get("color", "#fff"),
            "userId": str(context.user_id),
            "username": user.get("nickname") or "观众",
            "userAvatar": user.get("avatar") or "",
            "id": f"{context.user_id}-{datetime.now(timezone.utc).isoformat()}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {"code": 0, "message": "发送成功"}


@app.get("/api/creator/active-room")
async def active_room(
    request: Request,
    response: Response,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    room = db.query(LiveRoom).filter(
        LiveRoom.anchor_id == context.user_id,
        LiveRoom.status == 1,
    ).order_by(desc(LiveRoom.created_at)).first()
    if not room:
        return None
    return (await render_rooms([room], request, response))[0]


@app.post("/api/reports")
def create_report(
    data: ReportCreate,
    context: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    report = Report(
        reporter_id=context.user_id,
        target_type=data.target_type,
        target_id=data.target_id,
        reason=data.reason,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": str(report.id), "status": report.status or 0}


def report_payload(
    row: Report,
    users: dict[str, dict],
    videos: dict[str, dict],
    comments: dict[str, Comment],
    rooms: dict[str, LiveRoom],
) -> dict:
    """渲染举报条目: 带上举报者、举报对象内容以及来源跳转链接。

    - target_type 0=视频 1=评论 2=直播
    - 评论举报需要借助 comments 反查所属视频, 才能跳转到原视频页。
    """
    target_info: dict = {}
    target_url = "#"
    video_id = None

    if row.target_type == 0:  # 视频
        video = videos.get(str(row.target_id))
        target_info = {"title": video["title"] if video else "已删除", "type": "video"}
        target_url = f"/#/video/{row.target_id}"
    elif row.target_type == 1:  # 评论
        comment = comments.get(str(row.target_id))
        if comment:
            video_id = str(comment.video_id)
            target_info = {"content": (comment.content or "")[:50], "type": "comment"}
            target_url = f"/#/video/{comment.video_id}#comment-{row.target_id}"
        else:
            target_info = {"content": "已删除", "type": "comment"}
            target_url = "#"
    elif row.target_type == 2:  # 直播
        room = rooms.get(str(row.target_id))
        target_info = {"title": room.title if room else "已删除", "type": "live"}
        target_url = f"/#/live/{row.target_id}"

    reporter = users.get(str(row.reporter_id), {})
    return {
        "id": str(row.id),
        "reporterId": str(row.reporter_id),
        "reporterName": reporter.get("nickname") or "未知用户",
        "reporterAvatar": reporter.get("avatar") or "",
        "targetType": row.target_type,
        "targetId": str(row.target_id),
        "targetInfo": target_info,
        "targetUrl": target_url,
        "videoId": video_id,
        "reason": row.reason,
        "status": row.status or 0,
        "handlerId": str(row.handler_id) if row.handler_id else None,
        "handledAt": row.handled_at.isoformat() if row.handled_at else "",
        "createTime": row.created_at.isoformat() if row.created_at else "",
        "createdAt": row.created_at.isoformat() if row.created_at else "",
    }


@app.get("/api/admin/reports")
async def admin_reports(
    request: Request,
    response: Response,
    page: int = 1,
    limit: int = 20,
    status: Optional[int] = None,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Report)
    if status is not None:
        query = query.filter(Report.status == status)
    total = query.count()
    rows = query.order_by(desc(Report.created_at)).offset((page - 1) * limit).limit(limit).all()
    if not rows:
        return {"items": [], "total": total, "page": page, "hasMore": False}

    # 举报者信息(用户服务)
    users = await fetch_users([row.reporter_id for row in rows], request, response)

    # 评论/直播间存在社交服务本地, 先反查
    comment_ids = [row.target_id for row in rows if row.target_type == 1]
    comments: dict[str, Comment] = {}
    if comment_ids:
        for comment in db.query(Comment).filter(Comment.id.in_(comment_ids)).all():
            comments[str(comment.id)] = comment

    room_ids = [row.target_id for row in rows if row.target_type == 2]
    rooms: dict[str, LiveRoom] = {}
    if room_ids:
        for room in db.query(LiveRoom).filter(LiveRoom.id.in_(room_ids)).all():
            rooms[str(room.id)] = room

    # 视频信息(内容服务)
    video_ids = [str(row.target_id) for row in rows if row.target_type == 0]
    videos: dict[str, dict] = {}
    if video_ids:
        try:
            batch = await get_content_client().request_json(
                "POST",
                "/internal/videos/batch",
                request.state.request_id,
                json={"ids": video_ids},
            )
            videos = {item["id"]: item for item in batch}
        except (ServiceUnavailable, httpx.HTTPError, KeyError, TypeError):
            response.headers["X-StreamHub-Degraded"] = "content-service"

    return {
        "items": [
            report_payload(row, users, videos, comments, rooms) for row in rows
        ],
        "total": total,
        "page": page,
        "hasMore": page * limit < total,
    }


def resolve_report(report_id: UUID, status: int, context: AuthContext, db: Session):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="举报不存在")
    report.status = status
    report.handler_id = context.user_id
    report.handled_at = datetime.now(timezone.utc)
    db.commit()
    return {"code": 0, "message": "处理成功"}


@app.patch("/api/admin/reports/{report_id}/handle")
def handle_report(
    report_id: UUID,
    context: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return resolve_report(report_id, 1, context, db)


@app.patch("/api/admin/reports/{report_id}/ignore")
def ignore_report(
    report_id: UUID,
    context: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return resolve_report(report_id, 2, context, db)


@app.get("/api/admin/sensitive-words")
def list_sensitive_words(
    _: AuthContext = Depends(require_admin), db: Session = Depends(get_db)
):
    # 前端与管理页契约期望 {"items": [...]}（与单体一致），裸数组会让列表永远为空。
    items = [
        {
            "id": row.id,
            "word": row.word,
            "createdAt": row.created_at.isoformat() if row.created_at else "",
        }
        for row in db.query(SensitiveWord).order_by(SensitiveWord.id).all()
    ]
    return {"items": items, "total": len(items)}


@app.post("/api/admin/sensitive-words")
def add_sensitive_word(
    data: dict,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    word = (data.get("word") or "").strip()
    if not word:
        raise HTTPException(status_code=400, detail="敏感词不能为空")
    if db.query(SensitiveWord).filter(SensitiveWord.word == word).first():
        raise HTTPException(status_code=400, detail="敏感词已存在")
    row = SensitiveWord(word=word)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "word": row.word}


@app.delete("/api/admin/sensitive-words/{word_id}")
def delete_sensitive_word(
    word_id: int,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.get(SensitiveWord, word_id)
    if not row:
        raise HTTPException(status_code=404, detail="敏感词不存在")
    db.delete(row)
    db.commit()
    return {"code": 0, "message": "删除成功"}


@app.get("/api/admin/live-rooms")
async def admin_live_rooms(
    request: Request,
    response: Response,
    page: int = 1,
    limit: int = 20,
    keyword: Optional[str] = None,
    status: Optional[int] = None,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(LiveRoom)
    if keyword:
        query = query.filter(LiveRoom.title.ilike(f"%{keyword}%"))
    if status is not None:
        query = query.filter(LiveRoom.status == status)
    total = query.count()
    rows = query.order_by(desc(LiveRoom.created_at)).offset((page - 1) * limit).limit(limit).all()
    return {"items": await render_rooms(rows, request, response), "total": total, "page": page}


@app.post("/api/admin/live-rooms/{room_id}/warn")
def warn_live_room(
    room_id: UUID,
    data: dict,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="直播间不存在")
    enqueue_outbox(
        db,
        "notification.created",
        {
            "recipientId": str(room.anchor_id),
            "senderId": None,
            "notifType": 4,
            "targetType": 2,
            "targetId": str(room.id),
            "content": f'您的直播间 "{room.title}" 收到管理员警告：{data.get("reason", "管理员警告")}',
        },
    )
    db.commit()
    return {"code": 0, "message": "警告已发送"}


@app.post("/api/admin/live-rooms/{room_id}/close")
def close_live_room(
    room_id: UUID,
    data: dict,
    _: AuthContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="直播间不存在")
    room.status = 2
    room.end_time = datetime.now(timezone.utc)
    enqueue_outbox(
        db,
        "notification.created",
        {
            "recipientId": str(room.anchor_id),
            "senderId": None,
            "notifType": 4,
            "targetType": 2,
            "targetId": str(room.id),
            "content": f'您的直播间 "{room.title}" 已被管理员关闭，理由：{data.get("reason", "管理员关闭")}',
        },
    )
    db.commit()
    return {"code": 0, "message": "直播间已关闭"}


@app.get("/api/users/{user_id}/likes")
async def user_likes(
    user_id: UUID,
    request: Request,
    page: int = 1,
    page_size: int = 20,
    _: AuthContext = Depends(current_auth_context),
    db: Session = Depends(get_db),
):
    query = db.query(VideoLike).filter(VideoLike.user_id == user_id).order_by(
        desc(VideoLike.created_at)
    )
    total = query.count()
    likes = query.offset((page - 1) * page_size).limit(page_size).all()
    try:
        items = await get_content_client().request_json(
            "POST",
            "/internal/videos/batch",
            request.state.request_id,
            json={"ids": [str(row.video_id) for row in likes]},
        )
    except (ServiceUnavailable, httpx.HTTPError) as exc:
        raise HTTPException(status_code=503, detail="内容服务暂不可用") from exc
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": page * page_size < total,
    }


@app.get("/api/creator/comments")
async def creator_comments(
    request: Request,
    response: Response,
    page: int = 1,
    limit: int = 20,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    rows = db.query(Comment).order_by(desc(Comment.created_at)).all()
    if not rows:
        return {"items": [], "total": 0}
    videos = await get_content_client().request_json(
        "POST",
        "/internal/videos/batch",
        request.state.request_id,
        json={"ids": list(dict.fromkeys(str(row.video_id) for row in rows))},
    )
    owned = {row["id"]: row for row in videos if row["uploaderId"] == str(context.user_id)}
    filtered = [row for row in rows if str(row.video_id) in owned]
    page_rows = filtered[(page - 1) * limit : page * limit]
    users = await fetch_users([row.user_id for row in page_rows], request, response)
    return {
        "items": [
            {
                "id": str(row.id),
                "videoTitle": owned[str(row.video_id)]["title"],
                "content": row.content,
                "userName": users.get(str(row.user_id), {}).get("nickname", "匿名用户"),
                "userAvatar": users.get(str(row.user_id), {}).get("avatar", ""),
                "time": row.created_at.isoformat() if row.created_at else "",
            }
            for row in page_rows
        ],
        "total": len(filtered),
    }


@app.delete("/api/creator/comments/{comment_id}")
async def creator_delete_comment(
    comment_id: UUID,
    request: Request,
    context: AuthContext = Depends(require_creator),
    db: Session = Depends(get_db),
):
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    target = await validate_video(comment.video_id, request.state.request_id)
    if UUID(target["uploaderId"]) != context.user_id:
        raise HTTPException(status_code=403, detail="无权删除评论")
    db.delete(comment)
    enqueue_counts(db, comment.video_id)
    db.commit()
    return {"code": 0, "message": "删除成功"}


@app.post("/internal/events/video-deleted")
def consume_video_deleted(
    event: VideoDeletedEvent,
    db: Session = Depends(get_db),
):
    if db.get(ProcessedEvent, event.eventId):
        return {"ok": True, "duplicate": True}
    comment_ids = [
        row[0]
        for row in db.query(Comment.id).filter(Comment.video_id == event.videoId).all()
    ]
    if comment_ids:
        db.query(CommentMention).filter(
            CommentMention.comment_id.in_(comment_ids)
        ).delete(synchronize_session=False)
    db.query(Comment).filter(Comment.video_id == event.videoId).delete()
    db.query(VideoLike).filter(VideoLike.video_id == event.videoId).delete()
    db.query(VideoFavorite).filter(VideoFavorite.video_id == event.videoId).delete()
    db.query(VideoInteractionBaseline).filter(
        VideoInteractionBaseline.video_id == event.videoId
    ).delete()
    db.query(Danmaku).filter(
        Danmaku.target_id == event.videoId,
        Danmaku.target_type == 0,
    ).delete()
    db.add(
        ProcessedEvent(
            event_id=event.eventId,
            event_type="video.deleted",
        )
    )
    db.commit()
    return {"ok": True, "duplicate": False}

import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from minio import Minio
from sqlalchemy import desc, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from shared.streamhub_common.request_id import RequestIdMiddleware
from shared.streamhub_common.service_client import ServiceClient, ServiceUnavailable

from .config import CONTENT_SERVICE_URL, SERVICE_VERSION
from .database import SessionLocal, get_db
from .models import Conversation, Follow, Message, Notification, User
from .outbox import record_notification_once
from .schemas import (
    ChangePasswordRequest,
    ConversationOut,
    FollowListItem,
    InternalNotificationIn,
    InternalUserOut,
    IntrospectionOut,
    LoginIn,
    MessageCreate,
    MessageOut,
    NotificationOut,
    ProfileUpdate,
    RegisterIn,
    RelationOut,
    UnreadCountOut,
    UserBatchIn,
    UserBrief,
    UserOut,
)
from .security import (
    create_token,
    get_current_user,
    hash_password,
    parse_token,
    require_admin,
    require_creator,
    verify_password,
)


_content_client: ServiceClient | None = None


def get_content_client() -> ServiceClient:
    global _content_client
    if _content_client is None:
        _content_client = ServiceClient(CONTENT_SERVICE_URL)
    return _content_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if _content_client is not None:
        await _content_client.aclose()


app = FastAPI(
    title="StreamHub User Service",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)


def user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        account=user.account,
        nickname=user.nickname,
        avatar=user.avatar or "",
        bio=user.bio or "",
        userType=user.user_type or 0,
        status=user.status or 0,
        streamKey=user.stream_key,
    )


def user_brief(user: User) -> UserBrief:
    return UserBrief(
        id=str(user.id),
        account=user.account,
        nickname=user.nickname,
        avatar=user.avatar or "",
        bio=user.bio or "",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "user"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "service": "user"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"service": "user", "version": SERVICE_VERSION}


@app.post("/api/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.account == data.account).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="账号或密码错误")
    if user.status == 1:
        raise HTTPException(status_code=403, detail="账号已被封禁")
    return {"token": create_token(user), "user": user_out(user)}


@app.post("/api/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.account == data.account).first():
        raise HTTPException(status_code=400, detail="账号已存在")
    user = User(
        account=data.account,
        password_hash=hash_password(data.password),
        nickname=data.nickname,
        avatar=f"https://api.dicebear.com/7.x/avataaars/svg?seed={data.account}",
        user_type=0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user), "user": user_out(user)}


@app.get("/api/auth/me")
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 创作者需要稳定的推流密钥(开播页首次进入即展示)。
    # 缺失时惰性生成一次, 之后每次开播都复用同一个 key。
    if user.user_type >= 1:
        ensure_stream_key(user, db)
    return user_out(user)


@app.patch("/api/auth/me")
def update_me(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.bio is not None:
        user.bio = data.bio
    if data.avatar is not None:
        user.avatar = data.avatar
    db.commit()
    db.refresh(user)
    return user_out(user)


@app.put("/api/auth/change-password")
def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少6位")
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"code": 0, "message": "密码修改成功"}


@app.post("/api/auth/upgrade-to-creator")
def upgrade_to_creator(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.user_type >= 1:
        raise HTTPException(status_code=400, detail="已经是创作者或管理员")
    user.user_type = 1
    db.commit()
    db.refresh(user)
    return {
        "code": 0,
        "message": "已成功升级为创作者",
        "data": {"userType": user.user_type},
    }


def get_avatar_storage() -> Minio:
    secret_key = os.getenv("MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", ""))
    if not secret_key:
        raise HTTPException(status_code=503, detail="对象存储未配置")
    return Minio(
        os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "streamhub")),
        secret_key=secret_key,
        secure=os.getenv("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
    )


@app.get("/avatars/{avatar_path:path}")
def get_avatar(avatar_path: str):
    if not avatar_path or ".." in avatar_path or "\\" in avatar_path:
        raise HTTPException(status_code=404, detail="头像不存在")
    object_name = f"avatars/{avatar_path}"
    bucket = os.getenv("MINIO_BUCKET", "streamhub-media")
    try:
        storage = get_avatar_storage()
        metadata = storage.stat_object(bucket, object_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="头像不存在") from exc

    def stream_object():
        result = storage.get_object(bucket, object_name)
        try:
            yield from result.stream(64 * 1024)
        finally:
            result.close()
            result.release_conn()

    return StreamingResponse(
        stream_object(),
        media_type=metadata.content_type or "application/octet-stream",
    )


def upload_avatar_object(file: UploadFile, object_name: str, length: int) -> None:
    client = get_avatar_storage()
    bucket = os.getenv("MINIO_BUCKET", "streamhub-media")
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        file.file.seek(0)
        client.put_object(
            bucket,
            object_name,
            file.file,
            length,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="对象存储上传失败") from exc


def upload_length(file: UploadFile) -> int:
    if file.size is not None:
        return int(file.size)
    current = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    length = file.file.tell()
    file.file.seek(current)
    return int(length)


@app.post("/api/auth/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")
    length = upload_length(file)
    if length > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过5MB")
    candidate = (file.filename or "").rsplit(".", 1)[-1].lower()
    extension = candidate if re.fullmatch(r"[a-z0-9]{1,10}", candidate) else "jpg"
    filename = f"{user.id}_{secrets.token_hex(8)}.{extension}"
    upload_avatar_object(file, f"avatars/{filename}", length)
    user.avatar = f"/avatars/{filename}"
    db.commit()
    db.refresh(user)
    return {
        "code": 0,
        "message": "头像上传成功",
        "data": {"avatar": user.avatar},
    }


def create_notification(
    db: Session,
    *,
    recipient_id,
    sender_id,
    notif_type: int,
    target_type: int = 0,
    target_id=None,
    content: str = "",
) -> Notification | None:
    if str(recipient_id) == str(sender_id):
        return None
    notification = Notification(
        recipient_id=recipient_id,
        sender_id=sender_id,
        notif_type=notif_type,
        target_type=target_type,
        target_id=target_id,
        content=content[:500],
    )
    db.add(notification)
    return notification


@app.post("/api/users/{user_id}/follow")
def follow_user(
    user_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="不能关注自己")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    existing = db.query(Follow).filter(
        Follow.follower_id == me.id,
        Follow.followee_id == user_id,
    ).first()
    if existing:
        return {"ok": True, "isFollowing": True}
    db.add(Follow(follower_id=me.id, followee_id=user_id))
    create_notification(
        db,
        recipient_id=user_id,
        sender_id=me.id,
        notif_type=2,
        content=f"{me.nickname} 关注了你",
    )
    db.commit()
    return {"ok": True, "isFollowing": True}


@app.delete("/api/users/{user_id}/follow")
def unfollow_user(
    user_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Follow).filter(
        Follow.follower_id == me.id,
        Follow.followee_id == user_id,
    ).delete()
    db.commit()
    return {"ok": True, "isFollowing": False}


@app.get("/api/users/{user_id}/relation")
def get_relation(
    user_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_following = db.query(Follow).filter(
        Follow.follower_id == me.id,
        Follow.followee_id == user_id,
    ).first() is not None
    is_followed_by = db.query(Follow).filter(
        Follow.follower_id == user_id,
        Follow.followee_id == me.id,
    ).first() is not None
    follower_count = db.query(Follow).filter(Follow.followee_id == user_id).count()
    following_count = db.query(Follow).filter(Follow.follower_id == user_id).count()
    return RelationOut(
        isFollowing=is_following,
        isFollowedBy=is_followed_by,
        isMutual=is_following and is_followed_by,
        followerCount=follower_count,
        followingCount=following_count,
    )


@app.get("/api/users/{user_id}/followers")
def list_followers(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Follow, User)
        .join(User, User.id == Follow.follower_id)
        .filter(Follow.followee_id == user_id)
        .order_by(desc(Follow.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        FollowListItem(
            **user_brief(user).model_dump(),
            followedAt=follow.created_at.isoformat() if follow.created_at else "",
        )
        for follow, user in rows
    ]


@app.get("/api/users/{user_id}/following")
def list_following(
    user_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Follow, User)
        .join(User, User.id == Follow.followee_id)
        .filter(Follow.follower_id == user_id)
        .order_by(desc(Follow.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        FollowListItem(
            **user_brief(user).model_dump(),
            followedAt=follow.created_at.isoformat() if follow.created_at else "",
        )
        for follow, user in rows
    ]


@app.get("/api/users/{user_id}")
def get_user_profile(user_id: UUID, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user_out(user)


@app.get("/api/users/{user_id}/stats")
async def get_user_stats(
    user_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    follower_count = db.query(Follow).filter(Follow.followee_id == user_id).count()
    following_count = db.query(Follow).filter(Follow.follower_id == user_id).count()
    try:
        result = await get_content_client().request_json(
            "GET",
            f"/internal/users/{user_id}/received-like-count",
            request.state.request_id,
        )
        like_count = max(0, int(result["likeCount"]))
    except (ServiceUnavailable, KeyError, TypeError, ValueError):
        like_count = 0
        response.headers["X-StreamHub-Degraded"] = "content-service"
    return {
        "followerCount": follower_count,
        "followingCount": following_count,
        "likeCount": like_count,
    }


@app.get("/api/creator/fans")
def creator_fans(
    page: int = 1,
    limit: int = 20,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db),
):
    fans = (
        db.query(Follow, User)
        .join(User, User.id == Follow.follower_id)
        .filter(Follow.followee_id == user.id)
        .order_by(desc(Follow.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": str(follow.id),
                "name": fan.nickname,
                "avatar": fan.avatar,
                "followTime": follow.created_at.isoformat() if follow.created_at else "",
            }
            for follow, fan in fans
        ],
        "total": db.query(Follow).filter(Follow.followee_id == user.id).count(),
    }


def notification_out(notification: Notification) -> NotificationOut:
    sender = notification.sender
    return NotificationOut(
        id=str(notification.id),
        notifType=notification.notif_type or 0,
        targetType=notification.target_type or 0,
        targetId=str(notification.target_id) if notification.target_id else "",
        senderId=str(notification.sender_id) if notification.sender_id else "",
        senderName=sender.nickname if sender else "系统",
        senderAvatar=sender.avatar if sender else "",
        content=notification.content or "",
        isRead=bool(notification.is_read),
        createTime=notification.created_at.isoformat() if notification.created_at else "",
    )


@app.get("/api/notifications")
def list_notifications(
    notif_type: Optional[int] = Query(None, ge=0, le=4),
    only_unread: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.recipient_id == me.id)
    if notif_type is not None:
        query = query.filter(Notification.notif_type == notif_type)
    if only_unread:
        query = query.filter(Notification.is_read.is_(False))
    rows = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit).all()
    return [notification_out(row) for row in rows]


@app.get("/api/notifications/unread-count")
def unread_count(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification_unread = db.query(Notification).filter(
        Notification.recipient_id == me.id,
        Notification.is_read.is_(False),
    ).count()
    chat_unread = db.query(Message).filter(
        Message.receiver_id == me.id,
        Message.is_read.is_(False),
        Message.is_recalled.is_(False),
    ).count()
    return UnreadCountOut(
        total=notification_unread + chat_unread,
        chat=chat_unread,
        notification=notification_unread,
    )


@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.get(Notification, notif_id)
    if not notification or notification.recipient_id != me.id:
        raise HTTPException(status_code=404, detail="通知不存在")
    notification.is_read = True
    db.commit()
    return {"ok": True}


@app.post("/api/notifications/read-all")
def mark_all_read(
    notif_type: Optional[int] = Query(None, ge=0, le=4),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(
        Notification.recipient_id == me.id,
        Notification.is_read.is_(False),
    )
    if notif_type is not None:
        query = query.filter(Notification.notif_type == notif_type)
    query.update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


def order_pair(first, second):
    return (first, second) if str(first) < str(second) else (second, first)


def get_or_create_conversation(db: Session, first, second) -> Conversation:
    user_a, user_b = order_pair(first, second)
    conversation = db.query(Conversation).filter(
        Conversation.user_a_id == user_a,
        Conversation.user_b_id == user_b,
    ).first()
    if conversation:
        return conversation
    conversation = Conversation(user_a_id=user_a, user_b_id=user_b)
    db.add(conversation)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent requests can both miss the row before one insert wins the
        # unique constraint. Roll back the failed transaction before querying
        # the conversation committed by the winner.
        db.rollback()
        conversation = db.query(Conversation).filter(
            Conversation.user_a_id == user_a,
            Conversation.user_b_id == user_b,
        ).first()
        if conversation:
            return conversation
        raise
    db.refresh(conversation)
    return conversation


def message_out(
    db: Session,
    message: Message,
    sender_user: User | None = None,
) -> MessageOut:
    sender = sender_user or db.get(User, message.sender_id)
    content = "消息已撤回" if message.is_recalled else (message.content or "")
    return MessageOut(
        id=str(message.id),
        conversationId=str(message.conversation_id),
        senderId=str(message.sender_id),
        senderName=sender.nickname if sender else "",
        senderAvatar=sender.avatar if sender else "",
        receiverId=str(message.receiver_id),
        content=content,
        messageType=message.message_type or 0,
        isRecalled=bool(message.is_recalled),
        isRead=bool(message.is_read),
        createTime=message.created_at.isoformat() if message.created_at else "",
    )


def conversation_out(
    db: Session,
    conversation: Conversation,
    me_id,
) -> ConversationOut:
    peer_id = (
        conversation.user_b_id
        if conversation.user_a_id == me_id
        else conversation.user_a_id
    )
    peer = db.get(User, peer_id)
    last_message = (
        db.get(Message, conversation.last_message_id)
        if conversation.last_message_id
        else None
    )
    unread = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.receiver_id == me_id,
        Message.is_read.is_(False),
        Message.is_recalled.is_(False),
    ).count()
    return ConversationOut(
        id=str(conversation.id),
        peerId=str(peer_id),
        peerName=peer.nickname if peer else "未知用户",
        peerAvatar=peer.avatar if peer else "",
        lastMessage=(
            "[已撤回]"
            if last_message and last_message.is_recalled
            else (last_message.content if last_message else "")
        ),
        lastMessageType=last_message.message_type if last_message else 0,
        lastMessageAt=(
            conversation.last_message_at.isoformat()
            if conversation.last_message_at
            else ""
        ),
        unreadCount=unread,
    )


class ChatHub:
    def __init__(self) -> None:
        self.user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.user_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        connections = self.user_connections.get(user_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.user_connections.pop(user_id, None)

    async def push_to_user(self, user_id: str, payload: dict) -> None:
        dead: list[WebSocket] = []
        for websocket in self.user_connections.get(user_id, []).copy():
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(user_id, websocket)


chat_hub = ChatHub()


@app.get("/api/chat/conversations")
def list_conversations(
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = db.query(Conversation).filter(
        or_(
            Conversation.user_a_id == me.id,
            Conversation.user_b_id == me.id,
        )
    ).all()
    conversations.sort(
        key=lambda item: (
            item.last_message_at is None,
            -(item.last_message_at.timestamp() if item.last_message_at else 0),
        )
    )
    return [conversation_out(db, item, me.id) for item in conversations]


@app.post("/api/chat/conversations")
def create_conversation(
    payload: dict,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    peer_id_text = payload.get("peerId")
    if not peer_id_text:
        raise HTTPException(status_code=400, detail="缺少 peerId")
    try:
        peer_id = UUID(peer_id_text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="peerId 不是有效 UUID") from exc
    if peer_id == me.id:
        raise HTTPException(status_code=400, detail="不能跟自己聊天")
    if not db.get(User, peer_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    conversation = get_or_create_conversation(db, me.id, peer_id)
    return conversation_out(db, conversation, me.id)


@app.get("/api/chat/conversations/{conv_id}/messages")
def list_messages(
    conv_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = None,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conv_id)
    if not conversation or me.id not in {
        conversation.user_a_id,
        conversation.user_b_id,
    }:
        raise HTTPException(status_code=404, detail="会话不存在")
    query = db.query(Message).filter(Message.conversation_id == conv_id)
    if before:
        try:
            timestamp = datetime.fromisoformat(before.replace("Z", "+00:00"))
            query = query.filter(Message.created_at < timestamp)
        except ValueError:
            pass
    messages = query.order_by(desc(Message.created_at)).limit(limit).all()
    messages.reverse()
    return [message_out(db, message) for message in messages]


async def persist_and_push_message(
    db: Session,
    sender: User,
    receiver_id,
    content: str,
    message_type: int,
) -> Message:
    if not content.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    if sender.id == receiver_id:
        raise HTTPException(status_code=400, detail="不能给自己发消息")
    if not db.get(User, receiver_id):
        raise HTTPException(status_code=404, detail="接收人不存在")
    conversation = get_or_create_conversation(db, sender.id, receiver_id)
    message = Message(
        conversation_id=conversation.id,
        sender_id=sender.id,
        receiver_id=receiver_id,
        content=content[:2000],
        message_type=message_type,
    )
    db.add(message)
    db.flush()
    conversation.last_message_id = message.id
    conversation.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    payload = {"type": "message", "data": message_out(db, message, sender).model_dump()}
    await chat_hub.push_to_user(str(receiver_id), payload)
    await chat_hub.push_to_user(str(sender.id), payload)
    return message


@app.post("/api/chat/conversations/{conv_id}/messages")
async def send_message_http(
    conv_id: UUID,
    data: MessageCreate,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conv_id)
    if not conversation or me.id not in {
        conversation.user_a_id,
        conversation.user_b_id,
    }:
        raise HTTPException(status_code=404, detail="会话不存在")
    peer_id = (
        conversation.user_b_id
        if conversation.user_a_id == me.id
        else conversation.user_a_id
    )
    message = await persist_and_push_message(
        db, me, peer_id, data.content, data.messageType
    )
    return message_out(db, message, me)


@app.post("/api/chat/messages/{msg_id}/recall")
async def recall_message(
    msg_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    message = db.get(Message, msg_id)
    if not message or message.sender_id != me.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    if message.is_recalled:
        return {"ok": True}
    if message.created_at:
        created_at = message.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - created_at).total_seconds() > 120:
            raise HTTPException(status_code=400, detail="超过 2 分钟,无法撤回")
    message.is_recalled = True
    message.recalled_at = datetime.now(timezone.utc)
    db.commit()
    payload = {
        "type": "recall",
        "messageId": str(message.id),
        "conversationId": str(message.conversation_id),
    }
    await chat_hub.push_to_user(str(message.receiver_id), payload)
    await chat_hub.push_to_user(str(message.sender_id), payload)
    return {"ok": True}


@app.post("/api/chat/conversations/{conv_id}/read")
async def mark_conversation_read(
    conv_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conv_id)
    if not conversation or me.id not in {
        conversation.user_a_id,
        conversation.user_b_id,
    }:
        raise HTTPException(status_code=404, detail="会话不存在")
    db.query(Message).filter(
        Message.conversation_id == conv_id,
        Message.receiver_id == me.id,
        Message.is_read.is_(False),
    ).update({Message.is_read: True}, synchronize_session=False)
    db.commit()
    peer_id = (
        conversation.user_b_id
        if conversation.user_a_id == me.id
        else conversation.user_a_id
    )
    await chat_hub.push_to_user(
        str(peer_id),
        {"type": "read", "conversationId": str(conv_id), "readerId": str(me.id)},
    )
    return {"ok": True}


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket, token: str = ""):
    if not token:
        await websocket.close(code=4401)
        return
    try:
        user_id = UUID(parse_token(token))
    except Exception:
        await websocket.close(code=4401)
        return
    db = SessionLocal()
    user = db.get(User, user_id)
    if not user or user.status != 0:
        db.close()
        await websocket.close(code=4401)
        return
    user_id_text = str(user.id)
    await chat_hub.connect(user_id_text, websocket)
    await websocket.send_json({"type": "connected", "userId": user_id_text})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue
            message_type = data.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif message_type == "send":
                peer_id_text = data.get("peerId") or ""
                content = (data.get("content") or "").strip()
                if not peer_id_text or not content:
                    continue
                try:
                    peer_id = UUID(peer_id_text)
                except ValueError:
                    continue
                try:
                    await persist_and_push_message(
                        db,
                        user,
                        peer_id,
                        content,
                        int(data.get("messageType") or 0),
                    )
                except HTTPException as exc:
                    await websocket.send_json({"type": "error", "detail": exc.detail})
            elif message_type == "typing":
                peer_id_text = data.get("peerId") or ""
                if peer_id_text:
                    await chat_hub.push_to_user(
                        peer_id_text,
                        {"type": "typing", "fromUserId": user_id_text},
                    )
    except WebSocketDisconnect:
        pass
    finally:
        chat_hub.disconnect(user_id_text, websocket)
        db.close()


@app.get("/api/admin/users")
def admin_users(
    page: int = 1,
    limit: int = 20,
    keyword: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if keyword:
        query = query.filter(
            or_(
                User.account.ilike(f"%{keyword}%"),
                User.nickname.ilike(f"%{keyword}%"),
            )
        )
    total = query.count()
    users = (
        query.order_by(desc(User.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "items": [user_out(user).model_dump() for user in users],
        "total": total,
        "page": page,
        "limit": limit,
    }


@app.patch("/api/admin/users/{user_id}/type")
def update_user_type(
    user_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.account == "admin":
        raise HTTPException(status_code=403, detail="不能修改管理员账户")
    user_type = data.get("userType")
    if user_type in {0, 1, 2}:
        user.user_type = user_type
        db.commit()
        db.refresh(user)
    return user_out(user)


@app.patch("/api/admin/users/{user_id}/ban")
def ban_user(
    user_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.account == "admin":
        raise HTTPException(status_code=403, detail="不能封禁管理员账户")
    user.status = data.get("status", 0)
    db.commit()
    db.refresh(user)
    return user_out(user)


@app.post("/internal/auth/introspect", response_model=IntrospectionOut)
def introspect(user: User = Depends(get_current_user)):
    return IntrospectionOut(
        user_id=str(user.id),
        user_type=user.user_type,
        status=user.status,
    )


def ensure_stream_key(user: User, db: Session) -> str:
    """为创作者生成/返回其稳定的推流密钥(每个房间复用, 与 OBS 配置一致)。"""
    if not user.stream_key:
        user.stream_key = secrets.token_hex(6)
        db.commit()
        db.refresh(user)
    return user.stream_key


@app.get("/internal/users/{user_id}/stream-key")
def internal_stream_key(user_id: UUID, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"streamKey": ensure_stream_key(user, db)}


@app.post("/internal/users/batch", response_model=list[InternalUserOut])
def batch_users(data: UserBatchIn, db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.id.in_(data.ids)).all() if data.ids else []
    by_id = {row.id: row for row in rows}
    return [
        InternalUserOut(
            id=str(user.id),
            account=user.account,
            nickname=user.nickname,
            avatar=user.avatar or "",
            bio=user.bio or "",
            userType=user.user_type,
            status=user.status,
        )
        for user_id in data.ids
        if (user := by_id.get(user_id)) is not None
    ]


@app.get("/internal/users/{user_id}/following-ids")
def internal_following_ids(user_id: UUID, db: Session = Depends(get_db)):
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    rows = db.query(Follow.followee_id).filter(
        Follow.follower_id == user_id
    ).order_by(Follow.created_at).all()
    return {"ids": [str(row[0]) for row in rows]}


@app.post("/internal/notifications")
def create_internal_notification(
    event: InternalNotificationIn,
    db: Session = Depends(get_db),
):
    duplicate = record_notification_once(db, event)
    return {"ok": True, "duplicate": duplicate}

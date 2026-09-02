import io
import os, secrets, json
import tempfile
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from minio.error import S3Error
from sqlalchemy import or_, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pathlib import Path
import random
import cv2
from urllib.parse import quote
import hashlib
import re
from contextlib import asynccontextmanager


from .database import Base, engine, get_db, SessionLocal
from .models import (
    Category, Comment, CommentMention, Conversation, Danmaku, Follow,
    LiveRoom, Message, Notification, User, Video, VideoLike, Report,
)
from .schemas import *
from .security import create_token, get_current_user, hash_password, require_admin, require_creator, verify_password, parse_token
from .object_storage import MinioObjectStorage, migrate_legacy_media, parse_range_header
from sqlalchemy import func


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_application()
    yield


app = FastAPI(
    title='StreamHub API',
    description='在线视频与直播网站 Python 后端',
    version='1.0.0',
    lifespan=lifespan,
)

LEGACY_PUBLIC_ROOT = Path(
    os.getenv(
        "LEGACY_PUBLIC_ROOT",
        str(Path(__file__).resolve().parents[2] / "public"),
    )
)
UPLOADS_DIR = LEGACY_PUBLIC_ROOT / "uploads"
media_storage = MinioObjectStorage.from_env()

origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173,http://localhost:8080').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _legacy_media_path(object_name: str) -> Optional[Path]:
    root = LEGACY_PUBLIC_ROOT.resolve()
    candidate = (root / object_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _media_response(object_name: str, range_header: Optional[str]):
    try:
        metadata = media_storage.stat_object(object_name)
    except (S3Error, KeyError, OSError) as exc:
        legacy_path = _legacy_media_path(object_name)
        if legacy_path:
            return FileResponse(legacy_path)
        if isinstance(exc, S3Error) and exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="媒体文件不存在") from exc
        if isinstance(exc, KeyError):
            raise HTTPException(status_code=404, detail="媒体文件不存在") from exc
        raise HTTPException(status_code=503, detail="对象存储暂不可用") from exc
    except Exception as exc:
        legacy_path = _legacy_media_path(object_name)
        if legacy_path:
            return FileResponse(legacy_path)
        raise HTTPException(status_code=503, detail="对象存储暂不可用") from exc

    object_size = int(metadata.size)
    content_type = metadata.content_type or "application/octet-stream"
    status_code = 200
    start = 0
    end = object_size - 1

    if range_header:
        try:
            start, end = parse_range_header(range_header, object_size)
        except ValueError as exc:
            raise HTTPException(
                status_code=416,
                detail="无效的媒体范围",
                headers={"Content-Range": f"bytes */{object_size}"},
            ) from exc
        status_code = 206

    length = end - start + 1

    def iter_object():
        response = media_storage.get_object(object_name, offset=start, length=length)
        try:
            yield from response.stream(64 * 1024)
        finally:
            response.close()
            response.release_conn()

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
    }
    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{object_size}"

    return StreamingResponse(
        iter_object(),
        status_code=status_code,
        media_type=content_type,
        headers=headers,
    )


@app.get("/uploads/{media_path:path}")
def get_uploaded_media(media_path: str, request: Request):
    return _media_response(f"uploads/{media_path}", request.headers.get("range"))


@app.get("/avatars/{media_path:path}")
def get_avatar_media(media_path: str, request: Request):
    return _media_response(f"avatars/{media_path}", request.headers.get("range"))

class LiveHub:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)
        await self.broadcast(room_id, {'type': 'online', 'count': len(self.rooms[room_id])})

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self.rooms and ws in self.rooms[room_id]:
            self.rooms[room_id].remove(ws)

    async def broadcast(self, room_id: str, payload: dict):
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(room_id, ws)

live_hub = LiveHub()

def safe_cover_filename(video_path: Path) -> str:
    """
    生成安全的封面文件名：
    1. 避免中文、空格、特殊符号导致 OpenCV/浏览器路径问题
    2. 加 hash，避免不同视频重名
    """
    stem = video_path.stem

    # 只保留英文、数字、横线、下划线
    safe_stem = re.sub(r'[^a-zA-Z0-9_-]+', '-', stem).strip('-')

    if not safe_stem:
        safe_stem = 'video'

    safe_stem = safe_stem[:40]

    file_hash = hashlib.md5(video_path.name.encode('utf-8')).hexdigest()[:8]

    return f"{safe_stem}-{file_hash}.jpg"


def generate_video_cover(video_path: Path, cover_dir: Path) -> str:
    """
    从本地视频中截取一帧作为封面图。
    使用 cv2.imencode + tofile，解决 Windows 中文路径下 cv2.imwrite 写入失败的问题。
    """
    cover_dir.mkdir(parents=True, exist_ok=True)

    cover_name = safe_cover_filename(video_path)
    cover_path = cover_dir / cover_name

    fallback_cover = (
        "https://images.unsplash.com/photo-1611162616475-46b635cb6868"
        "?w=900&auto=format&fit=crop"
    )

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(f"无法打开视频，封面生成失败：{video_path}")
        return fallback_cover

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if frame_count > 0:
        target_frames = [
            int(frame_count * 0.45),
            int(frame_count * 0.60),
            int(frame_count * 0.30),
            int(frame_count * 0.75),
            int(frame_count * 0.10),
            0,
        ]
    else:
        target_frames = [0]

    success = False
    frame = None

    for target_frame in target_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(target_frame, 0))
        success, frame = cap.read()

        if success and frame is not None:
            break

    cap.release()

    if not success or frame is None:
        print(f"无法读取视频帧，封面生成失败：{video_path}")
        return fallback_cover

    try:
        # 关键：不要用 cv2.imwrite。Windows 中文路径会失败。
        ok, encoded_image = cv2.imencode('.jpg', frame)

        if not ok:
            print(f"封面编码失败：{video_path}")
            return fallback_cover

        encoded_image.tofile(str(cover_path))

        if not cover_path.exists():
            print(f"封面文件未生成：{cover_path}")
            return fallback_cover

    except Exception as e:
        print(f"封面写入异常：{cover_path}，原因：{e}")
        return fallback_cover

    version = int(cover_path.stat().st_mtime)

    return f"/demo-covers/{cover_name}?v={version}"

def user_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id), 
        account=u.account, 
        nickname=u.nickname, 
        avatar=u.avatar, 
        bio=u.bio, 
        userType=u.user_type, 
        status=u.status,
        streamKey=u.stream_key
    )

def video_out(v: Video) -> VideoOut:
    return VideoOut(
        id=str(v.id), title=v.title, description=v.description or '', tags=v.tags or [],
        coverUrl=v.cover_url or '', videoUrl=v.video_url or '', duration=v.duration or 0,
        categoryId=str(v.category_id or ''), categoryName=v.category.name if v.category else '',
        viewCount=v.view_count or 0, likeCount=v.like_count or 0, commentCount=v.comment_count or 0,
        favoriteCount=v.favorite_count or 0, uploaderId=str(v.uploader_id),
        uploaderName=v.uploader.nickname if v.uploader else '未知用户',
        uploaderAvatar=v.uploader.avatar if v.uploader else '',
        uploadTime=v.created_at.isoformat() if v.created_at else '', auditStatus=v.audit_status or 0,
        rejectReason=v.reject_reason or ''
    )

def comment_out(c: Comment, reply_count: int = 0) -> CommentOutV2:
    reply_to_user = c.reply_to_user if c.reply_to_user_id else None
    return CommentOutV2(
        id=str(c.id), content=c.content, userId=str(c.user_id), username=c.user.nickname if c.user else '匿名用户',
        userAvatar=c.user.avatar if c.user else '', videoId=str(c.video_id), parentId=str(c.parent_id) if c.parent_id else '0',
        likeCount=c.like_count or 0, isTop=bool(c.is_top), createTime=c.created_at.isoformat() if c.created_at else '',
        replyToUserId=str(c.reply_to_user_id) if c.reply_to_user_id else '',
        replyToUsername=reply_to_user.nickname if reply_to_user else '',
        replyCount=reply_count,
    )

def danmaku_out(d: Danmaku) -> DanmakuOut:
    return DanmakuOut(
        id=str(d.id), content=d.content, color=d.color, position=d.position, userId=str(d.user_id),
        username=d.user.nickname if d.user else '匿名用户', videoTime=d.video_time or 0,
        sendTime=d.created_at.isoformat() if d.created_at else ''
    )

def live_out(r: LiveRoom) -> LiveRoomOut:
    return LiveRoomOut(
        id=str(r.id),
        title=r.title,
        description=r.description or "",  # 添加这一行
        categoryId=str(r.category_id),
        categoryName=r.category.name if r.category else '',
        cover=r.cover or 'https://images.unsplash.com/photo-1542751371-adc38448a05e?w=640&h=360&fit=crop',
        streamKey=r.stream_key,
        pushUrl=r.push_url,
        pullUrl=r.pull_url,
        anchorId=str(r.anchor_id),
        anchorName=r.anchor.nickname if r.anchor else '主播',
        anchorAvatar=r.anchor.avatar if r.anchor else '',
        onlineCount=r.online_count or 0,
        startTime=r.start_time.isoformat() if r.start_time else '',
        endTime=r.end_time.isoformat() if r.end_time else '',
        status=r.status or 0
    )

def seed_data(db: Session):
    """
    初始化课程作业演示数据。
    这个函数要做到：
    1. 不怕 Neon 里已经有旧数据
    2. 缺什么补什么
    3. 不重复插入相同视频、评论、弹幕、直播间
    4. 所有视频都使用浏览器可直接播放的 mp4 地址
    """

    if db.query(User).count() > 0:
        print("数据库已有数据，跳过初始化")
        return
    
    # 一、初始化用户：缺哪个补哪个
    demo_users = [
        {
            "account": "admin",
            "password": "admin123",
            "nickname": "管理员",
            "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=admin",
            "bio": "平台管理员，负责视频审核与社区管理",
            "user_type": 2,
        },
        {
            "account": "creator",
            "password": "creator123",
            "nickname": "创作者小明",
            "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=creator",
            "bio": "热爱拍摄、剪辑和分享生活的内容创作者",
            "user_type": 1,
        },
        {
            "account": "user",
            "password": "user123",
            "nickname": "xuyue",
            "avatar": "https://api.dicebear.com/7.x/avataaars/svg?seed=user",
            "bio": "喜欢看视频、发弹幕和评论的普通用户",
            "user_type": 0,
        },
    ]

    for item in demo_users:
        exists = db.query(User).filter(User.account == item["account"]).first()

        if exists:
            # 强制同步所有字段
            exists.nickname = item["nickname"]
            exists.avatar = item["avatar"]
            exists.bio = item["bio"]
            exists.user_type = item["user_type"]
            # 同时更新该用户所有视频的 uploader_name（通过关系动态获取，无需单独更新）
        else:
            db.add(User(
                account=item["account"],
                password_hash=hash_password(item["password"]),
                nickname=item["nickname"],
                avatar=item["avatar"],
                bio=item["bio"],
                user_type=item["user_type"],
                status=0,
            ))

    db.commit()

    # 二、初始化分类：逐个检查，缺哪个补哪个
    demo_categories = [
        {"id": 1, "name": "推荐", "type": 0, "sort_order": 1},
        {"id": 2, "name": "影视", "type": 0, "sort_order": 2},
        {"id": 3, "name": "动画", "type": 0, "sort_order": 3},
        {"id": 4, "name": "科技", "type": 0, "sort_order": 4},
        {"id": 5, "name": "学习", "type": 0, "sort_order": 5},
        {"id": 6, "name": "生活", "type": 0, "sort_order": 6},
        {"id": 7, "name": "音乐", "type": 0, "sort_order": 7},
        {"id": 8, "name": "游戏", "type": 0, "sort_order": 8},
        {"id": 9, "name": "旅行", "type": 0, "sort_order": 9},
        {"id": 10, "name": "直播", "type": 1, "sort_order": 10},
    ]

    for item in demo_categories:
        exists = db.query(Category).filter(Category.id == item["id"]).first()

        if exists:
            exists.name = item["name"]
            exists.type = item["type"]
            exists.sort_order = item["sort_order"]
        else:
            db.add(Category(
                id=item["id"],
                name=item["name"],
                type=item["type"],
                sort_order=item["sort_order"],
            ))

    db.commit()

    creator = db.query(User).filter(User.account == "creator").first()
    user = db.query(User).filter(User.account == "user").first()

    if not creator:
        return

    """
    # 三、初始化可播放视频
    sample_videos = [
        {
            "title": "Big Buck Bunny 动画短片",
            "description": "一部经典开源动画短片，适合用于测试在线视频播放功能。",
            "cover_url": "https://peach.blender.org/wp-content/uploads/title_anouncement.jpg?x11217",
            "video_url": "https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
            "duration": 596,
            "category_id": 3,
            "tags": ["动画", "短片", "开源影片"],
            "view_count": 12800,
            "like_count": 860,
            "favorite_count": 320,
        },
        {
            "title": "Sintel 电影宣传片",
            "description": "Blender Foundation 开源电影 Sintel，用于展示高清影视播放效果。",
            "cover_url": "https://download.blender.org/durian/trailer/sintel_trailer-480p.jpg",
            "video_url": "https://storage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
            "duration": 888,
            "category_id": 2,
            "tags": ["电影", "宣传片", "高清"],
            "view_count": 9360,
            "like_count": 742,
            "favorite_count": 226,
        },
        {
            "title": "Tears of Steel 科幻短片",
            "description": "一部科幻风格开源短片，可用于展示中长视频播放页面。",
            "cover_url": "https://mango.blender.org/wp-content/uploads/2013/05/01_thom_celia_bridge.jpg",
            "video_url": "https://storage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
            "duration": 734,
            "category_id": 2,
            "tags": ["科幻", "电影", "短片"],
            "view_count": 8420,
            "like_count": 611,
            "favorite_count": 188,
        },
        {
            "title": "Elephants Dream 开源动画",
            "description": "经典实验动画短片，适合展示平台推荐和播放功能。",
            "cover_url": "https://orange.blender.org/wp-content/themes/orange/images/media/gallery/s1_proog.jpg",
            "video_url": "https://storage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
            "duration": 653,
            "category_id": 3,
            "tags": ["动画", "实验短片", "创意"],
            "view_count": 7340,
            "like_count": 520,
            "favorite_count": 176,
        },
        {
            "title": "For Bigger Blazes 宣传片",
            "description": "Google 官方示例视频，适合测试网页播放器兼容性。",
            "cover_url": "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=900&auto=format&fit=crop",
            "video_url": "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
            "duration": 15,
            "category_id": 4,
            "tags": ["宣传片", "科技", "短视频"],
            "view_count": 5620,
            "like_count": 410,
            "favorite_count": 105,
        },
        {
            "title": "For Bigger Escape 宣传片",
            "description": "短视频宣传片素材，适合用于测试短视频与推荐列表。",
            "cover_url": "https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?w=900&auto=format&fit=crop",
            "video_url": "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
            "duration": 15,
            "category_id": 6,
            "tags": ["短视频", "生活", "宣传片"],
            "view_count": 4890,
            "like_count": 366,
            "favorite_count": 98,
        },
    ]
    """
    sample_videos = []

    created_videos = []

    for item in sample_videos:
        exists = db.query(Video).filter(Video.title == item["title"]).first()

        if exists:
            # 如果旧视频存在，就修正它的链接和状态，防止旧数据导致视频不能播放
            exists.description = item["description"]
            exists.cover_url = item["cover_url"]
            exists.video_url = item["video_url"]
            exists.duration = item["duration"]
            exists.category_id = item["category_id"]
            exists.tags = item["tags"]
            exists.view_count = item["view_count"]
            exists.like_count = item["like_count"]
            exists.favorite_count = item["favorite_count"]
            exists.comment_count = max(exists.comment_count or 0, 3)
            exists.uploader_id = creator.id
            exists.audit_status = 1
            exists.status = 0
            created_videos.append(exists)
        else:
            video = Video(
                title=item["title"],
                description=item["description"],
                cover_url=item["cover_url"],
                video_url=item["video_url"],
                duration=item["duration"],
                category_id=item["category_id"],
                tags=item["tags"],
                view_count=item["view_count"],
                like_count=item["like_count"],
                favorite_count=item["favorite_count"],
                comment_count=3,
                uploader_id=creator.id,
                audit_status=1,
                status=0,
            )
            db.add(video)
            db.commit()
            db.refresh(video)
            created_videos.append(video)

    db.commit()

    # 四、初始化固定评论
    for video in created_videos:
        exists_comment = db.query(Comment).filter(Comment.video_id == video.id).first()

        if exists_comment:
            continue

        comments = [
            Comment(
                video_id=video.id,
                user_id=user.id if user else creator.id,
                content="这个视频可以正常播放，画质也很清楚！",
                like_count=18,
            ),
            Comment(
                video_id=video.id,
                user_id=creator.id,
                content="这个页面已经有评论功能了，刷新后评论也会保留。",
                like_count=9,
            ),
            Comment(
                video_id=video.id,
                user_id=user.id if user else creator.id,
                content="弹幕和评论一起出现，感觉更像真实的视频平台。",
                like_count=12,
            ),
        ]

        db.add_all(comments)

    db.commit()

    # 五、初始化固定弹幕
    for video in created_videos:
        exists_danmaku = db.query(Danmaku).filter(
            Danmaku.target_id == video.id,
            Danmaku.target_type == 0
        ).first()

        if exists_danmaku:
            continue

        danmaku_list = [
            Danmaku(
                target_id=video.id,
                target_type=0,
                user_id=user.id if user else creator.id,
                content="来了来了！",
                video_time=2,
                color="#ffffff",
                position=0,
            ),
            Danmaku(
                target_id=video.id,
                target_type=0,
                user_id=user.id if user else creator.id,
                content="这个视频终于能播放了",
                video_time=5,
                color="#ff4d4f",
                position=0,
            ),
            Danmaku(
                target_id=video.id,
                target_type=0,
                user_id=creator.id,
                content="作业展示效果不错",
                video_time=8,
                color="#00d4ff",
                position=0,
            ),
            Danmaku(
                target_id=video.id,
                target_type=0,
                user_id=user.id if user else creator.id,
                content="前端 + 后端 + 数据库已经打通",
                video_time=12,
                color="#fadb14",
                position=0,
            ),
        ]

        db.add_all(danmaku_list)

    db.commit()

    # 六、初始化直播间
    live_category = db.query(Category).filter(Category.id == 10).first()

    if not live_category:
        live_category = Category(id=10, name="直播", type=1, sort_order=10)
        db.add(live_category)
        db.commit()

    sample_rooms = []

    for item in sample_rooms:
        exists_room = db.query(LiveRoom).filter(
            LiveRoom.stream_key == item["stream_key"]
        ).first()

        if exists_room:
            exists_room.title = item["title"]
            exists_room.category_id = item["category_id"]
            exists_room.cover = item["cover"]
            exists_room.push_url = item["push_url"]
            exists_room.pull_url = item["pull_url"]
            exists_room.anchor_id = creator.id
            exists_room.online_count = item["online_count"]
            exists_room.status = 1
        else:
            db.add(LiveRoom(
                title=item["title"],
                category_id=item["category_id"],
                cover=item["cover"],
                stream_key=item["stream_key"],
                push_url=item["push_url"],
                pull_url=item["pull_url"],
                anchor_id=creator.id,
                online_count=item["online_count"],
                status=1,
            ))

    db.commit()

    sync_local_videos(db)


def sync_local_videos(db: Session):
    """
    自动扫描前端 public/demo-videos 目录，把里面所有 mp4/webm/ogg 视频自动写入 videos 表。
    这样你只要把视频放进 public/demo-videos，系统启动后就会自动出现在首页。
    """

    # backend/app/main.py -> backend/app -> backend -> StreamHub
    project_root = Path(__file__).resolve().parents[2]
    video_dir = project_root / "public" / "demo-videos"

    if not video_dir.exists():
        print(f"本地视频目录不存在：{video_dir}")
        return

    video_files = []
    for suffix in ("*.mp4", "*.webm", "*.ogg"):
        video_files.extend(video_dir.glob(suffix))

    if not video_files:
        print(f"本地视频目录为空：{video_dir}")
        return

    creator = db.query(User).filter(User.account == "creator").first()
    if not creator:
        creator = db.query(User).first()

    if not creator:
        print("没有找到可用创作者用户，无法同步本地视频")
        return

    # 确保分类存在
    default_category = db.query(Category).filter(Category.id == 1).first()
    if not default_category:
        db.add(Category(id=1, name="推荐", type=0, sort_order=1))
        db.commit()

    category_ids = [
        item.id
        for item in db.query(Category).filter(Category.type == 0).all()
    ]

    if not category_ids:
        category_ids = [1]

    cover_dir = project_root / "public" / "demo-covers"

    created_count = 0
    updated_count = 0

    for file_path in video_files:
        file_name = file_path.name
        file_stem = file_path.stem

        # 前端 public 目录的访问路径
        video_url = f"/demo-videos/{file_name}"

        # 自动截帧生成封面
        cover_url = generate_video_cover(file_path, cover_dir)

        # 用文件名生成标题
        title = (
            file_stem
            .replace("-", " ")
            .replace("_", " ")
            .strip()
            .title()
        )

        if not title:
            title = "本地演示视频"

        exists = db.query(Video).filter(Video.video_url == video_url).first()

        if exists:
            exists.title = title
            exists.description = f"这是系统自动从 public/demo-videos 目录读取的视频文件：{file_name}"
            exists.video_url = video_url

            # 关键：每次同步都强制更新成视频自己的截图封面
            exists.cover_url = cover_url

            exists.audit_status = 1
            exists.status = 0
            exists.uploader_id = creator.id
            updated_count += 1
            continue

        video = Video(
            title=title,
            description=f"这是系统自动从 public/demo-videos 目录读取的视频文件：{file_name}",
            tags=["本地视频", "自动导入", "演示"],
            cover_url=cover_url,
            video_url=video_url,
            duration=random.choice([60, 120, 180, 240, 300, 596]),
            category_id=random.choice(category_ids),
            uploader_id=creator.id,
            view_count=random.randint(1000, 50000),
            like_count=random.randint(50, 3000),
            favorite_count=random.randint(20, 1000),
            comment_count=random.randint(1, 30),
            audit_status=1,
            status=0,
        )

        db.add(video)
        created_count += 1

    """
    # 隐藏所有不是 public/demo-videos 里的视频，避免首页加载外网慢视频
    db.query(Video).filter(
        ~Video.video_url.like('/demo-videos/%')
    ).update(
        {
            Video.status: 1
        },
        synchronize_session=False
    )
    """

    # 确保本地视频全部可见并审核通过
    db.query(Video).filter(
        Video.video_url.like('/demo-videos/%')
    ).update(
        {
            Video.status: 0,
            Video.audit_status: 1
        },
        synchronize_session=False
    )

    db.commit()

    print(
        f"本地视频同步完成：新增 {created_count} 个，更新 {updated_count} 个；已隐藏所有非本地视频。目录：{video_dir}"
    )


@app.post("/api/admin/local-videos/sync")
def sync_local_videos_api(
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    sync_local_videos(db)
    return {
        "message": "本地视频同步完成"
    }


def apply_social_migration():
    """为已存在的 comments 表追加 reply_to_user_id 字段。新表由 create_all 处理。"""
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE comments ADD COLUMN IF NOT EXISTS reply_to_user_id UUID"
        ))


def initialize_application():
    Base.metadata.create_all(bind=engine)
    try:
        apply_social_migration()
    except Exception as e:
        print("社区互动迁移失败：", e)
    
    db = SessionLocal()
    try:
        # 自动添加 live_rooms.description 字段
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE live_rooms ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''"))
                print("live_rooms.description 字段已添加")
        except Exception as e:
            print(f"添加 description 字段失败: {e}")
        
        # 自动添加 users.stream_key 字段
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS stream_key VARCHAR(20) UNIQUE"))
                print("users.stream_key 字段已添加")
        except Exception as e:
            print(f"添加 stream_key 字段失败: {e}")
        
        # 自动添加 videos.reject_reason 字段
        try:
            from sqlalchemy import text
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE videos ADD COLUMN IF NOT EXISTS reject_reason TEXT"))
                print("videos.reject_reason 字段已添加")
        except Exception as e:
            print(f"添加 reject_reason 字段失败: {e}")
        
        # 自动创建 sensitive_words 表
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS sensitive_words (
                        id SERIAL PRIMARY KEY,
                        word VARCHAR(100) NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                print("sensitive_words 表已创建")
        except Exception as e:
            print(f"创建 sensitive_words 表失败: {e}")
        
        seed_data(db)

        # 种子数据也会创建创作者，因此必须在 seed_data 之后补齐直播密钥。
        import random
        creators = db.query(User).filter(User.user_type >= 1, User.stream_key == None).all()
        for creator in creators:
            creator.stream_key = str(random.randint(100000, 999999))
        db.commit()
        if creators:
            print(f"已为 {len(creators)} 位创作者生成 stream_key")

        if os.getenv("MINIO_MIGRATE_ON_STARTUP", "false").lower() in {"1", "true", "yes"}:
            migrated = migrate_legacy_media(media_storage, LEGACY_PUBLIC_ROOT)
            print(f"旧媒体复制到 MinIO 完成：新增 {len(migrated)} 个对象，原文件已保留")
    except Exception as e:
        db.rollback()
        print("初始化演示数据失败：", e)
        raise e
    finally:
        db.close()

@app.get('/api/health')
def health():
    return {'status': 'ok'}

@app.post('/api/auth/login')
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.account == data.account).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail='账号或密码错误')
    if user.status == 1:
        raise HTTPException(status_code=403, detail='账号已被封禁')
    return {'token': create_token(user), 'user': user_out(user)}

@app.post('/api/auth/register')
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.account == data.account).first():
        raise HTTPException(status_code=400, detail='账号已存在')
    user = User(account=data.account, password_hash=hash_password(data.password), nickname=data.nickname, avatar=f'https://api.dicebear.com/7.x/avataaars/svg?seed={data.account}', user_type=0)
    db.add(user); db.commit(); db.refresh(user)
    return {'token': create_token(user), 'user': user_out(user)}

@app.get('/api/auth/me')
def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return user_out(user)

@app.patch('/api/auth/me')
def update_me(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.bio is not None:
        user.bio = data.bio
    if data.avatar is not None:
        user.avatar = data.avatar
    db.commit()
    db.refresh(user)
    return user_out(user)

@app.get('/api/categories')
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(Category).order_by(Category.type, Category.sort_order).all()
    return [{'id': '0', 'name': '推荐', 'type': 0}] + [CategoryOut(id=str(c.id), name=c.name, type=c.type).model_dump() for c in rows]

@app.get('/api/videos')
def list_videos(
    category_id: Optional[str] = None,
    keyword: Optional[str] = None,
    sort: str = 'comprehensive',
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    q = db.query(Video).filter(
        Video.status == 0,
        Video.audit_status == 1
    )

    if category_id and category_id != '0':
        q = q.filter(Video.category_id == int(category_id))

    if keyword:
        q = q.filter(
            or_(
                Video.title.ilike(f'%{keyword}%'),
                Video.description.ilike(f'%{keyword}%')
            )
        )

    if sort == 'latest':
        q = q.order_by(desc(Video.created_at))
    elif sort == 'hottest':
        q = q.order_by(desc(Video.view_count), desc(Video.like_count))
    else:
        q = q.order_by(func.random())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        'items': [video_out(v).model_dump() for v in items],
        'hasMore': page * page_size < total
    }

# ======================================================================
# 推荐视频
# ======================================================================

@app.get('/api/videos/recommended')
def recommended_videos(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    authorization: str = Header(None)
):
    """获取推荐视频（已登录用户自动使用个性化推荐）"""
    from datetime import datetime, timedelta
    import random
    from sqlalchemy import func
    from .security import parse_token
    
    # 尝试获取登录用户
    user = None
    if authorization and authorization.startswith('Bearer '):
        try:
            user_id = parse_token(authorization.replace('Bearer ', '', 1))
            user = db.get(User, user_id)
        except:
            pass
    
    all_videos = db.query(Video).filter(
        Video.status == 0,
        Video.audit_status == 1
    ).all()
    
    if not all_videos:
        return {'items': [], 'hasMore': False}
    
    # 获取用户偏好分类（仅登录用户）
    pref_categories = []
    if user:
        result = db.query(
            Video.category_id
        ).join(
            VideoLike, VideoLike.video_id == Video.id
        ).filter(
            VideoLike.user_id == user.id,
            Video.category_id != None
        ).group_by(Video.category_id).order_by(
            func.count(VideoLike.id).desc()
        ).limit(3).all()
        pref_categories = [row[0] for row in result if row[0]]
    
    now = datetime.now()
    
    scored_videos = []
    for v in all_videos:
        # 热度分
        hot_score = (v.view_count or 0) + (v.like_count or 0) * 2
        
        # 随机扰动（范围增大，让顺序更多变）
        random_noise = random.randint(0, 50000)
        
        # 用户偏好加成
        preference_bonus = 0
        if pref_categories and v.category_id in pref_categories:
            position = pref_categories.index(v.category_id)
            preference_bonus = (3 - position) * 1000
        
        final_score = hot_score + random_noise + preference_bonus
        scored_videos.append((v, final_score))
    
    # 按分数降序排序
    scored_videos.sort(key=lambda x: x[1], reverse=True)
    
    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_items = scored_videos[start:end]
    
    return {
        'items': [video_out(v[0]).model_dump() for v in page_items],
        'hasMore': end < len(scored_videos)
    }

@app.get('/api/videos/{video_id}')
def get_video(video_id: UUID, db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    v.view_count += 1; db.commit(); db.refresh(v)
    return video_out(v)

@app.get('/api/videos/{video_id}/related')
def related(video_id: UUID, db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v:
        return {'items': []}
    
    items = db.query(Video).filter(
        Video.id != video_id,
        Video.category_id == v.category_id,
        Video.status == 0,
        Video.audit_status == 1,
        Video.video_url.like('/demo-videos/%')
    ).order_by(func.random()).limit(5).all()

    return {
        'items': [video_out(x).model_dump() for x in items]
    }
    
    # 分离同类视频和其他视频
    same_category = [x for x in all_other if x.category_id == v.category_id]
    other_videos = [x for x in all_other if x.category_id != v.category_id]
    
    # 同类视频按热度排序（播放量 + 喜欢数 * 2）
    def hot_score(video):
        return (video.view_count or 0) + (video.like_count or 0) * 2
    
    same_category.sort(key=hot_score, reverse=True)
    
    # 其他视频随机打乱顺序
    import random
    random.shuffle(other_videos)
    
    result = []
    
    # 同类视频足够5个：取热度最高的5个同类
    if len(same_category) >= 5:
        result = same_category[:5]
    else:
        # 先取所有同类
        result = same_category.copy()
        # 计算还需要多少个
        need = 5 - len(result)
        # 从其他视频中随机取来补充
        if other_videos and need > 0:
            result.extend(other_videos[:need])
    
    return {
        'items': [video_out(x).model_dump() for x in result]
    }

@app.post('/api/videos')
def create_video(data: VideoCreate, user: User = Depends(require_creator), db: Session = Depends(get_db)):
    default_video_url = "/demo-videos/video1.mp4"
    default_cover_url = "https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop"

    video_url = (data.videoUrl or "").strip()
    cover_url = (data.coverUrl or "").strip()

    if not video_url or ".mp4" not in video_url.lower():
        video_url = default_video_url

    if not cover_url:
        cover_url = default_cover_url

    category_id = int(data.categoryId or 1)
    exists_category = db.query(Category).filter(Category.id == category_id).first()
    if not exists_category:
        category_id = 1

    v = Video(
        title=data.title or "未命名视频",
        description=data.description or "这是一个由创作者上传的视频。",
        tags=data.tags or ["投稿", "视频", "StreamHub"],
        cover_url=cover_url,
        video_url=video_url,
        duration=data.duration or 596,
        category_id=category_id,
        uploader_id=user.id,
        audit_status=0,
        status=0,
    )

    db.add(v)
    db.commit()
    db.refresh(v)

    return video_out(v)
@app.get('/api/creator/videos')
def creator_videos(user: User = Depends(require_creator), db: Session = Depends(get_db)):
    rows = db.query(Video).filter(Video.uploader_id == user.id).order_by(desc(Video.created_at)).all()
    return {'items': [video_out(v).model_dump() for v in rows]}

@app.get('/api/admin/videos/pending')
def pending_videos(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Video).filter(Video.audit_status == 0).order_by(desc(Video.created_at)).all()
    return {'items': [video_out(v).model_dump() for v in rows]}

@app.patch('/api/admin/videos/{video_id}/audit')
def audit_video(
    video_id: UUID, 
    data: AuditIn, 
    _: User = Depends(require_admin), 
    db: Session = Depends(get_db)
):
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    v.audit_status = data.auditStatus
    if data.rejectReason:
        v.reject_reason = data.rejectReason
    
    db.commit()
    db.refresh(v)
    
    # 发送通知
    if data.auditStatus == 1:
        content = f'您的视频 "{v.title}" 已通过审核'
    else:
        reason = data.rejectReason or '未填写具体原因'
        content = f'您的视频 "{v.title}" 未通过审核，理由：{reason}'
    
    create_notification(
        db,
        recipient_id=v.uploader_id,
        sender_id=None,
        notif_type=4,
        target_type=0,
        target_id=video_id,
        content=content,
        auto_commit=True
    )
    
    return video_out(v)

"""
@app.post('/api/videos/{video_id}/like')
def like_video(video_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    v.like_count += 1; db.commit(); db.refresh(v)
    return video_out(v)
"""
@app.post('/api/videos/{video_id}/like')
def like_video(
    video_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 检查视频是否存在
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    # 检查是否已经点过赞
    existing_like = db.query(VideoLike).filter(
        VideoLike.user_id == user.id,
        VideoLike.video_id == video_id
    ).first()
    
    if existing_like:
        raise HTTPException(status_code=400, detail='已经点过赞了')
    
    # 创建点赞记录
    like = VideoLike(user_id=user.id, video_id=video_id)
    db.add(like)
    
    # 视频点赞数 +1
    v.like_count += 1
    
    db.commit()
    db.refresh(v)
    
    return video_out(v)

@app.delete('/api/videos/{video_id}/like')
def unlike_video(
    video_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 检查视频是否存在
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    # 查找点赞记录
    like = db.query(VideoLike).filter(
        VideoLike.user_id == user.id,
        VideoLike.video_id == video_id
    ).first()
    
    if not like:
        raise HTTPException(status_code=400, detail='还没有点过赞')
    
    # 删除点赞记录
    db.delete(like)
    
    # 视频点赞数 -1
    v.like_count -= 1
    if v.like_count < 0:
        v.like_count = 0
    
    db.commit()
    db.refresh(v)
    
    return {
        'code': 0,
        'message': '取消点赞成功',
        'data': {
            'likeCount': v.like_count,
            'isLiked': False
        }
    }

@app.get('/api/videos/{video_id}/like-status')
def get_like_status(
    video_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """检查当前用户是否点赞了该视频"""
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    is_liked = db.query(VideoLike).filter(
        VideoLike.user_id == user.id,
        VideoLike.video_id == video_id
    ).first() is not None
    
    return {
        'isLiked': is_liked,
        'likeCount': v.like_count
    }

@app.post('/api/videos/{video_id}/favorite')
def favorite_video(video_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    v.favorite_count += 1; db.commit(); db.refresh(v)
    return video_out(v)

MENTION_RE = re.compile(r'@([\w一-龥]+)')


def parse_mentions(db: Session, content: str) -> List[User]:
    """从评论正文里提取 @用户名,返回匹配到的用户列表(去重)。"""
    names = list(dict.fromkeys(MENTION_RE.findall(content)))
    if not names:
        return []
    users = db.query(User).filter(User.nickname.in_(names)).all()
    return users


@app.get('/api/videos/{video_id}/comments')
def get_comments(video_id: UUID, db: Session = Depends(get_db)):
    # 只返回顶层评论(parent_id 为空),回复数由前端按需展开拉取
    rows = db.query(Comment).filter(
        Comment.video_id == video_id,
        Comment.parent_id == None,
    ).order_by(desc(Comment.created_at)).all()
    # 计算每条顶层评论的回复数
    counts = {}
    if rows:
        parent_ids = [c.id for c in rows]
        from sqlalchemy import func as sa_func
        rc = (
            db.query(Comment.parent_id, sa_func.count(Comment.id))
            .filter(Comment.parent_id.in_(parent_ids))
            .group_by(Comment.parent_id)
            .all()
        )
        counts = {pid: cnt for pid, cnt in rc}
    return [comment_out(c, counts.get(c.id, 0)).model_dump() for c in rows]


@app.get('/api/comments/{comment_id}/replies')
def get_comment_replies(comment_id: UUID, db: Session = Depends(get_db)):
    rows = db.query(Comment).filter(Comment.parent_id == comment_id).order_by(Comment.created_at).all()
    return [comment_out(c).model_dump() for c in rows]


@app.post('/api/videos/{video_id}/comments')
def add_comment(
    video_id: UUID, data: CommentCreateV2,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    v = db.get(Video, video_id)
    if not v:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    # 敏感词过滤
    filtered_content = filter_sensitive_words(data.content, db)

    parent_id = None if data.parentId == '0' else UUID(data.parentId)
    reply_to_user_id = UUID(data.replyToUserId) if data.replyToUserId else None

    # 如果是回复,校验父评论存在;并自动填充 reply_to_user_id
    parent_comment: Optional[Comment] = None
    if parent_id:
        parent_comment = db.get(Comment, parent_id)
        if not parent_comment or parent_comment.video_id != video_id:
            raise HTTPException(status_code=400, detail='父评论不存在')
        # 二级回复始终挂在顶层评论下(平铺,不无限嵌套)
        if parent_comment.parent_id:
            parent_id = parent_comment.parent_id
        if not reply_to_user_id:
            reply_to_user_id = parent_comment.user_id

    c = Comment(
        content=filtered_content,
        user_id=user.id,
        video_id=video_id,
        parent_id=parent_id,
        reply_to_user_id=reply_to_user_id,
    )
    v.comment_count += 1
    db.add(c)
    db.flush()

    # 解析 @提及 → 写入 comment_mentions,并向被 @ 的人发通知
    mentioned = parse_mentions(db, filtered_content)
    notify_to = set()
    for u in mentioned:
        if str(u.id) == str(user.id):
            continue
        db.add(CommentMention(comment_id=c.id, mentioned_user_id=u.id))
        notify_to.add(str(u.id))

    db.commit()
    db.refresh(c)

    # 通知:被 @ 的人
    for uid_str in notify_to:
        create_notification(
            db, recipient_id=UUID(uid_str), sender_id=user.id,
            notif_type=3, target_type=0, target_id=video_id,
            content=f'{user.nickname} 在评论里 @了你: {filtered_content[:60]}',
        )
    # 通知:被回复的人
    if reply_to_user_id and str(reply_to_user_id) not in notify_to:
        create_notification(
            db, recipient_id=reply_to_user_id, sender_id=user.id,
            notif_type=1, target_type=0, target_id=video_id,
            content=f'{user.nickname} 回复了你: {filtered_content[:60]}',
        )
    # 通知:视频作者(顶层评论才通知,避免和回复通知重复)
    if not parent_id and v.uploader_id and str(v.uploader_id) != str(user.id) \
            and str(v.uploader_id) not in notify_to:
        create_notification(
            db, recipient_id=v.uploader_id, sender_id=user.id,
            notif_type=1, target_type=0, target_id=video_id,
            content=f'{user.nickname} 评论了你的视频: {filtered_content[:60]}',
        )

    return comment_out(c).model_dump()

@app.get('/api/videos/{video_id}/danmaku')
def get_danmaku(video_id: UUID, db: Session = Depends(get_db)):
    rows = db.query(Danmaku).filter(Danmaku.target_id == video_id, Danmaku.target_type == 0).order_by(Danmaku.video_time).all()
    return [danmaku_out(d).model_dump() for d in rows]

@app.post('/api/videos/{video_id}/danmaku')
def add_danmaku(video_id: UUID, data: DanmakuCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 敏感词过滤
    filtered_content = filter_sensitive_words(data.content, db)
    
    d = Danmaku(
        content=filtered_content,
        color=data.color,
        position=data.position,
        video_time=data.videoTime,
        target_id=video_id,
        target_type=0,
        user_id=user.id
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return danmaku_out(d)

@app.get('/api/live/rooms')
def list_rooms(category_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(LiveRoom).filter(LiveRoom.status == 1)
    if category_id: q = q.filter(LiveRoom.category_id == int(category_id))
    return {'items': [live_out(r).model_dump() for r in q.order_by(desc(LiveRoom.start_time)).all()]}

@app.get('/api/live/rooms/{room_id}')
def room_detail(room_id: UUID, db: Session = Depends(get_db)):
    r = db.get(LiveRoom, room_id)
    if not r: raise HTTPException(status_code=404, detail='直播间不存在')
    return live_out(r)

@app.post('/api/live/rooms')
def create_room(data: LiveRoomCreate, user: User = Depends(require_creator), db: Session = Depends(get_db)):
    # 检查是否已有正在直播的房间
    existing_active = db.query(LiveRoom).filter(
        LiveRoom.anchor_id == user.id,
        LiveRoom.status == 1
    ).first()
    
    if existing_active:
        raise HTTPException(status_code=400, detail='你已有一个正在直播的房间，请先结束当前直播')
    
    # 删除该用户所有已结束的旧房间
    db.query(LiveRoom).filter(
        LiveRoom.anchor_id == user.id,
        LiveRoom.status == 2
    ).delete()
    
    # 确保用户有唯一的 stream_key
    if not user.stream_key:
        import random
        user.stream_key = str(random.randint(100000, 999999))
        db.commit()
    
    category_id = int(data.categoryId or 10)
    exists_category = db.query(Category).filter(Category.id == category_id).first()
    if not exists_category:
        category_id = 10
        live_category = db.query(Category).filter(Category.id == 10).first()
        if not live_category:
            db.add(Category(id=10, name="直播", type=1, sort_order=10))
            db.commit()

    # 使用用户上传的封面，如果没有则使用默认封面
    cover_url = data.cover if data.cover else "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=900&auto=format&fit=crop"

    r = LiveRoom(
        title=data.title or "新的直播间",
        description=data.description or "",
        category_id=category_id,
        cover=cover_url,
        stream_key=user.stream_key,
        push_url=f"rtmp://localhost:1935/live/{user.stream_key}",
        pull_url=f"http://localhost:8080/live/{user.stream_key}.flv",
        anchor_id=user.id,
        online_count=0,
        status=1,
    )

    db.add(r)
    db.commit()
    db.refresh(r)
    
    return live_out(r)

@app.post('/api/live/rooms/{room_id}/end')
def end_room(room_id: UUID, user: User = Depends(require_creator), db: Session = Depends(get_db)):
    r = db.get(LiveRoom, room_id)
    if not r: raise HTTPException(status_code=404, detail='直播间不存在')
    if user.user_type < 2 and r.anchor_id != user.id: raise HTTPException(status_code=403, detail='只能结束自己的直播')
    r.status = 2; r.end_time = datetime.now(timezone.utc)
    db.commit()
    return {'ok': True}

@app.websocket('/ws/live/{room_id}')
async def live_ws(ws: WebSocket, room_id: str, token: str = ''):
    username = '游客'
    user_id = ''
    if token:
        try:
            uid = parse_token(token)
            db = SessionLocal(); user = db.get(User, uid); db.close()
            if user:
                username = user.nickname; user_id = str(user.id)
        except Exception:
            pass
    try:
        await live_hub.connect(room_id, ws)
        await ws.send_json({'type': 'join_ack', 'onlineCount': len(live_hub.rooms.get(room_id, []))})
        await live_hub.broadcast(room_id, {'type': 'system', 'content': f'{username} 进入直播间', 'timestamp': datetime.now(timezone.utc).isoformat()})
    except (WebSocketDisconnect, RuntimeError):
        live_hub.disconnect(room_id, ws)
        await live_hub.broadcast(room_id, {'type': 'online', 'count': len(live_hub.rooms.get(room_id, []))})
        return
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            if data.get('type') == 'heartbeat':
                await ws.send_json({'type': 'online', 'count': len(live_hub.rooms.get(room_id, []))})
            elif data.get('type') == 'danmaku':
                await live_hub.broadcast(room_id, {'type': 'danmaku', 'id': secrets.token_hex(8), 'content': data.get('content', ''), 'color': data.get('color', '#fff'), 'position': data.get('position', 0), 'username': username, 'userId': user_id, 'timestamp': datetime.now(timezone.utc).isoformat()})
    except WebSocketDisconnect:
        live_hub.disconnect(room_id, ws)
        await live_hub.broadcast(room_id, {'type': 'online', 'count': len(live_hub.rooms.get(room_id, []))})


# ======================================================================
# 社区互动:关注 / 粉丝
# ======================================================================

def user_brief(u: User) -> UserBrief:
    return UserBrief(
        id=str(u.id), account=u.account, nickname=u.nickname,
        avatar=u.avatar or '', bio=u.bio or '',
    )


def create_notification(
    db: Session,
    *,
    recipient_id,
    sender_id,
    notif_type: int,
    target_type: int = 0,
    target_id=None,
    content: str = '',
    auto_commit: bool = True,
):
    """统一创建通知。不要给自己发通知。"""
    if str(recipient_id) == str(sender_id):
        return None
    n = Notification(
        recipient_id=recipient_id,
        sender_id=sender_id,
        notif_type=notif_type,
        target_type=target_type,
        target_id=target_id,
        content=content[:500],
    )
    db.add(n)
    if auto_commit:
        db.commit()
        db.refresh(n)
    return n


@app.post('/api/users/{user_id}/follow')
def follow_user(user_id: UUID, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if str(user_id) == str(me.id):
        raise HTTPException(status_code=400, detail='不能关注自己')
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail='用户不存在')

    existing = db.query(Follow).filter(
        Follow.follower_id == me.id,
        Follow.followee_id == user_id,
    ).first()
    if existing:
        return {'ok': True, 'isFollowing': True}

    db.add(Follow(follower_id=me.id, followee_id=user_id))
    db.commit()

    create_notification(
        db,
        recipient_id=user_id,
        sender_id=me.id,
        notif_type=2,  # 关注
        target_type=0,
        target_id=None,
        content=f'{me.nickname} 关注了你',
    )
    return {'ok': True, 'isFollowing': True}


@app.delete('/api/users/{user_id}/follow')
def unfollow_user(user_id: UUID, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Follow).filter(
        Follow.follower_id == me.id,
        Follow.followee_id == user_id,
    ).delete()
    db.commit()
    return {'ok': True, 'isFollowing': False}


@app.get('/api/users/{user_id}/relation')
def get_relation(user_id: UUID, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    is_following = db.query(Follow).filter(
        Follow.follower_id == me.id, Follow.followee_id == user_id,
    ).first() is not None
    is_followed_by = db.query(Follow).filter(
        Follow.follower_id == user_id, Follow.followee_id == me.id,
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


@app.get('/api/users/{user_id}/followers')
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
        .offset(offset).limit(limit).all()
    )
    return [
        FollowListItem(
            **user_brief(u).model_dump(),
            followedAt=f.created_at.isoformat() if f.created_at else '',
        ) for f, u in rows
    ]


@app.get('/api/users/{user_id}/following')
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
        .offset(offset).limit(limit).all()
    )
    return [
        FollowListItem(
            **user_brief(u).model_dump(),
            followedAt=f.created_at.isoformat() if f.created_at else '',
        ) for f, u in rows
    ]


@app.get('/api/users/{user_id}')
def get_user_profile(user_id: UUID, db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail='用户不存在')
    return user_out(u)

@app.get('/api/users/{user_id}/videos')
def get_user_videos(
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    """获取指定用户上传的视频列表"""
    # 检查用户是否存在
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    
    # 查询该用户的已审核通过的视频
    q = db.query(Video).filter(
        Video.uploader_id == user_id,
        Video.audit_status == 1,
        Video.status == 0
    ).order_by(desc(Video.created_at))
    
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        'items': [video_out(v).model_dump() for v in items],
        'total': total,
        'page': page,
        'pageSize': page_size,
        'hasMore': page * page_size < total
    }

@app.get('/api/users/{user_id}/likes')
def get_user_likes(
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户喜欢的视频列表"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    
    # 查询用户点赞的视频
    q = db.query(Video).join(
        VideoLike, VideoLike.video_id == Video.id
    ).filter(
        VideoLike.user_id == user_id,
        Video.audit_status == 1,
        Video.status == 0
    ).order_by(desc(VideoLike.created_at))
    
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        'items': [video_out(v).model_dump() for v in items],
        'total': total,
        'page': page,
        'pageSize': page_size,
        'hasMore': page * page_size < total
    }

# ======================================================================
# 社区互动:通知中心
# ======================================================================

def notification_out(n: Notification) -> NotificationOut:
    sender = n.sender
    return NotificationOut(
        id=str(n.id),
        notifType=n.notif_type or 0,
        targetType=n.target_type or 0,
        targetId=str(n.target_id) if n.target_id else '',
        senderId=str(n.sender_id) if n.sender_id else '',
        senderName=sender.nickname if sender else '系统',
        senderAvatar=sender.avatar if sender else '',
        content=n.content or '',
        isRead=bool(n.is_read),
        createTime=n.created_at.isoformat() if n.created_at else '',
    )


@app.get('/api/notifications')
def list_notifications(
    notif_type: Optional[int] = Query(None, ge=0, le=4),
    only_unread: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(Notification.recipient_id == me.id)
    if notif_type is not None:
        q = q.filter(Notification.notif_type == notif_type)
    if only_unread:
        q = q.filter(Notification.is_read == False)
    rows = q.order_by(desc(Notification.created_at)).offset(offset).limit(limit).all()
    return [notification_out(n) for n in rows]


@app.get('/api/notifications/unread-count')
def unread_count(me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif_unread = db.query(Notification).filter(
        Notification.recipient_id == me.id,
        Notification.is_read == False,
    ).count()
    chat_unread = db.query(Message).filter(
        Message.receiver_id == me.id,
        Message.is_read == False,
        Message.is_recalled == False,
    ).count()
    return UnreadCountOut(
        total=notif_unread + chat_unread,
        chat=chat_unread,
        notification=notif_unread,
    )


@app.post('/api/notifications/{notif_id}/read')
def mark_notification_read(
    notif_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notif_id)
    if not n or n.recipient_id != me.id:
        raise HTTPException(status_code=404, detail='通知不存在')
    n.is_read = True
    db.commit()
    return {'ok': True}


@app.post('/api/notifications/read-all')
def mark_all_read(
    notif_type: Optional[int] = Query(None, ge=0, le=4),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter(
        Notification.recipient_id == me.id,
        Notification.is_read == False,
    )
    if notif_type is not None:
        q = q.filter(Notification.notif_type == notif_type)
    q.update({Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {'ok': True}


# ======================================================================
# 社区互动:私聊
# ======================================================================

def _order_pair(a, b):
    """保证 user_a_id < user_b_id,这样每对用户只会有一个会话。"""
    sa, sb = str(a), str(b)
    return (a, b) if sa < sb else (b, a)


def get_or_create_conversation(db: Session, user1, user2) -> Conversation:
    ua, ub = _order_pair(user1, user2)
    conv = db.query(Conversation).filter(
        Conversation.user_a_id == ua,
        Conversation.user_b_id == ub,
    ).first()
    if conv:
        return conv
    conv = Conversation(user_a_id=ua, user_b_id=ub)
    db.add(conv)
    try:
        db.commit()
    except IntegrityError:
        # Two clients can create the same user pair after both initial reads
        # return no row. The unique constraint selects one winner; recover the
        # losing transaction and return that committed conversation.
        db.rollback()
        conv = db.query(Conversation).filter(
            Conversation.user_a_id == ua,
            Conversation.user_b_id == ub,
        ).first()
        if conv:
            return conv
        raise
    db.refresh(conv)
    return conv


def message_out(m: Message, sender_user: Optional[User] = None) -> MessageOut:
    s = sender_user or m.sender
    content = '消息已撤回' if m.is_recalled else (m.content or '')
    return MessageOut(
        id=str(m.id),
        conversationId=str(m.conversation_id),
        senderId=str(m.sender_id),
        senderName=s.nickname if s else '',
        senderAvatar=s.avatar if s else '',
        receiverId=str(m.receiver_id),
        content=content,
        messageType=m.message_type or 0,
        isRecalled=bool(m.is_recalled),
        isRead=bool(m.is_read),
        createTime=m.created_at.isoformat() if m.created_at else '',
    )


def conversation_out(db: Session, conv: Conversation, me_id) -> ConversationOut:
    peer_id = conv.user_b_id if str(conv.user_a_id) == str(me_id) else conv.user_a_id
    peer = db.get(User, peer_id)
    last_msg = db.get(Message, conv.last_message_id) if conv.last_message_id else None
    unread = db.query(Message).filter(
        Message.conversation_id == conv.id,
        Message.receiver_id == me_id,
        Message.is_read == False,
        Message.is_recalled == False,
    ).count()
    return ConversationOut(
        id=str(conv.id),
        peerId=str(peer_id),
        peerName=peer.nickname if peer else '未知用户',
        peerAvatar=peer.avatar if peer else '',
        lastMessage=('[已撤回]' if last_msg and last_msg.is_recalled else (last_msg.content if last_msg else '')),
        lastMessageType=last_msg.message_type if last_msg else 0,
        lastMessageAt=conv.last_message_at.isoformat() if conv.last_message_at else '',
        unreadCount=unread,
    )


class ChatHub:
    """每个用户可同时有多端在线;按 user_id 广播。"""
    def __init__(self):
        self.user_conns: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.user_conns.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self.user_conns and ws in self.user_conns[user_id]:
            self.user_conns[user_id].remove(ws)
            if not self.user_conns[user_id]:
                del self.user_conns[user_id]

    async def push_to_user(self, user_id: str, payload: dict):
        dead = []
        for ws in self.user_conns.get(user_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    def is_online(self, user_id: str) -> bool:
        return user_id in self.user_conns and len(self.user_conns[user_id]) > 0


chat_hub = ChatHub()


@app.get('/api/chat/conversations')
def list_conversations(me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    convs = db.query(Conversation).filter(
        or_(Conversation.user_a_id == me.id, Conversation.user_b_id == me.id)
    ).all()
    # 按最后消息时间倒序(无消息的放最后)
    convs.sort(key=lambda c: (c.last_message_at is None, -(c.last_message_at.timestamp() if c.last_message_at else 0)))
    return [conversation_out(db, c, me.id) for c in convs]


@app.post('/api/chat/conversations')
def create_conversation(payload: dict, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    peer_id_str = payload.get('peerId')
    if not peer_id_str:
        raise HTTPException(status_code=400, detail='缺少 peerId')
    try:
        peer_id = UUID(peer_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail='peerId 不是有效 UUID')
    if str(peer_id) == str(me.id):
        raise HTTPException(status_code=400, detail='不能跟自己聊天')
    peer = db.get(User, peer_id)
    if not peer:
        raise HTTPException(status_code=404, detail='用户不存在')
    conv = get_or_create_conversation(db, me.id, peer_id)
    return conversation_out(db, conv, me.id)


@app.get('/api/chat/conversations/{conv_id}/messages')
def list_messages(
    conv_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = Query(None, description='ISO 时间戳,只返回此时间之前的'),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conv_id)
    if not conv or (str(conv.user_a_id) != str(me.id) and str(conv.user_b_id) != str(me.id)):
        raise HTTPException(status_code=404, detail='会话不存在')
    q = db.query(Message).filter(Message.conversation_id == conv_id)
    if before:
        try:
            t = datetime.fromisoformat(before.replace('Z', '+00:00'))
            q = q.filter(Message.created_at < t)
        except ValueError:
            pass
    msgs = q.order_by(desc(Message.created_at)).limit(limit).all()
    msgs.reverse()  # 时间正序返回
    return [message_out(m) for m in msgs]


async def _persist_and_push_message(
    db: Session, sender: User, receiver_id, content: str, message_type: int
) -> Message:
    if not content.strip():
        raise HTTPException(status_code=400, detail='消息不能为空')
    if str(sender.id) == str(receiver_id):
        raise HTTPException(status_code=400, detail='不能给自己发消息')
    receiver = db.get(User, receiver_id)
    if not receiver:
        raise HTTPException(status_code=404, detail='接收人不存在')
    conv = get_or_create_conversation(db, sender.id, receiver_id)
    m = Message(
        conversation_id=conv.id,
        sender_id=sender.id,
        receiver_id=receiver_id,
        content=content[:2000],
        message_type=message_type,
    )
    db.add(m)
    db.flush()
    conv.last_message_id = m.id
    conv.last_message_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(m)

    payload = {'type': 'message', 'data': message_out(m, sender).model_dump()}
    await chat_hub.push_to_user(str(receiver_id), payload)
    await chat_hub.push_to_user(str(sender.id), payload)  # 多端同步
    return m


@app.post('/api/chat/conversations/{conv_id}/messages')
async def send_message_http(
    conv_id: UUID,
    data: MessageCreate,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conv_id)
    if not conv or (str(conv.user_a_id) != str(me.id) and str(conv.user_b_id) != str(me.id)):
        raise HTTPException(status_code=404, detail='会话不存在')
    peer_id = conv.user_b_id if str(conv.user_a_id) == str(me.id) else conv.user_a_id
    m = await _persist_and_push_message(db, me, peer_id, data.content, data.messageType)
    return message_out(m, me)


@app.post('/api/chat/messages/{msg_id}/recall')
async def recall_message(
    msg_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = db.get(Message, msg_id)
    if not m or str(m.sender_id) != str(me.id):
        raise HTTPException(status_code=404, detail='消息不存在')
    if m.is_recalled:
        return {'ok': True}
    # 2 分钟内可撤回
    if m.created_at and (datetime.now(timezone.utc) - m.created_at).total_seconds() > 120:
        raise HTTPException(status_code=400, detail='超过 2 分钟,无法撤回')
    m.is_recalled = True
    m.recalled_at = datetime.now(timezone.utc)
    db.commit()

    payload = {'type': 'recall', 'messageId': str(m.id), 'conversationId': str(m.conversation_id)}
    await chat_hub.push_to_user(str(m.receiver_id), payload)
    await chat_hub.push_to_user(str(m.sender_id), payload)
    return {'ok': True}


@app.post('/api/chat/conversations/{conv_id}/read')
async def mark_conversation_read(
    conv_id: UUID,
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.get(Conversation, conv_id)
    if not conv or (str(conv.user_a_id) != str(me.id) and str(conv.user_b_id) != str(me.id)):
        raise HTTPException(status_code=404, detail='会话不存在')
    db.query(Message).filter(
        Message.conversation_id == conv_id,
        Message.receiver_id == me.id,
        Message.is_read == False,
    ).update({Message.is_read: True}, synchronize_session=False)
    db.commit()
    peer_id = conv.user_b_id if str(conv.user_a_id) == str(me.id) else conv.user_a_id
    await chat_hub.push_to_user(str(peer_id), {
        'type': 'read', 'conversationId': str(conv_id), 'readerId': str(me.id)
    })
    return {'ok': True}


@app.websocket('/ws/chat')
async def chat_ws(ws: WebSocket, token: str = ''):
    if not token:
        await ws.close(code=4401)
        return
    try:
        uid = parse_token(token)
    except Exception:
        await ws.close(code=4401)
        return
    db = SessionLocal()
    user = db.get(User, uid)
    if not user:
        db.close()
        await ws.close(code=4401)
        return
    user_id_str = str(user.id)
    await chat_hub.connect(user_id_str, ws)
    await ws.send_json({'type': 'connected', 'userId': user_id_str})
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue
            mtype = data.get('type')
            if mtype == 'ping':
                await ws.send_json({'type': 'pong'})
            elif mtype == 'send':
                peer_id_str = data.get('peerId') or ''
                content = (data.get('content') or '').strip()
                message_type = int(data.get('messageType') or 0)
                if not peer_id_str or not content:
                    continue
                try:
                    peer_id = UUID(peer_id_str)
                except ValueError:
                    continue
                try:
                    await _persist_and_push_message(db, user, peer_id, content, message_type)
                except HTTPException as e:
                    await ws.send_json({'type': 'error', 'detail': e.detail})
            elif mtype == 'typing':
                peer_id_str = data.get('peerId') or ''
                if peer_id_str:
                    await chat_hub.push_to_user(peer_id_str, {
                        'type': 'typing', 'fromUserId': user_id_str
                    })
    except WebSocketDisconnect:
        chat_hub.disconnect(user_id_str, ws)
    finally:
        db.close()

# ======================================================================
# 修改密码
# ======================================================================

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@app.put('/api/auth/change-password')
def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail='原密码错误')
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail='新密码至少6位')
    if data.old_password == data.new_password:
        raise HTTPException(status_code=400, detail='新密码不能与原密码相同')
    
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {'code': 0, 'message': '密码修改成功'}

# ======================================================================
# 成为创作者
# ======================================================================

@app.post('/api/auth/upgrade-to-creator')
def upgrade_to_creator(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """将普通用户升级为创作者"""
    # 已经是创作者或管理员
    if user.user_type >= 1:
        raise HTTPException(status_code=400, detail='已经是创作者或管理员')
    
    # 升级为创作者
    user.user_type = 1
    db.commit()
    db.refresh(user)
    
    return {
        'code': 0,
        'message': '已成功升级为创作者',
        'data': {
            'userType': user.user_type
        }
    }

# ======================================================================
# 头像
# ======================================================================

import shutil
from fastapi import UploadFile, File

AVATAR_UPLOAD_DIR = LEGACY_PUBLIC_ROOT / "avatars"


def _safe_upload_extension(filename: Optional[str], default: str) -> str:
    candidate = (filename or "").rsplit(".", 1)[-1].lower()
    return candidate if re.fullmatch(r"[a-z0-9]{1,10}", candidate) else default


def _upload_length(file: UploadFile) -> int:
    if file.size is not None:
        return int(file.size)
    current = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    length = file.file.tell()
    file.file.seek(current)
    return int(length)


def _store_upload(
    file: UploadFile,
    object_name: str,
    content_type: str,
) -> None:
    try:
        file.file.seek(0)
        media_storage.upload_stream(
            file.file,
            object_name,
            _upload_length(file),
            content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="对象存储上传失败") from exc

@app.post('/api/auth/upload-avatar')
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传头像"""
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='只支持图片文件')
    
    if _upload_length(file) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='图片大小不能超过5MB')

    ext = _safe_upload_extension(file.filename, 'jpg')
    filename = f"{user.id}_{secrets.token_hex(8)}.{ext}"
    object_name = f"avatars/{filename}"
    _store_upload(file, object_name, file.content_type)
    
    # 生成访问URL
    avatar_url = f"/avatars/{filename}"
    
    # 更新用户头像
    user.avatar = avatar_url
    db.commit()
    db.refresh(user)
    
    return {
        'code': 0,
        'message': '头像上传成功',
        'data': {'avatar': avatar_url}
    }

# ======================================================================
# 数据统计
# ======================================================================

@app.get('/api/users/{user_id}/stats')
def get_user_stats(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    """获取用户统计数据：粉丝数、关注数、获赞数"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    
    # 粉丝数：关注该用户的人数
    follower_count = db.query(Follow).filter(Follow.followee_id == user_id).count()
    
    # 关注数：该用户关注的人数
    following_count = db.query(Follow).filter(Follow.follower_id == user_id).count()
    
    # 获赞数：该用户所有视频的点赞总数
    like_count = db.query(func.sum(Video.like_count)).filter(Video.uploader_id == user_id).scalar() or 0
    
    return {
        'followerCount': follower_count,
        'followingCount': following_count,
        'likeCount': like_count
    }

# ======================================================================
# 真正的视频文件上传
# ======================================================================

import shutil
from fastapi import UploadFile, File

VIDEO_UPLOAD_DIR = LEGACY_PUBLIC_ROOT / "uploads" / "videos"
COVER_UPLOAD_DIR = LEGACY_PUBLIC_ROOT / "uploads" / "covers"

@app.post('/api/videos/upload-file')
async def upload_video_file(
    file: UploadFile = File(...),
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    if not file.content_type or not file.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail='只支持视频文件')
    if file.size is not None and file.size > 500 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='文件大小不能超过500MB')

    ext = _safe_upload_extension(file.filename, 'mp4')
    filename = f"{user.id}_{secrets.token_hex(8)}.{ext}"
    object_name = f"uploads/videos/{filename}"
    video_url = f"/uploads/videos/{filename}"
    temp_path: Optional[Path] = None

    try:
        file.file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_path = Path(temp_file.name)

        if temp_path.stat().st_size > 500 * 1024 * 1024:
            raise HTTPException(status_code=400, detail='文件大小不能超过500MB')

        try:
            media_storage.upload_path(
                temp_path,
                object_name,
                file.content_type or "video/mp4",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="对象存储上传失败") from exc

        cover_filename = f"{user.id}_{secrets.token_hex(8)}.jpg"
        cover_object_name = f"uploads/covers/{cover_filename}"
        cover_url = ""
        duration = 0

        try:
            cap = cv2.VideoCapture(str(temp_path))
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    encoded_ok, encoded_frame = cv2.imencode('.jpg', frame)
                    if encoded_ok:
                        cover_bytes = encoded_frame.tobytes()
                        media_storage.upload_stream(
                            io.BytesIO(cover_bytes),
                            cover_object_name,
                            len(cover_bytes),
                            "image/jpeg",
                        )
                        cover_url = f"/uploads/covers/{cover_filename}"

                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if fps > 0:
                    duration = int(frame_count / fps)
            cap.release()
        except Exception as exc:
            print(f"视频封面或时长读取失败: {exc}")

        return {
            'code': 0,
            'message': '上传成功',
            'data': {
                'videoUrl': video_url,
                'duration': duration,
                'coverUrl': cover_url
            }
        }
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()

# ======================================================================
# 视频封面上传
# ======================================================================

VIDEO_COVER_UPLOAD_DIR = LEGACY_PUBLIC_ROOT / "uploads" / "covers"

@app.post('/api/videos/upload-cover')
async def upload_video_cover(
    file: UploadFile = File(...),
    user: User = Depends(require_creator),
):
    """上传视频封面（独立接口，不影响用户头像）"""
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='只支持图片文件')
    
    if _upload_length(file) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='图片大小不能超过5MB')

    ext = _safe_upload_extension(file.filename, 'jpg')
    filename = f"cover_{user.id}_{secrets.token_hex(8)}.{ext}"
    object_name = f"uploads/covers/{filename}"
    _store_upload(file, object_name, file.content_type)

    cover_url = f"/uploads/covers/{filename}"
    
    return {
        'code': 0,
        'message': '封面上传成功',
        'data': {'coverUrl': cover_url}
    }

# ======================================================================
# 视频动态
# ======================================================================

@app.get('/api/feed')
def get_feed(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取关注用户的动态（视频作品）"""
    # 获取当前用户关注的人
    following_ids = db.query(Follow.followee_id).filter(
        Follow.follower_id == user.id
    ).subquery()
    
    # 查询这些用户的视频
    q = db.query(Video).filter(
        Video.uploader_id.in_(following_ids),
        Video.status == 0,
        Video.audit_status == 1
    ).order_by(Video.created_at.desc())
    
    # 分页
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    total = q.count()
    
    return {
        'items': [video_out(v).model_dump() for v in items],
        'hasMore': page * page_size < total
    }

# ======================================================================
# 创作者中心 - 粉丝列表
# ======================================================================

@app.get('/api/creator/fans')
def creator_fans(
    page: int = 1, 
    limit: int = 20,
    user: User = Depends(require_creator), 
    db: Session = Depends(get_db)
):
    """获取创作者的粉丝列表"""
    fans = db.query(Follow, User).join(
        User, User.id == Follow.follower_id
    ).filter(
        Follow.followee_id == user.id
    ).order_by(Follow.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        'items': [{
            'id': str(f[0].id),
            'name': f[1].nickname,
            'avatar': f[1].avatar,
            'followTime': f[0].created_at.isoformat()
        } for f in fans],
        'total': db.query(Follow).filter(Follow.followee_id == user.id).count()
    }

# ======================================================================
# 创作者中心 - 评论管理
# ======================================================================

@app.get('/api/creator/comments')
def creator_comments(
    page: int = 1,
    limit: int = 20,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """获取创作者收到的评论"""
    comments = db.query(Comment).join(
        Video, Video.id == Comment.video_id
    ).filter(
        Video.uploader_id == user.id
    ).order_by(Comment.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        'items': [{
            'id': str(c.id),
            'videoTitle': db.get(Video, c.video_id).title,
            'content': c.content,
            'userName': c.user.nickname,
            'userAvatar': c.user.avatar,
            'time': c.created_at.isoformat()
        } for c in comments],
        'total': db.query(Comment).join(Video).filter(Video.uploader_id == user.id).count()
    }

# ======================================================================
# 创作者中心 - 近7天播放量趋势
# ======================================================================

from datetime import datetime, timedelta

@app.get('/api/creator/week-stats')
def creator_week_stats(
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """获取创作者近7天播放量趋势"""
    today = datetime.now().date()
    week_stats = []
    
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        # 查询当天该创作者所有视频的播放量总和
        # 注意：需要 video_views 每日统计表，这里简化处理
        # 暂时返回模拟数据，后续可根据实际需求完善
        week_stats.append({
            'day': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][6-i],
            'views': 0  # 实际需要从统计数据获取
        })
    
    return week_stats

# ======================================================================
# 创作者中心 - 按状态获取视频
# ======================================================================

@app.get('/api/creator/videos/{status}')
def creator_videos_by_status(
    status: int,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """获取创作者指定审核状态的视频"""
    rows = db.query(Video).filter(
        Video.uploader_id == user.id,
        Video.audit_status == status
    ).order_by(desc(Video.created_at)).all()
    return {'items': [video_out(v).model_dump() for v in rows]}

# ======================================================================
# 删除视频
# ======================================================================

@app.delete('/api/creator/videos/{video_id}')
def delete_video(
    video_id: UUID,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """删除创作者自己的视频"""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.uploader_id == user.id
    ).first()
    
    if not video:
        raise HTTPException(status_code=404, detail='视频不存在或无权限删除')
    
    # 先删除关联的评论
    db.query(Comment).filter(Comment.video_id == video_id).delete()
    
    # 删除关联的弹幕
    db.query(Danmaku).filter(
        Danmaku.target_id == video_id,
        Danmaku.target_type == 0
    ).delete()
    
    # 删除关联的点赞记录
    db.query(VideoLike).filter(VideoLike.video_id == video_id).delete()
    
    # 最后删除视频
    db.delete(video)
    db.commit()
    
    return {'code': 0, 'message': '删除成功'}

# ======================================================================
# 编辑视频
# ======================================================================

class VideoUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None

@app.put('/api/creator/videos/{video_id}')
def update_video(
    video_id: UUID,
    data: VideoUpdateRequest,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """编辑创作者自己的视频"""
    video = db.query(Video).filter(
        Video.id == video_id,
        Video.uploader_id == user.id
    ).first()
    
    if not video:
        raise HTTPException(status_code=404, detail='视频不存在或无权限编辑')
    
    if data.title is not None:
        video.title = data.title
    if data.description is not None:
        video.description = data.description
    if data.category_id is not None:
        # 验证分类是否存在
        category = db.get(Category, data.category_id)
        if category:
            video.category_id = data.category_id
    
    db.commit()
    db.refresh(video)
    
    return {'code': 0, 'message': '更新成功', 'data': video_out(video).model_dump()}

# ======================================================================
# 删除评论
# ======================================================================

@app.delete('/api/creator/comments/{comment_id}')
def delete_comment(
    comment_id: UUID,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """创作者删除自己视频下的评论"""
    # 检查评论是否属于创作者的视频
    comment = db.query(Comment).join(
        Video, Video.id == Comment.video_id
    ).filter(
        Comment.id == comment_id,
        Video.uploader_id == user.id
    ).first()
    
    if not comment:
        raise HTTPException(status_code=404, detail='评论不存在或无权限删除')
    
    db.delete(comment)
    db.commit()
    
    return {'code': 0, 'message': '删除成功'}

# ======================================================================
# 获取创作者当前直播中的房间
# ======================================================================

@app.get('/api/creator/active-room')
def get_active_room(
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """获取创作者当前正在直播的房间"""
    room = db.query(LiveRoom).filter(
        LiveRoom.anchor_id == user.id,
        LiveRoom.status == 1  # 直播中
    ).first()
    
    if room:
        return live_out(room)
    return None


# ======================================================================
# 停止直播（关闭直播间）
# ======================================================================

@app.post('/api/live/rooms/{room_id}/stop')
def stop_room(
    room_id: UUID,
    user: User = Depends(require_creator),
    db: Session = Depends(get_db)
):
    """停止直播（删除直播间记录）"""
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail='直播间不存在')
    if room.anchor_id != user.id:
        raise HTTPException(status_code=403, detail='只能结束自己的直播')
    
    # 直接删除记录，而不是更新状态
    db.delete(room)
    db.commit()
    
    return {'code': 0, 'message': '直播已结束'}

# ======================================================================
# 直播弹幕 HTTP 接口
# ======================================================================

@app.post('/api/live/{room_id}/danmaku')
async def send_live_danmaku(
    room_id: UUID,
    data: DanmakuCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail='直播间不存在')
    
    # 敏感词过滤
    filtered_content = filter_sensitive_words(data.content, db)
    
    danmaku = Danmaku(
        content=filtered_content,
        color=data.color,
        position=data.position,
        video_time=data.videoTime,
        target_id=room_id,
        target_type=1,
        user_id=user.id
    )
    db.add(danmaku)
    db.commit()
    
    await live_hub.broadcast(str(room_id), {
        'type': 'danmaku',
        'id': str(danmaku.id),
        'content': filtered_content,
        'color': data.color,
        'username': user.nickname,
        'userAvatar': user.avatar,
        'userId': str(user.id),
        'timestamp': datetime.now().isoformat()
    })
    
    return {'code': 0, 'message': '发送成功'}

# ======================================================================
# 用户管理（管理员）
# ======================================================================

@app.get('/api/admin/users')
def admin_users(
    page: int = 1,
    limit: int = 20,
    keyword: Optional[str] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    q = db.query(User)
    if keyword:
        q = q.filter(or_(
            User.account.ilike(f'%{keyword}%'),
            User.nickname.ilike(f'%{keyword}%')
        ))
    total = q.count()
    users = q.order_by(User.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        'items': [user_out(u).model_dump() for u in users],
        'total': total,
        'page': page,
        'limit': limit
    }


@app.patch('/api/admin/users/{user_id}/type')
def update_user_type(
    user_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """修改用户类型"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    if user.account == 'admin':
        raise HTTPException(status_code=403, detail='不能修改管理员账户')
    
    user_type = data.get('userType')
    if user_type is not None and user_type in [0, 1, 2]:
        user.user_type = user_type
        db.commit()
        db.refresh(user)
    
    return user_out(user)


@app.patch('/api/admin/users/{user_id}/ban')
def ban_user(
    user_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """封禁/解封用户"""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='用户不存在')
    if user.account == 'admin':
        raise HTTPException(status_code=403, detail='不能封禁管理员账户')
    
    status = data.get('status', 0)
    user.status = status
    db.commit()
    db.refresh(user)
    
    return user_out(user)

# ======================================================================
# 举报功能
# ======================================================================

class ReportCreate(BaseModel):
    target_type: int  # 0视频 1评论 2直播
    target_id: str
    reason: str

@app.post('/api/reports')
def create_report(
    data: ReportCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建举报"""
    report = Report(
        reporter_id=user.id,
        target_type=data.target_type,
        target_id=UUID(data.target_id),
        reason=data.reason,
        status=0
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {'code': 0, 'message': '举报已提交'}


@app.get('/api/admin/reports')
def admin_reports(
    status: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取举报列表"""
    q = db.query(Report)
    if status is not None:
        q = q.filter(Report.status == status)
    q = q.order_by(Report.created_at.desc())
    total = q.count()
    items = q.offset((page-1)*limit).limit(limit).all()
    
    result = []
    for r in items:
        target_info = {}
        video_id = None  # 用于评论跳转
        
        if r.target_type == 0:  # 视频
            video = db.get(Video, r.target_id)
            target_info = {'title': video.title if video else '已删除', 'type': 'video'}
            target_url = f"/#/video/{r.target_id}"
        elif r.target_type == 1:  # 评论
            comment = db.get(Comment, r.target_id)
            if comment:
                video_id = str(comment.video_id)
                target_info = {'content': comment.content[:50] if comment else '已删除', 'type': 'comment'}
                target_url = f"/#/video/{comment.video_id}#comment-{r.target_id}"
            else:
                target_info = {'content': '已删除', 'type': 'comment'}
                target_url = "#"
        elif r.target_type == 2:  # 直播
            room = db.get(LiveRoom, r.target_id)
            target_info = {'title': room.title if room else '已删除', 'type': 'live'}
            target_url = f"/#/live/{r.target_id}"
        else:
            target_url = "#"
        
        result.append({
            'id': str(r.id),
            'reporterId': str(r.reporter_id),
            'reporterName': r.reporter.nickname,
            'reporterAvatar': r.reporter.avatar,
            'targetType': r.target_type,
            'targetId': str(r.target_id),
            'targetInfo': target_info,
            'targetUrl': target_url,
            'videoId': video_id,  # 添加视频ID
            'reason': r.reason,
            'status': r.status,
            'handlerId': str(r.handler_id) if r.handler_id else None,
            'handlerName': r.handler.nickname if r.handler else None,
            'handledAt': r.handled_at.isoformat() if r.handled_at else None,
            'createdAt': r.created_at.isoformat()
        })
    
    return {'items': result, 'total': total, 'page': page, 'hasMore': page * limit < total}

@app.patch('/api/admin/reports/{report_id}/handle')
def handle_report(
    report_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """标记举报为已处理"""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail='举报不存在')
    report.status = 1
    db.commit()
    return {'code': 0, 'message': '已标记为已处理'}


@app.patch('/api/admin/reports/{report_id}/ignore')
def ignore_report(
    report_id: UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """标记举报为已忽略"""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail='举报不存在')
    report.status = 2
    db.commit()
    return {'code': 0, 'message': '已忽略'}

# ======================================================================
# 敏感词管理
# ======================================================================

from .models import SensitiveWord

# 敏感词缓存
_sensitive_words_cache = []
_cache_loaded = False

def load_sensitive_words(db: Session):
    """加载敏感词到缓存"""
    global _sensitive_words_cache, _cache_loaded
    words = db.query(SensitiveWord.word).all()
    _sensitive_words_cache = [w[0] for w in words]
    _cache_loaded = True
    return _sensitive_words_cache

def filter_sensitive_words(text: str, db: Session) -> str:
    """过滤敏感词，替换为*"""
    global _sensitive_words_cache, _cache_loaded
    if not _cache_loaded:
        load_sensitive_words(db)
    
    result = text
    for word in _sensitive_words_cache:
        if word in result:
            result = result.replace(word, '*' * len(word))
    return result

@app.get('/api/admin/sensitive-words')
def list_sensitive_words(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取敏感词列表"""
    words = db.query(SensitiveWord).order_by(SensitiveWord.created_at.desc()).all()
    return {'items': [{'id': w.id, 'word': w.word} for w in words]}

@app.post('/api/admin/sensitive-words')
def add_sensitive_word(
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """添加敏感词"""
    word = data.get('word', '').strip()
    if not word:
        raise HTTPException(status_code=400, detail='敏感词不能为空')
    
    exists = db.query(SensitiveWord).filter(SensitiveWord.word == word).first()
    if exists:
        raise HTTPException(status_code=400, detail='敏感词已存在')
    
    sw = SensitiveWord(word=word)
    db.add(sw)
    db.commit()
    
    # 重新加载缓存
    load_sensitive_words(db)
    
    return {'code': 0, 'message': '添加成功', 'data': {'id': sw.id, 'word': sw.word}}

@app.delete('/api/admin/sensitive-words/{word_id}')
def delete_sensitive_word(
    word_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """删除敏感词"""
    sw = db.get(SensitiveWord, word_id)
    if not sw:
        raise HTTPException(status_code=404, detail='敏感词不存在')
    
    db.delete(sw)
    db.commit()
    
    # 重新加载缓存
    load_sensitive_words(db)
    
    return {'code': 0, 'message': '删除成功'}

# ======================================================================
# 视频管理（管理员）
# ======================================================================

@app.get('/api/admin/videos')
def admin_videos(
    page: int = 1,
    limit: int = 20,
    keyword: Optional[str] = None,
    audit_status: Optional[int] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取所有视频列表"""
    q = db.query(Video).filter(Video.status == 0)
    
    if keyword:
        q = q.filter(Video.title.ilike(f'%{keyword}%'))
    if audit_status is not None:
        q = q.filter(Video.audit_status == audit_status)
    
    total = q.count()
    items = q.order_by(Video.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        'items': [video_out(v).model_dump() for v in items],
        'total': total,
        'page': page,
        'hasMore': page * limit < total
    }


@app.post('/api/admin/videos/{video_id}/warn')
def warn_video(
    video_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """警告视频创作者"""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    reason = data.get('reason', '管理员警告')
    
    create_notification(
        db,
        recipient_id=video.uploader_id,
        sender_id=None,
        notif_type=4,
        target_type=0,
        target_id=video_id,
        content=f'您的视频 "{video.title}" 收到管理员警告：{reason}',
        auto_commit=True
    )
    
    return {'code': 0, 'message': '警告已发送'}


@app.post('/api/admin/videos/{video_id}/unapprove')
def unapprove_video(
    video_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """视频审核不通过（设为待审核状态）"""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail='视频不存在')
    
    reason = data.get('reason', '管理员将视频设为待审核状态')
    
    video.audit_status = 0
    video.reject_reason = reason
    db.commit()
    
    create_notification(
        db,
        recipient_id=video.uploader_id,
        sender_id=None,
        notif_type=4,
        target_type=0,
        target_id=video_id,
        content=f'您的视频 "{video.title}" 已被设为待审核，理由：{reason}',
        auto_commit=True
    )
    
    return {'code': 0, 'message': '已设为待审核'}


# ======================================================================
# 直播管理（管理员）
# ======================================================================

@app.get('/api/admin/live-rooms')
def admin_live_rooms(
    page: int = 1,
    limit: int = 20,
    keyword: Optional[str] = None,
    status: Optional[int] = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取所有直播间列表"""
    q = db.query(LiveRoom)
    
    if keyword:
        q = q.filter(LiveRoom.title.ilike(f'%{keyword}%'))
    if status is not None:
        q = q.filter(LiveRoom.status == status)
    
    total = q.count()
    items = q.order_by(LiveRoom.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    
    return {
        'items': [live_out(r).model_dump() for r in items],
        'total': total,
        'page': page,
        'hasMore': page * limit < total
    }


@app.post('/api/admin/live-rooms/{room_id}/warn')
def warn_live_room(
    room_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """警告主播"""
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail='直播间不存在')
    
    reason = data.get('reason', '管理员警告')
    
    create_notification(
        db,
        recipient_id=room.anchor_id,
        sender_id=None,
        notif_type=4,
        target_type=2,
        target_id=room_id,
        content=f'您的直播间 "{room.title}" 收到管理员警告：{reason}',
        auto_commit=True
    )
    
    return {'code': 0, 'message': '警告已发送'}


@app.post('/api/admin/live-rooms/{room_id}/close')
def close_live_room(
    room_id: UUID,
    data: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """关闭直播间"""
    room = db.get(LiveRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail='直播间不存在')
    
    reason = data.get('reason', '管理员关闭')
    
    room.status = 2
    room.end_time = datetime.now(timezone.utc)
    db.commit()
    
    create_notification(
        db,
        recipient_id=room.anchor_id,
        sender_id=None,
        notif_type=4,
        target_type=2,
        target_id=room_id,
        content=f'您的直播间 "{room.title}" 已被管理员关闭，理由：{reason}',
        auto_commit=True
    )
    
    return {'code': 0, 'message': '直播间已关闭'}

# ======================================================================
# 清理残留上传文件
# ======================================================================

@app.post('/api/admin/cleanup-uploads')
def cleanup_uploads(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """清理数据库中没有记录的视频文件"""
    import os
    
    # 获取数据库中所有视频的 URL
    db_videos = db.query(Video.video_url).filter(Video.video_url.like('/uploads/videos/%')).all()
    db_urls = set([v[0] for v in db_videos])
    
    # 扫描 uploads 目录
    video_dir = Path("/app/public/uploads/videos")
    deleted = []
    
    if video_dir.exists():
        for file in video_dir.iterdir():
            if file.is_file():
                # 构建对应的 URL
                file_url = f"/uploads/videos/{file.name}"
                if file_url not in db_urls:
                    file.unlink()
                    deleted.append(file.name)
    
    return {
        'code': 0,
        'message': f'已清理 {len(deleted)} 个残留文件',
        'deleted': deleted
    }

def cleanup_orphan_uploads(db: Session):
    """清理数据库中没有记录的上传文件"""
    import os
    from pathlib import Path
    
    # 获取数据库中所有视频的 URL
    db_videos = db.query(Video.video_url).filter(Video.video_url.like('/uploads/videos/%')).all()
    db_urls = set([v[0] for v in db_videos])
    
    # 扫描 uploads 目录
    video_dir = Path("/app/public/uploads/videos")
    deleted_count = 0
    
    if video_dir.exists():
        for file in video_dir.iterdir():
            if file.is_file():
                file_url = f"/uploads/videos/{file.name}"
                if file_url not in db_urls:
                    try:
                        file.unlink()
                        deleted_count += 1
                    except Exception as e:
                        print(f"删除文件失败 {file.name}: {e}")
    
    if deleted_count > 0:
        print(f"已清理 {deleted_count} 个残留上传文件")

# ======================================================================
# 删除评论（权限：评论作者、视频作者、管理员）
# ======================================================================

@app.delete('/api/comments/{comment_id}')
def delete_comment(
    comment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除评论（评论作者、视频作者、管理员可删除）"""
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail='评论不存在')
    
    # 获取视频信息
    video = db.get(Video, comment.video_id)
    
    # 权限检查
    is_author = str(comment.user_id) == str(user.id)
    is_video_owner = video and str(video.uploader_id) == str(user.id)
    is_admin = user.user_type == 2
    
    if not (is_author or is_video_owner or is_admin):
        raise HTTPException(status_code=403, detail='无权删除此评论')
    
    # 删除评论的回复
    db.query(Comment).filter(Comment.parent_id == comment_id).delete()
    
    # 删除评论
    db.delete(comment)
    
    # 更新视频的评论数
    if video:
        video.comment_count = max((video.comment_count or 0) - 1, 0)
    
    db.commit()
    
    return {'code': 0, 'message': '删除成功'}

# ======================================================================
# 用户偏好分类获取
# ======================================================================

def get_user_preference_categories(user_id: str, db: Session, limit: int = 3):
    """获取用户偏好的分类（按点赞次数排序）"""
    from sqlalchemy import func
    
    result = db.query(
        Video.category_id
    ).join(
        VideoLike, VideoLike.video_id == Video.id
    ).filter(
        VideoLike.user_id == user_id,
        Video.category_id != None
    ).group_by(Video.category_id).order_by(
        func.count(VideoLike.id).desc()
    ).limit(limit).all()
    
    return [row[0] for row in result if row[0]]

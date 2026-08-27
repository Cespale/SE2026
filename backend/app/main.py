import os, secrets, json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, desc
from sqlalchemy.orm import Session
from pathlib import Path
import random
import cv2
from urllib.parse import quote
import hashlib
import re


from .database import Base, engine, get_db, SessionLocal
from .models import Category, Comment, Danmaku, LiveRoom, User, Video
from .schemas import *
from .security import create_token, get_current_user, hash_password, require_admin, require_creator, verify_password, parse_token
from sqlalchemy import func
app = FastAPI(title='StreamHub API', description='在线视频与直播网站 Python 后端', version='1.0.0')
origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173,http://localhost:8080').split(',')
app.add_middleware(CORSMiddleware, allow_origins=origins + ['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

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
    return UserOut(id=str(u.id), account=u.account, nickname=u.nickname, avatar=u.avatar, bio=u.bio, userType=u.user_type, status=u.status)

def video_out(v: Video) -> VideoOut:
    return VideoOut(
        id=str(v.id), title=v.title, description=v.description or '', tags=v.tags or [],
        coverUrl=v.cover_url or '', videoUrl=v.video_url or '', duration=v.duration or 0,
        categoryId=str(v.category_id or ''), categoryName=v.category.name if v.category else '',
        viewCount=v.view_count or 0, likeCount=v.like_count or 0, commentCount=v.comment_count or 0,
        favoriteCount=v.favorite_count or 0, uploaderId=str(v.uploader_id),
        uploaderName=v.uploader.nickname if v.uploader else '未知用户',
        uploaderAvatar=v.uploader.avatar if v.uploader else '',
        uploadTime=v.created_at.isoformat() if v.created_at else '', auditStatus=v.audit_status or 0
    )

def comment_out(c: Comment) -> CommentOut:
    return CommentOut(
        id=str(c.id), content=c.content, userId=str(c.user_id), username=c.user.nickname if c.user else '匿名用户',
        userAvatar=c.user.avatar if c.user else '', videoId=str(c.video_id), parentId=str(c.parent_id) if c.parent_id else '0',
        likeCount=c.like_count or 0, isTop=bool(c.is_top), createTime=c.created_at.isoformat() if c.created_at else ''
    )

def danmaku_out(d: Danmaku) -> DanmakuOut:
    return DanmakuOut(
        id=str(d.id), content=d.content, color=d.color, position=d.position, userId=str(d.user_id),
        username=d.user.nickname if d.user else '匿名用户', videoTime=d.video_time or 0,
        sendTime=d.created_at.isoformat() if d.created_at else ''
    )

def live_out(r: LiveRoom) -> LiveRoomOut:
    return LiveRoomOut(
        id=str(r.id), title=r.title, categoryId=str(r.category_id), categoryName=r.category.name if r.category else '',
        cover=r.cover or 'https://images.unsplash.com/photo-1542751371-adc38448a05e?w=640&h=360&fit=crop',
        streamKey=r.stream_key, pushUrl=r.push_url, pullUrl=r.pull_url,
        anchorId=str(r.anchor_id), anchorName=r.anchor.nickname if r.anchor else '主播',
        anchorAvatar=r.anchor.avatar if r.anchor else '', onlineCount=r.online_count or 0,
        startTime=r.start_time.isoformat() if r.start_time else '', endTime=r.end_time.isoformat() if r.end_time else '', status=r.status or 0
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
            # 如果用户已经存在，就同步一下昵称、头像、身份，避免旧数据不一致
            exists.nickname = item["nickname"]
            exists.avatar = item["avatar"]
            exists.bio = item["bio"]
            exists.user_type = item["user_type"]
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

    sample_rooms = [
        {
            "title": "学习区直播：软件工程项目答疑",
            "category_id": 10,
            "cover": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=900&auto=format&fit=crop",
            "stream_key": "stream_demo_001",
            "push_url": "rtmp://localhost/live/stream_demo_001",
            "pull_url": "http://localhost:8080/live/stream_demo_001.flv",
            "online_count": 128,
        },
        {
            "title": "生活区直播：今晚一起剪视频",
            "category_id": 10,
            "cover": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=900&auto=format&fit=crop",
            "stream_key": "stream_demo_002",
            "push_url": "rtmp://localhost/live/stream_demo_002",
            "pull_url": "http://localhost:8080/live/stream_demo_002.flv",
            "online_count": 86,
        },
    ]

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

    # 隐藏所有不是 public/demo-videos 里的视频，避免首页加载外网慢视频
    db.query(Video).filter(
        ~Video.video_url.like('/demo-videos/%')
    ).update(
        {
            Video.status: 1
        },
        synchronize_session=False
    )

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


@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
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
    return {'token': create_token(user), 'user': user_out(user)}

@app.post('/api/auth/register')
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.account == data.account).first():
        raise HTTPException(status_code=400, detail='账号已存在')
    user = User(account=data.account, password_hash=hash_password(data.password), nickname=data.nickname, avatar=f'https://api.dicebear.com/7.x/avataaars/svg?seed={data.account}', user_type=0)
    db.add(user); db.commit(); db.refresh(user)
    return {'token': create_token(user), 'user': user_out(user)}

@app.patch('/api/auth/me')
def update_me(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if data.nickname is not None: user.nickname = data.nickname
    if data.bio is not None: user.bio = data.bio
    if data.avatar is not None: user.avatar = data.avatar
    db.commit(); db.refresh(user)
    return user_out(user)

@app.get('/api/categories')
def list_categories(db: Session = Depends(get_db)):
    rows = db.query(Category).order_by(Category.type, Category.sort_order).all()
    return [{'id': '0', 'name': '推荐', 'type': 0}] + [CategoryOut(id=str(c.id), name=c.name, type=c.type).dict() for c in rows]

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
        Video.audit_status == 1,
        Video.video_url.like('/demo-videos/%')
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
        'items': [video_out(v).dict() for v in items],
        'hasMore': page * page_size < total
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
        'items': [video_out(x).dict() for x in items]
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
    return {'items': [video_out(v).dict() for v in rows]}

@app.get('/api/admin/videos/pending')
def pending_videos(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Video).filter(Video.audit_status == 0).order_by(desc(Video.created_at)).all()
    return {'items': [video_out(v).dict() for v in rows]}

@app.patch('/api/admin/videos/{video_id}/audit')
def audit_video(video_id: UUID, data: AuditIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    v.audit_status = data.auditStatus
    db.commit(); db.refresh(v)
    return video_out(v)

@app.post('/api/videos/{video_id}/like')
def like_video(video_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    v.like_count += 1; db.commit(); db.refresh(v)
    return video_out(v)

@app.post('/api/videos/{video_id}/favorite')
def favorite_video(video_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    v.favorite_count += 1; db.commit(); db.refresh(v)
    return video_out(v)

@app.get('/api/videos/{video_id}/comments')
def get_comments(video_id: UUID, db: Session = Depends(get_db)):
    rows = db.query(Comment).filter(Comment.video_id == video_id).order_by(desc(Comment.created_at)).all()
    return [comment_out(c).dict() for c in rows]

@app.post('/api/videos/{video_id}/comments')
def add_comment(video_id: UUID, data: CommentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    v = db.get(Video, video_id)
    if not v: raise HTTPException(status_code=404, detail='视频不存在')
    parent = None if data.parentId == '0' else data.parentId
    c = Comment(content=data.content, user_id=user.id, video_id=video_id, parent_id=parent)
    v.comment_count += 1
    db.add(c); db.commit(); db.refresh(c)
    return comment_out(c)

@app.get('/api/videos/{video_id}/danmaku')
def get_danmaku(video_id: UUID, db: Session = Depends(get_db)):
    rows = db.query(Danmaku).filter(Danmaku.target_id == video_id, Danmaku.target_type == 0).order_by(Danmaku.video_time).all()
    return [danmaku_out(d).dict() for d in rows]

@app.post('/api/videos/{video_id}/danmaku')
def add_danmaku(video_id: UUID, data: DanmakuCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = Danmaku(content=data.content, color=data.color, position=data.position, video_time=data.videoTime, target_id=video_id, target_type=0, user_id=user.id)
    db.add(d); db.commit(); db.refresh(d)
    return danmaku_out(d)

@app.get('/api/live/rooms')
def list_rooms(category_id: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(LiveRoom).filter(LiveRoom.status == 1)
    if category_id: q = q.filter(LiveRoom.category_id == int(category_id))
    return {'items': [live_out(r).dict() for r in q.order_by(desc(LiveRoom.start_time)).all()]}

@app.get('/api/live/rooms/{room_id}')
def room_detail(room_id: UUID, db: Session = Depends(get_db)):
    r = db.get(LiveRoom, room_id)
    if not r: raise HTTPException(status_code=404, detail='直播间不存在')
    return live_out(r)

@app.post('/api/live/rooms')
def create_room(data: LiveRoomCreate, user: User = Depends(require_creator), db: Session = Depends(get_db)):
    key = 'stream_' + secrets.token_hex(8)

    category_id = int(data.categoryId or 10)

    exists_category = db.query(Category).filter(Category.id == category_id).first()
    if not exists_category:
        category_id = 10

        live_category = db.query(Category).filter(Category.id == 10).first()
        if not live_category:
            db.add(Category(id=10, name="直播", type=1, sort_order=10))
            db.commit()

    r = LiveRoom(
        title=data.title or "新的直播间",
        category_id=category_id,
        cover=data.cover or "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?w=900&auto=format&fit=crop",
        stream_key=key,
        push_url=f'rtmp://localhost/live/{key}',
        pull_url=f'http://localhost:8080/live/{key}.flv',
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

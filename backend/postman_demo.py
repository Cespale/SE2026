from fastapi import FastAPI

app = FastAPI(title="StreamHub Postman Demo API")


@app.get("/")
def root():
    return {
        "message": "StreamHub backend is running",
        "project": "StreamHub 在线视频与直播平台"
    }


@app.get("/api/videos")
def get_videos():
    return {
        "code": 200,
        "message": "success",
        "data": [
            {
                "id": 1,
                "title": "StreamHub 演示视频 1",
                "author": "creator",
                "views": 1024,
                "category": "推荐",
                "url": "/demo-videos/video1.mp4"
            },
            {
                "id": 2,
                "title": "在线视频平台功能演示",
                "author": "admin",
                "views": 2048,
                "category": "科技",
                "url": "/demo-videos/video2.mp4"
            }
        ]
    }


@app.post("/api/auth/login")
def login(data: dict):
    username = data.get("username")
    password = data.get("password")

    if username == "user" and password == "user123":
        return {
            "code": 200,
            "message": "login success",
            "token": "streamhub-demo-token",
            "user": {
                "username": "user",
                "user_type": 0
            }
        }

    return {
        "code": 401,
        "message": "用户名或密码错误"
    }
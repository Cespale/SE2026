import io
from pathlib import Path
from types import SimpleNamespace

from app import main


def login_headers(client, account, password):
    response = client.post(
        "/api/auth/login",
        json={"account": account, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


class ObjectResponse:
    def __init__(self, content):
        self.content = content
        self.closed = False
        self.released = False

    def stream(self, chunk_size):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start : start + chunk_size]

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.content_types = {}

    def upload_stream(self, stream, object_name, length, content_type):
        self.objects[object_name] = stream.read(length)
        self.content_types[object_name] = content_type
        return object_name

    def upload_path(self, path, object_name, content_type):
        self.objects[object_name] = Path(path).read_bytes()
        self.content_types[object_name] = content_type
        return object_name

    def stat_object(self, object_name):
        content = self.objects[object_name]
        return SimpleNamespace(
            size=len(content),
            content_type=self.content_types.get(object_name, "application/octet-stream"),
        )

    def get_object(self, object_name, offset=0, length=0):
        content = self.objects[object_name][offset:]
        if length:
            content = content[:length]
        return ObjectResponse(content)


def test_avatar_upload_writes_to_object_storage(client, monkeypatch, tmp_path):
    storage = FakeStorage()
    monkeypatch.setattr(main, "media_storage", storage, raising=False)
    monkeypatch.setattr(main, "AVATAR_UPLOAD_DIR", tmp_path / "avatars")
    headers = login_headers(client, "user", "user123")

    response = client.post(
        "/api/auth/upload-avatar",
        headers=headers,
        files={"file": ("avatar.jpg", b"avatar-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    avatar_url = response.json()["data"]["avatar"]
    assert avatar_url.startswith("/avatars/")
    assert avatar_url.endswith(".jpg")
    assert len(storage.objects) == 1
    assert storage.objects[avatar_url.lstrip("/")] == b"avatar-bytes"
    assert storage.content_types[avatar_url.lstrip("/")] == "image/jpeg"
    assert not list(tmp_path.rglob("*"))


def test_cover_upload_writes_to_object_storage(client, monkeypatch, tmp_path):
    storage = FakeStorage()
    monkeypatch.setattr(main, "media_storage", storage, raising=False)
    monkeypatch.setattr(main, "VIDEO_COVER_UPLOAD_DIR", tmp_path / "covers")
    headers = login_headers(client, "creator", "creator123")

    response = client.post(
        "/api/videos/upload-cover",
        headers=headers,
        files={"file": ("cover.png", b"cover-bytes", "image/png")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    cover_url = response.json()["data"]["coverUrl"]
    assert cover_url.startswith("/uploads/covers/")
    assert cover_url.endswith(".png")
    assert len(storage.objects) == 1
    assert storage.objects[cover_url.lstrip("/")] == b"cover-bytes"
    assert storage.content_types[cover_url.lstrip("/")] == "image/png"
    assert not list(tmp_path.rglob("*"))


def test_video_upload_writes_to_object_storage(client, monkeypatch):
    storage = FakeStorage()
    monkeypatch.setattr(main, "media_storage", storage, raising=False)
    headers = login_headers(client, "creator", "creator123")

    response = client.post(
        "/api/videos/upload-file",
        headers=headers,
        files={"file": ("sample.mp4", b"not-a-real-video", "video/mp4")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    video_url = response.json()["data"]["videoUrl"]
    assert video_url.startswith("/uploads/videos/")
    assert video_url.endswith(".mp4")
    assert len(storage.objects) == 1
    assert storage.objects[video_url.lstrip("/")] == b"not-a-real-video"
    assert storage.content_types[video_url.lstrip("/")] == "video/mp4"


def test_media_route_supports_video_byte_ranges(client, monkeypatch):
    storage = FakeStorage()
    storage.objects["uploads/videos/sample.mp4"] = b"0123456789"
    storage.content_types["uploads/videos/sample.mp4"] = "video/mp4"
    monkeypatch.setattr(main, "media_storage", storage, raising=False)

    response = client.get(
        "/uploads/videos/sample.mp4",
        headers={"Range": "bytes=2-5"},
    )

    assert response.status_code == 206
    assert response.content == b"2345"
    assert len(response.content) == 4
    assert response.headers["content-length"] == "4"
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-type"].startswith("video/mp4")

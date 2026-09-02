from app.database import SessionLocal
from app.models import IntegrationOutbox, Video
from uuid import UUID


def test_admin_audit_and_warning_create_outbox_atomically(
    client, auth_headers, ids
):
    pending = client.get(
        "/api/admin/videos/pending", headers=auth_headers("admin")
    )
    assert pending.status_code == 200
    audited = client.patch(
        f"/api/admin/videos/{ids['pending']}/audit",
        headers=auth_headers("admin"),
        json={"auditStatus": 1},
    )
    assert audited.status_code == 200
    warned = client.post(
        f"/api/admin/videos/{ids['video']}/warn",
        headers=auth_headers("admin"),
        json={"reason": "check"},
    )
    assert warned.status_code == 200
    assert client.post(
        f"/api/admin/videos/{ids['video']}/unapprove",
        headers=auth_headers("admin"),
        json={"reason": "review again"},
    ).status_code == 200
    with SessionLocal() as db:
        assert db.query(IntegrationOutbox).count() == 3


def test_creator_feed_week_status_update_and_delete(
    client, auth_headers, ids
):
    creator_headers = auth_headers("creator")
    assert client.get("/api/feed", headers=auth_headers("viewer")).status_code == 200
    week = client.get("/api/creator/week-stats", headers=creator_headers)
    assert week.status_code == 200
    assert len(week.json()) == 7
    assert client.get(
        "/api/creator/videos/1", headers=creator_headers
    ).status_code == 200
    updated = client.put(
        f"/api/creator/videos/{ids['video']}",
        headers=creator_headers,
        json={"title": "Updated"},
    )
    assert updated.status_code == 200
    deleted = client.delete(
        f"/api/creator/videos/{ids['video']}", headers=creator_headers
    )
    assert deleted.status_code == 200
    with SessionLocal() as db:
        assert db.get(Video, UUID(ids["video"])) is None
        assert db.query(IntegrationOutbox).filter(
            IntegrationOutbox.event_type == "video.deleted"
        ).count() == 1


def test_admin_video_list(client, auth_headers):
    response = client.get("/api/admin/videos", headers=auth_headers("admin"))
    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_upload_routes_use_content_storage(
    client, auth_headers, monkeypatch
):
    class Storage:
        def __init__(self):
            self.paths = []
            self.streams = []

        def upload_path(self, path, object_name, content_type):
            self.paths.append(object_name)

        def upload_stream(self, stream, object_name, length, content_type):
            self.streams.append(object_name)

    storage = Storage()
    monkeypatch.setattr("app.main.get_media_storage", lambda: storage)
    cover = client.post(
        "/api/videos/upload-cover",
        headers=auth_headers("creator"),
        files={"file": ("cover.png", b"image", "image/png")},
    )
    assert cover.status_code == 200
    video = client.post(
        "/api/videos/upload-file",
        headers=auth_headers("creator"),
        files={"file": ("video.mp4", b"not-a-real-video", "video/mp4")},
    )
    assert video.status_code == 200
    assert storage.paths


def test_media_range_and_cleanup_only_content_prefix(
    client, auth_headers, monkeypatch, ids
):
    class ObjectResponse:
        def stream(self, _):
            yield b"2345"

        def close(self):
            pass

        def release_conn(self):
            pass

    class Metadata:
        size = 10
        content_type = "video/mp4"

    class Storage:
        def __init__(self):
            self.removed = []

        def stat_object(self, object_name):
            assert object_name == "uploads/videos/test.mp4"
            return Metadata()

        def get_object(self, object_name, offset=0, length=0):
            assert (offset, length) == (2, 4)
            return ObjectResponse()

        def iter_names(self, prefix):
            assert prefix == "uploads/videos/"
            return ["uploads/videos/used.mp4", "uploads/videos/orphan.mp4"]

        def remove_object(self, object_name):
            self.removed.append(object_name)

    storage = Storage()
    monkeypatch.setattr("app.main.get_media_storage", lambda: storage)
    ranged = client.get(
        "/uploads/videos/test.mp4", headers={"Range": "bytes=2-5"}
    )
    assert ranged.status_code == 206
    assert ranged.content == b"2345"

    with SessionLocal() as db:
        video = db.get(Video, UUID(ids["video"]))
        video.video_url = "/uploads/videos/used.mp4"
        db.commit()
    cleaned = client.post(
        "/api/admin/cleanup-uploads", headers=auth_headers("admin")
    )
    assert cleaned.status_code == 200
    assert cleaned.json()["deleted"] == ["orphan.mp4"]
    assert storage.removed == ["uploads/videos/orphan.mp4"]

import io
from pathlib import Path

import pytest

from app.object_storage import (
    MinioObjectStorage,
    migrate_legacy_media,
    object_name_from_url,
    parse_range_header,
)


class FakeMinioClient:
    def __init__(self):
        self.buckets = set()
        self.uploads = []

    def bucket_exists(self, bucket_name):
        return bucket_name in self.buckets

    def make_bucket(self, bucket_name):
        self.buckets.add(bucket_name)

    def put_object(self, bucket_name, object_name, data, length, content_type):
        self.uploads.append(
            {
                "bucket": bucket_name,
                "object_name": object_name,
                "content": data.read(length),
                "length": length,
                "content_type": content_type,
            }
        )


class RecordingStorage:
    def __init__(self):
        self.objects = set()
        self.uploaded_paths = []

    def object_exists(self, object_name):
        return object_name in self.objects

    def upload_path(self, path, object_name, content_type):
        self.objects.add(object_name)
        self.uploaded_paths.append((Path(path), object_name, content_type))


def test_upload_stream_creates_bucket_and_preserves_content_metadata():
    client = FakeMinioClient()
    storage = MinioObjectStorage(client=client, bucket_name="streamhub-media")

    object_name = storage.upload_stream(
        stream=io.BytesIO(b"video-data"),
        object_name="uploads/videos/example.mp4",
        length=10,
        content_type="video/mp4",
    )

    assert object_name == "uploads/videos/example.mp4"
    assert isinstance(object_name, str)
    assert client.buckets == {"streamhub-media"}
    assert len(client.uploads) == 1
    assert client.uploads[0]["bucket"] == "streamhub-media"
    assert client.uploads[0]["object_name"] == object_name
    assert client.uploads[0]["content"] == b"video-data"
    assert client.uploads[0]["length"] == 10
    assert client.uploads[0]["content_type"] == "video/mp4"
    assert client.uploads == [
        {
            "bucket": "streamhub-media",
            "object_name": "uploads/videos/example.mp4",
            "content": b"video-data",
            "length": 10,
            "content_type": "video/mp4",
        }
    ]


def test_from_env_requires_minio_secret(monkeypatch):
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    monkeypatch.delenv("MINIO_ROOT_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="MINIO_SECRET_KEY") as error:
        MinioObjectStorage.from_env()

    assert "MINIO_SECRET_KEY" in str(error.value)


def test_legacy_migration_copies_files_without_deleting_originals(tmp_path):
    legacy_root = tmp_path / "public"
    avatar = legacy_root / "avatars" / "user.jpg"
    cover = legacy_root / "uploads" / "covers" / "cover.png"
    video = legacy_root / "uploads" / "videos" / "video.mp4"

    for path, content in (
        (avatar, b"avatar"),
        (cover, b"cover"),
        (video, b"video"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    storage = RecordingStorage()
    first_result = migrate_legacy_media(storage, legacy_root)
    second_result = migrate_legacy_media(storage, legacy_root)

    assert first_result == [
        "avatars/user.jpg",
        "uploads/covers/cover.png",
        "uploads/videos/video.mp4",
    ]
    assert second_result == []
    assert len(first_result) == 3
    assert len(storage.uploaded_paths) == 3
    assert avatar.exists()
    assert cover.exists()
    assert video.exists()
    assert avatar.read_bytes() == b"avatar"
    assert cover.read_bytes() == b"cover"
    assert video.read_bytes() == b"video"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("/avatars/user.jpg", "avatars/user.jpg"),
        ("/uploads/covers/cover.png", "uploads/covers/cover.png"),
        ("/uploads/videos/video.mp4", "uploads/videos/video.mp4"),
    ],
)
def test_object_name_from_url_accepts_only_media_paths(url, expected):
    assert object_name_from_url(url) == expected
    assert expected.startswith(("avatars/", "uploads/"))
    assert ".." not in expected


@pytest.mark.parametrize(
    "url",
    [
        "/demo-videos/video.mp4",
        "/uploads/../secret.txt",
        "https://example.com/video.mp4",
    ],
)
def test_object_name_from_url_rejects_non_media_or_traversal_paths(url):
    with pytest.raises(ValueError) as error:
        object_name_from_url(url)

    assert isinstance(error.value, ValueError)


@pytest.mark.parametrize(
    ("header", "size", "expected"),
    [
        ("bytes=10-19", 100, (10, 19)),
        ("bytes=90-", 100, (90, 99)),
        ("bytes=-10", 100, (90, 99)),
    ],
)
def test_parse_range_header_supports_video_seeking(header, size, expected):
    parsed = parse_range_header(header, size)
    assert parsed == expected
    assert 0 <= parsed[0] < size
    assert parsed[0] <= parsed[1]
    assert parsed[1] < size


@pytest.mark.parametrize(
    "header",
    ["items=0-1", "bytes=100-101", "bytes=30-20", "bytes=0-1,5-6"],
)
def test_parse_range_header_rejects_invalid_or_multiple_ranges(header):
    with pytest.raises(ValueError) as error:
        parse_range_header(header, 100)

    assert isinstance(error.value, ValueError)

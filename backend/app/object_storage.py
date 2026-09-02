import mimetypes
import os
import re
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import BinaryIO, Protocol
from urllib.parse import unquote, urlsplit

from minio import Minio
from minio.error import S3Error


MEDIA_PREFIXES = ("avatars", "uploads")
_RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")


class StorageWriter(Protocol):
    def object_exists(self, object_name: str) -> bool: ...

    def upload_path(
        self,
        path: Path,
        object_name: str,
        content_type: str,
    ) -> str: ...


def object_name_from_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        raise ValueError("media URL must be relative")

    path = unquote(parsed.path).lstrip("/")
    parts = PurePosixPath(path).parts
    if not parts or parts[0] not in MEDIA_PREFIXES or ".." in parts:
        raise ValueError("unsupported media URL")

    return PurePosixPath(*parts).as_posix()


def parse_range_header(header: str, object_size: int) -> tuple[int, int]:
    if object_size <= 0 or "," in header:
        raise ValueError("invalid byte range")

    match = _RANGE_PATTERN.fullmatch(header.strip())
    if not match:
        raise ValueError("invalid byte range")

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        raise ValueError("invalid byte range")

    if not start_text:
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("invalid byte range")
        start = max(object_size - suffix_length, 0)
        return start, object_size - 1

    start = int(start_text)
    end = int(end_text) if end_text else object_size - 1
    if start >= object_size or end < start:
        raise ValueError("invalid byte range")

    return start, min(end, object_size - 1)


class MinioObjectStorage:
    def __init__(self, client: Minio, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        self._bucket_ready = False
        self._bucket_lock = Lock()

    @classmethod
    def from_env(cls) -> "MinioObjectStorage":
        endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
        access_key = os.getenv(
            "MINIO_ACCESS_KEY",
            os.getenv("MINIO_ROOT_USER", "streamhub"),
        )
        secret_key = os.getenv(
            "MINIO_SECRET_KEY",
            os.getenv("MINIO_ROOT_PASSWORD", ""),
        )
        if not secret_key:
            raise RuntimeError(
                "MINIO_SECRET_KEY or MINIO_ROOT_PASSWORD must be configured"
            )
        secure = os.getenv("MINIO_SECURE", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        bucket_name = os.getenv("MINIO_BUCKET", "streamhub-media")
        return cls(
            client=Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            ),
            bucket_name=bucket_name,
        )

    def ensure_bucket(self) -> None:
        if self._bucket_ready:
            return

        with self._bucket_lock:
            if self._bucket_ready:
                return
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
            self._bucket_ready = True

    def upload_stream(
        self,
        stream: BinaryIO,
        object_name: str,
        length: int,
        content_type: str,
    ) -> str:
        self.ensure_bucket()
        self.client.put_object(
            self.bucket_name,
            object_name,
            stream,
            length,
            content_type,
        )
        return object_name

    def upload_path(
        self,
        path: Path,
        object_name: str,
        content_type: str,
    ) -> str:
        self.ensure_bucket()
        self.client.fput_object(
            self.bucket_name,
            object_name,
            str(path),
            content_type=content_type,
        )
        return object_name

    def object_exists(self, object_name: str) -> bool:
        self.ensure_bucket()
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                return False
            raise

    def stat_object(self, object_name: str):
        self.ensure_bucket()
        return self.client.stat_object(self.bucket_name, object_name)

    def get_object(self, object_name: str, offset: int = 0, length: int = 0):
        self.ensure_bucket()
        kwargs = {"offset": offset}
        if length > 0:
            kwargs["length"] = length
        return self.client.get_object(
            self.bucket_name,
            object_name,
            **kwargs,
        )


def migrate_legacy_media(
    storage: StorageWriter,
    legacy_public_root: Path,
) -> list[str]:
    migrated: list[str] = []
    for prefix in MEDIA_PREFIXES:
        source_root = legacy_public_root / prefix
        if not source_root.exists():
            continue

        for path in sorted(source_root.rglob("*")):
            if not path.is_file():
                continue
            object_name = path.relative_to(legacy_public_root).as_posix()
            if storage.object_exists(object_name):
                continue
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            storage.upload_path(path, object_name, content_type)
            migrated.append(object_name)

    return migrated

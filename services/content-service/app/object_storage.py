import os
from pathlib import Path
from threading import Lock
from typing import BinaryIO

from minio import Minio


class ContentObjectStorage:
    def __init__(self, client: Minio, bucket_name: str):
        self.client = client
        self.bucket_name = bucket_name
        self._bucket_ready = False
        self._lock = Lock()

    @classmethod
    def from_env(cls):
        secret_key = os.getenv(
            "MINIO_SECRET_KEY", os.getenv("MINIO_ROOT_PASSWORD", "")
        )
        if not secret_key:
            raise RuntimeError("MINIO_SECRET_KEY is required")
        client = Minio(
            os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000"),
            access_key=os.getenv(
                "MINIO_ACCESS_KEY", os.getenv("MINIO_ROOT_USER", "streamhub")
            ),
            secret_key=secret_key,
            secure=os.getenv("MINIO_SECURE", "false").lower()
            in {"1", "true", "yes"},
        )
        return cls(client, os.getenv("MINIO_BUCKET", "streamhub-media"))

    def ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        with self._lock:
            if not self._bucket_ready:
                if not self.client.bucket_exists(self.bucket_name):
                    self.client.make_bucket(self.bucket_name)
                self._bucket_ready = True

    @staticmethod
    def validate_name(object_name: str) -> None:
        if not object_name.startswith(("uploads/videos/", "uploads/covers/")):
            raise ValueError("content service may only access video and cover objects")

    def upload_path(self, path: Path, object_name: str, content_type: str) -> None:
        self.validate_name(object_name)
        self.ensure_bucket()
        self.client.fput_object(
            self.bucket_name,
            object_name,
            str(path),
            content_type=content_type,
        )

    def upload_stream(
        self,
        stream: BinaryIO,
        object_name: str,
        length: int,
        content_type: str,
    ) -> None:
        self.validate_name(object_name)
        self.ensure_bucket()
        self.client.put_object(
            self.bucket_name,
            object_name,
            stream,
            length,
            content_type=content_type,
        )

    def stat_object(self, object_name: str):
        self.validate_name(object_name)
        self.ensure_bucket()
        return self.client.stat_object(self.bucket_name, object_name)

    def get_object(self, object_name: str, offset: int = 0, length: int = 0):
        self.validate_name(object_name)
        self.ensure_bucket()
        kwargs = {"offset": offset}
        if length > 0:
            kwargs["length"] = length
        return self.client.get_object(self.bucket_name, object_name, **kwargs)

    def iter_names(self, prefix: str) -> list[str]:
        self.validate_name(f"{prefix}placeholder")
        self.ensure_bucket()
        return [
            item.object_name
            for item in self.client.list_objects(
                self.bucket_name,
                prefix=prefix,
                recursive=True,
            )
        ]

    def remove_object(self, object_name: str) -> None:
        self.validate_name(object_name)
        self.ensure_bucket()
        self.client.remove_object(self.bucket_name, object_name)

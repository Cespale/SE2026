import os


SOCIAL_DATABASE_URL = os.getenv("SOCIAL_DATABASE_URL")
if not SOCIAL_DATABASE_URL:
    raise RuntimeError("SOCIAL_DATABASE_URL is required")

SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
CONTENT_SERVICE_URL = os.getenv("CONTENT_SERVICE_URL", "http://content-service:8000")
OUTBOX_WORKER_ENABLED = os.getenv("OUTBOX_WORKER_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}
SRS_PUBLIC_RTMP_BASE = os.getenv(
    "SRS_PUBLIC_RTMP_BASE", "rtmp://localhost:1935/live"
).rstrip("/")
SRS_PUBLIC_HTTP_BASE = os.getenv(
    "SRS_PUBLIC_HTTP_BASE", "http://localhost:8080/live"
).rstrip("/")

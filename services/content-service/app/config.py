import os


CONTENT_DATABASE_URL = os.getenv("CONTENT_DATABASE_URL")
if not CONTENT_DATABASE_URL:
    raise RuntimeError("CONTENT_DATABASE_URL is required")

SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8000")
SOCIAL_SERVICE_URL = os.getenv("SOCIAL_SERVICE_URL", "http://social-service:8000")
OUTBOX_WORKER_ENABLED = os.getenv("OUTBOX_WORKER_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}

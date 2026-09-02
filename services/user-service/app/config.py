import os


USER_DATABASE_URL = os.getenv("USER_DATABASE_URL")
if not USER_DATABASE_URL:
    raise RuntimeError("USER_DATABASE_URL is required")

SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")
CONTENT_SERVICE_URL = os.getenv("CONTENT_SERVICE_URL", "http://content-service:8000")

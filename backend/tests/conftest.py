import os

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg2://postgres:123456@127.0.0.1:5433/streamhub_test"
)
os.environ["SECRET_KEY"] = "streamhub-test-secret"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_test_database():
    database_url = str(engine.url)

    if not database_url.endswith("/streamhub_test"):
        raise RuntimeError(f"测试数据库错误：{database_url}")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
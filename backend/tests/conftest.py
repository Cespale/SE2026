import os

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg2://postgres:123456@127.0.0.1:5433/streamhub_test"
)
os.environ["SECRET_KEY"] = "streamhub-test-secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import Base, engine
from app.main import app


def reset_test_schema():
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


@pytest.fixture(autouse=True)
def reset_test_database():
    database_url = str(engine.url)

    if not database_url.endswith("/streamhub_test"):
        raise RuntimeError(f"测试数据库错误：{database_url}")

    reset_test_schema()
    Base.metadata.create_all(bind=engine)

    yield

    reset_test_schema()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

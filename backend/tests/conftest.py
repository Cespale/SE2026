import os

# 本地默认连测试库（streamhub_test），避免误删开发库；CI（GitHub Actions）会通过环境变量
# 注入 DATABASE_URL（库名为 streamhub），这里用 setdefault 而不是硬赋值，保证 CI 注入的连接串不被覆盖。
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:123456@127.0.0.1:5433/streamhub_test",
)
os.environ.setdefault("SECRET_KEY", "streamhub-test-secret")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def _is_safe_test_db(database_url: str) -> bool:
    # 本地测试库：streamhub_test；CI 临时库：streamhub。二者都允许 drop/create。
    return database_url.endswith("/streamhub_test") or database_url.endswith("/streamhub")


@pytest.fixture(autouse=True)
def reset_test_database():
    database_url = str(engine.url)

    if not _is_safe_test_db(database_url):
        raise RuntimeError(f"测试数据库错误：{database_url}")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

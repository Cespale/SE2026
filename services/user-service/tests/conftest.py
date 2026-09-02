import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT))

os.environ["USER_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "user-service-test-secret"
os.environ["SERVICE_VERSION"] = "test-version"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import create_token, hash_password  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        users = [
            User(
                account="admin",
                password_hash=hash_password("admin123"),
                nickname="管理员",
                user_type=2,
            ),
            User(
                account="alice",
                password_hash=hash_password("alice123"),
                nickname="Alice",
                user_type=0,
            ),
            User(
                account="creator",
                password_hash=hash_password("creator123"),
                nickname="Creator",
                user_type=1,
            ),
        ]
        db.add_all(users)
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def users():
    with SessionLocal() as db:
        rows = db.query(User).all()
        return {row.account: str(row.id) for row in rows}


@pytest.fixture
def auth_headers():
    def make(account: str) -> dict[str, str]:
        with SessionLocal() as db:
            user = db.query(User).filter(User.account == account).one()
            return {"Authorization": f"Bearer {create_token(user)}"}

    return make

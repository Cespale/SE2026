from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import USER_DATABASE_URL


if USER_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        USER_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        USER_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=180,
        connect_args={
            "connect_timeout": 5,
            "options": "-csearch_path=user_service",
        },
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

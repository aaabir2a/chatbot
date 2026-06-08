"""SQLAlchemy engine, session factory, declarative Base, and get_db dependency."""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    # Ensure the directory for a file-based SQLite DB exists.
    path = settings.database_url.replace("sqlite:///", "", 1)
    if path and path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

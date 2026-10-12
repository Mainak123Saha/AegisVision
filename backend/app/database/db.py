"""SQLAlchemy engine/session setup. The engine is created lazily so that importing
the app (or starting FastAPI) never requires a reachable database."""
from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import load_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    s = load_settings()
    # pool_pre_ping drops dead connections (e.g. after a PostgreSQL restart).
    return create_engine(s.database_url, echo=s.db_echo, pool_pre_ping=True, pool_size=5, max_overflow=5,
                         connect_args={"connect_timeout": 5})


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:
    return get_sessionmaker()()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_connection() -> bool:
    from sqlalchemy import text

    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

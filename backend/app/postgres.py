"""Optional PostgreSQL foundation. No implicit connection or schema changes."""
import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine():
    url = os.getenv("NEXIS_DATABASE_URL")
    if not url or not url.startswith(("postgresql+psycopg://",)):
        raise RuntimeError("NEXIS_DATABASE_URL must be a postgresql+psycopg URL")
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def session_scope():
    """Call as a context manager; caller owns commit/rollback."""
    return session_factory()()

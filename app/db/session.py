from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base


@lru_cache
def get_engine() -> Engine:
    engine_options = {"pool_pre_ping": True}
    if get_settings().database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}

    return create_engine(
        get_settings().database_url,
        **engine_options,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


def initialize_database() -> None:
    import app.db.models

    Base.metadata.create_all(bind=get_engine())


def close_database_connection() -> None:
    get_engine().dispose()

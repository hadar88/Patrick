from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base


@lru_cache
def get_engine() -> Engine:
    engine_options = {"pool_pre_ping": True}
    database_url = get_settings().get_database_url()
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        engine_options["connect_args"] = {"check_same_thread": False}

    engine = create_engine(
        database_url,
        **engine_options,
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


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

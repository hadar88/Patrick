from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import (
    check_database_connection,
    close_database_connection,
    initialize_database,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_database_connection()
    initialize_database()
    yield
    close_database_connection()

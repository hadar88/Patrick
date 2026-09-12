from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.endpoints import router as endpoints_router
from app.exceptions import (
    ApplicationError,
    application_error_handler,
    integrity_error_handler,
)


settings = get_settings()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.environment.lower() == "production",
    same_site="lax",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)
app.add_exception_handler(ApplicationError, application_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.include_router(endpoints_router)

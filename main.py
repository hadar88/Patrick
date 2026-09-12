from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from app.core.lifespan import lifespan
from app.core.config import get_settings
from app.endpoints import router as endpoints_router
from app.exceptions import (
	ApplicationError,
	application_error_handler,
	integrity_error_handler,
)


app = FastAPI(lifespan=lifespan)
app.add_middleware(
	CORSMiddleware,
	allow_origins=get_settings().cors_origins,
	allow_credentials=False,
	allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
	allow_headers=["Accept", "Authorization", "Content-Type"],
)
app.add_exception_handler(ApplicationError, application_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.include_router(endpoints_router)


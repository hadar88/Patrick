from fastapi import FastAPI

from app.core.lifespan import lifespan
from app.endpoints import router as endpoints_router
from app.exceptions import ApplicationError, application_error_handler


app = FastAPI(lifespan=lifespan)
app.add_exception_handler(ApplicationError, application_error_handler)
app.include_router(endpoints_router)


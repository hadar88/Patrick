from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class ApplicationError(Exception):
    status_code = 500
    detail = "Application error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail


class ResourceNotFoundError(ApplicationError):
    status_code = 404

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found")


class ResourceConflictError(ApplicationError):
    status_code = 409


async def application_error_handler(
    request: Request, error: ApplicationError
) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"detail": error.detail})


async def integrity_error_handler(
    request: Request, error: IntegrityError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"detail": "The requested change conflicts with existing data"},
    )

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import check_database_connection
from app.endpoints.review_tasks import router as review_tasks_router
from app.endpoints.task_reviewers import router as task_reviewers_router
from app.endpoints.users import router as users_router

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK, tags=["health"])
def health_check() -> dict[str, str]:
    try:
        check_database_connection()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from error
    return {"status": "healthy"}


router.include_router(review_tasks_router, prefix="/api")
router.include_router(task_reviewers_router, prefix="/api")
router.include_router(users_router, prefix="/api")
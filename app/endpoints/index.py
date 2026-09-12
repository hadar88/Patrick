from fastapi import APIRouter, status

from app.endpoints.review_tasks import router as review_tasks_router
from app.endpoints.task_reviewers import router as task_reviewers_router
from app.endpoints.users import router as users_router

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK, tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


router.include_router(review_tasks_router, prefix="/api")
router.include_router(task_reviewers_router, prefix="/api")
router.include_router(users_router, prefix="/api")
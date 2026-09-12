from fastapi import APIRouter, status

from app.endpoints.gitlab import router as gitlab_router
from app.endpoints.auth import router as auth_router
from app.endpoints.review_tasks import router as review_tasks_router
from app.endpoints.task_reviewers import router as task_reviewers_router
from app.endpoints.users import router as users_router

router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK, tags=["root"])
def root() -> dict[str, str]:
    return {"message": "Patrick API"}


@router.get("/health", status_code=status.HTTP_200_OK, tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


router.include_router(review_tasks_router, prefix="/api")
router.include_router(task_reviewers_router, prefix="/api")
router.include_router(users_router, prefix="/api")
router.include_router(gitlab_router, prefix="/api")
router.include_router(auth_router, prefix="/api")
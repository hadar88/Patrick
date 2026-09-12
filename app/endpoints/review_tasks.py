from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.endpoints.schemas import (
    ReviewTaskCreate,
    ReviewTaskResponse,
    ReviewTaskUpdate,
)
from app.queriers import ReviewTaskQuerier

router = APIRouter(prefix="/review-tasks", tags=["review-tasks"])


@router.get("", response_model=list[ReviewTaskResponse])
def list_review_tasks(
    author_user_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ReviewTaskResponse]:
    return ReviewTaskQuerier(db).list(author_user_id)


@router.post("", response_model=ReviewTaskResponse, status_code=status.HTTP_201_CREATED)
def create_review_task(
    payload: ReviewTaskCreate,
    db: Session = Depends(get_db),
) -> ReviewTaskResponse:
    return ReviewTaskQuerier(db).create(payload.model_dump())


@router.get("/by-mr", response_model=ReviewTaskResponse)
def get_review_task_by_mr(
    repo_gitlab_id: int,
    gitlab_mr_id: int,
    db: Session = Depends(get_db),
) -> ReviewTaskResponse:
    return ReviewTaskQuerier(db).get_by_mr(repo_gitlab_id, gitlab_mr_id)


@router.get("/{task_id}", response_model=ReviewTaskResponse)
def get_review_task(task_id: UUID, db: Session = Depends(get_db)) -> ReviewTaskResponse:
    return ReviewTaskQuerier(db).get(task_id)


@router.patch("/{task_id}", response_model=ReviewTaskResponse)
def update_review_task(
    task_id: UUID,
    payload: ReviewTaskUpdate,
    db: Session = Depends(get_db),
) -> ReviewTaskResponse:
    return ReviewTaskQuerier(db).update(
        task_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review_task(task_id: UUID, db: Session = Depends(get_db)) -> None:
    ReviewTaskQuerier(db).delete(task_id)
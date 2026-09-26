from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.task_reviewer import (
    TaskReviewerCreate,
    TaskReviewerResponse,
    TaskReviewerUpdate,
)
from app.queriers import TaskReviewerQuerier

router = APIRouter(prefix="/task-reviewers", tags=["task-reviewers"])


@router.get("", response_model=list[TaskReviewerResponse])
def list_task_reviewers(db: Session = Depends(get_db)) -> list[TaskReviewerResponse]:
    return TaskReviewerQuerier(db).list()


@router.get("/by-task/{task_id}", response_model=list[TaskReviewerResponse])
def list_reviewers_by_task(
    task_id: UUID,
    db: Session = Depends(get_db),
) -> list[TaskReviewerResponse]:
    return TaskReviewerQuerier(db).list_by_task(task_id)


@router.get("/by-user/{user_id}", response_model=list[TaskReviewerResponse])
def list_reviewers_by_user(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> list[TaskReviewerResponse]:
    return TaskReviewerQuerier(db).list_by_user(user_id)


@router.post("", response_model=TaskReviewerResponse, status_code=status.HTTP_201_CREATED)
def create_task_reviewer(
    payload: TaskReviewerCreate,
    db: Session = Depends(get_db),
) -> TaskReviewerResponse:
    return TaskReviewerQuerier(db).create(payload.model_dump())


@router.get("/status-counts/reviewer/{user_id}", response_model=dict[str, int])
def get_status_counts_as_reviewer(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return TaskReviewerQuerier(db).count_status_as_reviewer(user_id)


@router.get("/status-counts/assignee/{user_id}", response_model=dict[str, int])
def get_status_counts_as_assignee(
    user_id: UUID,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    return TaskReviewerQuerier(db).count_status_as_assignee(user_id)


@router.get("/{reviewer_entry_id}", response_model=TaskReviewerResponse)
def get_task_reviewer(
    reviewer_entry_id: UUID,
    db: Session = Depends(get_db),
) -> TaskReviewerResponse:
    return TaskReviewerQuerier(db).get(reviewer_entry_id)


@router.patch("/{reviewer_entry_id}", response_model=TaskReviewerResponse)
def update_task_reviewer(
    reviewer_entry_id: UUID,
    payload: TaskReviewerUpdate,
    db: Session = Depends(get_db),
) -> TaskReviewerResponse:
    return TaskReviewerQuerier(db).update(
        reviewer_entry_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{reviewer_entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_reviewer(
    reviewer_entry_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    TaskReviewerQuerier(db).delete(reviewer_entry_id)
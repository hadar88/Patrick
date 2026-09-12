from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.models import GitLabConnection, User
from app.db.session import get_db
from app.endpoints.auth import get_current_user
from app.integrations.gitlab import GitLabClient
from app.schemas.review_task import (
    ReviewTaskCreate,
    ReviewTaskFromGitLabCreate,
    ReviewTaskResponse,
    ReviewTaskUpdate,
)
from app.queriers import ReviewTaskQuerier

router = APIRouter(prefix="/review-tasks", tags=["review-tasks"])


@router.get("", response_model=list[ReviewTaskResponse])
def list_review_tasks(
    author_user_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReviewTaskResponse]:
    if author_user_id is not None and author_user_id != current_user.user_id:
        return []
    return ReviewTaskQuerier(db).list(current_user.user_id)


@router.get("/assigned", response_model=list[ReviewTaskResponse])
def list_assigned_review_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReviewTaskResponse]:
    return ReviewTaskQuerier(db).list_assigned(current_user.user_id)


@router.post("", response_model=ReviewTaskResponse, status_code=status.HTTP_201_CREATED)
def create_review_task(
    payload: ReviewTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    if payload.author_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Cannot create a task for another user")
    return ReviewTaskQuerier(db).create(payload.model_dump())


@router.post(
    "/from-gitlab",
    response_model=ReviewTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review_task_from_gitlab(
    payload: ReviewTaskFromGitLabCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    connection = db.query(GitLabConnection).filter(
        GitLabConnection.user_id == current_user.user_id
    ).one_or_none()
    if connection is None:
        raise HTTPException(status_code=401, detail="GitLab authentication required")
    merge_request = GitLabClient.from_token(connection.access_token).merge_request(
        payload.project_id, payload.merge_request_iid
    )
    return ReviewTaskQuerier(db).create_from_gitlab(
        current_user,
        payload.project_id,
        payload.merge_request_iid,
        merge_request,
        payload.priority,
        payload.jira_ticket_key,
        payload.description,
        payload.reviewer_user_ids,
    )


@router.get("/by-mr", response_model=ReviewTaskResponse)
def get_review_task_by_mr(
    repo_gitlab_id: int,
    gitlab_mr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    task = ReviewTaskQuerier(db).get_by_mr(repo_gitlab_id, gitlab_mr_id)
    if task.author_user_id != current_user.user_id:
        return ReviewTaskQuerier(db).ensure_visible(task.task_id, current_user.user_id)
    return task


@router.get("/{task_id}", response_model=ReviewTaskResponse)
def get_review_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    return ReviewTaskQuerier(db).ensure_visible(task_id, current_user.user_id)


@router.patch("/{task_id}", response_model=ReviewTaskResponse)
def update_review_task(
    task_id: UUID,
    payload: ReviewTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewTaskResponse:
    return ReviewTaskQuerier(db).update(
        task_id, current_user.user_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ReviewTaskQuerier(db).delete(task_id, current_user.user_id)
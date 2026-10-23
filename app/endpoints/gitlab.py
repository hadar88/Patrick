from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import GitLabConnection, User
from app.db.session import get_db
from app.endpoints.auth import get_current_user
from app.integrations.gitlab import (
    GitLabAuthenticationError,
    GitLabClient,
)

router = APIRouter(prefix="/gitlab", tags=["gitlab"])


def get_gitlab_client(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GitLabClient:
    connection = db.query(GitLabConnection).filter(
        GitLabConnection.user_id == current_user.user_id
    ).one_or_none()
    if connection is None:
        raise HTTPException(status_code=401, detail="GitLab authentication required")

    if connection.expires_at is not None:
        expires_at = connection.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            if not connection.refresh_token:
                raise HTTPException(
                    status_code=401,
                    detail="GitLab authentication required",
                )
            try:
                token = GitLabClient.from_settings().refresh_access_token(
                    connection.refresh_token
                )
            except GitLabAuthenticationError as error:
                raise HTTPException(
                    status_code=401,
                    detail="GitLab authentication required",
                ) from error

            connection.access_token = str(token["access_token"])
            refreshed_token = token.get("refresh_token")
            if refreshed_token:
                connection.refresh_token = str(refreshed_token)
            expires_in = token.get("expires_in")
            connection.expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                if isinstance(expires_in, (int, float))
                else None
            )
            db.commit()

    return GitLabClient.from_token(connection.access_token)


@router.get("/projects")
def list_gitlab_projects(
    search: str | None = Query(default=None),
    gitlab: GitLabClient = Depends(get_gitlab_client),
) -> list[dict[str, object]]:
    return gitlab.projects(search)


@router.get("/merge-requests")
def list_authored_gitlab_merge_requests(
    project_id: int | None = Query(default=None),
    gitlab: GitLabClient = Depends(get_gitlab_client),
) -> list[dict[str, object]]:
    return gitlab.authored_merge_requests(project_id)


@router.get("/projects/{project_id}/merge-requests/{merge_request_iid}")
def get_gitlab_merge_request(
    project_id: int,
    merge_request_iid: int,
    gitlab: GitLabClient = Depends(get_gitlab_client),
) -> dict[str, object]:
    return gitlab.merge_request(project_id, merge_request_iid)
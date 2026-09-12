from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import GitLabConnection, User
from app.db.session import get_db
from app.endpoints.auth import get_current_user
from app.integrations.gitlab import GitLabClient

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
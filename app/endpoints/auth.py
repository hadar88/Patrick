import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import GitLabConnection, User
from app.db.session import get_db
from app.integrations.gitlab import GitLabClient, GitLabError

router = APIRouter(prefix="/auth", tags=["auth"])


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="GitLab authentication required")
    try:
        user_uuid = UUID(str(user_id))
    except ValueError as error:
        raise HTTPException(status_code=401, detail="Invalid session") from error
    user = db.get(User, user_uuid)
    if user is None:
        raise HTTPException(status_code=401, detail="GitLab authentication required")
    return user


@router.get("/gitlab/login")
def gitlab_login(request: Request) -> RedirectResponse:
    state = secrets.token_urlsafe(32)
    pending_states = request.session.get("gitlab_oauth_states", [])
    if not isinstance(pending_states, list):
        pending_states = []
    request.session["gitlab_oauth_states"] = [*pending_states[-4:], state]
    try:
        url = GitLabClient.from_settings().oauth_authorization_url(state)
    except GitLabError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return RedirectResponse(url)


@router.get("/gitlab/callback")
def gitlab_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Start GitLab login from /api/auth/gitlab/login",
        )
    pending_states = request.session.get("gitlab_oauth_states", [])
    if not isinstance(pending_states, list):
        pending_states = []
    matching_state = next(
        (
            pending_state
            for pending_state in pending_states
            if isinstance(pending_state, str)
            and secrets.compare_digest(pending_state, state)
        ),
        None,
    )
    if matching_state is None:
        raise HTTPException(status_code=400, detail="Invalid GitLab OAuth state")
    request.session["gitlab_oauth_states"] = [
        pending_state for pending_state in pending_states if pending_state != matching_state
    ]
    try:
        client = GitLabClient.from_settings()
        token = client.exchange_code(code)
        gitlab_user = GitLabClient.from_token(str(token["access_token"])).current_user()
    except GitLabError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    gitlab_id = int(gitlab_user["id"])
    user = db.query(User).filter(User.gitlab_id == gitlab_id).one_or_none()
    if user is None:
        user = User(
            gitlab_id=gitlab_id,
            username=str(gitlab_user.get("username", gitlab_id)),
            display_name=gitlab_user.get("name"),
        )
        db.add(user)
        db.flush()
    else:
        user.username = str(gitlab_user.get("username", user.username))
        user.display_name = gitlab_user.get("name", user.display_name)

    expires_in = token.get("expires_in")
    expires_at = None
    if isinstance(expires_in, (int, float)):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    connection = user.gitlab_connection or GitLabConnection(user=user)
    connection.access_token = str(token["access_token"])
    connection.refresh_token = token.get("refresh_token")
    connection.expires_at = expires_at
    db.add(connection)
    db.commit()
    request.session["user_id"] = str(user.user_id)
    return RedirectResponse("/")
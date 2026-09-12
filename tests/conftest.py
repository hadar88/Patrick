from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import ReviewTask, TaskReviewer, User
from app.db.session import get_db
from app.endpoints.auth import get_current_user
from app.main import app


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as database_session:
        yield database_session

    engine.dispose()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def login_as(client):
    def login(user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    return login


@pytest.fixture
def user_factory(session: Session):
    def create_user(
        *,
        gitlab_id: int = 1,
        username: str = "alice",
        display_name: str | None = "Alice",
    ) -> User:
        user = User(
            gitlab_id=gitlab_id,
            username=username,
            display_name=display_name,
        )
        session.add(user)
        session.flush()
        return user

    return create_user


@pytest.fixture
def task_factory(session: Session, user_factory):
    def create_task(
        *,
        author: User | None = None,
        repo_gitlab_id: int = 10,
        gitlab_mr_id: int = 20,
        mr_title: str = "Improve review flow",
    ) -> ReviewTask:
        task = ReviewTask(
            author=author or user_factory(),
            repo_gitlab_id=repo_gitlab_id,
            repo_name="patrick",
            repo_web_url="https://gitlab.example/patrick",
            gitlab_mr_id=gitlab_mr_id,
            mr_title=mr_title,
        )
        session.add(task)
        session.flush()
        return task

    return create_task


@pytest.fixture
def reviewer_factory(session: Session, task_factory, user_factory):
    def create_reviewer(
        *,
        task: ReviewTask | None = None,
        assigned_user: User | None = None,
        status: str = "WAITING_FOR_REVIEW",
    ) -> TaskReviewer:
        reviewer = TaskReviewer(
            task=task or task_factory(),
            assigned_user=assigned_user or user_factory(gitlab_id=2, username="bob"),
            status=status,
        )
        session.add(reviewer)
        session.flush()
        return reviewer

    return create_reviewer
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import ReviewTaskDAL
from app.db.models import ReviewTask
from app.exceptions import ResourceConflictError, ResourceNotFoundError


class ReviewTaskQuerier:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.dal = ReviewTaskDAL(session)

    def list(self, author_user_id: UUID | None = None) -> list[ReviewTask]:
        if author_user_id is None:
            return self.dal.list()
        return self.dal.list_by_author(author_user_id)

    def create(self, values: dict[str, object]) -> ReviewTask:
        if self.dal.get_by_gitlab_mr_id(
            values["repo_gitlab_id"], values["gitlab_mr_id"]
        ):
            raise ResourceConflictError("Review task already exists")
        task = self.dal.create(values)
        self.session.commit()
        return task

    def get_by_mr(self, repo_gitlab_id: int, gitlab_mr_id: int) -> ReviewTask:
        task = self.dal.get_by_gitlab_mr_id(repo_gitlab_id, gitlab_mr_id)
        if task is None:
            raise ResourceNotFoundError("Review task")
        return task

    def get(self, task_id: UUID) -> ReviewTask:
        task = self.dal.get(task_id)
        if task is None:
            raise ResourceNotFoundError("Review task")
        return task

    def update(self, task_id: UUID, values: dict[str, object]) -> ReviewTask:
        task = self.get(task_id)
        updated_task = self.dal.update(task, values)
        self.session.commit()
        return updated_task

    def delete(self, task_id: UUID) -> None:
        task = self.get(task_id)
        self.dal.delete(task)
        self.session.commit()

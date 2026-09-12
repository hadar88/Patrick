from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import TaskReviewerDAL
from app.db.models import TaskReviewer
from app.exceptions import ResourceConflictError, ResourceNotFoundError


class TaskReviewerQuerier:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.dal = TaskReviewerDAL(session)

    def list(self) -> list[TaskReviewer]:
        return self.dal.list()

    def list_by_task(self, task_id: UUID) -> list[TaskReviewer]:
        return self.dal.list_by_task(task_id)

    def list_by_user(self, user_id: UUID) -> list[TaskReviewer]:
        return self.dal.list_by_user(user_id)

    def create(self, values: dict[str, object]) -> TaskReviewer:
        if self.dal.get_for_task_and_user(
            values["task_id"], values["assigned_user_id"]
        ):
            raise ResourceConflictError("Reviewer is already assigned to this task")
        reviewer = self.dal.create(values)
        self.session.commit()
        return reviewer

    def get(self, reviewer_entry_id: UUID) -> TaskReviewer:
        reviewer = self.dal.get(reviewer_entry_id)
        if reviewer is None:
            raise ResourceNotFoundError("Reviewer")
        return reviewer

    def update(
        self, reviewer_entry_id: UUID, values: dict[str, object]
    ) -> TaskReviewer:
        reviewer = self.get(reviewer_entry_id)
        updated_reviewer = self.dal.update(reviewer, values)
        self.session.commit()
        return updated_reviewer

    def delete(self, reviewer_entry_id: UUID) -> None:
        reviewer = self.get(reviewer_entry_id)
        self.dal.delete(reviewer)
        self.session.commit()

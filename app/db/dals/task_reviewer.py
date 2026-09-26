from sqlalchemy import func, select

from app.db.dals.base import BaseDAL
from app.db.models import ReviewTask, TaskReviewer


class TaskReviewerDAL(BaseDAL[TaskReviewer]):
    model = TaskReviewer

    def get_for_task_and_user(
        self, task_id: object, assigned_user_id: object
    ) -> TaskReviewer | None:
        statement = select(TaskReviewer).where(
            TaskReviewer.task_id == task_id,
            TaskReviewer.assigned_user_id == assigned_user_id,
        )
        return self.session.scalar(statement)

    def list_by_task(self, task_id: object) -> list[TaskReviewer]:
        statement = select(TaskReviewer).where(TaskReviewer.task_id == task_id)
        return list(self.session.scalars(statement).all())

    def list_by_user(self, assigned_user_id: object) -> list[TaskReviewer]:
        statement = select(TaskReviewer).where(
            TaskReviewer.assigned_user_id == assigned_user_id
        )
        return list(self.session.scalars(statement).all())

    def count_status_by_reviewer(self, assigned_user_id: object) -> list[tuple[str, int]]:
        statement = (
            select(TaskReviewer.status, func.count(TaskReviewer.reviewer_entry_id))
            .where(TaskReviewer.assigned_user_id == assigned_user_id)
            .group_by(TaskReviewer.status)
        )
        return list(self.session.execute(statement).all())

    def count_status_by_assignee(self, assignee_id: object) -> list[tuple[str, int]]:
        statement = (
            select(TaskReviewer.status, func.count(TaskReviewer.reviewer_entry_id))
            .join(ReviewTask, TaskReviewer.task_id == ReviewTask.task_id)
            .where(ReviewTask.author_user_id == assignee_id)
            .group_by(TaskReviewer.status)
        )
        return list(self.session.execute(statement).all())
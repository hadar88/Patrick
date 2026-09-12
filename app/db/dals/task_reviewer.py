from sqlalchemy import select

from app.db.dals.base import BaseDAL
from app.db.models import TaskReviewer


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
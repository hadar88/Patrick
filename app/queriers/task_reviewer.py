from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import TaskReviewerDAL
from app.db.models import ReviewStatus, TaskReviewer
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
        values.setdefault("status", ReviewStatus.WAITING_FOR_REVIEW)
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
        self,
        reviewer_entry_id: UUID,
        values: dict[str, object],
    ) -> TaskReviewer:
        reviewer = self.get(reviewer_entry_id)
        updated_reviewer = self.dal.update(reviewer, values)
        if "status" in values:
            self._update_task_status(reviewer)
        self.session.commit()
        return updated_reviewer

    def update_for_task(
        self,
        task_id: UUID,
        user_id: UUID,
        values: dict[str, object],
    ) -> TaskReviewer:
        reviewer = self.dal.get_for_task_and_user(task_id, user_id)
        if reviewer is None:
            raise ResourceNotFoundError("Reviewer")
        return self.update(reviewer.reviewer_entry_id, values)

    def update_for_assignee(
        self,
        task_id: UUID,
        reviewer_entry_id: UUID,
        user_id: UUID,
        values: dict[str, object],
    ) -> TaskReviewer:
        reviewer = self.get(reviewer_entry_id)
        if (
            reviewer.task_id != task_id
            or reviewer.task.author_user_id != user_id
        ):
            raise ResourceNotFoundError("Reviewer")
        if (
            values.get("status") == ReviewStatus.WAITING_FOR_REVIEW.value
            and reviewer.task.status == ReviewStatus.CLOSED.value
        ):
            reviewer.task.status = ReviewStatus.WAITING_FOR_REVIEW.value
        return self.update(reviewer_entry_id, values)

    def _update_task_status(self, reviewer: TaskReviewer) -> None:
        task = reviewer.task
        if task.status == ReviewStatus.CLOSED.value:
            return

        reviewer_statuses = [entry.status for entry in task.reviewers]
        if any(status == ReviewStatus.CHANGES_NEEDED for status in reviewer_statuses):
            task.status = ReviewStatus.CHANGES_NEEDED.value
        elif any(status == ReviewStatus.IN_REVIEW for status in reviewer_statuses):
            task.status = ReviewStatus.IN_REVIEW.value
        elif reviewer_statuses and all(
            status == ReviewStatus.APPROVED for status in reviewer_statuses
        ):
            task.status = ReviewStatus.APPROVED.value
        else:
            task.status = ReviewStatus.WAITING_FOR_REVIEW.value

    def delete(self, reviewer_entry_id: UUID) -> None:
        reviewer = self.get(reviewer_entry_id)
        self.dal.delete(reviewer)
        self.session.commit()

    def count_status_as_reviewer(self, user_id: UUID) -> dict[str, int]:
        counts = {
            "WAITING_FOR_REVIEW": 0, 
            "IN_REVIEW": 0, 
            "CHANGES_NEEDED": 0, 
            "APPROVED": 0, 
            "CLOSED": 0
        }
        
        results = self.dal.count_status_by_reviewer(user_id)
        
        for status, count in results:
            status = status.value if hasattr(status, "value") else status
            if status in counts:
                counts[status] = count

        return counts

    def count_status_as_assignee(self, user_id: UUID) -> dict[str, int]:
        counts = {
            "WAITING_FOR_REVIEW": 0, 
            "IN_REVIEW": 0, 
            "CHANGES_NEEDED": 0, 
            "APPROVED": 0, 
            "CLOSED": 0
        }
        
        results = self.dal.count_status_by_assignee(user_id)
        
        for status, count in results:
            status = status.value if hasattr(status, "value") else status
            if status in counts:
                counts[status] = count

        return counts

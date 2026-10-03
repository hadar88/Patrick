from datetime import datetime
from typing import cast

from sqlalchemy import asc, desc, exists, select

from app.db.dals.base import BaseDAL
from app.db.models import ReviewTask, TaskReviewer
from app.queriers.filter_operators import FILTER_OPERATORS


class ReviewTaskDAL(BaseDAL[ReviewTask]):
    model = ReviewTask

    _task_sort_columns = {
        "title": ReviewTask.mr_title,
        "status": ReviewTask.status,
        "priority": ReviewTask.priority,
        "created_at": ReviewTask.created_at,
    }

    def get_by_gitlab_mr_id(
        self, repo_gitlab_id: int, gitlab_mr_id: int
    ) -> ReviewTask | None:
        statement = select(ReviewTask).where(
            ReviewTask.repo_gitlab_id == repo_gitlab_id,
            ReviewTask.gitlab_mr_id == gitlab_mr_id,
        )
        return self.session.scalar(statement)

    def list_by_author(
        self,
        author_user_id: object,
        *,
        offset: int = 0,
        limit: int | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        filters: dict[str, dict[str, object]] | None = None,
    ) -> list[ReviewTask]:
        statement = select(ReviewTask).where(
            ReviewTask.author_user_id == author_user_id
        )
        statement = self._apply_filters(statement, ReviewTask.status, filters)
        if sort_by is not None:
            sort_column = self._task_sort_columns[sort_by]
            statement = statement.order_by(
                (asc if sort_order == "asc" else desc)(sort_column),
                ReviewTask.task_id,
            )
        statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement).all())

    def list_by_reviewer(
        self,
        assigned_user_id: object,
        *,
        offset: int = 0,
        limit: int | None = None,
        sort_by: str | None = None,
        sort_order: str = "desc",
        filters: dict[str, dict[str, object]] | None = None,
    ) -> list[ReviewTask]:
        reviewer_status = (
            select(TaskReviewer.status)
            .where(
                TaskReviewer.task_id == ReviewTask.task_id,
                TaskReviewer.assigned_user_id == assigned_user_id,
            )
            .scalar_subquery()
        )
        sort_columns = {
            **self._task_sort_columns,
            "status": reviewer_status,
        }
        statement = select(ReviewTask).where(
            exists().where(
                TaskReviewer.task_id == ReviewTask.task_id,
                TaskReviewer.assigned_user_id == assigned_user_id,
            )
        )
        statement = self._apply_filters(statement, reviewer_status, filters)
        if sort_by is not None:
            sort_column = sort_columns[sort_by]
            statement = statement.order_by(
                (asc if sort_order == "asc" else desc)(sort_column),
                ReviewTask.task_id,
            )
        statement = statement.offset(offset)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement).all())

    @staticmethod
    def _apply_filters(
        statement,
        reviewer_status,
        filters: dict[str, dict[str, object]] | None,
    ):
        if not filters:
            return statement
        columns = {
            "title": ReviewTask.mr_title,
            "mr_title": ReviewTask.mr_title,
            "status": reviewer_status,
            "priority": ReviewTask.priority,
            "created_at": ReviewTask.created_at,
        }
        for field, filter_data in filters.items():
            operator = filter_data["operator"]
            column = columns[field]
            if operator == "EQUALS":
                values = cast(list[str], filter_data["values"])
                if field == "status":
                    values = [value.replace(" ", "_") for value in values]
                statement = FILTER_OPERATORS[operator].apply(
                    statement,
                    column,
                    values,
                )
            else:
                range_values = cast(dict[str, str], filter_data["values"])
                from_value = range_values["from"]
                to_value = range_values["to"]
                if field == "created_at":
                    from_value = datetime.fromisoformat(from_value)
                    to_value = datetime.fromisoformat(to_value)
                statement = FILTER_OPERATORS[operator].apply(
                    statement,
                    column,
                    (from_value, to_value),
                )
        return statement

    def is_visible_to_user(self, task_id: object, user_id: object) -> bool:
        statement = select(
            exists().where(
                ReviewTask.task_id == task_id,
                ReviewTask.author_user_id == user_id,
            )
            | exists().where(
                TaskReviewer.task_id == task_id,
                TaskReviewer.assigned_user_id == user_id,
            )
        )
        return bool(self.session.scalar(statement))
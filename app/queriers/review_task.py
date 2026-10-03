from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import ReviewTaskDAL
from app.db.models import ReviewStatus, ReviewTask, TaskReviewer, User
from app.exceptions import ResourceConflictError, ResourceNotFoundError

SortField = Literal["title", "status", "priority", "created_at"]
SortOrder = Literal["asc", "desc"]


class ReviewTaskQuerier:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.dal = ReviewTaskDAL(session)

    def list(
        self,
        author_user_id: UUID,
        *,
        offset: int = 0,
        limit: int | None = None,
        sort_by: SortField | None = None,
        sort_order: SortOrder = "desc",
        filters: dict[str, dict[str, object]] | None = None,
    ) -> list[ReviewTask]:
        return self.dal.list_by_author(
            author_user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )

    def list_assigned(self, user_id: UUID) -> list[ReviewTask]:
        return self.dal.list_by_reviewer(user_id)

    def list_my_prs(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        sort_by: SortField,
        sort_order: SortOrder,
        filters: Mapping[str, object],
    ) -> list[ReviewTask]:
        return self.list(
            user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=self._serialize_filters(filters),
        )

    def list_my_reviews(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        sort_by: SortField,
        sort_order: SortOrder,
        filters: Mapping[str, object],
    ) -> list[dict[str, object]]:
        return self.list_reviewer_rows(
            user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=self._serialize_filters(filters),
        )

    @staticmethod
    def _serialize_filters(
        filters: Mapping[str, object],
    ) -> dict[str, dict[str, object]]:
        serialized: dict[str, dict[str, object]] = {}
        for field, rule in filters.items():
            if hasattr(rule, "model_dump"):
                serialized[field] = rule.model_dump(
                    by_alias=True,
                    exclude_none=True,
                )
        return serialized

    def list_reviewer_rows(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 10,
        sort_by: SortField | None = None,
        sort_order: SortOrder = "desc",
        filters: dict[str, dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        tasks = self.dal.list_by_reviewer(
            user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )
        rows: list[dict[str, object]] = []
        for task in tasks:
            reviewer = next(
                reviewer
                for reviewer in task.reviewers
                if reviewer.assigned_user_id == user_id
            )
            rows.append(
                {
                    "mr_title": task.mr_title,
                    "mr_web_url": task.mr_web_url,
                    "status": reviewer.status,
                    "priority": task.priority,
                    "created_at": task.created_at,
                    "jira_ticket_url": task.jira_ticket_url,
                    "developer": task.author,
                }
            )
        return rows

    def create(self, values: dict[str, object]) -> ReviewTask:
        reviewer_user_ids = values.pop("reviewer_user_ids", [])
        if self.dal.get_by_gitlab_mr_id(
            values["repo_gitlab_id"], values["gitlab_mr_id"]
        ):
            raise ResourceConflictError("Review task already exists")
        task = self.dal.create(values)
        self._add_reviewers(task, reviewer_user_ids, source="MANUAL")
        self.session.commit()
        return task

    def create_from_gitlab(
        self,
        user: User,
        project_id: int,
        merge_request_iid: int,
        gitlab_data: dict[str, object],
        priority: str = "NORMAL",
        jira_ticket_url: str | None = None,
        description: str | None = None,
        reviewer_user_ids: list[UUID] | None = None,
        reviewer_gitlab_ids: list[int] | None = None,
    ) -> ReviewTask:
        if self.dal.get_by_gitlab_mr_id(project_id, merge_request_iid):
            raise ResourceConflictError("Review task already exists")

        web_url = str(gitlab_data.get("web_url", ""))
        references = gitlab_data.get("references")
        repo_name = str(project_id)
        if isinstance(references, dict):
            full_reference = references.get("full")
            if isinstance(full_reference, str):
                repo_name = full_reference.rsplit("!", 1)[0]

        task = ReviewTask(
            author_user_id=user.user_id,
            repo_gitlab_id=project_id,
            repo_name=repo_name,
            mr_web_url=web_url,
            gitlab_mr_id=merge_request_iid,
            mr_title=str(gitlab_data.get("title", "")),
            description=description,
            mr_state=str(gitlab_data.get("state", "opened")),
            priority=priority,
            jira_ticket_url=jira_ticket_url,
        )
        self.session.add(task)
        manual_reviewer_ids = reviewer_user_ids or []
        self._add_reviewers(task, manual_reviewer_ids, source="MANUAL")
        for reviewer_gitlab_id in reviewer_gitlab_ids or []:
            assigned_user = self.session.query(User).filter(
                User.gitlab_id == reviewer_gitlab_id
            ).one_or_none()
            if (
                assigned_user
                and not any(
                    reviewer_entry.assigned_user_id == assigned_user.user_id
                    for reviewer_entry in task.reviewers
                )
            ):
                task.reviewers.append(
                    TaskReviewer(
                        assigned_user=assigned_user,
                        status=ReviewStatus.WAITING_FOR_REVIEW,
                        source="GITLAB",
                    )
                )
        self.session.commit()
        return task

    def _add_reviewers(
        self,
        task: ReviewTask,
        reviewer_user_ids: object,
        source: str,
    ) -> None:
        if not isinstance(reviewer_user_ids, list):
            return
        for reviewer_user_id in reviewer_user_ids:
            if not isinstance(reviewer_user_id, UUID):
                continue
            assigned_user = self.session.get(User, reviewer_user_id)
            if (
                assigned_user
                and not any(
                    reviewer_entry.assigned_user_id == assigned_user.user_id
                    for reviewer_entry in task.reviewers
                )
            ):
                task.reviewers.append(
                    TaskReviewer(
                        assigned_user=assigned_user,
                        status=ReviewStatus.WAITING_FOR_REVIEW,
                        source=source,
                    )
                )

    def ensure_visible(self, task_id: UUID, user_id: UUID) -> ReviewTask:
        task = self.get(task_id)
        if not self.dal.is_visible_to_user(task_id, user_id):
            raise ResourceNotFoundError("Review task")
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

    def update(
        self, task_id: UUID, user_id: UUID, values: dict[str, object]
    ) -> ReviewTask:
        task = self.ensure_visible(task_id, user_id)
        updated_task = self.dal.update(task, values)
        self.session.commit()
        return updated_task

    def delete(self, task_id: UUID, user_id: UUID) -> None:
        task = self.ensure_visible(task_id, user_id)
        self.dal.delete(task)
        self.session.commit()

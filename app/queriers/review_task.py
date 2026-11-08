from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import ReviewTaskDAL
from app.db.models import ReviewStatus, ReviewTask, TaskReviewer, User
from app.exceptions import ResourceConflictError, ResourceNotFoundError

SortField = Literal["mr_title", "status", "priority", "created_at"]
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
        mr_state: str | None = None,
        task_status: str | None = None,
    ) -> list[ReviewTask]:
        return self.dal.list_by_author(
            author_user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
            mr_state=mr_state,
            task_status=task_status,
        )

    def list_assigned(
        self,
        user_id: UUID,
        *,
        mr_state: str | None = None,
        task_status: str | None = None,
    ) -> list[ReviewTask]:
        return self.dal.list_by_reviewer(
            user_id,
            mr_state=mr_state,
            task_status=task_status,
        )

    def list_my_prs(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        sort_by: SortField,
        sort_order: SortOrder,
        filters: Mapping[str, object],
        mr_state: str | None = None,
        task_status: str | None = None,
    ) -> list[ReviewTask]:
        return self.list(
            user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=self._serialize_filters(filters),
            mr_state=mr_state,
            task_status=task_status,
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
        mr_state: str | None = None,
        task_status: str | None = None,
    ) -> list[dict[str, object]]:
        return self.list_reviewer_rows(
            user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=self._serialize_filters(filters),
            mr_state=mr_state,
            task_status=task_status,
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
        mr_state: str | None = None,
        task_status: str | None = None,
    ) -> list[dict[str, object]]:
        tasks = self.dal.list_by_reviewer(
            user_id,
            offset=offset,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
            mr_state=mr_state,
            task_status=task_status,
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
                    "task_id": task.task_id,
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
            raise ResourceConflictError("This review task already exists")
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
        priority: str = "MEDIUM",
        jira_ticket_url: str | None = None,
        description: str | None = None,
        reviewer_user_ids: list[UUID] | None = None,
        reviewer_gitlab_ids: list[int] | None = None,
    ) -> ReviewTask:
        if self.dal.get_by_gitlab_mr_id(project_id, merge_request_iid):
            raise ResourceConflictError("This review task already exists")

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
            if assigned_user is None:
                reviewer_data = gitlab_data.get("reviewers", [])
                reviewer_info = next(
                    (
                        item
                        for item in reviewer_data
                        if isinstance(item, dict)
                        and item.get("id") == reviewer_gitlab_id
                    ),
                    None,
                ) if isinstance(reviewer_data, list) else None
                if isinstance(reviewer_info, dict):
                    username = reviewer_info.get("username")
                    if isinstance(username, str) and username:
                        assigned_user = User(
                            gitlab_id=reviewer_gitlab_id,
                            username=username,
                            display_name=(
                                reviewer_info.get("name")
                                if isinstance(reviewer_info.get("name"), str)
                                else None
                            ),
                        )
                        self.session.add(assigned_user)
                        self.session.flush()
            if assigned_user is None:
                raise ResourceNotFoundError("GitLab reviewer user")
            if (
                not any(
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
            if assigned_user is None:
                raise ResourceNotFoundError("Reviewer user")
            if any(
                reviewer_entry.assigned_user_id == assigned_user.user_id
                for reviewer_entry in task.reviewers
            ):
                continue
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
        reviewer_user_ids = values.pop("reviewer_user_ids", None)
        updated_task = self.dal.update(task, values)
        if reviewer_user_ids is not None:
            requested_reviewer_ids = {
                reviewer_id
                for reviewer_id in reviewer_user_ids
                if isinstance(reviewer_id, UUID)
            }
            task.reviewers[:] = [
                reviewer
                for reviewer in task.reviewers
                if reviewer.assigned_user_id in requested_reviewer_ids
            ]
            self._add_reviewers(
                task,
                list(requested_reviewer_ids),
                source="MANUAL",
            )
        if values.get("status") == ReviewStatus.CLOSED.value:
            for reviewer in task.reviewers:
                reviewer.status = ReviewStatus.CLOSED
        elif reviewer_user_ids is not None:
            self._recalculate_status(task)
        self.session.commit()
        return updated_task

    @staticmethod
    def _recalculate_status(task: ReviewTask) -> None:
        reviewer_statuses = [reviewer.status for reviewer in task.reviewers]
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

    def delete(self, task_id: UUID, user_id: UUID) -> None:
        task = self.ensure_visible(task_id, user_id)
        self.dal.delete(task)
        self.session.commit()

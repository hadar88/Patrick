from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import ReviewTaskDAL
from app.db.models import ReviewTask, TaskReviewer, User
from app.exceptions import ResourceConflictError, ResourceNotFoundError


class ReviewTaskQuerier:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.dal = ReviewTaskDAL(session)

    def list(self, author_user_id: UUID) -> list[ReviewTask]:
        return self.dal.list_by_author(author_user_id)

    def list_assigned(self, user_id: UUID) -> list[ReviewTask]:
        return self.dal.list_by_reviewer(user_id)

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
        jira_ticket_key: str | None = None,
        description: str | None = None,
        reviewer_user_ids: list[UUID] | None = None,
    ) -> ReviewTask:
        if self.dal.get_by_gitlab_mr_id(project_id, merge_request_iid):
            raise ResourceConflictError("Review task already exists")

        web_url = str(gitlab_data.get("web_url", ""))
        repo_web_url = web_url.split("/-/", 1)[0] or web_url.rsplit(
            "/merge_requests/", 1
        )[0]
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
            repo_web_url=repo_web_url,
            gitlab_mr_id=merge_request_iid,
            mr_title=str(gitlab_data.get("title", "")),
            description=description,
            mr_state=str(gitlab_data.get("state", "opened")),
            priority=priority,
            jira_ticket_key=jira_ticket_key,
        )
        self.session.add(task)
        manual_reviewer_ids = reviewer_user_ids or []
        self._add_reviewers(task, manual_reviewer_ids, source="MANUAL")
        reviewers = gitlab_data.get("reviewers")
        for reviewer in reviewers if isinstance(reviewers, list) else []:
            if not isinstance(reviewer, dict) or not isinstance(reviewer.get("id"), int):
                continue
            assigned_user = self.session.query(User).filter(
                User.gitlab_id == reviewer["id"]
            ).one_or_none()
            if (
                assigned_user
                and assigned_user.user_id != user.user_id
                and not any(
                    reviewer_entry.assigned_user_id == assigned_user.user_id
                    for reviewer_entry in task.reviewers
                )
            ):
                task.reviewers.append(
                    TaskReviewer(assigned_user=assigned_user, source="GITLAB")
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
                and assigned_user.user_id != task.author_user_id
                and not any(
                    reviewer_entry.assigned_user_id == assigned_user.user_id
                    for reviewer_entry in task.reviewers
                )
            ):
                task.reviewers.append(
                    TaskReviewer(assigned_user=assigned_user, source=source)
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

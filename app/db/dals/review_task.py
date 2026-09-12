from sqlalchemy import select

from app.db.dals.base import BaseDAL
from app.db.models import ReviewTask


class ReviewTaskDAL(BaseDAL[ReviewTask]):
    model = ReviewTask

    def get_by_gitlab_mr_id(
        self, repo_gitlab_id: int, gitlab_mr_id: int
    ) -> ReviewTask | None:
        statement = select(ReviewTask).where(
            ReviewTask.repo_gitlab_id == repo_gitlab_id,
            ReviewTask.gitlab_mr_id == gitlab_mr_id,
        )
        return self.session.scalar(statement)

    def list_by_author(self, author_user_id: object) -> list[ReviewTask]:
        statement = select(ReviewTask).where(
            ReviewTask.author_user_id == author_user_id
        )
        return list(self.session.scalars(statement).all())
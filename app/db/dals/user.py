from sqlalchemy import select

from app.db.dals.base import BaseDAL
from app.db.models import User


class UserDAL(BaseDAL[User]):
    model = User

    def get_by_gitlab_id(self, gitlab_id: int) -> User | None:
        statement = select(User).where(User.gitlab_id == gitlab_id)
        return self.session.scalar(statement)

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.session.scalar(statement)
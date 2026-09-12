from uuid import UUID

from sqlalchemy.orm import Session

from app.db.dals import UserDAL
from app.db.models import User
from app.exceptions import ResourceConflictError, ResourceNotFoundError


class UserQuerier:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.dal = UserDAL(session)

    def list(self) -> list[User]:
        return self.dal.list()

    def create(self, values: dict[str, object]) -> User:
        if self.dal.get_by_gitlab_id(values["gitlab_id"]):
            raise ResourceConflictError("User already exists")
        user = self.dal.create(values)
        self.session.commit()
        return user

    def get(self, user_id: UUID) -> User:
        user = self.dal.get(user_id)
        if user is None:
            raise ResourceNotFoundError("User")
        return user

    def update(self, user_id: UUID, values: dict[str, object]) -> User:
        user = self.get(user_id)
        updated_user = self.dal.update(user, values)
        self.session.commit()
        return updated_user

    def delete(self, user_id: UUID) -> None:
        user = self.get(user_id)
        self.dal.delete(user)
        self.session.commit()

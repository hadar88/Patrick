from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseDAL(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, object_id: Any) -> ModelT | None:
        return self.session.get(self.model, object_id)

    def list(self) -> list[ModelT]:
        return list(self.session.scalars(select(self.model)).all())

    def create(self, values: Mapping[str, Any]) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        self.session.flush()
        return instance

    def update(self, instance: ModelT, values: Mapping[str, Any]) -> ModelT:
        for field, value in values.items():
            setattr(instance, field, value)
        self.session.flush()
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)
        self.session.flush()
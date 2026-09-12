import uuid

from sqlalchemy import BigInteger, Column, String, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gitlab_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)

    authored_tasks = relationship(
        "ReviewTask", back_populates="author", cascade="all, delete-orphan"
    )
    assigned_reviews = relationship(
        "TaskReviewer", back_populates="assigned_user", cascade="all, delete-orphan"
    )
    gitlab_connection = relationship(
        "GitLabConnection",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

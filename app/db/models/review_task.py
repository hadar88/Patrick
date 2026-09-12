import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReviewTask(Base):
    __tablename__ = "review_tasks"
    __table_args__ = (
        UniqueConstraint(
            "repo_gitlab_id",
            "gitlab_mr_id",
            name="uq_review_tasks_repo_mr",
        ),
    )

    task_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    author_user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", name="fk_tasks_author"),
        nullable=False,
    )
    repo_gitlab_id = Column(BigInteger, nullable=False)
    repo_name = Column(String(255), nullable=False)
    repo_web_url = Column(Text, nullable=False)
    gitlab_mr_id = Column(BigInteger, nullable=False)
    mr_title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    mr_state = Column(String(50), server_default="opened")
    priority = Column(String(50), server_default="NORMAL")
    status = Column(String(50), server_default="WAITING_FOR_REVIEW")
    jira_ticket_key = Column(String(100), nullable=True)

    author = relationship("User", back_populates="authored_tasks")
    reviewers = relationship(
        "TaskReviewer", back_populates="task", cascade="all, delete-orphan"
    )

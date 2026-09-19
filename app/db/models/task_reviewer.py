import uuid
import enum

from sqlalchemy import Column, ForeignKey, String, UniqueConstraint, Uuid, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship

from app.db.base import Base


class ReviewStatus(str, enum.Enum):
    WAITING = "waiting"
    REVIEW = "review"
    CHANGES_NEEDED = "changes_needed"
    APPROVED = "approved"
    CLOSED = "closed"


class TaskReviewer(Base):
    __tablename__ = "task_reviewers"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "assigned_user_id",
            name="uq_task_reviewers_task_user",
        ),
    )

    reviewer_entry_id = Column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("review_tasks.task_id", name="fk_reviewers_task"),
        nullable=False,
    )
    assigned_user_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", name="fk_reviewers_user"),
        nullable=False,
    )
    status = Column(
        SQLAlchemyEnum(ReviewStatus, name="review_status_enum"), 
        server_default=ReviewStatus.WAITING.value,
        nullable=False
    )
    source = Column(String(50), server_default="MANUAL")

    task = relationship("ReviewTask", back_populates="reviewers")
    assigned_user = relationship("User", back_populates="assigned_reviews")

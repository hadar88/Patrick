from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.time import humanize_status


class TaskReviewerCreate(BaseModel):
    task_id: UUID
    assigned_user_id: UUID
    status: str = "WAITING_FOR_REVIEW"
    source: str = "MANUAL"


class TaskReviewerUpdate(BaseModel):
    status: str | None = None
    source: str | None = None

    @field_validator("status", "source", mode="before")
    @classmethod
    def non_nullable_fields_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class TaskReviewerResponse(TaskReviewerCreate):
    model_config = ConfigDict(from_attributes=True)

    reviewer_entry_id: UUID
    username: str
    display_name: str | None = None
    avatar_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def include_assigned_user_details(cls, value: object) -> object:
        if isinstance(value, dict):
            return value
        assigned_user = getattr(value, "assigned_user", None)
        if assigned_user is None:
            return value
        return {
            "reviewer_entry_id": value.reviewer_entry_id,
            "task_id": value.task_id,
            "assigned_user_id": value.assigned_user_id,
            "status": value.status,
            "source": value.source,
            "username": assigned_user.username,
            "display_name": assigned_user.display_name,
            "avatar_url": assigned_user.avatar_url,
        }

    @field_serializer("status")
    def serialize_status(self, value: str) -> str:
        return humanize_status(value)


class StatusCountResponse(BaseModel):
    status: str
    count: int
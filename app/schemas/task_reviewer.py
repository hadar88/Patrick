from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


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
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class UserCreate(BaseModel):
    gitlab_id: int
    username: str
    display_name: str | None = None


class UserUpdate(BaseModel):
    username: str | None = None
    display_name: str | None = None

    @field_validator("username", mode="before")
    @classmethod
    def username_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("username cannot be null")
        return value


class UserResponse(UserCreate):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID


class ReviewTaskCreate(BaseModel):
    author_user_id: UUID
    repo_gitlab_id: int
    repo_name: str
    repo_web_url: str
    gitlab_mr_id: int
    mr_title: str
    mr_state: str = "opened"
    priority: str = "NORMAL"
    status: str = "WAITING_FOR_REVIEW"
    jira_ticket_key: str | None = None


class ReviewTaskUpdate(BaseModel):
    mr_state: str | None = None
    priority: str | None = None
    status: str | None = None
    jira_ticket_key: str | None = None

    @field_validator("mr_state", "priority", "status", mode="before")
    @classmethod
    def non_nullable_fields_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class ReviewTaskResponse(ReviewTaskCreate):
    model_config = ConfigDict(from_attributes=True)

    task_id: UUID


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
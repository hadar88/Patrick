from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


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
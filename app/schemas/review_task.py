from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReviewTaskCreate(BaseModel):
    author_user_id: UUID
    repo_gitlab_id: int
    repo_name: str
    repo_web_url: str
    gitlab_mr_id: int
    mr_title: str
    description: str | None = None
    reviewer_user_ids: list[UUID] = Field(default_factory=list)
    mr_state: str = "opened"
    priority: str = "NORMAL"
    status: str = "WAITING_FOR_REVIEW"
    jira_ticket_key: str | None = None


class ReviewTaskFromGitLabCreate(BaseModel):
    project_id: int
    merge_request_iid: int
    description: str | None = None
    reviewer_user_ids: list[UUID] = Field(default_factory=list)
    priority: str = "NORMAL"
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
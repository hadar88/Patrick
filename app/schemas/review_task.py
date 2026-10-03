from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_serializer,
    field_validator,
    model_validator,
)
from typing import Literal

from app.core.time import JERUSALEM_TIMEZONE, humanize_status
from app.schemas.task_reviewer import TaskReviewerResponse
from app.schemas.user import UserResponse


class ReviewTaskCreate(BaseModel):
    author_user_id: UUID
    repo_gitlab_id: int
    repo_name: str
    mr_web_url: str
    gitlab_mr_id: int
    mr_title: str
    description: str | None = None
    reviewer_user_ids: list[UUID] = Field(default_factory=list)
    mr_state: str = "opened"
    priority: str = "NORMAL"
    status: str = "WAITING_FOR_REVIEW"
    jira_ticket_url: str | None = None


class ReviewTaskFromGitLabCreate(BaseModel):
    project_id: int
    merge_request_iid: int
    description: str | None = None
    reviewer_user_ids: list[UUID] = Field(default_factory=list)
    reviewer_gitlab_ids: list[int] = Field(default_factory=list)
    priority: str = "NORMAL"
    jira_ticket_url: str | None = None


class ReviewTaskUpdate(BaseModel):
    mr_state: str | None = None
    priority: str | None = None
    status: str | None = None
    jira_ticket_url: str | None = None

    @field_validator("mr_state", "priority", "status", mode="before")
    @classmethod
    def non_nullable_fields_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("field cannot be null")
        return value


class ReviewTaskResponse(ReviewTaskCreate):
    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    created_at: datetime
    reviewers: list[TaskReviewerResponse] = Field(default_factory=list)

    @field_serializer("status")
    def serialize_status(self, value: str) -> str:
        return humanize_status(value)

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_jerusalem_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=JERUSALEM_TIMEZONE)
        return value


class ReviewerTaskResponse(BaseModel):
    mr_title: str
    mr_web_url: str
    status: str
    priority: str
    created_at: datetime
    jira_ticket_url: str | None = None
    developer: UserResponse

    @field_validator("created_at", mode="before")
    @classmethod
    def ensure_jerusalem_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=JERUSALEM_TIMEZONE)
        return value

    @field_serializer("status")
    def serialize_status(self, value: str) -> str:
        return humanize_status(value)


class ReviewTaskFilter(BaseModel):
    operator: Literal["EQUALS", "RANGE"]
    values: list[str] | dict[str, str]

    @model_validator(mode="after")
    def validate_operator_values(self) -> "ReviewTaskFilter":
        if self.operator == "EQUALS":
            if not isinstance(self.values, list) or not self.values:
                raise ValueError("EQUALS requires a non-empty values list")
        elif not (
            isinstance(self.values, dict)
            and set(self.values) == {"from", "to"}
            and self.values["from"]
            and self.values["to"]
        ):
            raise ValueError("RANGE requires values with from and to")
        return self


class ReviewTaskFilters(RootModel[dict[str, ReviewTaskFilter]]):
    @model_validator(mode="after")
    def validate_filters(self) -> "ReviewTaskFilters":
        supported_fields = {"status", "priority", "created_at"}
        unsupported_fields = set(self.root) - supported_fields
        if unsupported_fields:
            raise ValueError(
                f"Unsupported filter fields: {', '.join(sorted(unsupported_fields))}"
            )
        created_at_filter = self.root.get("created_at")
        if created_at_filter and created_at_filter.operator == "RANGE":
            range_values = created_at_filter.values
            if isinstance(range_values, dict):
                try:
                    datetime.fromisoformat(range_values["from"])
                    datetime.fromisoformat(range_values["to"])
                except ValueError as error:
                    raise ValueError(
                        "created_at RANGE values must be valid ISO-8601 datetimes"
                    ) from error
        return self
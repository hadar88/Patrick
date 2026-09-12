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
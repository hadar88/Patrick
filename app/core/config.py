from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    environment: str = Field(default="development", validation_alias="APP_ENV")
    database_url: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
    )
    database_user: str | None = Field(default=None, validation_alias="DATABASE_USER")
    database_password: str | None = Field(
        default=None,
        validation_alias="DATABASE_PASSWORD",
    )
    database_host: str | None = Field(default=None, validation_alias="DATABASE_HOST")
    database_port: int = Field(default=5432, validation_alias="DATABASE_PORT")
    database_name: str | None = Field(default=None, validation_alias="DATABASE_NAME")
    cors_origins: list[str] = Field(
        default_factory=list,
        validation_alias="CORS_ORIGINS",
    )
    gitlab_url: str = Field(
        default="https://gitlab.com",
        validation_alias="GITLAB_URL",
    )
    gitlab_client_id: str | None = Field(
        default=None,
        validation_alias="GITLAB_CLIENT_ID",
    )
    gitlab_client_secret: str | None = Field(
        default=None,
        validation_alias="GITLAB_CLIENT_SECRET",
    )
    gitlab_redirect_uri: str = Field(
        default="http://localhost:8000/api/auth/gitlab/callback",
        validation_alias="GITLAB_REDIRECT_URI",
    )
    session_secret: str = Field(
        default="change-this-session-secret",
        validation_alias="SESSION_SECRET",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_database_url(self) -> str:
        if self.database_url:
            return self.database_url

        postgres_settings = (
            self.database_user,
            self.database_password,
            self.database_host,
            self.database_name,
        )
        if all(value is not None for value in postgres_settings):
            return URL.create(
                "postgresql+psycopg",
                username=self.database_user,
                password=self.database_password,
                host=self.database_host,
                port=self.database_port,
                database=self.database_name,
            ).render_as_string(hide_password=False)

        return "sqlite:///./dev.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
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

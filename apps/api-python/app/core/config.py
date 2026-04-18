from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Campus Face Recognition Attendance System"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "attendance"
    postgres_user: str = "attendance"
    postgres_password: str = "attendance"
    redis_url: str = "redis://redis:6379/0"
    insightface_model_name: str = "buffalo_l"
    insightface_allowed_providers: list[str] = Field(default_factory=lambda: ["CPUExecutionProvider"])
    insightface_model_root: str = "/models/insightface"
    default_detection_size_width: int = 320
    default_detection_size_height: int = 320
    object_storage_mode: Literal["local"] = "local"
    object_storage_root: str = "/app/data/object-storage"
    cooldown_seconds: int = 30
    heartbeat_ttl_seconds: int = 30
    recent_match_ttl_seconds: int = 15

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @computed_field
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @field_validator("insightface_allowed_providers", mode="before")
    @classmethod
    def parse_providers(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_paths_and_sizes(self) -> "Settings":
        if self.default_detection_size_width <= 0 or self.default_detection_size_height <= 0:
            raise ValueError("default detection size must be positive")
        Path(self.object_storage_root).mkdir(parents=True, exist_ok=True)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


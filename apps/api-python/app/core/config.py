from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.security import is_secret_key_safe

LOGGER = logging.getLogger(__name__)


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
    postgres_password: str = ""
    redis_url: str = "redis://redis:6379/0"
    insightface_model_name: str = "buffalo_l"
    insightface_allowed_providers: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["CPUExecutionProvider"])
    insightface_model_root: str = "/app/models/insightface"
    default_detection_size_width: int = 320
    default_detection_size_height: int = 320
    object_storage_mode: Literal["local"] = "local"
    object_storage_root: str = "/app/data/object-storage"
    cooldown_seconds: int = 30
    heartbeat_ttl_seconds: int = 30
    recent_match_ttl_seconds: int = 15
    recognition_confidence_threshold: float = 0.55
    recognition_candidate_margin_threshold: float = 0.05
    attendance_quality_mode: Literal["normal", "local_fast", "strict"] = "normal"
    recognition_slow_request_ms: int = 2500
    recognition_warmup_on_startup: bool = False
    auth_secret_key: str = ""
    admin_session_ttl_seconds: int = 28800
    default_admin_username: str = "admin"
    default_admin_email: str | None = "admin@local.test"
    default_admin_password: str | None = None
    login_rate_limit_max: int = 5
    login_rate_limit_window_seconds: int = 60
    ml_rate_limit_max: int = 30
    ml_rate_limit_window_seconds: int = 60
    # Kiosk UI paces enrollment frames at >=1.2s apart (~50/min); keep the
    # limit above that so auto-capture does not trip 429 on a healthy flow.
    enrollment_rate_limit_max: int = 60
    enrollment_rate_limit_window_seconds: int = 60
    attendance_rate_limit_max: int = 40
    attendance_rate_limit_window_seconds: int = 60
    public_app_url: str | None = None
    public_api_url: str | None = None
    cors_allowed_origins: list[str] = Field(default_factory=list)
    trusted_tunnel_origins: list[str] = Field(default_factory=list)
    # Behind a reverse proxy or tunnel every request arrives from the proxy's own
    # address, which collapses per-IP rate limiting into one shared bucket: one
    # brute-forcer then locks out every other user. Turning this on makes the
    # limiter read the first X-Forwarded-For hop instead. Only enable it when a
    # proxy you control sets that header — otherwise a client can forge it and
    # sidestep the limit entirely.
    trust_proxy_headers: bool = False
    kiosk_public_mode: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8000", "http://127.0.0.1:8000"])
    csrf_enabled: bool = True
    csrf_ttl_seconds: int = 3600
    max_frame_b64_length: int = 10_000_000
    max_frames_per_recognition: int = 10

    @field_validator("cors_origins", "cors_allowed_origins", "trusted_tunnel_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @computed_field
    @property
    def effective_cors_origins(self) -> list[str]:
        origins: list[str] = []
        for value in [
            *self.cors_origins,
            *self.cors_allowed_origins,
            *self.trusted_tunnel_origins,
            self.public_app_url,
        ]:
            if value and value not in origins:
                origins.append(value)
        return origins

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
        if any(origin == "*" for origin in self.effective_cors_origins):
            raise ValueError("Wildcard CORS origins are not allowed when credentialed admin cookies are enabled")
        Path(self.object_storage_root).mkdir(parents=True, exist_ok=True)
        key_ok, key_msg = is_secret_key_safe(self.auth_secret_key)
        if not key_ok:
            if self.app_env == "production":
                raise ValueError(f"Production startup rejected: {key_msg}")
            LOGGER.warning("AUTH_SECRET_KEY is unsafe (%s). Generating temporary dev key.", key_msg)
            self.auth_secret_key = secrets.token_urlsafe(48)
            LOGGER.info("Generated temporary AUTH_SECRET_KEY for development session.")
        if self.app_env == "production":
            missing = []
            if not self.postgres_password:
                missing.append("POSTGRES_PASSWORD")
            if not self.default_admin_password:
                missing.append("DEFAULT_ADMIN_PASSWORD")
            if missing:
                raise ValueError(f"Missing required environment variables in production: {', '.join(missing)}")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

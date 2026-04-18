from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COCOON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Cocoon-SIT API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "dev-secret-key-for-cocoon-sit-at-least-32-bytes"
    access_token_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = Field(default_factory=list)

    database_url: str = "sqlite:///./cocoon.db"
    redis_url: str = "redis://localhost:6379/0"
    chat_dispatch_backend: str = "redis"
    realtime_backend: str = "redis"
    auto_create_schema: bool = True
    auto_seed_defaults: bool = True

    artifact_root: Path = Field(default=Path(".artifacts"))
    artifact_ttl_hours: int = 24 * 7
    provider_master_key: str = "0d2f0gQbYFoA7Ff7w2HoQ5gUlf8QqPgo6pI6sL2X6P0="

    chat_dispatch_stream: str = "cocoon:dispatch:chat"
    chat_dispatch_group: str = "cocoon-workers"
    realtime_channel_prefix: str = "cocoon:events"
    durable_job_worker_name: str = "worker-1"

    default_admin_username: str = "admin"
    default_admin_email: str | None = "admin@example.com"
    default_admin_password: str = "admin"

    dump_openapi_path: str = "../packages/ts-sdk/openapi.json"
    frontend_dist_path: Path = Field(default=Path("frontend_dist"))


@lru_cache
def get_settings() -> Settings:
    return Settings()

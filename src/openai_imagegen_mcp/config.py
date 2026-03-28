"""Environment-based configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    openai_api_key: str

    openai_imagegen_output_dir: str = "./generated-images"
    openai_imagegen_default_model: str = "gpt-image-1.5"
    openai_imagegen_default_quality: str = "auto"
    openai_imagegen_timeout: int = 180

    port: int = 8000

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None

    @property
    def output_dir(self) -> Path:
        path = Path(self.openai_imagegen_output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def has_google_oauth(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

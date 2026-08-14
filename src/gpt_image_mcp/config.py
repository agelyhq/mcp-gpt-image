"""Environment-based configuration.

Read from the process environment and from a local .env file. OPENAI_API_KEY keeps
its standard name so an existing OpenAI setup works untouched; everything specific
to this server is prefixed GPT_IMAGE_.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from gpt_image_mcp.domain.types import MODEL, ORCHESTRATOR_MODEL


class Settings(BaseSettings):
    """Runtime settings for the image server."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        # Without this, building Settings in code with a field name rather than
        # its environment alias is silently ignored and the default wins.
        populate_by_name=True,
    )

    # SecretStr so the key cannot land in a log line or a traceback through an
    # incidental repr of the settings object.
    openai_api_key: SecretStr

    output_dir: Path = Field(default=Path("./generated-images"), alias="gpt_image_output_dir")

    # Only gpt-image-2 ids belong here. The pinned snapshot gpt-image-2-2026-04-21
    # freezes behaviour if a silent model update ever changes the output.
    model: str = Field(default=MODEL, alias="gpt_image_model")

    # gpt-image-2 plans before it draws, and the guide warns that complex prompts
    # can take up to two minutes. 4K sizes sit at the top of that range.
    timeout: int = Field(default=300, alias="gpt_image_timeout")

    # The chat model that drives the image tool during refinement. The default
    # follows the newest model automatically; pin an exact id here when a specific
    # one refines better, or when a moving alias starts drifting.
    refine_model: str = Field(default=ORCHESTRATOR_MODEL, alias="gpt_image_refine_model")

    # Refinement adds a reasoning model in front of the drawing, so it is slower.
    refine_timeout: int = Field(default=300, alias="gpt_image_refine_timeout")


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()  # type: ignore[call-arg]

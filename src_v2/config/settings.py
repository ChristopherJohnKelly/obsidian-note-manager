"""Application settings loaded from environment and .env."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for vault root, API keys, and paths."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    vault_root: Path = Field(
        default_factory=Path.cwd,
        alias="OBSIDIAN_VAULT_ROOT",
        description="Root path of the Obsidian vault",
    )
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        description="Google Gemini API key for LLM calls",
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    registry_output_path: str = Field(
        default="99. System/Manual/02. Code Registry.md",
        alias="OBSIDIAN_REGISTRY_PATH",
        description="Relative path for the Code Registry output file",
    )

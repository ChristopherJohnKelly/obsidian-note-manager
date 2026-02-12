"""Context configuration for AssistantService."""

import os

from pydantic import BaseModel, Field


def _default_system_instructions() -> str:
    return os.getenv(
        "OBSIDIAN_SYSTEM_INSTRUCTIONS",
        "30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md",
    )


def _default_tag_glossary() -> str:
    return os.getenv("OBSIDIAN_TAG_GLOSSARY", "00. Inbox/00. Tag Glossary.md")


class ContextConfig(BaseModel):
    """Configuration for context loading (system instructions, glossary, etc.)."""

    system_instructions_path: str = Field(default_factory=_default_system_instructions)
    tag_glossary_path: str = Field(default_factory=_default_tag_glossary)

"""Shared domain models for Obsidian automation.

All models use Pydantic v2. See TRD Section 4.7 for full specifications.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Frontmatter(BaseModel):
    """Structured metadata for an Obsidian note.

    extra='allow' preserves unknown fields from the note's frontmatter
    without causing validation errors.
    """

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    status: str | None = None
    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    code: str | None = None
    folder: str | None = None


class VaultNote(BaseModel):
    """An Obsidian note with metadata and body content."""

    path: Path
    frontmatter: Frontmatter
    body: str = ""


class ValidationResult(BaseModel):
    """A single file's Night Watchman scan result."""

    path: Path
    score: int
    reasons: list[str] = Field(default_factory=list)


class CodeRegistryEntry(BaseModel):
    """A project or area entry with a code field."""

    code: str
    name: str
    type: str = ""
    folder: str


class VaultContext(BaseModel):
    """Aggregated context for a project/area/product, used by the ReAct agent."""

    context_code: str
    root_note: VaultNote
    related_notes: list[VaultNote]
    skeleton: str
    code_registry: str


class FilingProposal(BaseModel):
    """Output of the Filer LLM activity — proposed destination for an inbox note."""

    source_path: Path
    proposed_path: Path
    proposed_frontmatter: Frontmatter
    reasoning: str


class AuditProposal(BaseModel):
    """Output of the NightWatchman LLM activity — proposed fix for a violating note."""

    target_path: Path
    proposed_content: str
    reasons: list[str]
    score: int


class ChatMessage(BaseModel):
    """A single message in a Copilot session chat history."""

    role: Literal["user", "assistant", "tool"]
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_name: str | None = None
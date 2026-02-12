"""Domain entities for Obsidian Vault automation."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Frontmatter(BaseModel):
    """Structured metadata for an Obsidian note."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    status: str | None = None
    title: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    code: str | None = None
    folder: str | None = None


class Note(BaseModel):
    """An Obsidian note with metadata and body content."""

    path: Path
    frontmatter: Frontmatter
    body: str = ""


class Link(BaseModel):
    """A parsed Wiki Link within a note."""

    source: Path  # Note containing the link
    target: str  # Resolved target, e.g. [[Title]] or path
    link_type: Literal["wiki", "md"]  # wiki [[Title]] vs [[file.md]]


class ValidationResult(BaseModel):
    """A single file's Night Watchman scan result."""

    path: Path
    score: int
    reasons: list[str] = Field(default_factory=list)


class CodeRegistryEntry(BaseModel):
    """A Code Registry entry from Areas/Projects (project or area with code)."""

    code: str
    name: str
    type: str = ""
    folder: str

"""Shared utility functions for vault operations."""

import re
from pathlib import Path


def sanitize_filename(title: str, max_length: int = 200) -> str:
    """
    Sanitize a title to create a valid filename.

    Allows letters, numbers, spaces, dots, dashes, underscores, parentheses.

    Args:
        title: The title to sanitize.
        max_length: Maximum filename length.

    Returns:
        Sanitized filename (without extension).
    """
    safe_chars = "".join(
        c if (c.isalnum() or c in " .-_()") else "-" for c in title
    )
    safe_chars = re.sub(r"[-_\s]+", "-", safe_chars)
    safe_chars = safe_chars.strip("-")
    if len(safe_chars) > max_length:
        safe_chars = safe_chars[:max_length].rstrip("-")
    if not safe_chars:
        safe_chars = "untitled"
    return safe_chars


def get_safe_path(target_path: Path) -> Path:
    """
    Return a path that does not exist, appending -1, -2, etc. if needed.

    Args:
        target_path: Desired file path (can be absolute or relative).

    Returns:
        Path that does not exist.
    """
    if not target_path.exists():
        return target_path

    counter = 1
    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent

    while True:
        new_name = f"{stem}-{counter}{suffix}"
        candidate = parent / new_name
        if not candidate.exists():
            return candidate
        counter += 1

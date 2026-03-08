"""Helpers for the Chainlit Copilot UI."""

from pathlib import Path

from src_v2.infrastructure.file_system.adapters import EXCLUDED_DIRS


def scan_top_level_dirs(vault_root: Path) -> list[str]:
    """Scan vault root for top-level directories, excluding hidden and system dirs."""
    if not vault_root.exists() or not vault_root.is_dir():
        return []
    dirs = [
        p.name
        for p in vault_root.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and p.name not in EXCLUDED_DIRS
    ]
    return sorted(dirs)

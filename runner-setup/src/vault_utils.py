"""
Shared utility functions for vault operations.
"""
from pathlib import Path

# Standard excluded directories that should be skipped during vault operations
EXCLUDED_DIRS = {
    "99. System",
    "00. Inbox",
    ".git",
    ".obsidian",
    ".trash"
}


def is_excluded(path: Path, vault_root: Path) -> bool:
    """
    Check if a path is in an excluded directory.
    
    Args:
        path: Full path to check
        vault_root: Root path of the vault
        
    Returns:
        bool: True if path should be excluded
    """
    try:
        rel_path = path.relative_to(vault_root)
        parts = rel_path.parts
        return any(excluded in parts for excluded in EXCLUDED_DIRS)
    except ValueError:
        # Path is not relative to vault_root
        return True

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


def get_safe_path(target_path: Path) -> Path:
    """
    Returns a path that doesn't exist, appending -N if needed.
    
    Args:
        target_path: Desired file path
        
    Returns:
        Path: Safe path that doesn't exist
    """
    if not target_path.exists():
        return target_path
    
    # Collision handling: append -1, -2, etc.
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

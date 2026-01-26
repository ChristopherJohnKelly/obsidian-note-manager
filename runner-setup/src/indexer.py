import os
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .vault_utils import is_excluded
except ImportError:
    # Fallback for when run as script
    from vault_utils import is_excluded


class VaultIndexer:
    def __init__(self, vault_root: str):
        """
        Initialize the Vault Indexer with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)
        area_folder = os.getenv("OBSIDIAN_AREAS_FOLDER", "30. Areas")
        projects_folder = os.getenv("OBSIDIAN_PROJECTS_FOLDER", "20. Projects")
        resources_folder = os.getenv("OBSIDIAN_RESOURCES_FOLDER", "40. Resources")
        self.scan_dirs = [
            area_folder,
            projects_folder,
            resources_folder
        ]

    def _normalize_aliases(self, aliases) -> list:
        """
        Normalize aliases to a list format.
        Handles list, comma-separated string, or single string.
        
        Args:
            aliases: Aliases from frontmatter (various formats)
            
        Returns:
            list: Normalized list of aliases
        """
        if not aliases:
            return []
        
        if isinstance(aliases, list):
            return [str(a).strip() for a in aliases if a]
        
        if isinstance(aliases, str):
            # Check if comma-separated
            if ',' in aliases:
                return [a.strip() for a in aliases.split(',') if a.strip()]
            else:
                return [aliases.strip()] if aliases.strip() else []
        
        return []

    def build_skeleton(self) -> str:
        """
        Scans vault and returns a formatted string of valid link targets.
        
        Returns:
            str: Formatted list of entries, one per line
        """
        skeleton = []
        print("🕸️  Indexing Vault...")
        
        for scan_dir in self.scan_dirs:
            scan_path = self.vault_root / scan_dir
            if not scan_path.exists():
                continue
            
            for file_path in scan_path.rglob("*.md"):
                if is_excluded(file_path, self.vault_root):
                    continue
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        post = frontmatter.loads(f.read())
                    
                    # Extract title (fallback to filename)
                    title = post.metadata.get("title", file_path.stem)
                    
                    # Extract and normalize aliases
                    aliases = self._normalize_aliases(post.metadata.get("aliases"))
                    
                    # Build relative path
                    rel_path = file_path.relative_to(self.vault_root)
                    
                    # Format entry
                    entry = f"- [[{title}]] ({rel_path})"
                    if aliases:
                        aliases_str = ", ".join(aliases)
                        entry += f" [Aliases: {aliases_str}]"
                    
                    skeleton.append(entry)
                    
                except Exception:
                    continue  # Skip files with errors
        
        result = "\n".join(skeleton)
        print(f"✅ Indexed {len(skeleton)} notes")
        return result

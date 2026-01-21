import frontmatter
from pathlib import Path


class VaultIndexer:
    def __init__(self, vault_root: str):
        """
        Initialize the Vault Indexer with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)
        self.excluded_dirs = {
            "00. Inbox",
            "99. System",
            ".git",
            ".obsidian",
            ".trash"
        }
        self.scan_dirs = [
            "30. Areas",
            "20. Projects",
            "40. Resources"
        ]

    def _is_excluded(self, path: Path) -> bool:
        """
        Check if a path is in an excluded directory.
        
        Args:
            path: Full path to check
            
        Returns:
            bool: True if path should be excluded
        """
        try:
            rel_path = path.relative_to(self.vault_root)
            parts = rel_path.parts
            return any(excluded in parts for excluded in self.excluded_dirs)
        except ValueError:
            # Path is not relative to vault_root
            return True

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
                if self._is_excluded(file_path):
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

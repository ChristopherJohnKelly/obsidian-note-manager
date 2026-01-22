import os
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .indexer import VaultIndexer
except ImportError:
    # Fallback for when run as script
    from indexer import VaultIndexer


class ContextLoader:
    def __init__(self, vault_root: str):
        """
        Initialize the context loader with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)
        self.indexer = VaultIndexer(vault_root)

    def read_file(self, relative_path: str) -> str:
        """
        Reads a file from the vault, returning empty string if not found.
        
        Args:
            relative_path: Relative path from vault root to the file
            
        Returns:
            str: File contents, or empty string if file not found
        """
        file_path = self.vault_root / relative_path
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                print(f"⚠️ Warning: Context file not found: {relative_path}")
                return ""
        except Exception as e:
            print(f"❌ Error reading {relative_path}: {e}")
            return ""

    def build_code_registry(self) -> str:
        """
        Dynamically scans Areas and Projects directories to build a Code Registry table.
        Extracts code, type, name (filename), and folder from frontmatter of all .md files.
        
        Returns:
            str: Markdown table string with Code Registry entries
        """
        registry = ["| Code | Name | Type | Folder |", "| :--- | :--- | :--- | :--- |"]
        scan_paths = [
            self.vault_root / "30. Areas",
            self.vault_root / "20. Projects"
        ]
        
        for root_path in scan_paths:
            if not root_path.exists():
                continue
                
            for file_path in root_path.rglob("*.md"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        post = frontmatter.loads(f.read())
                    
                    code = post.metadata.get("code")
                    if not code:
                        continue  # Skip files without code (silently)
                    
                    name = file_path.stem
                    type_val = post.metadata.get("type", "")
                    folder = str(file_path.relative_to(self.vault_root).parent)
                    
                    registry.append(f"| {code} | {name} | {type_val} | {folder} |")
                except Exception:
                    continue  # Skip files with errors (I/O, parsing, etc.)
        
        return "\n".join(registry)

    def get_project_registry(self) -> dict:
        """
        Builds a dictionary mapping folder paths to project codes.
        
        Returns:
            dict: Mapping of folder paths (relative to vault root) to codes
            Example: {"20. Projects/Pepsi": "PEPS", "30. Areas/Clients/Coca-Cola": "COKE"}
        """
        registry = {}
        scan_paths = [
            self.vault_root / "30. Areas",
            self.vault_root / "20. Projects"
        ]
        
        for root_path in scan_paths:
            if not root_path.exists():
                continue
                
            for file_path in root_path.rglob("*.md"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        post = frontmatter.loads(f.read())
                    
                    code = post.metadata.get("code")
                    if not code:
                        continue
                    
                    folder = str(file_path.relative_to(self.vault_root).parent)
                    registry[folder] = code
                except Exception:
                    continue
        
        return registry

    def get_full_context(self) -> str:
        """
        Aggregates all context files into a single string.
        
        Returns:
            str: Combined context from System Instructions, Tag Glossary, Code Registry, and Vault Map
        """
        # 1. System Instructions (The Rules)
        instructions = self.read_file(
            "30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md"
        )
        
        # 2. Tag Glossary (The Taxonomy)
        glossary = self.read_file("00. Inbox/00. Tag Glossary.md")
        
        # 3. Code Registry (The Project Codes)
        # Dynamically scanned from Areas and Projects directories
        registry = self.build_code_registry()
        
        # 4. Vault Map (The Skeleton Graph for Deep Linking)
        skeleton = self.indexer.build_skeleton()

        return f"""
=== SYSTEM INSTRUCTIONS ===
{instructions}

=== TAG GLOSSARY ===
{glossary}

=== CODE REGISTRY ===
{registry}

=== VAULT MAP (Use these for Deep Links) ===
{skeleton}
"""

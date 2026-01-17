import os
from pathlib import Path


class ContextLoader:
    def __init__(self, vault_root: str):
        """
        Initialize the context loader with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)

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

    def get_full_context(self) -> str:
        """
        Aggregates all context files into a single string.
        
        Returns:
            str: Combined context from System Instructions, Tag Glossary, and Code Registry
        """
        # 1. System Instructions (The Rules)
        instructions = self.read_file(
            "30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md"
        )
        
        # 2. Tag Glossary (The Taxonomy)
        glossary = self.read_file("00. Inbox/00. Tag Glossary.md")
        
        # 3. Code Registry (The Project Codes)
        # Note: Ensure this file exists or the AI won't know your codes!
        registry = self.read_file("00. Inbox/00. Code Registry.md")

        return f"""
=== SYSTEM INSTRUCTIONS ===
{instructions}

=== TAG GLOSSARY ===
{glossary}

=== CODE REGISTRY ===
{registry}
"""

import os
import sys
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .response_parser import ResponseParser
except ImportError:
    from response_parser import ResponseParser


class NoteFiler:
    def __init__(self, vault_root: str):
        """
        Initialize the Note Filer with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)
        self.review_dir = self.vault_root / "00. Inbox/1. Review Queue"
        self.parser = ResponseParser()

    def _get_safe_path(self, target_path: Path) -> Path:
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

    def file_approved_notes(self) -> int:
        """
        Executes proposals with 'librarian: file' by creating multiple files.
        
        Parses proposal notes, extracts files using ResponseParser, creates
        necessary directories, writes files with collision handling, and
        deletes the proposal after successful execution.
        
        Returns:
            int: Total number of NEW files created (not proposals processed)
        """
        if not self.review_dir.exists():
            return 0

        proposals = list(self.review_dir.glob("*.md"))
        
        if not proposals:
            return 0
        
        print(f"📂 Filer scanning {len(proposals)} proposals in Review Queue...")

        files_created_total = 0

        for prop_path in proposals:
            try:
                # 1. Load Proposal
                with open(prop_path, "r", encoding="utf-8") as f:
                    post = frontmatter.loads(f.read())
                
                # Check for the trigger property
                if post.metadata.get("librarian") != "file":
                    continue

                print(f"🚀 Executing proposal: {prop_path.name}")
                
                # 2. Parse Body to get file contents
                # The body contains the %%FILE%% blocks from the LLM response
                parsed = self.parser.parse(post.content)
                
                if not parsed["files"]:
                    print(f"⚠️ Warning: Proposal {prop_path.name} has no %%FILE%% blocks. Skipping.")
                    continue

                # 3. Write Files
                files_created_this_proposal = 0
                for file_data in parsed["files"]:
                    rel_path = file_data["path"]
                    content = file_data["content"]
                    
                    # Security check: prevent path traversal
                    if ".." in rel_path or rel_path.startswith("/"):
                        print(f"❌ Unsafe path skipped: {rel_path}")
                        continue

                    # Resolve full path
                    full_target_path = self.vault_root / rel_path
                    
                    # Create parent directories
                    full_target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Handle collisions
                    safe_target = self._get_safe_path(full_target_path)
                    
                    # Write file
                    with open(safe_target, "w", encoding="utf-8") as f:
                        f.write(content)
                    
                    print(f"✅ Created: {safe_target.relative_to(self.vault_root)}")
                    files_created_this_proposal += 1
                    files_created_total += 1

                # 4. Cleanup Proposal (only if files were created)
                if files_created_this_proposal > 0:
                    prop_path.unlink()
                    print(f"🗑️ Deleted proposal: {prop_path.name}")
                else:
                    print(f"⚠️ No files created from proposal {prop_path.name}, keeping proposal.")

            except Exception as e:
                print(f"❌ Filer Error on {prop_path.name}: {e}")
                import traceback
                traceback.print_exc()
                # Continue processing remaining proposals

        return files_created_total

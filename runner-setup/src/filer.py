import os
import sys
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports (for future use)
# Currently no dependencies, but pattern matches other modules


class NoteFiler:
    def __init__(self, vault_root: str):
        """
        Initialize the Note Filer with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)
        self.review_dir = self.vault_root / "00. Inbox/1. Review Queue"

    def file_approved_notes(self) -> int:
        """
        Moves notes with 'librarian: file' to their target folder.
        
        Scans the Review Queue for notes with librarian property set to "file",
        extracts the folder path from frontmatter, and moves them to their
        final destination. Removes the librarian property after filing.
        
        Returns:
            int: Number of notes successfully filed
        """
        if not self.review_dir.exists():
            return 0

        files = list(self.review_dir.glob("*.md"))
        
        if not files:
            return 0
        
        print(f"📂 Filer scanning {len(files)} notes in Review Queue...")

        filed_count = 0
        
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    post = frontmatter.loads(f.read())
                
                # Check for the trigger property
                if post.metadata.get("librarian") != "file":
                    continue

                # Get destination folder
                target_folder_rel = post.metadata.get("folder")
                if not target_folder_rel:
                    print(f"⚠️ Skipping {file_path.name}: 'librarian: file' set but no 'folder' property.")
                    continue

                # Build destination path
                target_dir = self.vault_root / target_folder_rel
                target_dir.mkdir(parents=True, exist_ok=True)

                # Remove the ephemeral librarian property
                del post.metadata["librarian"]

                # Handle filename collisions (dash format, matching main.py)
                target_path = target_dir / file_path.name
                counter = 1
                while target_path.exists():
                    stem = file_path.stem
                    target_path = target_dir / f"{stem}-{counter}.md"
                    counter += 1

                # Write file to destination
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(frontmatter.dumps(post))
                
                # Delete original file from Review Queue
                file_path.unlink()
                
                print(f"✅ Filed: {file_path.name} -> {target_folder_rel}")
                filed_count += 1

            except Exception as e:
                print(f"❌ Filer Error on {file_path.name}: {e}")
                import traceback
                traceback.print_exc()
                # Continue processing remaining files

        return filed_count

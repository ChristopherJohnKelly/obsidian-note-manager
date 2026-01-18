import os
import sys
import re
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .processor import NoteProcessor
    from .git_ops import GitOps
    from .filer import NoteFiler
except ImportError:
    # Fallback for when run as script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from processor import NoteProcessor
    from git_ops import GitOps
    from filer import NoteFiler

# Configuration - use environment variable or default to current directory
VAULT_ROOT = os.getenv("OBSIDIAN_VAULT_ROOT", os.getcwd())
CAPTURE_DIR = Path(VAULT_ROOT) / "00. Inbox/0. Capture"
REVIEW_DIR = Path(VAULT_ROOT) / "00. Inbox/1. Review Queue"


def clean_markdown(content: str) -> str:
    """
    Removes any existing frontmatter from the raw note content.
    
    Args:
        content: Raw note content that may contain frontmatter
        
    Returns:
        str: Cleaned note body without frontmatter
    """
    if content.startswith("---"):
        try:
            post = frontmatter.loads(content)
            return post.content
        except Exception:
            # If parsing fails, return original content
            pass
    return content


def sanitize_filename(title: str, max_length: int = 200) -> str:
    """
    Sanitizes a title to create a valid filename.
    Allows letters, numbers, spaces, dots, dashes, underscores, parentheses.
    
    Args:
        title: The title to sanitize
        max_length: Maximum filename length
        
    Returns:
        str: Sanitized filename (without extension)
    """
    # Replace problematic characters with dashes
    safe_chars = "".join([
        c if (c.isalnum() or c in " .-_()") else "-"
        for c in title
    ])
    
    # Collapse multiple dashes/spaces into single dash
    safe_chars = re.sub(r'[-_\s]+', '-', safe_chars)
    
    # Remove leading/trailing dashes
    safe_chars = safe_chars.strip('-')
    
    # Truncate if too long
    if len(safe_chars) > max_length:
        safe_chars = safe_chars[:max_length].rstrip('-')
    
    # Ensure we have at least something
    if not safe_chars:
        safe_chars = "untitled"
    
    return safe_chars


def main():
    """Main orchestrator function."""
    print("🤖 Librarian Starting...")
    
    # 1. Setup
    processor = NoteProcessor(VAULT_ROOT)
    git = GitOps(VAULT_ROOT)
    filer = NoteFiler(VAULT_ROOT)
    
    # Ensure Review Queue directory exists
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    
    # 2. Phase 1: Filing Approved Notes
    filed_count = filer.file_approved_notes()
    
    # 3. Phase 2: Scan Capture Directory
    files_to_process = list(CAPTURE_DIR.glob("*.md"))
    
    if not files_to_process:
        print("📭 Capture folder is empty.")
        # Continue to commit logic if files were filed
        if filed_count == 0:
            print("💤 No notes to file or process. Exiting.")
            return
    else:
        print(f"🔎 Found {len(files_to_process)} notes to process.")
    
    # 4. Process Loop (only if files exist)
    processed_count = 0
    
    if files_to_process:
        for file_path in files_to_process:
            print(f"\n📄 Processing: {file_path.name}...")
            
            try:
                # Read raw content
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                # Clean existing frontmatter from body
                clean_body = clean_markdown(raw_content)

                # AI Magic - Get metadata dict from processor
                metadata_dict = processor.process_note(clean_body)
                
                # Set ephemeral property for review workflow
                metadata_dict['librarian'] = 'review'
                
                # Get title from metadata or use original filename
                title = metadata_dict.get('title', file_path.stem)
                
                # Sanitize filename
                safe_filename = sanitize_filename(title)
                new_filename = f"{safe_filename}.md"
                
                # Construct target path
                target_path = REVIEW_DIR / new_filename
                
                # Handle filename conflicts (append number if exists)
                counter = 1
                while target_path.exists():
                    new_filename = f"{safe_filename}-{counter}.md"
                    target_path = REVIEW_DIR / new_filename
                    counter += 1
                
                # Create frontmatter Post with cleaned body + metadata
                final_note = frontmatter.Post(clean_body, **metadata_dict)
                
                # Write to Review Queue
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(frontmatter.dumps(final_note))
                
                print(f"✅ Saved to: {target_path.name}")
                
                # Delete original file
                os.remove(file_path)
                processed_count += 1

            except Exception as e:
                print(f"❌ Failed to process {file_path.name}: {e}")
                import traceback
                traceback.print_exc()
                # Continue processing remaining files

    # 5. Commit Changes
    total_changes = filed_count + processed_count
    if total_changes > 0:
        try:
            msg_parts = []
            if filed_count > 0:
                msg_parts.append(f"Filed {filed_count}")
            if processed_count > 0:
                msg_parts.append(f"Ingested {processed_count}")
            
            commit_msg = f"🤖 Librarian: {', '.join(msg_parts)} [skip ci]"
            git.commit_and_push(commit_msg)
        except Exception as e:
            print(f"⚠️ Warning: Failed to commit/push changes: {e}")
            print("   Changes are saved locally but not pushed to remote.")
    else:
        print("💤 No notes were filed or processed. Nothing to commit.")


if __name__ == "__main__":
    main()

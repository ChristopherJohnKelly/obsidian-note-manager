import os
import sys
import json
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .response_parser import ResponseParser
except ImportError:
    from response_parser import ResponseParser

# #region agent log
DEBUG_LOG_PATH = "/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log"
def _debug_log(location, message, data, hypothesis_id=None):
    try:
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(__import__("time").time() * 1000)
            }) + "\n")
    except: pass
# #endregion


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
        # #region agent log
        _debug_log("filer.py:51", "file_approved_notes called", {"vault_root": str(self.vault_root), "review_dir": str(self.review_dir)}, "A")
        # #endregion
        
        if not self.review_dir.exists():
            # #region agent log
            _debug_log("filer.py:63", "review_dir does not exist", {"review_dir": str(self.review_dir)}, "B")
            # #endregion
            return 0

        proposals = list(self.review_dir.glob("*.md"))
        
        # #region agent log
        _debug_log("filer.py:65", "proposals found", {"count": len(proposals), "review_dir": str(self.review_dir), "proposal_names": [str(p.name) for p in proposals]}, "C")
        # #endregion
        
        if not proposals:
            # #region agent log
            _debug_log("filer.py:68", "no proposals found", {"review_dir": str(self.review_dir)}, "C")
            # #endregion
            return 0
        
        print(f"📂 Filer scanning {len(proposals)} proposals in Review Queue...")

        files_created_total = 0

        for prop_path in proposals:
            try:
                # 1. Load Proposal
                with open(prop_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                post = frontmatter.loads(raw_content)
                
                # #region agent log
                _debug_log("filer.py:77", "proposal loaded", {"prop_name": prop_path.name, "metadata_keys": list(post.metadata.keys()), "librarian_value": post.metadata.get("librarian"), "body_length": len(post.content)}, "D")
                # #endregion
                
                # Check for the trigger property
                librarian_value = post.metadata.get("librarian")
                # #region agent log
                _debug_log("filer.py:81", "checking librarian property", {"prop_name": prop_path.name, "librarian_value": librarian_value, "is_file": librarian_value == "file"}, "D")
                # #endregion
                
                if librarian_value != "file":
                    # #region agent log
                    _debug_log("filer.py:82", "skipping proposal - librarian not 'file'", {"prop_name": prop_path.name, "librarian_value": librarian_value}, "D")
                    # #endregion
                    continue

                print(f"🚀 Executing proposal: {prop_path.name}")
                
                # 2. Parse Body to get file contents
                # The body contains the %%FILE%% blocks from the LLM response
                # #region agent log
                _debug_log("filer.py:88", "parsing proposal body", {"prop_name": prop_path.name, "body_preview": post.content[:200]}, "E")
                # #endregion
                parsed = self.parser.parse(post.content)
                
                # #region agent log
                _debug_log("filer.py:89", "parser result", {"prop_name": prop_path.name, "files_count": len(parsed.get("files", [])), "has_explanation": bool(parsed.get("explanation")), "file_paths": [f.get("path") for f in parsed.get("files", [])]}, "E")
                # #endregion
                
                if not parsed["files"]:
                    print(f"⚠️ Warning: Proposal {prop_path.name} has no %%FILE%% blocks. Skipping.")
                    # #region agent log
                    _debug_log("filer.py:91", "no files found in proposal", {"prop_name": prop_path.name}, "E")
                    # #endregion
                    continue

                # 3. Write Files
                files_created_this_proposal = 0
                for file_data in parsed["files"]:
                    rel_path = file_data["path"]
                    content = file_data["content"]
                    
                    # #region agent log
                    _debug_log("filer.py:96", "processing file", {"prop_name": prop_path.name, "rel_path": rel_path, "content_length": len(content)}, "F")
                    # #endregion
                    
                    # Security check: prevent path traversal
                    if ".." in rel_path or rel_path.startswith("/"):
                        print(f"❌ Unsafe path skipped: {rel_path}")
                        # #region agent log
                        _debug_log("filer.py:101", "unsafe path rejected", {"rel_path": rel_path}, "F")
                        # #endregion
                        continue

                    # Resolve full path
                    full_target_path = self.vault_root / rel_path
                    
                    # #region agent log
                    _debug_log("filer.py:106", "path resolved", {"rel_path": rel_path, "full_target_path": str(full_target_path), "vault_root": str(self.vault_root)}, "F")
                    # #endregion
                    
                    # Create parent directories
                    full_target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # #region agent log
                    _debug_log("filer.py:109", "directories created", {"parent_dir": str(full_target_path.parent), "exists": full_target_path.parent.exists()}, "F")
                    # #endregion
                    
                    # Handle collisions
                    safe_target = self._get_safe_path(full_target_path)
                    
                    # #region agent log
                    _debug_log("filer.py:112", "safe path determined", {"original": str(full_target_path), "safe": str(safe_target)}, "F")
                    # #endregion
                    
                    # Write file
                    with open(safe_target, "w", encoding="utf-8") as f:
                        f.write(content)
                    
                    # #region agent log
                    _debug_log("filer.py:115", "file written", {"safe_target": str(safe_target), "file_exists": safe_target.exists()}, "F")
                    # #endregion
                    
                    print(f"✅ Created: {safe_target.relative_to(self.vault_root)}")
                    files_created_this_proposal += 1
                    files_created_total += 1

                # 4. Cleanup Proposal (only if files were created)
                if files_created_this_proposal > 0:
                    prop_path.unlink()
                    print(f"🗑️ Deleted proposal: {prop_path.name}")
                    # #region agent log
                    _debug_log("filer.py:124", "proposal deleted", {"prop_name": prop_path.name, "files_created": files_created_this_proposal}, "F")
                    # #endregion
                else:
                    print(f"⚠️ No files created from proposal {prop_path.name}, keeping proposal.")
                    # #region agent log
                    _debug_log("filer.py:127", "proposal kept - no files created", {"prop_name": prop_path.name}, "F")
                    # #endregion

            except Exception as e:
                print(f"❌ Filer Error on {prop_path.name}: {e}")
                import traceback
                traceback.print_exc()
                # #region agent log
                _debug_log("filer.py:129", "exception caught", {"prop_name": prop_path.name, "error": str(e), "error_type": type(e).__name__}, "G")
                # #endregion
                # Continue processing remaining proposals

        # #region agent log
        _debug_log("filer.py:135", "file_approved_notes completed", {"files_created_total": files_created_total}, "A")
        # #endregion
        return files_created_total

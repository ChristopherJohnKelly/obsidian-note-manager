import os
import json
from pathlib import Path
from datetime import datetime, timedelta


class StateManager:
    def __init__(self, vault_root: str):
        """
        Initialize the State Manager with the vault root path.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
        """
        self.vault_root = Path(vault_root)
        history_file = os.getenv("OBSIDIAN_HISTORY_FILE", "99. System/maintenance_history.json")
        self.history_file = self.vault_root / history_file
        self.history = self._load_history()

    def _load_history(self) -> dict:
        """
        Load history from JSON file.
        
        Returns:
            dict: History data with default structure if file doesn't exist
        """
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Validate structure: ensure 'files' is a dict
                    if not isinstance(data, dict):
                        print(f"⚠️ Warning: History file has invalid root structure, using defaults")
                        return {"last_run": None, "files": {}}
                    # Ensure 'files' key exists and is a dict
                    if "files" not in data or not isinstance(data.get("files"), dict):
                        data["files"] = {}
                    # Ensure 'last_run' is None or a string
                    if "last_run" in data and not (data["last_run"] is None or isinstance(data["last_run"], str)):
                        data["last_run"] = None
                    return data
            except Exception as e:
                print(f"⚠️ Warning: Failed to load history: {e}")
                return {"last_run": None, "files": {}}
        return {"last_run": None, "files": {}}

    def save_history(self):
        """Save history to JSON file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history["last_run"] = datetime.now().isoformat()
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"⚠️ Warning: Failed to save history: {e}")

    def is_cooldown_active(self, rel_path: str, days: int = 7) -> bool:
        """
        Returns True if file was proposed within last N days.
        
        Args:
            rel_path: Relative path to the file from vault root
            days: Cooldown period in days (default: 7)
            
        Returns:
            bool: True if cooldown is active (should skip), False otherwise
        """
        files = self.history.get("files", {})
        if not isinstance(files, dict) or rel_path not in files:
            return False
        
        file_entry = files[rel_path]
        if not isinstance(file_entry, dict):
            return False
        
        last_proposed_str = file_entry.get("last_proposed")
        if not last_proposed_str:
            return False

        try:
            last_proposed = datetime.fromisoformat(last_proposed_str)
            if datetime.now() - last_proposed < timedelta(days=days):
                return True
        except Exception:
            return False
        
        return False

    def record_scan(self, rel_path: str, score: int):
        """
        Record that a file was scanned and proposed as a maintenance candidate.
        
        Args:
            rel_path: Relative path to the file from vault root
            score: Quality deficit score
        """
        if "files" not in self.history or not isinstance(self.history.get("files"), dict):
            self.history["files"] = {}
        
        files = self.history["files"]
        if rel_path not in files or not isinstance(files.get(rel_path), dict):
            files[rel_path] = {}
        
        now = datetime.now().isoformat()
        files[rel_path]["last_scanned"] = now
        files[rel_path]["last_proposed"] = now
        files[rel_path]["last_score"] = score

    def filter_candidates(self, candidates: list) -> list:
        """
        Filter out candidates in cooldown period.
        
        Args:
            candidates: List of candidate dicts with "path" key
            
        Returns:
            list: Filtered list excluding candidates in cooldown
        """
        filtered = []
        for candidate in candidates:
            if not self.is_cooldown_active(candidate["path"]):
                filtered.append(candidate)
        return filtered

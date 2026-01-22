import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .vault_utils import is_excluded
except ImportError:
    # Fallback for when run as script
    from vault_utils import is_excluded


class VaultScanner:
    def __init__(self, vault_root: str, context_loader):
        """
        Initialize the Vault Scanner with the vault root and context loader.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
            context_loader: ContextLoader instance to get project registry
        """
        self.vault_root = Path(vault_root)
        self.registry = context_loader.get_project_registry()
        self.bad_titles = {"untitled", "meeting", "note", "call"}

    def _find_expected_code(self, folder_path: str) -> str:
        """
        Find the expected project code for a folder by walking up the directory tree.
        
        Args:
            folder_path: Relative folder path from vault root
            
        Returns:
            str: Expected code if found, None otherwise
        """
        # Walk up the directory tree to find most specific match
        path_parts = Path(folder_path).parts
        for i in range(len(path_parts), 0, -1):
            check_path = str(Path(*path_parts[:i]))
            if check_path in self.registry:
                return self.registry[check_path]
        return None

    def _score_file(self, path: Path) -> tuple:
        """
        Calculate quality deficit score for a single file.
        
        Args:
            path: Full path to the file
            
        Returns:
            tuple: (score, reasons_list)
        """
        score = 0
        reasons = []
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                post = frontmatter.loads(f.read())
            
            # Rule 1: Missing Frontmatter (+10)
            if not post.metadata.get('aliases') and not post.metadata.get('tags'):
                score += 10
                reasons.append("Missing aliases/tags")
            
            # Rule 2: Code Mismatch (+50)
            rel_path = path.relative_to(self.vault_root)
            folder_path = str(rel_path.parent)
            expected_code = self._find_expected_code(folder_path)
            
            if expected_code:
                filename_stem = path.stem
                if not filename_stem.startswith(expected_code):
                    score += 50
                    reasons.append(f"Missing Project Code: {expected_code}")
            
            # Rule 3: Bad Title (+20)
            if path.stem.lower() in self.bad_titles:
                score += 20
                reasons.append("Generic Filename")
            
        except Exception as e:
            # Silently skip files with errors
            pass
        
        return score, reasons

    def scan(self) -> list:
        """
        Scan the vault and identify quality issues.
        
        Returns:
            list: List of candidate dicts with "path", "score", and "reasons" keys
        """
        candidates = []
        dirs_to_scan = [
            self.vault_root / "20. Projects",
            self.vault_root / "30. Areas"
        ]
        
        for root_dir in dirs_to_scan:
            if not root_dir.exists():
                continue
            
            for file_path in root_dir.rglob("*.md"):
                if is_excluded(file_path, self.vault_root):
                    continue
                
                score, reasons = self._score_file(file_path)
                if score > 0:
                    rel_path = str(file_path.relative_to(self.vault_root))
                    candidates.append({
                        "path": rel_path,
                        "score": score,
                        "reasons": reasons
                    })
        
        return candidates

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
        
        # #region agent log
        import json
        try:
            with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"context_loader.py:34","message":"read_file called","data":{"relative_path":relative_path,"vault_root":str(self.vault_root),"full_path":str(file_path),"file_exists":file_path.exists()},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        try:
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # #region agent log
                    try:
                        with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"context_loader.py:42","message":"file read success","data":{"relative_path":relative_path,"content_length":len(content)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                    except: pass
                    # #endregion
                    
                    return content
            else:
                print(f"⚠️ Warning: Context file not found: {relative_path}")
                
                # #region agent log
                try:
                    with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"context_loader.py:50","message":"file not found","data":{"relative_path":relative_path,"full_path":str(file_path)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                except: pass
                # #endregion
                
                return ""
        except Exception as e:
            print(f"❌ Error reading {relative_path}: {e}")
            
            # #region agent log
            try:
                with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"context_loader.py:57","message":"file read error","data":{"relative_path":relative_path,"error":str(e)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            except: pass
            # #endregion
            
            return ""

    def _scan_code_files(self) -> list:
        """
        Common scanning logic to extract code information from Areas and Projects directories.
        
        Returns:
            list: List of dicts with keys: code, name, type, folder
        """
        results = []
        area_folder = os.getenv("OBSIDIAN_AREAS_FOLDER", "30. Areas")
        projects_folder = os.getenv("OBSIDIAN_PROJECTS_FOLDER", "20. Projects")
        scan_paths = [
            self.vault_root / area_folder,
            self.vault_root / projects_folder
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
                    
                    results.append({
                        "code": code,
                        "name": name,
                        "type": type_val,
                        "folder": folder
                    })
                except Exception:
                    continue  # Skip files with errors (I/O, parsing, etc.)
        
        return results

    def build_code_registry(self) -> str:
        """
        Dynamically scans Areas and Projects directories to build a Code Registry table.
        Extracts code, type, name (filename), and folder from frontmatter of all .md files.
        
        Returns:
            str: Markdown table string with Code Registry entries
        """
        registry = ["| Code | Name | Type | Folder |", "| :--- | :--- | :--- | :--- |"]
        
        for entry in self._scan_code_files():
            registry.append(f"| {entry['code']} | {entry['name']} | {entry['type']} | {entry['folder']} |")
        
        return "\n".join(registry)

    def get_project_registry(self) -> dict:
        """
        Builds a dictionary mapping folder paths to project codes.
        
        Returns:
            dict: Mapping of folder paths (relative to vault root) to codes
            Example: {"20. Projects/Pepsi": "PEPS", "30. Areas/Clients/Coca-Cola": "COKE"}
        """
        registry = {}
        
        for entry in self._scan_code_files():
            registry[entry["folder"]] = entry["code"]
        
        return registry

    def get_full_context(self) -> str:
        """
        Aggregates all context files into a single string.
        
        Returns:
            str: Combined context from System Instructions, Tag Glossary, Code Registry, and Vault Map
        """
        # #region agent log
        import json
        try:
            with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"context_loader.py:119","message":"get_full_context entry","data":{"vault_root":str(self.vault_root)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # 1. System Instructions (The Rules)
        system_instructions = os.getenv(
            "OBSIDIAN_SYSTEM_INSTRUCTIONS",
            "30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md"
        )
        
        # #region agent log
        try:
            with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"context_loader.py:132","message":"system_instructions env var","data":{"env_var_value":system_instructions,"env_var_set":os.getenv("OBSIDIAN_SYSTEM_INSTRUCTIONS") is not None,"full_path":str(self.vault_root / system_instructions),"file_exists":(self.vault_root / system_instructions).exists()},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        instructions = self.read_file(system_instructions)
        
        # #region agent log
        try:
            with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"context_loader.py:140","message":"instructions read result","data":{"instructions_length":len(instructions),"instructions_empty":len(instructions) == 0},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        # 2. Tag Glossary (The Taxonomy)
        tag_glossary = os.getenv("OBSIDIAN_TAG_GLOSSARY", "00. Inbox/00. Tag Glossary.md")
        
        # #region agent log
        try:
            with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"context_loader.py:147","message":"tag_glossary env var","data":{"env_var_value":tag_glossary,"env_var_set":os.getenv("OBSIDIAN_TAG_GLOSSARY") is not None,"full_path":str(self.vault_root / tag_glossary),"file_exists":(self.vault_root / tag_glossary).exists()},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
        glossary = self.read_file(tag_glossary)
        
        # #region agent log
        try:
            with open('/Users/christopherkelly/myrepos/obsidian-note-manager/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"context_loader.py:153","message":"glossary read result","data":{"glossary_length":len(glossary),"glossary_empty":len(glossary) == 0},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        except: pass
        # #endregion
        
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

#!/usr/bin/env python3
"""
Vault Maintenance Scanner - The Night Watchman

Scans the vault for quality issues and identifies the top maintenance candidates.
"""

import os
import sys
import time
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .scanner import VaultScanner
    from .state_manager import StateManager
    from .context_loader import ContextLoader
    from .llm_client import LLMClient
    from .fixer import MaintenanceFixer
except ImportError:
    # Fallback for when run as script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scanner import VaultScanner
    from state_manager import StateManager
    from context_loader import ContextLoader
    from llm_client import LLMClient
    from fixer import MaintenanceFixer
<<<<<<< HEAD


def check_conflict(file_path: Path) -> bool:
    """
    Returns True if the file has been modified in the last hour.
    Prevents the bot from interfering with active work.
    
    Args:
        file_path: Path object to the file to check
        
    Returns:
        bool: True if file was modified recently (conflict), False otherwise
    """
    try:
        if not file_path.exists():
            return False
        
        mtime = file_path.stat().st_mtime
        time_since_modification = time.time() - mtime
        
        # 1 hour = 3600 seconds
        if time_since_modification < 3600:
            return True
    except (OSError, FileNotFoundError):
        # If we can't check, assume no conflict (safe default)
        return False
    
    return False
=======
>>>>>>> 4740136 (Implemented fixer.py to suggest fixes for the vault.)


def print_results(candidates: list):
    """
    Print scan results in a formatted table.
    
    Args:
        candidates: List of candidate dicts
    """
    if not candidates:
        print("✅ No maintenance candidates found. Vault is clean!")
        return
    
    print("\n🔍 Vault Maintenance Scan Results")
    print("=" * 80)
    print(f"Top {len(candidates)} Maintenance Candidates:\n")
    
    # Table header
    print(f"{'Rank':<6} | {'Score':<6} | {'Path':<50} | {'Reasons'}")
    print("-" * 80)
    
    # Table rows
    for idx, candidate in enumerate(candidates, 1):
        rank = str(idx)
        score = str(candidate["score"])
        path = candidate["path"]
        reasons = ", ".join(candidate["reasons"])
        
        # Truncate path if too long
        if len(path) > 48:
            path = path[:45] + "..."
        
        print(f"{rank:<6} | {score:<6} | {path:<50} | {reasons}")
    
    print("=" * 80)


def main():
    """Main orchestrator function."""
    print("🌙 Night Watchman Starting...")
    
    # Get vault root from environment or use current directory
    vault_root = os.getenv("OBSIDIAN_VAULT_ROOT", os.getcwd())
    vault_root_path = Path(vault_root)
    
    print(f"📁 Vault root: {vault_root_path}")
    
    # Initialize components
    context_loader = ContextLoader(vault_root)
    scanner = VaultScanner(vault_root, context_loader)
    state_manager = StateManager(vault_root)
    
    # Run scan
    print("🔍 Scanning vault for quality issues...")
    all_candidates = scanner.scan()
    
    print(f"📊 Found {len(all_candidates)} files with quality issues")
    
    # Filter by cooldown
    filtered_candidates = state_manager.filter_candidates(all_candidates)
    print(f"🔇 Filtered {len(all_candidates) - len(filtered_candidates)} files in cooldown")
    
    # Sort by score (descending)
    filtered_candidates.sort(key=lambda x: x["score"], reverse=True)
    
    # Limit to top 20
    top_candidates = filtered_candidates[:20]
    
<<<<<<< HEAD
    # Filter out files with recent modifications (conflict detection)
    clean_candidates = []
    for candidate in top_candidates:
        full_path = vault_root_path / candidate['path']
        if check_conflict(full_path):
            print(f"⏳ Skipping active file: {candidate['path']} (modified recently)")
            continue
        clean_candidates.append(candidate)
    
    if not clean_candidates:
        print("✅ No maintenance candidates found after conflict filtering. Vault is clean!")
        return
    
    # Print results summary
    print_results(clean_candidates)
=======
    if not top_candidates:
        print("✅ No maintenance candidates found. Vault is clean!")
        return
    
    # Print results summary
    print_results(top_candidates)
>>>>>>> 4740136 (Implemented fixer.py to suggest fixes for the vault.)
    
    # Generate fix proposals
    try:
        # Initialize LLM Client
        print("\n🤖 Initializing LLM Client...")
        llm_client = LLMClient(vault_root=vault_root)
        
        # Initialize Maintenance Fixer
        fixer = MaintenanceFixer(vault_root, llm_client, context_loader)
        
<<<<<<< HEAD
        # Generate proposals for clean candidates
        print(f"\n🔧 Generating fix proposals for {len(clean_candidates)} candidates...")
        processed_files = fixer.generate_fixes(clean_candidates)
=======
        # Generate proposals for top candidates
        print(f"\n🔧 Generating fix proposals for {len(top_candidates)} candidates...")
        processed_files = fixer.generate_fixes(top_candidates)
>>>>>>> 4740136 (Implemented fixer.py to suggest fixes for the vault.)
        
        print(f"\n✅ Generated {len(processed_files)} proposals")
        
        # Record scan in history only for successfully processed files
        for rel_path in processed_files:
            # Find the score for this path
<<<<<<< HEAD
            candidate = next((c for c in clean_candidates if c["path"] == rel_path), None)
=======
            candidate = next((c for c in top_candidates if c["path"] == rel_path), None)
>>>>>>> 4740136 (Implemented fixer.py to suggest fixes for the vault.)
            if candidate:
                state_manager.record_scan(rel_path, candidate["score"])
        
        # Save history
        state_manager.save_history()
        
        print(f"✅ Scan complete. History saved to {state_manager.history_file.relative_to(vault_root_path)}")
        print(f"📝 Proposals written to: {fixer.review_dir.relative_to(vault_root_path)}")
        
    except ValueError as e:
        # LLM API key not set
        print(f"\n❌ Error: {e}")
        print("⚠️ Skipping proposal generation. Set GEMINI_API_KEY environment variable to enable fix proposals.")
        # Still record the scan even if proposals weren't generated
<<<<<<< HEAD
        for candidate in clean_candidates:
=======
        for candidate in top_candidates:
>>>>>>> 4740136 (Implemented fixer.py to suggest fixes for the vault.)
            state_manager.record_scan(candidate["path"], candidate["score"])
        state_manager.save_history()
    except Exception as e:
        print(f"\n❌ Error during proposal generation: {e}")
        import traceback
        traceback.print_exc()
        # Still record the scan even if proposals failed
<<<<<<< HEAD
        for candidate in clean_candidates:
=======
        for candidate in top_candidates:
>>>>>>> 4740136 (Implemented fixer.py to suggest fixes for the vault.)
            state_manager.record_scan(candidate["path"], candidate["score"])
        state_manager.save_history()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Vault Maintenance Scanner - The Night Watchman

Scans the vault for quality issues and identifies the top maintenance candidates.
"""

import os
import sys
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .scanner import VaultScanner
    from .state_manager import StateManager
    from .context_loader import ContextLoader
except ImportError:
    # Fallback for when run as script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scanner import VaultScanner
    from state_manager import StateManager
    from context_loader import ContextLoader


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
    
    # Print results
    print_results(top_candidates)
    
    # Record scan in history
    for candidate in top_candidates:
        state_manager.record_scan(candidate["path"], candidate["score"])
    
    # Save history
    state_manager.save_history()
    
    print(f"\n✅ Scan complete. History saved to {state_manager.history_file.relative_to(vault_root_path)}")


if __name__ == "__main__":
    main()

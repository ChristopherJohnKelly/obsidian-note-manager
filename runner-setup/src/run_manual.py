import sys
import os
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from processor import NoteProcessor


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run_manual.py <path_to_note> [vault_root]")
        print("  vault_root: Optional path to Obsidian vault root (defaults to current directory)")
        return 1

    note_path = sys.argv[1]
    vault_root = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    
    # Validate note file exists
    if not os.path.exists(note_path):
        print(f"❌ Error: Note file not found: {note_path}")
        return 1
    
    print(f"📄 Reading note: {note_path}")
    try:
        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ Error reading note file: {e}")
        return 1

    print(f"📁 Using vault root: {vault_root}")
    processor = NoteProcessor(vault_root)
    
    # Show vault index count for verification
    skeleton = processor.loader.indexer.build_skeleton()
    index_count = len([line for line in skeleton.split('\n') if line.strip()]) if skeleton else 0
    print(f"📊 Vault index: {index_count} entries")
    
    print("🤖 Analyzing with Gemini (this may take 5-10s)...")
    try:
        result = processor.process_note(content)
        
        print("\n" + "="*50)
        print("GEMINI SUGGESTION (Frontmatter)")
        print("="*50)
        
        # Pretty print the frontmatter
        import yaml
        print(yaml.dump(result, default_flow_style=False, sort_keys=False))
        
        print("="*50)
        print("✅ Processing completed successfully!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

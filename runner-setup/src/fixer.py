import os
import frontmatter
from pathlib import Path

# Handle both relative and absolute imports
try:
    from .context_loader import ContextLoader
    from .vault_utils import get_safe_path
except ImportError:
    # Fallback for when run as script
    from context_loader import ContextLoader
    from vault_utils import get_safe_path


class MaintenanceFixer:
    def __init__(self, vault_root: str, llm_client, context_loader: ContextLoader):
        """
        Initialize the Maintenance Fixer.
        
        Args:
            vault_root: Path to the root of the Obsidian vault
            llm_client: LLMClient instance for generating proposals
            context_loader: ContextLoader instance for getting vault context
        """
        self.vault_root = Path(vault_root)
        review_dir = os.getenv("OBSIDIAN_REVIEW_DIR", "00. Inbox/1. Review Queue")
        self.review_dir = self.vault_root / review_dir
        self.llm_client = llm_client
        self.context_loader = context_loader

    def generate_fixes(self, candidates: list) -> list:
        """
        Generates proposals for the given candidates.
        
        Args:
            candidates: List of candidate dicts with "path", "score", and "reasons" keys
            
        Returns:
            list: List of relative file paths that were successfully processed
        """
        processed_files = []
        
        # Ensure review directory exists
        self.review_dir.mkdir(parents=True, exist_ok=True)
        
        # Get context once for all candidates (more efficient)
        try:
            full_context = self.context_loader.get_full_context()
            skeleton = self.context_loader.indexer.build_skeleton()
        except Exception as e:
            print(f"⚠️ Warning: Failed to load full context, using minimal context: {e}")
            full_context = "[Maintenance Mode - Context loading failed]"
            skeleton = ""

        for item in candidates:
            try:
                rel_path = item['path']
                reasons = item['reasons']
                score = item['score']
                full_path = self.vault_root / rel_path
                
                print(f"🔧 Fixing: {rel_path} (Issues: {', '.join(reasons)})")

                # 1. Read Original Content
                if not full_path.exists():
                    print(f"⚠️ Warning: File not found: {rel_path}, skipping")
                    continue
                
                with open(full_path, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                # 2. Construct Maintenance Instructions
                # We are specific about the detected issues to guide the LLM
                instructions = (
                    f"MAINTENANCE MODE. This note has failed quality checks.\n"
                    f"Detected Issues: {', '.join(reasons)}.\n\n"
                    f"Task:\n"
                    f"1. Fix the Frontmatter (add missing aliases, tags, or other required metadata).\n"
                    f"2. Rename the file if it violates Project Code conventions (filename should start with the expected project code).\n"
                    f"3. Do NOT rewrite the body text unless essential for formatting or fixing critical errors.\n"
                    f"4. Preserve all existing content and structure.\n"
                    f"5. Output the result using the %%FILE%% schema with the corrected path if renaming is needed."
                )

                # 3. Call LLM to generate proposal
                try:
                    proposal_body = self.llm_client.generate_proposal(
                        instructions=instructions,
                        body=raw_content,
                        context=full_context,
                        skeleton=skeleton
                    )
                except Exception as e:
                    print(f"❌ LLM API Error for {rel_path}: {e}")
                    continue

                # 4. Write Proposal Note
                # Extract original filename stem for proposal naming
                original_stem = full_path.stem
                proposal_filename = f"Refactor - {original_stem}.md"
                proposal_path = self.review_dir / proposal_filename

                # Handle filename collisions (e.g., same filename in different directories)
                proposal_path = get_safe_path(proposal_path)

                # Construct proposal content with frontmatter and body sections
                proposal_content = f"""%%INSTRUCTIONS%%
{instructions}
---
%%ORIGINAL%%
{raw_content}
---
{proposal_body}
"""
                
                # Create frontmatter for the proposal
                proposal_frontmatter = {
                    "type": "file_change_proposal",
                    "target-file": rel_path,
                    "score": score,
                    "reason": ", ".join(reasons),
                    "librarian": "review"
                }
                
                # Combine frontmatter and content
                proposal_note = frontmatter.Post(proposal_content, **proposal_frontmatter)
                proposal_text = frontmatter.dumps(proposal_note)

                # Write proposal file
                with open(proposal_path, "w", encoding="utf-8") as f:
                    f.write(proposal_text)

                processed_files.append(rel_path)
                print(f"✅ Generated: {proposal_filename}")

            except Exception as e:
                print(f"❌ Failed to fix {item.get('path', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                continue

        return processed_files

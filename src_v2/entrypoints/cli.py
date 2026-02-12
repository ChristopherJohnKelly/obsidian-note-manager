"""CLI entry point for manual use."""

import argparse
import sys
from pathlib import Path

from src_v2.config.context_config import ContextConfig
from src_v2.config.settings import Settings
from src_v2.core.domain.models import Frontmatter, Note
from src_v2.infrastructure.file_system.adapters import ObsidianFileSystemAdapter
from src_v2.infrastructure.llm.adapters import GeminiAdapter
from src_v2.infrastructure.testing.adapters import FakeLLM
from src_v2.use_cases.assistant_service import AssistantService
from src_v2.use_cases.librarian_service import LibrarianService
from src_v2.use_cases.maintenance_service import MaintenanceService


def _cmd_update_registry(args: argparse.Namespace) -> int:
    settings = Settings()
    repo = ObsidianFileSystemAdapter(settings.vault_root)
    service = LibrarianService(repo)
    registry_content = service.generate_registry()
    note = Note(
        path=Path(settings.registry_output_path),
        frontmatter=Frontmatter(title="Code Registry", type="system"),
        body=registry_content,
    )
    repo.save_note(Path(settings.registry_output_path), note)
    print(f"Registry updated: {settings.registry_output_path}")
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    settings = Settings()
    repo = ObsidianFileSystemAdapter(settings.vault_root)
    llm = FakeLLM()
    service = MaintenanceService(repo, llm)
    results = service.audit_vault()
    if not results:
        print("No maintenance candidates found. Vault is clean.")
        return 0
    print(f"\nTop {len(results)} Maintenance Candidates:\n")
    print(f"{'Rank':<6} | {'Score':<6} | {'Path':<50} | {'Reasons'}")
    print("-" * 80)
    for idx, r in enumerate(results, 1):
        reasons = ", ".join(r.reasons)
        path_str = str(r.path)
        if len(path_str) > 48:
            path_str = path_str[:45] + "..."
        print(f"{idx:<6} | {r.score:<6} | {path_str:<50} | {reasons}")
    return 0


def _cmd_fix(args: argparse.Namespace) -> int:
    settings = Settings()
    if not settings.gemini_api_key:
        print("Error: GEMINI_API_KEY is required for fix command.", file=sys.stderr)
        return 1
    path = Path(args.path)
    repo = ObsidianFileSystemAdapter(settings.vault_root)
    try:
        llm = GeminiAdapter(api_key=settings.gemini_api_key)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    config = ContextConfig()
    assistant = AssistantService(repo, llm, config)
    service = MaintenanceService(repo, llm, assistant_service=assistant)
    try:
        proposal = service.fix_file(path)
        print(proposal)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_blueprint(args: argparse.Namespace) -> int:
    settings = Settings()
    if not settings.gemini_api_key:
        print("Error: GEMINI_API_KEY is required for blueprint command.", file=sys.stderr)
        return 1
    repo = ObsidianFileSystemAdapter(settings.vault_root)
    try:
        llm = GeminiAdapter(api_key=settings.gemini_api_key)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    config = ContextConfig()
    service = AssistantService(repo, llm, config)
    result = service.generate_blueprint(args.request)
    print(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="obsidian", description="Obsidian vault automation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    librarian_parser = subparsers.add_parser("librarian", help="Librarian commands")
    librarian_sub = librarian_parser.add_subparsers(dest="librarian_command", required=True)
    librarian_sub.add_parser("update-registry", help="Regenerate the Code Registry")
    librarian_sub.choices["update-registry"].set_defaults(func=_cmd_update_registry)

    maintain_parser = subparsers.add_parser("maintain", help="Maintenance commands")
    maintain_sub = maintain_parser.add_subparsers(dest="maintain_command", required=True)
    maintain_sub.add_parser("audit", help="Run the Night Watchman scan")
    maintain_sub.choices["audit"].set_defaults(func=_cmd_audit)
    fix_parser = maintain_sub.add_parser("fix", help="Generate fix proposal for a file")
    fix_parser.add_argument("path", help="Relative path to the note (e.g. 20. Projects/Pepsi/DirtyFile.md)")
    fix_parser.set_defaults(func=_cmd_fix)

    assist_parser = subparsers.add_parser("assist", help="Assistant commands")
    assist_sub = assist_parser.add_subparsers(dest="assist_command", required=True)
    blueprint_parser = assist_sub.add_parser("blueprint", help="Generate a blueprint from a request")
    blueprint_parser.add_argument("request", help="User request (e.g. 'Create a new project for learning Rust')")
    blueprint_parser.set_defaults(func=_cmd_blueprint)

    args = parser.parse_args()

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

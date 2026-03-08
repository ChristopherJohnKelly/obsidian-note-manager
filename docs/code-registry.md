# Code Registry

This document provides a comprehensive registry of the `src_v2` codebase. The legacy `runner-setup/src/` codebase has been deprecated. All business logic now lives in `src_v2/` using Clean Architecture and Domain-Driven Design.

## File Overview

| File | Type | Primary Class/Function | Pipeline | Description |
|------|------|------------------------|----------|-------------|
| `entrypoints/ingest_runner.py` | Entry Point | `main()` | Ingestion | Headless Capture-to-Review-Queue pipeline |
| `entrypoints/cron_runner.py` | Entry Point | `main()` | Maintenance | Night Watchman audit and fix proposals |
| `entrypoints/cli.py` | Entry Point | `main()` | CLI | Manual commands (update-registry, audit, fix, blueprint) |
| `use_cases/ingestion_service.py` | Use Case | `IngestionService` | Ingestion | AI-powered note analysis from Capture |
| `use_cases/filer_service.py` | Use Case | `FilerService` | Both | Executes approved proposals |
| `use_cases/maintenance_service.py` | Use Case | `MaintenanceService` | Maintenance | Scans vault, generates fix proposals |
| `use_cases/librarian_service.py` | Use Case | `LibrarianService` | Both | Code Registry table generation |
| `use_cases/assistant_service.py` | Use Case | `AssistantService` | Maintenance | Blueprint generation, fix proposals |
| `core/domain/models.py` | Domain | `Note`, `Frontmatter`, `ValidationResult`, etc. | Both | Data models |
| `core/interfaces/ports.py` | Ports | `VaultRepository`, `LLMProvider` | Both | Abstract interfaces |
| `core/response_parser.py` | Core | `parse_proposal()` | Both | Parses %%FILE%% markers from LLM output |
| `core/vault_utils.py` | Core | `get_safe_path()`, `sanitize_filename()` | Both | Path safety, exclusions |
| `infrastructure/file_system/adapters.py` | Adapter | `ObsidianFileSystemAdapter` | Both | Implements VaultRepository |
| `infrastructure/llm/adapters.py` | Adapter | `GeminiAdapter` | Both | Implements LLMProvider |
| `infrastructure/testing/adapters.py` | Adapter | `MockVaultAdapter`, `FakeLLM` | Testing | Test doubles |
| `config/settings.py` | Config | `Settings` | Both | Environment-based settings |
| `config/context_config.py` | Config | `ContextConfig` | Both | Context loading (instructions, glossary) |
| `scripts/token_fetcher.py` | Infra | `get_registration_token()` | N/A | Runner registration via PAT |

---

## Clean Architecture Layout

### core/domain/

**models.py** – Domain entities

| Class | Purpose |
|-------|---------|
| `Frontmatter` | Structured metadata for an Obsidian note (type, status, title, aliases, tags, code, folder) |
| `Note` | Obsidian note with path, frontmatter, and body |
| `Link` | Parsed Wiki Link (source, target, link_type) |
| `ValidationResult` | Night Watchman scan result (path, score, reasons) |
| `CodeRegistryEntry` | Code Registry entry (code, name, type, folder) |

### core/interfaces/

**ports.py** – Abstract ports (implemented by infrastructure adapters)

| Port | Methods | Purpose |
|------|---------|---------|
| `VaultRepository` | `get_note`, `save_note`, `scan_vault`, `get_code_registry_entries`, `get_skeleton`, `validate_note`, `list_note_paths_in`, `read_raw`, `delete_note` | Vault storage operations |
| `LLMProvider` | `generate_text`, `generate_proposal` | LLM operations (Gemini) |

### core/ (shared)

| Module | Functions/Classes | Purpose |
|--------|-------------------|---------|
| `response_parser.py` | `parse_proposal(text) -> ParsedProposal` | Parses LLM output with %%FILE%% markers |
| `vault_utils.py` | `sanitize_filename()`, `get_safe_path()` | Path safety, collision protection |

### use_cases/

| Service | Key Methods | Purpose |
|---------|-------------|---------|
| `IngestionService` | `run() -> IngestionResult` | Process notes from Capture via LLM, write proposals to Review Queue |
| `FilerService` | `file_approved_notes() -> int` | Execute proposals with `librarian: file`, create/move/delete files |
| `MaintenanceService` | `audit_vault()`, `fix_file()` | Scan vault, generate fix proposals |
| `LibrarianService` | `generate_registry() -> str` | Build Code Registry markdown table |
| `AssistantService` | `generate_blueprint()`, `fix_file()` | Blueprint generation, fix proposals via LLM |

### infrastructure/

| Adapter | Implements | Purpose |
|---------|------------|---------|
| `ObsidianFileSystemAdapter` | VaultRepository | File system operations on vault |
| `GeminiAdapter` | LLMProvider | Google Gemini API |
| `MockVaultAdapter` | VaultRepository | In-memory test double |
| `FakeLLM` | LLMProvider | Test double for LLM |

### entrypoints/

| Module | Invocation | Purpose |
|--------|------------|---------|
| `ingest_runner` | `python3 -m src_v2.entrypoints.ingest_runner` | Used by ingest.yml workflow |
| `cron_runner` | `python3 -m src_v2.entrypoints.cron_runner` | Used by maintenance.yml workflow |
| `cli` | `python3 -m src_v2.entrypoints.cli <command>` or `obsidian <command>` | Manual CLI |

### config/

| Module | Purpose |
|--------|---------|
| `settings.py` | Loads from env: vault_root, gemini_api_key, capture_dir, review_dir, etc. |
| `context_config.py` | System instructions, tag glossary paths |

---

## Dependency Graph

```
ingest_runner.py
├── FilerService(repo, review_dir, vault_root)
│   └── ObsidianFileSystemAdapter (VaultRepository)
├── IngestionService(repo, llm, capture_dir, review_dir, vault_root)
│   ├── ObsidianFileSystemAdapter
│   ├── GeminiAdapter (LLMProvider)
│   └── parse_proposal, get_safe_path, sanitize_filename
└── Settings

cron_runner.py
├── MaintenanceService(repo, llm, assistant_service?)
│   ├── ObsidianFileSystemAdapter
│   ├── GeminiAdapter
│   └── AssistantService (for fix proposals)
├── LibrarianService(repo)
└── Settings

cli.py
├── LibrarianService → update-registry
├── MaintenanceService → audit, fix
├── AssistantService → blueprint
└── ObsidianFileSystemAdapter, GeminiAdapter
```

---

## Maintenance Guide

### Adding a New Quality Check

1. **Edit** `ObsidianFileSystemAdapter.validate_note()` or `MaintenanceService`:
   - Add scoring logic
   - Add new reason string to `ValidationResult.reasons`

### Adding a New Context Source

1. **Edit** `config/context_config.py`:
   - Add file path to context loading
   - Update `ContextConfig` if needed

### Modifying LLM Prompts

1. **System prompts**: Check `ContextConfig`, `GeminiAdapter`, and use case services
2. **User prompts**: In `IngestionService`, `AssistantService`, `MaintenanceService`

### Adding New Proposal Types

1. **Edit** `FilerService`:
   - Add detection logic for new metadata
   - Implement appropriate file handling

2. **Edit producer** (IngestionService, MaintenanceService, AssistantService):
   - Add new metadata fields to proposal frontmatter

### Updating Excluded Directories

1. **Edit** `infrastructure/file_system/adapters.py`:
   - Modify `_is_excluded()` or equivalent exclusion logic

---

## Testing Checklist

When modifying the codebase, verify:

- [ ] Ingestion pipeline processes new notes correctly
- [ ] Filer executes regular proposals
- [ ] Filer handles maintenance fixes (in-place and rename)
- [ ] MaintenanceService identifies quality issues
- [ ] Conflict detection works (recently modified files)
- [ ] Cooldown filtering works
- [ ] Path traversal attacks are blocked
- [ ] Collision protection prevents data loss
- [ ] Workflows perform Git operations (not Python)

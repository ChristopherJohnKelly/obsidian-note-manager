# API Reference

This document provides a technical reference for the `src_v2` codebase. The legacy `runner-setup/src/` modules have been deprecated.

## Entry Points

### `src_v2.entrypoints.ingest_runner`

#### `main() -> int`

Headless entry point for the Capture-to-Review-Queue pipeline. Used by `ingest.yml` workflow.

**Environment Variables**:
- `OBSIDIAN_VAULT_ROOT`: Path to vault root (from workflow: `${{ github.workspace }}`)
- `GEMINI_API_KEY`: Google Gemini API key

**Returns**: 0 on success, 1 on failure

**Invocation**: `python3 -m src_v2.entrypoints.ingest_runner`

---

### `src_v2.entrypoints.cron_runner`

#### `main() -> int`

Headless entry point for the Night Watchman. Used by `maintenance.yml` workflow.

**Environment Variables**: Same as ingest_runner

**Invocation**: `python3 -m src_v2.entrypoints.cron_runner`

---

### `src_v2.entrypoints.cli`

#### `main() -> int`

CLI entry point for manual commands.

**Commands**:
- `obsidian librarian update-registry`
- `obsidian maintain audit`
- `obsidian maintain fix <path>`
- `obsidian assist blueprint <request>`

**Invocation**: `python3 -m src_v2.entrypoints.cli <command>` or `obsidian <command>`

---

## Domain Models (`src_v2.core.domain.models`)

### `Frontmatter`

Structured metadata for an Obsidian note.

**Fields**: `type`, `status`, `title`, `aliases`, `tags`, `code`, `folder` (all optional)

---

### `Note`

Obsidian note with path, frontmatter, and body.

**Fields**:
- `path` (Path): File path
- `frontmatter` (Frontmatter): Metadata
- `body` (str): Note content

---

### `ValidationResult`

Night Watchman scan result.

**Fields**:
- `path` (Path): File path
- `score` (int): Quality deficit score
- `reasons` (list[str]): Issue descriptions

---

### `CodeRegistryEntry`

Code Registry entry from Areas/Projects.

**Fields**: `code`, `name`, `type`, `folder`

---

## Ports (`src_v2.core.interfaces.ports`)

### `VaultRepository` (ABC)

Abstract interface for vault storage.

**Methods**:
- `get_note(path) -> Note | None`
- `save_note(path, note) -> None`
- `scan_vault() -> list[ValidationResult]`
- `get_code_registry_entries() -> list[CodeRegistryEntry]`
- `get_skeleton() -> str`
- `validate_note(path) -> ValidationResult | None`
- `list_note_paths_in(directory) -> list[Path]`
- `read_raw(path) -> str | None`
- `delete_note(path) -> None`

---

### `LLMProvider` (ABC)

Abstract interface for LLM operations.

**Methods**:
- `generate_text(prompt: str) -> str`
- `generate_proposal(instructions, body, context, skeleton) -> str`

---

## Core Utilities

### `src_v2.core.response_parser`

#### `parse_proposal(text: str) -> ParsedProposal`

Parses LLM output with %%FILE%% markers into structured data.

**Parameters**:
- `text` (str): Raw LLM response

**Returns**: Dict with `explanation` and `files` keys. `files` is list of `{"path": str, "content": str}`.

**Expected Format**:
```
%%EXPLANATION%%
...
%%FILE: path/to/file.md%%
...
```

---

### `src_v2.core.vault_utils`

#### `sanitize_filename(title: str, max_length: int = 200) -> str`

Sanitizes a title to create a valid filename.

**Parameters**:
- `title` (str): The title to sanitize
- `max_length` (int): Maximum filename length (default: 200)

**Returns**: Sanitized filename (without extension)

---

#### `get_safe_path(target_path: Path) -> Path`

Returns a path that doesn't exist, appending `-N` if needed.

**Parameters**:
- `target_path` (Path): Desired file path

**Returns**: Safe path (e.g. `Note.md` → `Note-1.md` if Note.md exists)

---

## Use Cases

### `IngestionService`

**Location**: `src_v2.use_cases.ingestion_service`

**Constructor**: `IngestionService(repo, llm, capture_dir, review_dir, vault_root)`

**Methods**:
- `run() -> IngestionResult`: Process notes from Capture, write proposals to Review Queue

---

### `FilerService`

**Location**: `src_v2.use_cases.filer_service`

**Constructor**: `FilerService(repo, review_dir, vault_root)`

**Methods**:
- `file_approved_notes() -> int`: Execute proposals with `librarian: file`; returns count filed

---

### `MaintenanceService`

**Location**: `src_v2.use_cases.maintenance_service`

**Constructor**: `MaintenanceService(repo, llm, assistant_service=None)`

**Methods**:
- `audit_vault() -> list[ValidationResult]`: Scan vault for quality issues
- `fix_file(path) -> str`: Generate fix proposal for a file

---

### `LibrarianService`

**Location**: `src_v2.use_cases.librarian_service`

**Constructor**: `LibrarianService(repo)`

**Methods**:
- `generate_registry() -> str`: Build Code Registry markdown table

---

### `AssistantService`

**Location**: `src_v2.use_cases.assistant_service`

**Constructor**: `AssistantService(repo, llm, config)`

**Methods**:
- `generate_blueprint(request: str) -> str`: Generate blueprint from user request
- `fix_file(path) -> str`: Generate fix proposal for a file

---

## Infrastructure Adapters

### `ObsidianFileSystemAdapter`

**Location**: `src_v2.infrastructure.file_system.adapters`

**Implements**: `VaultRepository`

**Constructor**: `ObsidianFileSystemAdapter(vault_root: Path)`

---

### `GeminiAdapter`

**Location**: `src_v2.infrastructure.llm.adapters`

**Implements**: `LLMProvider`

**Constructor**: `GeminiAdapter(api_key: str)`

**Raises**: `ValueError` if `api_key` is empty

---

## Config

### `Settings`

**Location**: `src_v2.config.settings`

**Purpose**: Loads configuration from environment variables.

**Key attributes**: `vault_root`, `gemini_api_key`, `capture_dir`, `review_dir`, `registry_output_path`, `log_level`

---

### `ContextConfig`

**Location**: `src_v2.config.context_config`

**Purpose**: Context loading (system instructions, tag glossary paths).

---

## Scripts

### `scripts.token_fetcher`

#### `get_registration_token(repo_url: str, pat: str) -> str`

Fetches GitHub Actions runner registration token via PAT.

**Parameters**:
- `repo_url` (str): GitHub repository URL
- `pat` (str): Classic Personal Access Token with `repo` scope

**Returns**: Registration token

**API Endpoint**: `POST /repos/{owner}/{repo}/actions/runners/registration-token`

---

## Environment Variables

### Required (Workflow)

| Variable | Type | Used By | Description |
|----------|------|---------|-------------|
| `GEMINI_API_KEY` | String | GeminiAdapter, use cases | Google Gemini API key |
| `OBSIDIAN_VAULT_ROOT` | Path | Settings, adapters | Path to vault root (from `github.workspace`) |

### Optional (Runner / Container)

| Variable | Type | Used By | Description |
|----------|------|---------|-------------|
| `GITHUB_PAT` | String | entrypoint.sh | Classic PAT with `repo` scope |
| `REPO_URL` | URL | entrypoint.sh | GitHub repository URL |
| `RUNNER_NAME` | String | entrypoint.sh | Name for the runner |
| `OBSIDIAN_CAPTURE_DIR` | Path | Settings | Override Capture dir (default: `00. Inbox/0. Capture`) |
| `OBSIDIAN_REVIEW_DIR` | Path | Settings | Override Review dir (default: `00. Inbox/1. Review Queue`) |

---

## Dependencies

### Python Packages

- `google-generativeai`: Gemini API client
- `python-frontmatter`: Markdown frontmatter parsing
- `pyyaml`: YAML parsing
- `requests`: HTTP requests (token_fetcher)
- `pydantic`: Domain models

### System Requirements

- Python 3.10+
- Docker (for containerization)

**Note**: Git operations are performed by workflow steps, not Python. The application does not use `gitpython`.

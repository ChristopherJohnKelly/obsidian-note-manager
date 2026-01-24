# Code Registry

This document provides a comprehensive registry of all source files, classes, and methods in the Obsidian Note Automation system. Use this as a reference for understanding code relationships and for maintaining the codebase.

## File Overview

| File | Type | Primary Class/Function | Pipeline | Description |
|------|------|------------------------|----------|-------------|
| `main.py` | Orchestrator | `main()` | Ingestion | Main entry point for note ingestion |
| `vault_maintenance.py` | Orchestrator | `main()` | Maintenance | Main entry point for vault maintenance |
| `processor.py` | Core | `NoteProcessor` | Ingestion | AI-powered note analysis |
| `filer.py` | Core | `NoteFiler` | Both | Executes approved proposals |
| `fixer.py` | Core | `MaintenanceFixer` | Maintenance | Generates fix proposals |
| `scanner.py` | Core | `VaultScanner` | Maintenance | Scans vault for quality issues |
| `state_manager.py` | Core | `StateManager` | Maintenance | Tracks scan history |
| `llm_client.py` | Shared | `LLMClient` | Both | Gemini API interface |
| `context_loader.py` | Shared | `ContextLoader` | Both | Loads vault context |
| `indexer.py` | Shared | `VaultIndexer` | Both | Builds vault skeleton |
| `response_parser.py` | Shared | `ResponseParser` | Both | Parses LLM output |
| `yaml_parser.py` | Shared | Functions | Ingestion | YAML extraction |
| `vault_utils.py` | Shared | Functions | Both | Utility functions |
| `git_ops.py` | Shared | `GitOps` | Ingestion | Git operations |
| `token_fetcher.py` | Infra | Functions | N/A | Runner registration |
| `run_manual.py` | Utility | `main()` | N/A | Manual testing |
| `test_gemini.py` | Utility | N/A | N/A | API testing |

---

## Detailed File Registry

### `main.py` - Ingestion Pipeline Orchestrator

**Location**: `runner-setup/src/main.py`

**Purpose**: Coordinates the ingestion pipeline from raw notes to proposals.

**Dependencies**:
- `processor.NoteProcessor`
- `git_ops.GitOps`
- `filer.NoteFiler`
- `frontmatter` (external)

**Functions**:

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `clean_markdown` | `content: str` | `str` | Removes frontmatter from content |
| `sanitize_filename` | `title: str, max_length: int = 200` | `str` | Creates safe filename |
| `main` | None | None | Pipeline orchestrator |

**Called By**: GitHub Actions workflow, manual execution

**Calls**: `NoteFiler.file_approved_notes()`, `NoteProcessor.process_note()`, `GitOps.commit_and_push()`

---

### `vault_maintenance.py` - Maintenance Pipeline Orchestrator

**Location**: `runner-setup/src/vault_maintenance.py`

**Purpose**: Coordinates the maintenance pipeline for vault quality scanning.

**Dependencies**:
- `scanner.VaultScanner`
- `state_manager.StateManager`
- `context_loader.ContextLoader`
- `llm_client.LLMClient`
- `fixer.MaintenanceFixer`

**Functions**:

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `check_conflict` | `file_path: Path` | `bool` | Checks if file modified in last hour |
| `print_results` | `candidates: list` | None | Prints formatted scan results |
| `main` | None | None | Pipeline orchestrator |

**Called By**: GitHub Actions workflow, manual execution

**Calls**: `VaultScanner.scan()`, `StateManager.filter_candidates()`, `MaintenanceFixer.generate_fixes()`, `StateManager.save_history()`

---

### `processor.py` - Note Processor

**Location**: `runner-setup/src/processor.py`

**Purpose**: Processes new notes using AI to generate organization proposals.

**Dependencies**:
- `llm_client.LLMClient`
- `context_loader.ContextLoader`
- `yaml_parser` (functions)
- `response_parser.ResponseParser`
- `frontmatter` (external)

**Class**: `NoteProcessor`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str` | None | Initializes components |
| `_extract_instructions` | `content: str` | `tuple` | Extracts LLM-Instructions block |
| `process_note` | `note_content: str` | `str` | Main processing method |

**Called By**: `main.main()`

**Calls**: `ContextLoader.get_full_context()`, `VaultIndexer.build_skeleton()`, `LLMClient.generate_proposal()`, `ResponseParser.parse()`

**Constants**:
- `SYSTEM_PROMPT`: Head Librarian role definition for AI

---

### `filer.py` - Note Filer

**Location**: `runner-setup/src/filer.py`

**Purpose**: Executes approved proposals by creating files in the vault.

**Dependencies**:
- `response_parser.ResponseParser`
- `vault_utils.get_safe_path`
- `frontmatter` (external)

**Class**: `NoteFiler`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str` | None | Initializes with vault path |
| `file_approved_notes` | None | `int` | Processes approved proposals |

**Called By**: `main.main()`

**Calls**: `ResponseParser.parse()`, `get_safe_path()`

**Key Logic**:
- Detects maintenance fixes via `target-file` metadata
- Handles in-place updates vs renames differently
- Protects unrelated files from accidental deletion

---

### `fixer.py` - Maintenance Fixer

**Location**: `runner-setup/src/fixer.py`

**Purpose**: Generates AI-powered fix proposals for notes with quality issues.

**Dependencies**:
- `context_loader.ContextLoader`
- `vault_utils.get_safe_path`
- `frontmatter` (external)

**Class**: `MaintenanceFixer`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str, llm_client, context_loader` | None | Initializes with dependencies |
| `generate_fixes` | `candidates: list` | `list` | Generates proposals for candidates |

**Called By**: `vault_maintenance.main()`

**Calls**: `ContextLoader.get_full_context()`, `LLMClient.generate_proposal()`, `get_safe_path()`

**Proposal Metadata**:
- `type`: "file_change_proposal"
- `target-file`: Original file path (critical for filer)
- `score`: Quality deficit score
- `reason`: Comma-separated issue list
- `librarian`: "review"

---

### `scanner.py` - Vault Scanner

**Location**: `runner-setup/src/scanner.py`

**Purpose**: Scans vault for quality issues and scores files.

**Dependencies**:
- `vault_utils.is_excluded`
- `frontmatter` (external)

**Class**: `VaultScanner`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str, context_loader` | None | Initializes with registry |
| `_find_expected_code` | `folder_path: str` | `str\|None` | Finds expected project code |
| `_score_file` | `path: Path` | `tuple` | Calculates quality score |
| `scan` | None | `list` | Scans vault for issues |

**Called By**: `vault_maintenance.main()`

**Calls**: `is_excluded()`, `ContextLoader.get_project_registry()`

**Scoring Rules**:
| Issue | Points | Detection |
|-------|--------|-----------|
| Missing aliases/tags | +10 | No `aliases` or `tags` in frontmatter |
| Missing project code | +50 | Filename doesn't start with expected code |
| Generic filename | +20 | Filename in bad_titles set |

---

### `state_manager.py` - State Manager

**Location**: `runner-setup/src/state_manager.py`

**Purpose**: Tracks scan history and manages cooldown periods.

**Dependencies**: `json`, `datetime` (standard library)

**Class**: `StateManager`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str` | None | Loads history file |
| `_load_history` | None | `dict` | Loads and validates history |
| `save_history` | None | None | Persists history |
| `is_cooldown_active` | `rel_path: str, days: int = 7` | `bool` | Checks cooldown status |
| `record_scan` | `rel_path: str, score: int` | None | Records scan event |
| `filter_candidates` | `candidates: list` | `list` | Filters by cooldown |

**Called By**: `vault_maintenance.main()`

**History File**: `99. System/maintenance_history.json`

---

### `llm_client.py` - LLM Client

**Location**: `runner-setup/src/llm_client.py`

**Purpose**: Interface with Google Gemini API for AI-powered analysis.

**Dependencies**: `google.generativeai` (external)

**Class**: `LLMClient`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str, model_name: str, system_instruction: str\|None` | None | Configures Gemini |
| `generate_content` | `prompt: str` | `str` | Basic prompt→response |
| `generate_proposal` | `instructions, body, context, skeleton, model_name` | `str` | Full proposal generation |
| `_log_interaction` | Various | None | Archives interaction |

**Called By**: `NoteProcessor.process_note()`, `MaintenanceFixer.generate_fixes()`

**Constants**:
- `ARCHITECT_SYSTEM_PROMPT`: Defines AI role for proposal generation

**Logging**: `99. System/Logs/Librarian/`

---

### `context_loader.py` - Context Loader

**Location**: `runner-setup/src/context_loader.py`

**Purpose**: Loads and aggregates vault context for AI prompts.

**Dependencies**: `indexer.VaultIndexer`, `frontmatter` (external)

**Class**: `ContextLoader`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str` | None | Initializes indexer |
| `read_file` | `relative_path: str` | `str` | Reads file, returns "" if missing |
| `_scan_code_files` | None | `list` | Scans for project codes |
| `build_code_registry` | None | `str` | Builds markdown table |
| `get_project_registry` | None | `dict` | Returns folder→code mapping |
| `get_full_context` | None | `str` | Aggregates all context |

**Called By**: `NoteProcessor`, `MaintenanceFixer`, `VaultScanner`

**Context Sources**:
1. System Instructions: `30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md`
2. Tag Glossary: `00. Inbox/00. Tag Glossary.md`
3. Code Registry: Dynamically scanned
4. Vault Skeleton: From VaultIndexer

---

### `indexer.py` - Vault Indexer

**Location**: `runner-setup/src/indexer.py`

**Purpose**: Builds skeleton of valid link targets for deep linking.

**Dependencies**: `vault_utils.is_excluded`, `frontmatter` (external)

**Class**: `VaultIndexer`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `vault_root: str` | None | Sets scan directories |
| `_normalize_aliases` | `aliases` | `list` | Normalizes alias formats |
| `build_skeleton` | None | `str` | Builds formatted skeleton |

**Called By**: `ContextLoader.get_full_context()`, `NoteProcessor.process_note()`

**Scan Directories**: `30. Areas`, `20. Projects`, `40. Resources`

---

### `response_parser.py` - Response Parser

**Location**: `runner-setup/src/response_parser.py`

**Purpose**: Parses LLM output with `%%FILE%%` markers into structured data.

**Dependencies**: `re` (standard library)

**Class**: `ResponseParser`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `parse` | `text: str` | `dict` | Parses LLM output |

**Called By**: `NoteProcessor.process_note()`, `NoteFiler.file_approved_notes()`

**Input Format**:
```
%%EXPLANATION%%
...
%%FILE: path/file.md%%
...
```

**Output Format**:
```python
{"explanation": "...", "files": [{"path": "...", "content": "..."}]}
```

---

### `yaml_parser.py` - YAML Parser

**Location**: `runner-setup/src/yaml_parser.py`

**Purpose**: Extracts and parses YAML from markdown code blocks.

**Dependencies**: `re` (standard library), `yaml` (external)

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `extract_yaml_from_response` | `response: str` | `str\|None` | Extracts YAML from code blocks |
| `parse_frontmatter` | `yaml_content: str` | `dict` | Parses YAML to dict |

**Called By**: `NoteProcessor.process_note()`

---

### `vault_utils.py` - Vault Utilities

**Location**: `runner-setup/src/vault_utils.py`

**Purpose**: Shared utility functions for vault operations.

**Dependencies**: `pathlib` (standard library)

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `is_excluded` | `path: Path, vault_root: Path` | `bool` | Checks if path is excluded |
| `get_safe_path` | `target_path: Path` | `Path` | Returns non-colliding path |

**Called By**: `NoteFiler`, `MaintenanceFixer`, `VaultScanner`, `VaultIndexer`

**Constants**:
```python
EXCLUDED_DIRS = {"99. System", "00. Inbox", ".git", ".obsidian", ".trash"}
```

---

### `git_ops.py` - Git Operations

**Location**: `runner-setup/src/git_ops.py`

**Purpose**: Handles Git commit and push operations.

**Dependencies**: `git` (GitPython external)

**Class**: `GitOps`

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__` | `repo_path: str` | None | Initializes repo |
| `has_changes` | None | `bool` | Checks for uncommitted changes |
| `commit_and_push` | `message: str` | None | Stages, commits, pushes |

**Called By**: `main.main()`

**Git Actor**: "Obsidian Librarian" <librarian@automation.local>

---

### `token_fetcher.py` - Token Fetcher

**Location**: `runner-setup/src/token_fetcher.py`

**Purpose**: Fetches GitHub Actions runner registration tokens.

**Dependencies**: `requests` (external)

| Function | Parameters | Returns | Description |
|----------|------------|---------|-------------|
| `get_registration_token` | `repo_url: str, pat: str` | `str` | Fetches registration token |

**Called By**: `entrypoint.sh`

---

## Dependency Graph

```
main.py (Ingestion Pipeline)
├── processor.py (NoteProcessor)
│   ├── llm_client.py (LLMClient)
│   │   └── [google-generativeai]
│   ├── context_loader.py (ContextLoader)
│   │   └── indexer.py (VaultIndexer)
│   │       └── vault_utils.py (is_excluded)
│   ├── yaml_parser.py (functions)
│   │   └── [pyyaml]
│   └── response_parser.py (ResponseParser)
├── filer.py (NoteFiler)
│   ├── response_parser.py (ResponseParser)
│   └── vault_utils.py (get_safe_path)
└── git_ops.py (GitOps)
    └── [gitpython]

vault_maintenance.py (Maintenance Pipeline)
├── scanner.py (VaultScanner)
│   ├── context_loader.py (ContextLoader) [get_project_registry]
│   └── vault_utils.py (is_excluded)
├── state_manager.py (StateManager)
├── context_loader.py (ContextLoader)
├── llm_client.py (LLMClient)
└── fixer.py (MaintenanceFixer)
    ├── context_loader.py (ContextLoader)
    ├── llm_client.py (LLMClient)
    └── vault_utils.py (get_safe_path)
```

---

## Maintenance Guide

### Adding a New Quality Check

1. **Edit `scanner.py`**:
   - Add scoring logic to `_score_file()`
   - Add new reason string

2. **Edit `fixer.py`** (if needed):
   - Update maintenance instructions in `generate_fixes()`

### Adding a New Context Source

1. **Edit `context_loader.py`**:
   - Add file path to `get_full_context()`
   - Create new method if complex parsing needed

### Modifying LLM Prompts

1. **System prompts**:
   - `processor.py`: `SYSTEM_PROMPT` constant
   - `llm_client.py`: `ARCHITECT_SYSTEM_PROMPT` constant

2. **User prompts**:
   - `processor.py`: In `process_note()`
   - `llm_client.py`: In `generate_proposal()`

### Adding New Proposal Types

1. **Edit `filer.py`**:
   - Add detection logic for new metadata
   - Implement appropriate file handling

2. **Edit producer** (`processor.py` or `fixer.py`):
   - Add new metadata fields to proposal frontmatter

### Updating Excluded Directories

1. **Edit `vault_utils.py`**:
   - Modify `EXCLUDED_DIRS` set

---

## Testing Checklist

When modifying the codebase, verify:

- [ ] Ingestion pipeline processes new notes correctly
- [ ] Filer executes regular proposals
- [ ] Filer handles maintenance fixes (in-place and rename)
- [ ] Scanner identifies quality issues
- [ ] State manager tracks history correctly
- [ ] Conflict detection works (recently modified files)
- [ ] Cooldown filtering works
- [ ] Path traversal attacks are blocked
- [ ] Collision protection prevents data loss
- [ ] Git operations commit and push correctly

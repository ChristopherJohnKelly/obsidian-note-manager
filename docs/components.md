# Component Documentation

This document provides detailed information about each component in the Obsidian Note Automation system. The codebase uses Clean Architecture in `src_v2/`.

## Entry Points

### ingest_runner.py – Ingestion Pipeline Entry Point

**Purpose**: Headless entry point for the Capture-to-Review-Queue pipeline. Used by the `ingest.yml` workflow.

**Responsibilities**:
- Initializes FilerService and IngestionService
- Phase 1: Files approved proposals via FilerService
- Phase 2: Processes new notes from Capture via IngestionService
- Logs to vault `99. System/Logs/` and stdout for GitHub Actions visibility

**Invocation**: `python3 -m src_v2.entrypoints.ingest_runner`

**Configuration**: `OBSIDIAN_VAULT_ROOT` (from workflow: `${{ github.workspace }}`), `GEMINI_API_KEY`

**Dependencies**: FilerService, IngestionService, ObsidianFileSystemAdapter, GeminiAdapter, Settings

---

### cron_runner.py – Maintenance Pipeline Entry Point

**Purpose**: Headless entry point for the Night Watchman. Used by the `maintenance.yml` workflow.

**Responsibilities**:
- Initializes MaintenanceService and LibrarianService
- Runs vault audit and Code Registry update
- Generates fix proposals for quality issues
- Logs to vault and stdout

**Invocation**: `python3 -m src_v2.entrypoints.cron_runner`

**Configuration**: `OBSIDIAN_VAULT_ROOT`, `GEMINI_API_KEY`

**Dependencies**: MaintenanceService, LibrarianService, ObsidianFileSystemAdapter, GeminiAdapter, Settings

---

### cli.py – CLI Entry Point

**Purpose**: Manual commands for local or container execution.

**Commands**:
- `obsidian librarian update-registry` – Regenerate Code Registry
- `obsidian maintain audit` – Run Night Watchman scan
- `obsidian maintain fix <path>` – Generate fix proposal for a file
- `obsidian assist blueprint <request>` – Generate blueprint from request

**Invocation**: `python3 -m src_v2.entrypoints.cli <command>` or `obsidian <command>`

**Dependencies**: LibrarianService, MaintenanceService, AssistantService, ObsidianFileSystemAdapter, GeminiAdapter, ContextConfig, Settings

---

## Use Cases

### IngestionService

**Purpose**: Processes new notes from the Capture folder using AI.

**Key Methods**:
- `run() -> IngestionResult`: Main processing method; returns processed count and success status

**Flow**:
1. List notes in Capture directory
2. For each note: extract instructions, load context, call LLM, parse response, create proposal
3. Write proposals to Review Queue
4. Delete processed notes from Capture

**Dependencies**: VaultRepository, LLMProvider, ContextConfig (via context loading), parse_proposal, get_safe_path, sanitize_filename

---

### FilerService

**Purpose**: Executes approved proposals by creating, moving, and deleting files in the vault.

**Key Methods**:
- `file_approved_notes() -> int`: Processes all proposals with `librarian: file`; returns count filed

**Processing Logic**:
1. Scan Review Queue for proposals with `librarian: file`
2. Parse body to extract %%FILE%% blocks via parse_proposal
3. Detect maintenance fixes via `target-file` metadata
4. For each file block: validate path, create parent directories, handle collisions, write content
5. Delete processed proposal

**Maintenance Fix Handling**:
- **In-place update**: Overwrites original file directly
- **Rename**: Deletes original, uses get_safe_path for new location
- **Secondary files**: Treated as new files with collision protection

**Safety Features**:
- Path traversal prevention
- Collision protection via get_safe_path
- Maintenance fixes protect unrelated files at target paths

**Dependencies**: VaultRepository, parse_proposal, get_safe_path

---

### MaintenanceService

**Purpose**: Scans the vault for quality issues and generates fix proposals.

**Key Methods**:
- `audit_vault() -> list[ValidationResult]`: Scans vault, returns candidates with scores
- `fix_file(path) -> str`: Generates fix proposal for a single file (via AssistantService)

**Scoring Rules** (conceptual; implementation in adapter/use case):
| Issue | Points | Description |
|-------|--------|--------------|
| Missing aliases/tags | +10 | No aliases or tags in frontmatter |
| Missing Project Code | +50 | Filename doesn't start with expected code |
| Generic Filename | +20 | Filename is "untitled", "meeting", "note", or "call" |

**Scan Directories**: `20. Projects/`, `30. Areas/`

**Dependencies**: VaultRepository, LLMProvider, AssistantService (for fix generation)

---

### LibrarianService

**Purpose**: Generates the Code Registry markdown table from vault structure.

**Key Methods**:
- `generate_registry() -> str`: Builds markdown table of project/area codes

**Dependencies**: VaultRepository

---

### AssistantService

**Purpose**: Blueprint generation and fix proposals via LLM.

**Key Methods**:
- `generate_blueprint(request: str) -> str`: Generates blueprint from user request
- `fix_file(path) -> str`: Generates fix proposal for a file (used by MaintenanceService)

**Dependencies**: VaultRepository, LLMProvider, ContextConfig

---

## Core (Domain & Interfaces)

### core/domain/models.py

| Model | Purpose |
|-------|---------|
| `Frontmatter` | Structured metadata (type, status, title, aliases, tags, code, folder) |
| `Note` | Note with path, frontmatter, body |
| `Link` | Parsed Wiki Link |
| `ValidationResult` | Scan result (path, score, reasons) |
| `CodeRegistryEntry` | Code Registry entry |

### core/interfaces/ports.py

| Port | Purpose |
|------|---------|
| `VaultRepository` | Abstract interface for vault storage (get_note, save_note, scan_vault, etc.) |
| `LLMProvider` | Abstract interface for LLM (generate_text, generate_proposal) |

### core/response_parser.py

**Purpose**: Parses LLM output with %%FILE%% markers into structured data.

**Function**: `parse_proposal(text: str) -> ParsedProposal`

**Expected Format**:
```
%%EXPLANATION%%
...
%%FILE: path/to/file.md%%
...
```

### core/vault_utils.py

| Function | Purpose |
|----------|---------|
| `sanitize_filename(title, max_length)` | Creates safe filename from title |
| `get_safe_path(target_path)` | Returns non-colliding path (appends -N if exists) |

---

## Infrastructure Adapters

### ObsidianFileSystemAdapter

**Implements**: VaultRepository

**Purpose**: Concrete file system operations on the Obsidian vault.

**Key Methods**: get_note, save_note, scan_vault, get_code_registry_entries, get_skeleton, validate_note, list_note_paths_in, read_raw, delete_note

**Excluded Paths**: `99. System`, `00. Inbox`, `.git`, `.obsidian`, `.trash`

---

### GeminiAdapter

**Implements**: LLMProvider

**Purpose**: Interfaces with Google Gemini API.

**Configuration**: Model (e.g. gemini-2.5-flash), temperature, max output tokens

**Dependencies**: `google-generativeai` library, GEMINI_API_KEY

---

### MockVaultAdapter / FakeLLM

**Purpose**: Test doubles for unit tests.

**Location**: `infrastructure/testing/adapters.py`

---

## Infrastructure (Deployment)

### Dockerfile

**Location**: Repo root

**Build Steps**:
1. Install system dependencies (curl, jq, git, unzip, Python)
2. Create non-root `runner` user
3. Download GitHub Actions runner binary
4. Install Python dependencies
5. Copy scripts/ and src_v2/
6. `pip install .` (installs obsidian-note-manager package)

**Architecture Support**: ARM64 (Raspberry Pi), x64 (development)

---

### entrypoint.sh

**Location**: scripts/

**Purpose**: Runner registration and startup.

**Flow**:
1. Validate REPO_URL
2. Check if runner already configured
3. Fetch registration token via token_fetcher.py (PAT)
4. Register runner with GitHub
5. Start runner with run.sh

---

### docker-compose.yml

**Location**: Repo root

**Service**: librarian-runner

**Configuration**: Restart unless-stopped, environment from .env (REPO_URL, GITHUB_PAT, GEMINI_API_KEY, OBSIDIAN_* paths)

---

### token_fetcher.py

**Location**: scripts/

**Purpose**: Fetches GitHub Actions runner registration tokens via PAT.

**Function**: `get_registration_token(repo_url, pat)`

---

## Component Interaction Diagram

```
INGESTION PIPELINE (ingest_runner):
  FilerService.file_approved_notes()
    └── VaultRepository (ObsidianFileSystemAdapter)
    └── parse_proposal()
  IngestionService.run()
    └── VaultRepository
    └── LLMProvider (GeminiAdapter)
    └── parse_proposal, get_safe_path, sanitize_filename

MAINTENANCE PIPELINE (cron_runner):
  MaintenanceService.audit_vault()
    └── VaultRepository.scan_vault(), validate_note()
  LibrarianService.generate_registry()
    └── VaultRepository.get_code_registry_entries()
  MaintenanceService.fix_file() (via AssistantService)
    └── LLMProvider.generate_proposal()
    └── VaultRepository

GIT OPERATIONS: Performed by workflow steps, not Python
```

---

## Error Handling Patterns

All components follow consistent error handling:

1. **Validation Errors**: Raise early with clear messages
2. **Missing Dependencies**: Log warnings, continue if possible
3. **External API Errors**: Propagate with context
4. **File I/O Errors**: Log and continue processing remaining files
5. **Malformed Data**: Log warning and skip item (response parser)

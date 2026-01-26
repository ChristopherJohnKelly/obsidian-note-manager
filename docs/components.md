# Component Documentation

This document provides detailed information about each component in the Obsidian Note Automation system.

## Pipeline Orchestrators

### `main.py` - Ingestion Pipeline Orchestrator

**Purpose**: Main entry point that coordinates the entire note ingestion pipeline.

**Responsibilities**:
- Initializes core components (NoteProcessor, GitOps, NoteFiler)
- Phase 1: Files approved proposals via NoteFiler
- Phase 2: Scans Capture folder for new `.md` files
- Phase 3: Processes each file through NoteProcessor
- Phase 4: Moves proposals to Review Queue
- Phase 5: Commits and pushes changes via GitOps

**Key Functions**:
- `clean_markdown(content)`: Removes existing frontmatter from raw content
- `sanitize_filename(title)`: Creates safe filenames from titles
- `main()`: Orchestrates the entire pipeline

**Configuration**:
- `VAULT_ROOT`: From `OBSIDIAN_VAULT_ROOT` environment variable (default: current directory)
- `CAPTURE_DIR`: `{VAULT_ROOT}/00. Inbox/0. Capture`
- `REVIEW_DIR`: `{VAULT_ROOT}/00. Inbox/1. Review Queue`

**Dependencies**: `NoteProcessor`, `GitOps`, `NoteFiler`

---

### `vault_maintenance.py` - Maintenance Pipeline Orchestrator

**Purpose**: Scans the vault for quality issues and generates fix proposals.

**Responsibilities**:
- Initializes scanning components (VaultScanner, StateManager, ContextLoader)
- Scans vault for quality deficits
- Filters candidates by cooldown period
- Checks for recent file modifications (conflict detection)
- Generates fix proposals via MaintenanceFixer
- Records scan history

**Key Functions**:
- `check_conflict(file_path)`: Returns True if file modified in last hour
- `print_results(candidates)`: Displays formatted scan results
- `main()`: Orchestrates the maintenance pipeline

**Configuration**:
- `OBSIDIAN_VAULT_ROOT`: Environment variable for vault location

**Dependencies**: `VaultScanner`, `StateManager`, `ContextLoader`, `LLMClient`, `MaintenanceFixer`

---

## Processing Components

### `processor.py` - Note Processor

**Purpose**: Coordinates AI analysis of new notes by combining context with LLM calls.

**Class**: `NoteProcessor`

**Key Methods**:
- `__init__(vault_root)`: Initializes LLMClient and ContextLoader
- `_extract_instructions(content)`: Extracts `LLM-Instructions` block from note
- `process_note(note_content)`: Main processing method, returns complete proposal string

**Flow**:
1. Extract instructions and body from note content
2. Load full vault context (instructions, glossary, codes, skeleton)
3. Call LLM via `generate_proposal()`
4. Parse response to extract file paths
5. Build proposal note with frontmatter
6. Return formatted proposal string

**System Prompt**: Defines the AI's role as "Head Librarian" with tasks:
- Analyze note intent
- Classify type, status, code
- Enrich with title and tags
- Suggest folder path

**Dependencies**: `LLMClient`, `ContextLoader`, `ResponseParser`

---

### `filer.py` - Note Filer

**Purpose**: Executes approved proposals by creating files in the vault.

**Class**: `NoteFiler`

**Key Methods**:
- `__init__(vault_root)`: Initializes with vault root and ResponseParser
- `file_approved_notes()`: Processes all proposals with `librarian: file`

**Processing Logic**:
1. Scan Review Queue for proposals with `librarian: file`
2. Parse body to extract `%%FILE%%` blocks
3. Detect maintenance fixes via `target-file` metadata
4. For each file block:
   - Validate path (no traversal attacks)
   - Create parent directories
   - Handle collisions appropriately
   - Write file content
5. Delete processed proposal

**Maintenance Fix Handling**:
- **In-place update**: Overwrites original file directly
- **Rename**: Deletes original, uses `get_safe_path()` for new location
- **Secondary files**: Treated as new files with collision protection

**Safety Features**:
- Path traversal prevention (`..` and absolute paths rejected)
- Collision protection via `get_safe_path()`
- Maintenance fixes protect unrelated files at target paths

**Dependencies**: `ResponseParser`, `vault_utils.get_safe_path`

---

### `fixer.py` - Maintenance Fixer

**Purpose**: Generates fix proposals for notes with quality issues.

**Class**: `MaintenanceFixer`

**Key Methods**:
- `__init__(vault_root, llm_client, context_loader)`: Initializes with dependencies
- `generate_fixes(candidates)`: Generates proposals for candidate list

**Processing Logic**:
1. Load vault context once for efficiency
2. For each candidate:
   - Read original file content
   - Construct maintenance instructions with detected issues
   - Call LLM for fix proposal
   - Create proposal with `target-file` metadata
   - Write to Review Queue

**Proposal Format**:
```yaml
---
type: file_change_proposal
target-file: original/path.md
score: 60
reason: "Missing aliases/tags, Generic Filename"
librarian: review
---
```

**Dependencies**: `LLMClient`, `ContextLoader`, `vault_utils.get_safe_path`

---

### `scanner.py` - Vault Scanner

**Purpose**: Identifies quality deficits in existing vault notes.

**Class**: `VaultScanner`

**Key Methods**:
- `__init__(vault_root, context_loader)`: Initializes with project registry
- `_find_expected_code(folder_path)`: Finds expected project code for a folder
- `_score_file(path)`: Calculates quality deficit score for a file
- `scan()`: Scans vault and returns candidate list

**Scoring Rules**:
| Issue | Points | Description |
|-------|--------|-------------|
| Missing aliases/tags | +10 | No `aliases` or `tags` in frontmatter |
| Missing Project Code | +50 | Filename doesn't start with expected code |
| Generic Filename | +20 | Filename is "untitled", "meeting", "note", or "call" |

**Scan Directories**: `20. Projects/`, `30. Areas/`

**Excluded Paths**: `99. System`, `00. Inbox`, `.git`, `.obsidian`, `.trash`

**Dependencies**: `ContextLoader.get_project_registry()`, `vault_utils.is_excluded`

---

### `state_manager.py` - State Manager

**Purpose**: Tracks scan history and manages cooldown periods.

**Class**: `StateManager`

**Key Methods**:
- `__init__(vault_root)`: Loads history from JSON file
- `_load_history()`: Loads and validates history structure
- `save_history()`: Persists history with timestamp
- `is_cooldown_active(rel_path, days)`: Checks if file is in cooldown
- `record_scan(rel_path, score)`: Records a file as scanned
- `filter_candidates(candidates)`: Removes candidates in cooldown

**History File**: `99. System/maintenance_history.json`

**History Structure**:
```json
{
  "last_run": "2024-01-15T10:30:00",
  "files": {
    "path/to/file.md": {
      "last_scanned": "2024-01-15T10:30:00",
      "last_proposed": "2024-01-15T10:30:00",
      "last_score": 60
    }
  }
}
```

**Cooldown Period**: 7 days (configurable)

---

## Shared Infrastructure

### `llm_client.py` - Gemini API Client

**Purpose**: Interfaces with Google Gemini API for note analysis.

**Class**: `LLMClient`

**Key Methods**:
- `__init__(vault_root, model_name, system_instruction)`: Initializes Gemini client
- `generate_content(prompt)`: Basic prompt → response call
- `generate_proposal(instructions, body, context, skeleton)`: Full proposal generation
- `_log_interaction(...)`: Archives interactions for evaluation

**Configuration**:
- **Model**: `gemini-2.5-flash` (default)
- **Temperature**: 0.0 (deterministic output)
- **Max Output Tokens**: 8192

**Logging**: Interactions saved to `99. System/Logs/Librarian/` as JSON

**System Prompts**:
- **ARCHITECT_SYSTEM_PROMPT**: For proposal generation with `%%FILE%%` markers

**Dependencies**: `google-generativeai` library

---

### `context_loader.py` - Context Management

**Purpose**: Loads and aggregates context files from the Obsidian vault.

**Class**: `ContextLoader`

**Key Methods**:
- `__init__(vault_root)`: Initializes with VaultIndexer
- `read_file(relative_path)`: Reads a file, returns empty if not found
- `_scan_code_files()`: Scans Areas/Projects for code information
- `build_code_registry()`: Builds markdown table of project codes
- `get_project_registry()`: Returns folder→code mapping dict
- `get_full_context()`: Aggregates all context into single string

**Context Sources**:
1. **System Instructions**: `30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md`
2. **Tag Glossary**: `00. Inbox/00. Tag Glossary.md`
3. **Code Registry**: Dynamically scanned from vault
4. **Vault Skeleton**: Built by VaultIndexer

**Dependencies**: `VaultIndexer`

---

### `indexer.py` - Vault Indexer

**Purpose**: Builds a skeleton of valid link targets for deep linking.

**Class**: `VaultIndexer`

**Key Methods**:
- `__init__(vault_root)`: Initializes with scan directories
- `_normalize_aliases(aliases)`: Handles various alias formats
- `build_skeleton()`: Scans vault and returns formatted skeleton string

**Scan Directories**: `30. Areas`, `20. Projects`, `40. Resources`

**Output Format**:
```
- [[Title]] (path/to/file.md) [Aliases: alias1, alias2]
- [[Another Title]] (another/path.md)
```

**Dependencies**: `vault_utils.is_excluded`

---

### `response_parser.py` - LLM Response Parser

**Purpose**: Parses LLM output to extract structured file data.

**Class**: `ResponseParser`

**Key Methods**:
- `parse(text)`: Parses LLM output into structured data

**Expected Format**:
```
%%EXPLANATION%%
Reasoning text here...

%%FILE: path/to/file.md%%
File content here...

%%FILE: another/file.md%%
More content...
```

**Return Structure**:
```python
{
    "explanation": "Reasoning text here...",
    "files": [
        {"path": "path/to/file.md", "content": "File content here..."},
        {"path": "another/file.md", "content": "More content..."}
    ]
}
```

---

### `yaml_parser.py` - Frontmatter Parsing

**Purpose**: Extracts and parses YAML frontmatter from LLM responses.

**Key Functions**:
- `extract_yaml_from_response(response)`: Extracts YAML from markdown code blocks
- `parse_frontmatter(yaml_content)`: Parses YAML string into dictionary

**Supported Formats**:
- ````yaml ... ````
- ```` ... ````

**Dependencies**: `pyyaml` library

---

### `vault_utils.py` - Shared Utilities

**Purpose**: Provides shared utility functions for vault operations.

**Constants**:
- `EXCLUDED_DIRS`: Set of directories to skip (`99. System`, `00. Inbox`, `.git`, `.obsidian`, `.trash`)

**Key Functions**:

#### `is_excluded(path, vault_root)`
Checks if a path is in an excluded directory.

**Parameters**:
- `path`: Full path to check
- `vault_root`: Root path of the vault

**Returns**: `True` if path should be excluded

#### `get_safe_path(target_path)`
Returns a path that doesn't exist, appending `-N` suffix if needed.

**Parameters**:
- `target_path`: Desired file path

**Returns**: Safe path that doesn't exist (e.g., `Note.md` → `Note-1.md`)

---

### `git_ops.py` - Git Operations

**Purpose**: Handles Git commit and push operations.

**Class**: `GitOps`

**Key Methods**:
- `__init__(repo_path)`: Initializes with repository path
- `has_changes()`: Checks for uncommitted changes
- `commit_and_push(message)`: Stages, commits, and pushes

**Git Actor**:
- **Name**: "Obsidian Librarian"
- **Email**: "librarian@automation.local"

**Commit Behavior**:
- Stages all changes including deletions (`git add -A`)
- Uses custom actor for commits
- Pushes to `origin` remote

**Dependencies**: `GitPython` library

---

## Infrastructure Components

### `Dockerfile` - Container Image

**Base Image**: Ubuntu 22.04

**Build Steps**:
1. Install system dependencies
2. Create non-root `runner` user
3. Download GitHub Actions runner binary
4. Install Python dependencies
5. Copy application source to `/home/runner/src/`
6. Configure entrypoint

**Architecture Support**: ARM64 (Raspberry Pi), x64 (development)

---

### `entrypoint.sh` - Container Startup

**Purpose**: Handles runner registration and startup.

**Flow**:
1. Validate `REPO_URL` environment variable
2. Check if runner already configured
3. Fetch registration token via `token_fetcher.py`
4. Register runner with GitHub
5. Start runner with `run.sh`

**Registration Labels**: `self-hosted`, `docker`, `pi`

---

### `docker-compose.yml` - Container Orchestration

**Service**: `librarian-runner`

**Configuration**:
- **Restart Policy**: `unless-stopped`
- **Environment Variables**: `REPO_URL`, `GITHUB_PAT`, `RUNNER_NAME`, `GEMINI_API_KEY`

---

## Utility Scripts

### `token_fetcher.py` - Registration Token Fetcher

**Purpose**: Fetches GitHub Actions runner registration tokens.

**Function**: `get_registration_token(repo_url, pat)`

**API Endpoint**: `POST /repos/{owner}/{repo}/actions/runners/registration-token`

---

### `run_manual.py` - Manual Testing

**Purpose**: Test note processor without full pipeline.

**Usage**: `python3 src/run_manual.py <path_to_note> [vault_root]`

---

### `test_gemini.py` - Gemini API Test

**Purpose**: Verify Gemini API connectivity.

**Usage**: `python3 src/test_gemini.py`

---

## Component Interaction Diagram

```
INGESTION PIPELINE:
main.py
  ├─► NoteFiler.file_approved_notes()
  │     └─► ResponseParser.parse()
  ├─► NoteProcessor.process_note()
  │     ├─► ContextLoader.get_full_context()
  │     │     └─► VaultIndexer.build_skeleton()
  │     ├─► LLMClient.generate_proposal()
  │     └─► ResponseParser.parse()
  └─► GitOps.commit_and_push()

MAINTENANCE PIPELINE:
vault_maintenance.py
  ├─► VaultScanner.scan()
  │     └─► ContextLoader.get_project_registry()
  ├─► StateManager.filter_candidates()
  ├─► MaintenanceFixer.generate_fixes()
  │     ├─► ContextLoader.get_full_context()
  │     └─► LLMClient.generate_proposal()
  └─► StateManager.save_history()

SHARED:
  ├─► vault_utils.is_excluded()
  └─► vault_utils.get_safe_path()
```

## Error Handling Patterns

All components follow consistent error handling:

1. **Validation Errors**: Raise early with clear messages
2. **Missing Dependencies**: Log warnings, continue if possible
3. **External API Errors**: Propagate with context
4. **File I/O Errors**: Log and continue processing remaining files
5. **Git Errors**: Raise exceptions (caller decides whether to continue)
6. **Malformed Data**: Log warning and skip item (ResponseParser)

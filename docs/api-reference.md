# API Reference

This document provides a technical reference for all classes, functions, and modules in the Obsidian Note Automation system.

## Module: `main`

### Functions

#### `clean_markdown(content: str) -> str`

Removes any existing frontmatter from raw note content.

**Parameters**:
- `content` (str): Raw note content that may contain frontmatter

**Returns**:
- `str`: Cleaned note body without frontmatter

**Example**:
```python
content = "---\ntitle: Test\n---\nBody content"
cleaned = clean_markdown(content)  # Returns: "Body content"
```

---

#### `sanitize_filename(title: str, max_length: int = 200) -> str`

Sanitizes a title to create a valid filename.

**Parameters**:
- `title` (str): The title to sanitize
- `max_length` (int, optional): Maximum filename length (default: 200)

**Returns**:
- `str`: Sanitized filename (without extension)

**Allowed Characters**: Letters, numbers, spaces, dots, dashes, underscores, parentheses

---

#### `main() -> None`

Main orchestrator function for the ingestion pipeline.

**Environment Variables**:
- `OBSIDIAN_VAULT_ROOT`: Path to Obsidian vault root (default: current directory)

---

## Module: `vault_maintenance`

### Functions

#### `check_conflict(file_path: Path) -> bool`

Returns True if the file has been modified in the last hour.

**Parameters**:
- `file_path` (Path): Path object to the file to check

**Returns**:
- `bool`: True if file was modified recently (conflict), False otherwise

**Purpose**: Prevents the bot from interfering with active user work.

---

#### `print_results(candidates: list) -> None`

Prints scan results in a formatted table.

**Parameters**:
- `candidates` (list): List of candidate dicts with "path", "score", "reasons" keys

---

#### `main() -> None`

Main orchestrator function for the maintenance pipeline.

**Environment Variables**:
- `OBSIDIAN_VAULT_ROOT`: Path to Obsidian vault root (default: current directory)

---

## Module: `processor`

### Class: `NoteProcessor`

Orchestrates note analysis with Gemini AI.

#### `__init__(self, vault_root: str)`

Initialize the note processor.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault

**Initializes**:
- `self.llm` (LLMClient): Gemini API client with system instruction
- `self.loader` (ContextLoader): Context loader for vault files
- `self.parser` (ResponseParser): Parser for LLM responses

---

#### `_extract_instructions(self, content: str) -> tuple`

Extracts LLM-Instructions block from note content.

**Parameters**:
- `content` (str): Raw note content

**Returns**:
- `tuple`: (instructions, cleaned_body) or (None, content) if no instructions

**Pattern**: Looks for ``` `LLM-Instructions ... ` ``` blocks

---

#### `process_note(self, note_content: str) -> str`

Processes a note and generates a multi-file proposal.

**Parameters**:
- `note_content` (str): Raw note content (may contain instruction block)

**Returns**:
- `str`: Complete proposal note with frontmatter and sections

**Raises**:
- `Exception`: If LLM call fails or parsing fails

---

## Module: `filer`

### Class: `NoteFiler`

Executes approved proposals by creating files in the vault.

#### `__init__(self, vault_root: str)`

Initialize the Note Filer.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault

**Initializes**:
- `self.vault_root` (Path): Vault root path
- `self.review_dir` (Path): Path to Review Queue
- `self.parser` (ResponseParser): Parser for proposal content

---

#### `file_approved_notes(self) -> int`

Executes proposals with 'librarian: file' by creating files.

**Returns**:
- `int`: Total number of files created

**Process**:
1. Scans Review Queue for `.md` files
2. Filters for `librarian: file` in frontmatter
3. Parses `%%FILE%%` blocks from body
4. Creates files with appropriate collision handling
5. Deletes processed proposals

**Maintenance Fix Detection**:
- Checks for `target-file` metadata
- Handles renames vs in-place updates differently
- Protects unrelated files at target paths

---

## Module: `fixer`

### Class: `MaintenanceFixer`

Generates fix proposals for notes with quality issues.

#### `__init__(self, vault_root: str, llm_client: LLMClient, context_loader: ContextLoader)`

Initialize the Maintenance Fixer.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault
- `llm_client` (LLMClient): LLMClient instance for generating proposals
- `context_loader` (ContextLoader): ContextLoader instance for vault context

---

#### `generate_fixes(self, candidates: list) -> list`

Generates fix proposals for the given candidates.

**Parameters**:
- `candidates` (list): List of dicts with "path", "score", "reasons" keys

**Returns**:
- `list`: List of relative file paths that were successfully processed

**Proposal Frontmatter**:
```python
{
    "type": "file_change_proposal",
    "target-file": rel_path,  # Original file path
    "score": score,
    "reason": "comma, separated, reasons",
    "librarian": "review"
}
```

---

## Module: `scanner`

### Class: `VaultScanner`

Scans the vault for quality issues.

#### `__init__(self, vault_root: str, context_loader: ContextLoader)`

Initialize the Vault Scanner.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault
- `context_loader` (ContextLoader): ContextLoader instance for project registry

**Initializes**:
- `self.registry` (dict): Folder→code mapping from context_loader
- `self.bad_titles` (set): Generic titles to flag ("untitled", "meeting", "note", "call")

---

#### `_find_expected_code(self, folder_path: str) -> Optional[str]`

Finds the expected project code for a folder path.

**Parameters**:
- `folder_path` (str): Relative folder path from vault root

**Returns**:
- `str`: Expected code if found, None otherwise

**Logic**: Walks up directory tree to find most specific match in registry.

---

#### `_score_file(self, path: Path) -> tuple`

Calculates quality deficit score for a single file.

**Parameters**:
- `path` (Path): Full path to the file

**Returns**:
- `tuple`: (score, reasons_list)

**Scoring**:
- Missing aliases/tags: +10
- Missing project code: +50
- Generic filename: +20

---

#### `scan(self) -> list`

Scans the vault and identifies quality issues.

**Returns**:
- `list`: List of dicts with "path", "score", "reasons" keys

**Scanned Directories**: `20. Projects/`, `30. Areas/`

---

## Module: `state_manager`

### Class: `StateManager`

Tracks scan history and cooldown periods.

#### `__init__(self, vault_root: str)`

Initialize the State Manager.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault

**History File**: `99. System/maintenance_history.json`

---

#### `_load_history(self) -> dict`

Loads history from JSON file with validation.

**Returns**:
- `dict`: History data with structure `{"last_run": str|None, "files": dict}`

---

#### `save_history(self) -> None`

Saves history to JSON file with current timestamp.

---

#### `is_cooldown_active(self, rel_path: str, days: int = 7) -> bool`

Checks if a file was proposed within the cooldown period.

**Parameters**:
- `rel_path` (str): Relative path to the file
- `days` (int): Cooldown period in days (default: 7)

**Returns**:
- `bool`: True if cooldown is active (should skip)

---

#### `record_scan(self, rel_path: str, score: int) -> None`

Records that a file was scanned and proposed.

**Parameters**:
- `rel_path` (str): Relative path to the file
- `score` (int): Quality deficit score

---

#### `filter_candidates(self, candidates: list) -> list`

Filters out candidates in cooldown period.

**Parameters**:
- `candidates` (list): List of candidate dicts with "path" key

**Returns**:
- `list`: Filtered list excluding candidates in cooldown

---

## Module: `context_loader`

### Class: `ContextLoader`

Loads and aggregates context files from the Obsidian vault.

#### `__init__(self, vault_root: str)`

Initialize the context loader.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault

**Initializes**:
- `self.indexer` (VaultIndexer): For building vault skeleton

---

#### `read_file(self, relative_path: str) -> str`

Reads a file from the vault.

**Parameters**:
- `relative_path` (str): Relative path from vault root

**Returns**:
- `str`: File contents, or empty string if not found

---

#### `_scan_code_files(self) -> list`

Scans Areas and Projects for code information.

**Returns**:
- `list`: List of dicts with keys: code, name, type, folder

---

#### `build_code_registry(self) -> str`

Builds a markdown table of project codes.

**Returns**:
- `str`: Markdown table string

---

#### `get_project_registry(self) -> dict`

Builds folder→code mapping dictionary.

**Returns**:
- `dict`: Mapping of folder paths to project codes

**Example**:
```python
{
    "20. Projects/Pepsi": "PEPS",
    "30. Areas/Clients/Coca-Cola": "COKE"
}
```

---

#### `get_full_context(self) -> str`

Aggregates all context into a single string.

**Returns**:
- `str`: Combined context with sections for System Instructions, Tag Glossary, Code Registry, and Vault Map

---

## Module: `indexer`

### Class: `VaultIndexer`

Builds a skeleton of valid link targets.

#### `__init__(self, vault_root: str)`

Initialize the Vault Indexer.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault

**Scan Directories**: `30. Areas`, `20. Projects`, `40. Resources`

---

#### `_normalize_aliases(self, aliases) -> list`

Normalizes aliases to list format.

**Parameters**:
- `aliases`: Aliases from frontmatter (list, string, or comma-separated)

**Returns**:
- `list`: Normalized list of aliases

---

#### `build_skeleton(self) -> str`

Scans vault and returns formatted link targets.

**Returns**:
- `str`: Formatted list of entries

**Format**: `- [[Title]] (path/to/file.md) [Aliases: alias1, alias2]`

---

## Module: `llm_client`

### Class: `LLMClient`

Interfaces with Google Gemini API.

#### `__init__(self, vault_root: str, model_name: str = "gemini-2.5-flash", system_instruction: Optional[str] = None)`

Initialize the Gemini Client.

**Parameters**:
- `vault_root` (str): Path to vault root (for logging)
- `model_name` (str): Gemini model name (default: "gemini-2.5-flash")
- `system_instruction` (str, optional): System instruction for model

**Environment Variables**:
- `GEMINI_API_KEY`: Required

**Raises**:
- `ValueError`: If `GEMINI_API_KEY` not set

---

#### `generate_content(self, prompt: str) -> str`

Sends a prompt to Gemini and returns response.

**Parameters**:
- `prompt` (str): The user prompt

**Returns**:
- `str`: Model's text response

---

#### `generate_proposal(self, instructions: str, body: str, context: str, skeleton: str, model_name: str = "gemini-2.5-flash") -> str`

Generates a multi-file proposal using the Architect system prompt.

**Parameters**:
- `instructions` (str): User instructions from note
- `body` (str): Raw note content
- `context` (str): Full vault context
- `skeleton` (str): Vault skeleton for deep linking
- `model_name` (str): Model to use

**Returns**:
- `str`: Raw LLM response with `%%FILE%%` markers

---

#### `_log_interaction(self, ...)`

Archives the interaction for evaluation.

**Log Location**: `99. System/Logs/Librarian/`

**Format**: JSON with meta, input, and output fields

---

## Module: `response_parser`

### Class: `ResponseParser`

Parses LLM output into structured data.

#### `parse(self, text: str) -> dict`

Parses LLM output blob into structured data.

**Parameters**:
- `text` (str): Raw LLM response

**Returns**:
- `dict`: Structure with "explanation" and "files" keys

**Expected Input Format**:
```
%%EXPLANATION%%
...reasoning...

%%FILE: path/to/file.md%%
...content...
```

**Return Structure**:
```python
{
    "explanation": "reasoning text",
    "files": [
        {"path": "path/to/file.md", "content": "file content"}
    ]
}
```

---

## Module: `yaml_parser`

### Functions

#### `extract_yaml_from_response(response: str) -> Optional[str]`

Extracts YAML from markdown code blocks.

**Parameters**:
- `response` (str): LLM response text

**Returns**:
- `Optional[str]`: Extracted YAML, or None if not found

---

#### `parse_frontmatter(yaml_content: str) -> Dict`

Parses YAML string into dictionary.

**Parameters**:
- `yaml_content` (str): YAML content string

**Returns**:
- `Dict`: Parsed frontmatter

**Raises**:
- `yaml.YAMLError`: On parsing failure

---

## Module: `vault_utils`

### Constants

#### `EXCLUDED_DIRS`
```python
EXCLUDED_DIRS = {"99. System", "00. Inbox", ".git", ".obsidian", ".trash"}
```

### Functions

#### `is_excluded(path: Path, vault_root: Path) -> bool`

Checks if a path is in an excluded directory.

**Parameters**:
- `path` (Path): Full path to check
- `vault_root` (Path): Root path of the vault

**Returns**:
- `bool`: True if path should be excluded

---

#### `get_safe_path(target_path: Path) -> Path`

Returns a path that doesn't exist, appending -N if needed.

**Parameters**:
- `target_path` (Path): Desired file path

**Returns**:
- `Path`: Safe path that doesn't exist

**Example**:
```python
# If Note.md exists:
get_safe_path(Path("Note.md"))  # Returns Path("Note-1.md")
```

---

## Module: `git_ops`

### Class: `GitOps`

Handles Git commit and push operations.

#### `__init__(self, repo_path: str)`

Initialize GitOps.

**Parameters**:
- `repo_path` (str): Path to the git repository root

**Git Actor**:
- Name: "Obsidian Librarian"
- Email: "librarian@automation.local"

---

#### `has_changes(self) -> bool`

Check for uncommitted changes.

**Returns**:
- `bool`: True if there are changes (including untracked files)

---

#### `commit_and_push(self, message: str) -> None`

Stages all changes, commits, and pushes.

**Parameters**:
- `message` (str): Commit message

**Raises**:
- `GitCommandError`: If git operations fail

---

## Module: `token_fetcher`

### Functions

#### `get_registration_token(repo_url: str, pat: str) -> str`

Fetches GitHub Actions runner registration token.

**Parameters**:
- `repo_url` (str): GitHub repository URL
- `pat` (str): Personal Access Token with `repo` scope

**Returns**:
- `str`: Registration token

**API Endpoint**: `POST /repos/{owner}/{repo}/actions/runners/registration-token`

---

## Environment Variables

### Required

| Variable | Type | Used By | Description |
|----------|------|---------|-------------|
| `GEMINI_API_KEY` | String | `LLMClient` | Google Gemini API key |
| `OBSIDIAN_VAULT_ROOT` | Path | All modules | Path to vault root |

### Optional (Runner Setup)

| Variable | Type | Used By | Description |
|----------|------|---------|-------------|
| `GITHUB_PAT` | String | `entrypoint.sh` | Classic PAT with `repo` scope |
| `GITHUB_TOKEN` | String | `entrypoint.sh` | Direct registration token (legacy) |
| `REPO_URL` | URL | `entrypoint.sh` | GitHub repository URL |
| `RUNNER_NAME` | String | `entrypoint.sh` | Name for the runner |

---

## Error Types

| Error | Module | Cause |
|-------|--------|-------|
| `ValueError` | `llm_client` | `GEMINI_API_KEY` missing |
| `yaml.YAMLError` | `yaml_parser` | YAML parsing failure |
| `GitCommandError` | `git_ops` | Git operation failure |
| `requests.HTTPError` | `token_fetcher` | GitHub API error |

---

## Dependencies

### Python Packages

- `google-generativeai`: Gemini API client
- `python-frontmatter`: Markdown frontmatter parsing
- `gitpython`: Git operations
- `pyyaml`: YAML parsing
- `requests`: HTTP requests

### System Requirements

- Python 3.10+
- Git
- Docker (for containerization)

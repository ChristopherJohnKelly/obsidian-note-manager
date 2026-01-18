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

**Example**:
```python
title = "My Note: Special/Characters?"
safe = sanitize_filename(title)  # Returns: "My-Note-Special-Characters"
```

---

#### `main() -> None`

Main orchestrator function. Scans Capture folder, processes notes, moves to Review Queue, and commits changes.

**Environment Variables**:
- `OBSIDIAN_VAULT_ROOT`: Path to Obsidian vault root (default: current directory)

**Side Effects**:
- Reads files from `00. Inbox/0. Capture/`
- Writes files to `00. Inbox/1. Review Queue/`
- Commits and pushes changes via Git

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

---

#### `process_note(self, note_content: str) -> dict`

Sends the note + context to Gemini and returns metadata suggestions.

**Parameters**:
- `note_content` (str): The raw note content to analyze

**Returns**:
- `dict`: Parsed frontmatter metadata as dictionary

**Raises**:
- `ValueError`: If no YAML content found in LLM response
- `Exception`: If LLM call fails or YAML parsing fails

**Example**:
```python
processor = NoteProcessor("/path/to/vault")
metadata = processor.process_note("My note content here...")
# Returns: {"title": "...", "tags": [...], "status": "..."}
```

---

## Module: `context_loader`

### Class: `ContextLoader`

Loads and aggregates context files from the Obsidian vault.

#### `__init__(self, vault_root: str)`

Initialize the context loader with the vault root path.

**Parameters**:
- `vault_root` (str): Path to the root of the Obsidian vault

---

#### `read_file(self, relative_path: str) -> str`

Reads a file from the vault, returning empty string if not found.

**Parameters**:
- `relative_path` (str): Relative path from vault root to the file

**Returns**:
- `str`: File contents, or empty string if file not found

**Side Effects**:
- Prints warning if file not found
- Prints error message if read fails

---

#### `get_full_context(self) -> str`

Aggregates all context files into a single string.

**Returns**:
- `str`: Combined context from System Instructions, Tag Glossary, and Code Registry

**Format**:
```
=== SYSTEM INSTRUCTIONS ===
{instructions content}

=== TAG GLOSSARY ===
{glossary content}

=== CODE REGISTRY ===
{registry content}
```

---

## Module: `llm_client`

### Class: `LLMClient`

Interfaces with Google Gemini API.

#### `__init__(self, model_name: str = "gemini-2.5-flash", system_instruction: Optional[str] = None)`

Initialize the Gemini Client.

**Parameters**:
- `model_name` (str, optional): Name of the Gemini model to use (default: "gemini-2.5-flash")
- `system_instruction` (str, optional): System instruction to pass to the model

**Environment Variables**:
- `GEMINI_API_KEY`: Required - Google Gemini API key

**Raises**:
- `ValueError`: If `GEMINI_API_KEY` environment variable not set

---

#### `generate_content(self, prompt: str) -> str`

Sends a prompt to Gemini and returns the response.

**Parameters**:
- `prompt` (str): The user prompt to send

**Returns**:
- `str`: The text response from Gemini

**Raises**:
- `Exception`: Propagates any errors from the Gemini API

---

## Module: `yaml_parser`

### Functions

#### `extract_yaml_from_response(response: str) -> Optional[str]`

Extracts YAML content from markdown code blocks in LLM response.

**Parameters**:
- `response` (str): The LLM response text

**Returns**:
- `Optional[str]`: Extracted YAML content, or `None` if not found

**Supported Formats**:
- `````yaml ... ````
- ````` ... `````

---

#### `parse_frontmatter(yaml_content: str) -> Dict`

Parses YAML string into Python dictionary.

**Parameters**:
- `yaml_content` (str): YAML content string

**Returns**:
- `Dict`: Parsed frontmatter as dictionary

**Raises**:
- `yaml.YAMLError`: If YAML parsing fails

**Example**:
```python
yaml_str = "title: Test\ntags: [a, b]"
parsed = parse_frontmatter(yaml_str)
# Returns: {"title": "Test", "tags": ["a", "b"]}
```

---

## Module: `git_ops`

### Class: `GitOps`

Handles Git commit and push operations.

#### `__init__(self, repo_path: str)`

Initialize GitOps with the repository path.

**Parameters**:
- `repo_path` (str): Path to the git repository root

**Initializes**:
- `self.repo` (Repo): GitPython Repo object
- `self.actor` (Actor): Git actor with name "Obsidian Librarian" and email "librarian@automation.local"

**Raises**:
- `GitError`: If repository path is invalid

---

#### `has_changes(self) -> bool`

Check if the repository has uncommitted changes.

**Returns**:
- `bool`: `True` if there are changes (including untracked files), `False` otherwise

---

#### `commit_and_push(self, message: str) -> None`

Stages all changes, commits, and pushes to remote.

**Parameters**:
- `message` (str): Commit message

**Side Effects**:
- Stages all changes (`git add -A`)
- Creates a commit with custom actor
- Pushes to `origin` remote

**Raises**:
- `GitCommandError`: If git operations fail

**Note**: Does nothing if `has_changes()` returns `False`

---

## Module: `token_fetcher`

### Functions

#### `get_registration_token(repo_url: str, pat: str) -> str`

Fetches a GitHub Actions runner registration token using a Personal Access Token.

**Parameters**:
- `repo_url` (str): GitHub repository URL (e.g., "https://github.com/owner/repo")
- `pat` (str): Personal Access Token with `repo` scope

**Returns**:
- `str`: Registration token for runner configuration

**Raises**:
- `requests.HTTPError`: On HTTP errors (401, 403, 404, 500+)
- `requests.exceptions.RequestException`: On network errors

**API Endpoint**:
```
POST https://api.github.com/repos/{owner}/{repo}/actions/runners/registration-token
```

**Authentication**: Tries `token {pat}` and `Bearer {pat}` headers

---

## Environment Variables

### Required

#### `GEMINI_API_KEY`
- **Type**: String
- **Format**: `AIza...` (Google API key format)
- **Used By**: `LLMClient`
- **Location**: GitHub Secrets (for workflows) or `.env` (for local testing)

#### `OBSIDIAN_VAULT_ROOT`
- **Type**: String (path)
- **Description**: Path to the root of the Obsidian vault
- **Used By**: `main.py`
- **Default**: Current working directory

### Optional (Runner Setup)

#### `GITHUB_PAT`
- **Type**: String
- **Format**: `ghp_...` (GitHub Personal Access Token)
- **Used By**: `entrypoint.sh` → `token_fetcher.py`
- **Requirements**: Classic PAT with `repo` scope

#### `GITHUB_TOKEN`
- **Type**: String
- **Description**: Direct registration token (legacy method)
- **Used By**: `entrypoint.sh`
- **Note**: Expires after 1 hour; prefer `GITHUB_PAT`

#### `REPO_URL`
- **Type**: String (URL)
- **Format**: `https://github.com/owner/repo`
- **Used By**: `entrypoint.sh`
- **Example**: `https://github.com/christopherjohnkelly/obsidian-notes`

#### `RUNNER_NAME`
- **Type**: String
- **Used By**: `entrypoint.sh`
- **Default**: `"pi-docker-runner"`
- **Example**: `"pi-librarian"`

---

## Constants

### System Prompt

**Location**: `processor.py` (module-level constant)

**Purpose**: Defines the AI's role and behavior for note processing

**Key Instructions**:
- Role: "Head Librarian"
- Tasks: Analyze, classify, enrich, file
- Output: YAML frontmatter only

---

### Directory Paths

**Location**: `main.py` (module-level constants)

```python
CAPTURE_DIR = Path(VAULT_ROOT) / "00. Inbox/0. Capture"
REVIEW_DIR = Path(VAULT_ROOT) / "00. Inbox/1. Review Queue"
```

---

### Git Actor

**Location**: `git_ops.py` (class attribute)

```python
Actor("Obsidian Librarian", "librarian@automation.local")
```

---

## Error Types

### `ValueError`
Raised when:
- `GEMINI_API_KEY` is missing
- No YAML content found in LLM response

### `yaml.YAMLError`
Raised when:
- YAML parsing fails in `parse_frontmatter()`

### `GitCommandError`
Raised when:
- Git operations fail in `GitOps.commit_and_push()`

### `requests.HTTPError`
Raised when:
- GitHub API returns error in `get_registration_token()`

---

## Type Hints

All functions use Python type hints where applicable:

```python
def process_note(self, note_content: str) -> dict:
    ...
```

---

## Dependencies

### Python Packages

- `google-generativeai`: Gemini API client
- `python-frontmatter`: Markdown frontmatter parsing
- `gitpython`: Git operations
- `pyyaml`: YAML parsing
- `requests`: HTTP requests (for token fetcher)

### System Requirements

- Python 3.10+
- Git (for repository operations)
- Docker (for containerization)

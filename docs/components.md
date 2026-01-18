# Component Documentation

This document provides detailed information about each component in the Obsidian Note Automation system.

## Application Components (`src/`)

### `main.py` - Orchestrator

**Purpose**: Main entry point that coordinates the entire note processing pipeline.

**Responsibilities**:
- Scans the Capture folder for new `.md` files
- Processes each file through the NoteProcessor
- Moves processed notes to Review Queue with generated frontmatter
- Commits and pushes changes via GitOps

**Key Functions**:
- `clean_markdown(content)`: Removes existing frontmatter from raw content
- `sanitize_filename(title)`: Creates safe filenames from titles
- `main()`: Orchestrates the entire pipeline

**Configuration**:
- `VAULT_ROOT`: From `OBSIDIAN_VAULT_ROOT` environment variable (default: current directory)
- `CAPTURE_DIR`: `{VAULT_ROOT}/00. Inbox/0. Capture`
- `REVIEW_DIR`: `{VAULT_ROOT}/00. Inbox/1. Review Queue`

**Dependencies**:
- `NoteProcessor` (from `processor.py`)
- `GitOps` (from `git_ops.py`)
- `frontmatter` library

---

### `processor.py` - AI Processing Coordinator

**Purpose**: Coordinates the AI analysis of notes by combining context with LLM calls.

**Class**: `NoteProcessor`

**Key Methods**:
- `__init__(vault_root)`: Initializes with ContextLoader and LLMClient
- `process_note(note_content) -> dict`: Main processing method

**Flow**:
1. Loads full context (system instructions, tag glossary, code registry)
2. Builds user prompt with context + raw note content
3. Calls LLM via `LLMClient.generate_content()`
4. Extracts YAML from LLM response via `yaml_parser`
5. Parses frontmatter into dictionary

**Dependencies**:
- `LLMClient` (from `llm_client.py`)
- `ContextLoader` (from `context_loader.py`)
- `yaml_parser` (from `yaml_parser.py`)

**System Prompt**:
Defines the AI's role as "Head Librarian" with tasks:
- Analyze note intent
- Classify type, status, code
- Enrich with title and tags
- Suggest folder path

---

### `context_loader.py` - Context Management

**Purpose**: Loads and aggregates context files from the Obsidian vault.

**Class**: `ContextLoader`

**Key Methods**:
- `__init__(vault_root)`: Initializes with vault root path
- `read_file(relative_path) -> str`: Reads a file from vault (returns empty if not found)
- `get_full_context() -> str`: Aggregates all context into a single string

**Context Files Loaded**:
1. **System Instructions**: `30. Areas/4. Personal Management/Obsidian/Obsidian System Instructions.md`
   - Defines the rules and guidelines for note organization
2. **Tag Glossary**: `00. Inbox/00. Tag Glossary.md`
   - Defines available tags and their meanings
3. **Code Registry**: `00. Inbox/00. Code Registry.md`
   - Lists project codes (e.g., PEPS-P4, REX-*)

**Error Handling**:
- Missing files log warnings but don't fail processing
- Returns empty string if file doesn't exist

---

### `llm_client.py` - Gemini API Client

**Purpose**: Interfaces with Google Gemini API for note analysis.

**Class**: `LLMClient`

**Initialization**:
- Reads `GEMINI_API_KEY` from environment variables
- Configures Gemini API client
- Creates `GenerativeModel` with optional system instruction

**Key Methods**:
- `__init__(model_name, system_instruction)`: Initializes client
- `generate_content(prompt) -> str`: Sends prompt to Gemini and returns response

**Configuration**:
- **Model**: `gemini-2.5-flash` (default, can be overridden)
- **System Instruction**: Optional, passed to model at initialization

**Error Handling**:
- Raises `ValueError` if `GEMINI_API_KEY` is missing
- Propagates API errors from Gemini SDK

**Dependencies**:
- `google-generativeai` library

---

### `yaml_parser.py` - Frontmatter Parsing

**Purpose**: Extracts and parses YAML frontmatter from LLM responses.

**Key Functions**:
- `extract_yaml_from_response(response) -> Optional[str]`: Extracts YAML from markdown code blocks
- `parse_frontmatter(yaml_content) -> Dict`: Parses YAML string into Python dictionary

**YAML Extraction**:
- Looks for YAML in markdown code blocks: ````yaml ... ```` or ```` ... ````
- Strips leading/trailing whitespace and code block markers
- Returns `None` if no YAML found

**YAML Parsing**:
- Uses `pyyaml` library to parse YAML
- Validates that result is a dictionary
- Raises `YAMLError` on parsing failure

**Error Handling**:
- Returns `None` if extraction fails (caller should handle)
- Raises `YAMLError` if parsing fails (caller should catch)

---

### `git_ops.py` - Git Operations

**Purpose**: Handles Git commit and push operations.

**Class**: `GitOps`

**Key Methods**:
- `__init__(repo_path)`: Initializes with Git repository path
- `has_changes() -> bool`: Checks if repository has uncommitted changes
- `commit_and_push(message)`: Stages all changes, commits, and pushes

**Git Actor**:
- **Name**: "Obsidian Librarian"
- **Email**: "librarian@automation.local"

**Commit Behavior**:
- Stages all changes including deletions and untracked files (`git add -A`)
- Uses custom actor for commit
- Pushes to `origin` remote

**Error Handling**:
- Raises `GitCommandError` on Git operation failures
- Skips commit/push if no changes detected

**Dependencies**:
- `GitPython` library

---

### `token_fetcher.py` - Runner Registration Token Fetcher

**Purpose**: Fetches GitHub Actions runner registration tokens using a PAT.

**Key Functions**:
- `get_registration_token(repo_url, pat) -> str`: Fetches registration token via GitHub API

**API Endpoint**:
```
POST https://api.github.com/repos/{owner}/{repo}/actions/runners/registration-token
```

**Authentication**:
- Tries `token {pat}` header first
- Falls back to `Bearer {pat}` header if 403

**Error Handling**:
- Handles HTTP errors (401, 403, 404, 500+)
- Provides specific error messages for common issues:
  - Invalid/expired PAT
  - Fine-grained PAT (not supported)
  - Missing `repo` scope
  - Repository access issues

**CLI Usage**:
```bash
python3 src/token_fetcher.py <repo_url> <pat>
```

---

## Infrastructure Components

### `Dockerfile` - Container Image Definition

**Base Image**: Ubuntu 22.04

**Build Steps**:
1. Install system dependencies (curl, git, Python, etc.)
2. Create non-root `runner` user
3. Download and extract GitHub Actions runner binary
4. Install runner dependencies
5. Install Python dependencies (google-generativeai, python-frontmatter, gitpython, pyyaml, requests)
6. Copy application source code to `/home/runner/src/`
7. Copy and make entrypoint script executable

**Architecture Support**:
- **ARM64**: Default for Raspberry Pi
- **x64**: For local development/testing

**Build Args**:
- `RUNNER_VERSION`: GitHub Actions runner version (default: "2.311.0")
- `RUNNER_ARCH`: Architecture to build for (default: "arm64")

---

### `entrypoint.sh` - Container Startup Script

**Purpose**: Handles runner registration and startup.

**Flow**:
1. Validates `REPO_URL` environment variable
2. Checks if runner is already configured (`.runner` file exists)
   - If configured: Start runner immediately
   - If not: Proceed to registration
3. Fetches registration token:
   - **Option A**: Use `GITHUB_PAT` to fetch token dynamically (recommended)
   - **Option B**: Use `GITHUB_TOKEN` directly (legacy)
4. Registers runner with GitHub using `config.sh`
5. Starts runner with `run.sh`

**Registration Labels**:
- `self-hosted`
- `docker`
- `pi`

**Error Handling**:
- Validates URL format
- Provides helpful error messages for token/PAT issues
- Handles permission errors gracefully

---

### `docker-compose.yml` - Container Orchestration

**Service**: `librarian-runner`

**Configuration**:
- **Build**: Uses current directory as context
- **Image**: `obs-librarian-runner`
- **Restart Policy**: `unless-stopped`
- **Environment Variables**:
  - `REPO_URL`: GitHub repository URL
  - `GITHUB_PAT`: Personal Access Token (for token fetching)
  - `GITHUB_TOKEN`: Legacy registration token (optional)
  - `RUNNER_NAME`: Name for the runner (default: "pi-librarian")
  - `GEMINI_API_KEY`: For local testing (workflow uses secrets)

**Note**: Volume mounts are commented out by default. Uncomment for development.

---

## Workflow Components

### `.github/workflows/ingest.yml` - GitHub Actions Workflow

**Purpose**: Triggers note processing when new files are added to Capture folder.

**Trigger**:
- **Event**: `push`
- **Paths**: `00. Inbox/0. Capture/**/*.md`
- **Branches**: `master`

**Job**: `librarian`
- **Runner**: `self-hosted`
- **Steps**:
  1. **Checkout Vault**: Checks out the repository
  2. **Run Librarian**: Executes `python3 /home/runner/src/main.py`

**Environment Variables**:
- `GEMINI_API_KEY`: From repository secrets
- `OBSIDIAN_VAULT_ROOT`: Set to `github.workspace`

**Permissions**:
- `contents: write` - Required for Git push

---

## Utility Scripts

### `run_manual.py` - Manual Testing Script

**Purpose**: Allows testing the note processor without running the full pipeline.

**Usage**:
```bash
python3 src/run_manual.py <path_to_note> [vault_root]
```

**What it does**:
- Reads a note file
- Processes it with `NoteProcessor`
- Prints the generated frontmatter as YAML
- Does NOT move files or commit changes

**Use Cases**:
- Testing AI prompts
- Debugging processor issues
- Validating context loading

---

### `test_gemini.py` - Gemini API Test Script

**Purpose**: Tests Gemini API connectivity and basic functionality.

**Usage**:
```bash
python3 src/test_gemini.py
```

**What it does**:
- Checks if `GEMINI_API_KEY` is set
- Sends a test prompt to Gemini
- Prints the response

**Use Cases**:
- Verifying API key is correct
- Testing network connectivity
- Checking API availability

---

## Component Interactions

```
main.py
  ├─> processor.py
  │     ├─> context_loader.py (loads vault context)
  │     ├─> llm_client.py (calls Gemini API)
  │     └─> yaml_parser.py (parses AI response)
  └─> git_ops.py (commits/pushes changes)

entrypoint.sh
  └─> token_fetcher.py (fetches registration token)
```

## Error Handling Patterns

All components follow consistent error handling:

1. **Validation Errors**: Raise early with clear messages
2. **Missing Dependencies**: Log warnings, continue if possible
3. **External API Errors**: Propagate with context
4. **File I/O Errors**: Log and continue processing remaining files
5. **Git Errors**: Raise exceptions (caller decides whether to continue)

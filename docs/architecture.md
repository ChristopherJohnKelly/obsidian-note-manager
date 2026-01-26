# Architecture Overview

## System Architecture

The Obsidian Note Automation system is built around a **GitHub Actions self-hosted runner** that runs in a Docker container on a Raspberry Pi. The system provides two complementary pipelines for vault organization using Google Gemini AI.

## Dual Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          OBSIDIAN VAULT REPOSITORY                          │
│                                                                             │
│  ┌─────────────────────┐      ┌─────────────────────┐                       │
│  │ 00. Inbox/          │      │ 20. Projects/       │                       │
│  │   0. Capture/       │      │ 30. Areas/          │                       │
│  │   └─ Raw notes      │      │   └─ Existing notes │                       │
│  └─────────────────────┘      └─────────────────────┘                       │
│           │                            │                                    │
│           │ Git Push                   │ Scheduled/Manual                   │
│           ▼                            ▼                                    │
│  ┌─────────────────────┐      ┌─────────────────────┐                       │
│  │ INGESTION PIPELINE  │      │ MAINTENANCE PIPELINE│                       │
│  │ (The Librarian)     │      │ (Night Watchman)    │                       │
│  │                     │      │                     │                       │
│  │ main.py             │      │ vault_maintenance.py│                       │
│  │   ├─ processor.py   │      │   ├─ scanner.py     │                       │
│  │   ├─ filer.py       │      │   ├─ fixer.py       │                       │
│  │   └─ git_ops.py     │      │   └─ state_manager  │                       │
│  └─────────────────────┘      └─────────────────────┘                       │
│           │                            │                                    │
│           └──────────┬─────────────────┘                                    │
│                      ▼                                                      │
│         ┌────────────────────────┐                                          │
│         │ SHARED COMPONENTS      │                                          │
│         │                        │                                          │
│         │ ├─ llm_client.py       │ ◄── Google Gemini API                    │
│         │ ├─ context_loader.py   │                                          │
│         │ ├─ indexer.py          │                                          │
│         │ ├─ response_parser.py  │                                          │
│         │ └─ vault_utils.py      │                                          │
│         └────────────────────────┘                                          │
│                      │                                                      │
│                      ▼                                                      │
│         ┌────────────────────────┐                                          │
│         │ 00. Inbox/1. Review    │                                          │
│         │   └─ Proposals         │ ◄── Human Review Point                   │
│         └────────────────────────┘                                          │
│                      │                                                      │
│                      │ User sets librarian: file                            │
│                      ▼                                                      │
│         ┌────────────────────────┐                                          │
│         │ Final Vault Locations  │                                          │
│         │ 20. Projects/...       │                                          │
│         │ 30. Areas/...          │                                          │
│         └────────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Pipeline Details

### Ingestion Pipeline (The Librarian)

Triggered by Git push events to the Capture folder.

```
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE FLOW                       │
│                                                                  │
│  1. main.py orchestrates the pipeline                            │
│     │                                                            │
│     ├─► Phase 1: FILE APPROVED PROPOSALS                         │
│     │   └─► filer.py: NoteFiler.file_approved_notes()            │
│     │       ├─ Scans Review Queue for librarian: file            │
│     │       ├─ Parses %%FILE%% blocks via ResponseParser         │
│     │       ├─ Handles maintenance fixes (target-file)           │
│     │       ├─ Creates files with collision protection           │
│     │       └─ Deletes processed proposals                       │
│     │                                                            │
│     ├─► Phase 2: PROCESS NEW NOTES                               │
│     │   └─► processor.py: NoteProcessor.process_note()           │
│     │       ├─ Extracts LLM-Instructions from note               │
│     │       ├─ Loads vault context (ContextLoader)               │
│     │       ├─ Calls Gemini API (LLMClient)                      │
│     │       ├─ Parses response (ResponseParser)                  │
│     │       └─ Creates proposal note with frontmatter            │
│     │                                                            │
│     └─► Phase 3: COMMIT CHANGES                                  │
│         └─► git_ops.py: GitOps.commit_and_push()                 │
└─────────────────────────────────────────────────────────────────┘
```

### Maintenance Pipeline (Night Watchman)

Triggered by scheduled cron jobs or manual execution.

```
┌─────────────────────────────────────────────────────────────────┐
│                 MAINTENANCE PIPELINE FLOW                        │
│                                                                  │
│  1. vault_maintenance.py orchestrates the pipeline               │
│     │                                                            │
│     ├─► Phase 1: SCAN VAULT                                      │
│     │   └─► scanner.py: VaultScanner.scan()                      │
│     │       ├─ Scans 20. Projects/ and 30. Areas/                │
│     │       ├─ Scores files for quality deficits:                │
│     │       │   ├─ Missing aliases/tags (+10)                    │
│     │       │   ├─ Missing project code (+50)                    │
│     │       │   └─ Generic filename (+20)                        │
│     │       └─ Returns sorted candidate list                     │
│     │                                                            │
│     ├─► Phase 2: FILTER CANDIDATES                               │
│     │   ├─► state_manager.py: filter by cooldown (7 days)        │
│     │   └─► check_conflict(): skip recently modified (1 hour)    │
│     │                                                            │
│     ├─► Phase 3: GENERATE FIX PROPOSALS                          │
│     │   └─► fixer.py: MaintenanceFixer.generate_fixes()          │
│     │       ├─ Reads original file content                       │
│     │       ├─ Constructs maintenance instructions               │
│     │       ├─ Calls LLM for fix proposal                        │
│     │       ├─ Creates proposal with target-file metadata        │
│     │       └─ Writes to Review Queue                            │
│     │                                                            │
│     └─► Phase 4: RECORD HISTORY                                  │
│         └─► state_manager.py: record_scan()                      │
│             └─ Saves to 99. System/maintenance_history.json      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Orchestrators

| Component | File | Purpose |
|-----------|------|---------|
| Ingestion Pipeline | `main.py` | Processes new notes from Capture folder |
| Maintenance Pipeline | `vault_maintenance.py` | Scans vault for quality issues |

### 2. Processing Components

| Component | File | Class | Purpose |
|-----------|------|-------|---------|
| Note Processor | `processor.py` | `NoteProcessor` | Coordinates AI analysis of new notes |
| Note Filer | `filer.py` | `NoteFiler` | Executes approved proposals |
| Maintenance Fixer | `fixer.py` | `MaintenanceFixer` | Generates fix proposals for quality issues |
| Vault Scanner | `scanner.py` | `VaultScanner` | Identifies quality deficits in existing notes |
| State Manager | `state_manager.py` | `StateManager` | Tracks scan history and cooldown periods |

### 3. Shared Infrastructure

| Component | File | Class | Purpose |
|-----------|------|-------|---------|
| LLM Client | `llm_client.py` | `LLMClient` | Interfaces with Google Gemini API |
| Context Loader | `context_loader.py` | `ContextLoader` | Loads vault context (instructions, glossary, codes) |
| Vault Indexer | `indexer.py` | `VaultIndexer` | Builds skeleton of valid link targets |
| Response Parser | `response_parser.py` | `ResponseParser` | Parses %%FILE%% markers from LLM output |
| YAML Parser | `yaml_parser.py` | Functions | Extracts YAML from markdown code blocks |
| Vault Utils | `vault_utils.py` | Functions | Shared utilities (path safety, exclusions) |
| Git Operations | `git_ops.py` | `GitOps` | Handles Git commit and push |

### 4. Infrastructure

| Component | File | Purpose |
|-----------|------|---------|
| Docker Image | `Dockerfile` | Container image for runner |
| Orchestration | `docker-compose.yml` | Container configuration |
| Startup | `entrypoint.sh` | Runner registration and startup |
| Token Fetcher | `token_fetcher.py` | Fetches GitHub runner registration tokens |

## Obsidian Vault Structure

The system expects this vault structure:

```
vault-root/
├── 00. Inbox/
│   ├── 0. Capture/              # Input: Raw notes placed here
│   ├── 1. Review Queue/         # Output: Proposals for human review
│   ├── 00. Tag Glossary.md      # Context: Tag definitions
│   └── 00. Code Registry.md     # Context: Project codes (optional, auto-scanned)
├── 20. Projects/                # Scanned by maintenance
│   └── {Project folders}/
├── 30. Areas/                   # Scanned by maintenance
│   └── 4. Personal Management/
│       └── Obsidian/
│           └── Obsidian System Instructions.md  # Context: Rules
├── 40. Resources/               # Indexed for linking
└── 99. System/
    └── maintenance_history.json # Maintenance scan history
```

## Data Flow

### Ingestion Flow

1. **User Action**: User creates note in `00. Inbox/0. Capture/` and pushes to GitHub
2. **Trigger**: GitHub Actions workflow detects push
3. **Job Dispatch**: Workflow runs on self-hosted runner
4. **Phase 1 - Filing**: Filer checks for approved proposals (`librarian: file`)
5. **Phase 2 - Processing**: For each note in Capture:
   - Read content and extract instructions
   - Load context (system instructions, glossary, codes, skeleton)
   - Send to Gemini AI for analysis
   - Parse response and create proposal
   - Move proposal to Review Queue
6. **Commit**: Git commits and pushes all changes
7. **User Review**: User reviews proposals and sets `librarian: file` to approve

### Maintenance Flow

1. **Trigger**: Scheduled cron or manual execution
2. **Scan**: VaultScanner identifies quality issues in Projects/Areas
3. **Filter**: StateManager removes files in cooldown period
4. **Conflict Check**: Skip files modified in last hour
5. **Fix Generation**: MaintenanceFixer creates proposals via LLM
6. **Record**: StateManager records scan in history
7. **User Review**: User reviews proposals and approves fixes

## Proposal Types

### Regular Proposals (Ingestion)

```yaml
---
folders-to-create:
  - 20. Projects/New Project
files-to-create:
  - 20. Projects/New Project/Note.md
librarian: review
---
%%INSTRUCTIONS%%
...
---
%%ORIGINAL%%
...
---
%%FILE: 20. Projects/New Project/Note.md%%
...
```

### Maintenance Proposals (Fix)

```yaml
---
type: file_change_proposal
target-file: 30. Areas/Existing/Note.md    # Critical: identifies original file
score: 60
reason: Missing aliases/tags, Missing Project Code
librarian: review
---
%%INSTRUCTIONS%%
...
---
%%ORIGINAL%%
...
---
%%FILE: 30. Areas/Existing/CODE-Note.md%%  # May include rename
...
```

The `target-file` metadata is crucial for maintenance fixes:
- Tells the filer this is an update, not a new file
- Enables proper handling of renames (original deletion)
- Prevents creation of duplicate files (Note.md, Note-1.md, Note-2.md)

## Security & Authentication

### GitHub Authentication
- **Personal Access Token (PAT)**: Used for automatic runner registration
  - Required: Classic PAT with `repo` scope
  - Stored: Environment variable `GITHUB_PAT` in `.env` file
- **Registration Token**: Auto-fetched using PAT (expires after 1 hour)
- **GITHUB_TOKEN**: Workflow token for checkout/push (managed by GitHub Actions)

### API Keys
- **GEMINI_API_KEY**: Stored in GitHub Secrets, passed to workflow

### Safety Mechanisms
- **Path Traversal Protection**: Filer validates paths contain no `..` or absolute paths
- **Collision Protection**: `get_safe_path()` prevents overwriting unrelated files
- **Conflict Detection**: Maintenance skips files modified within 1 hour
- **Cooldown Period**: Files aren't re-scanned within 7 days

## Technology Stack

- **Containerization**: Docker, Docker Compose
- **Orchestration**: GitHub Actions (self-hosted runner)
- **Runtime**: Python 3.10+
- **AI/ML**: Google Gemini API (`google-generativeai` SDK)
- **Markdown Processing**: `python-frontmatter` library
- **Git Operations**: `GitPython` library
- **Runner**: GitHub Actions Runner v2.311.0+ (auto-updates)

## Scalability & Extensibility

The architecture is designed to be:
- **Modular**: Each component has a single responsibility
- **Extensible**: Easy to add new processors or scanners
- **Testable**: Components can be tested independently
- **Maintainable**: Clear separation between pipelines
- **Safe**: Multiple protection mechanisms against data loss

# Architecture Overview

## System Architecture

The Obsidian Note Automation system is built around a **GitHub Actions self-hosted runner** that runs in a Docker container on a Raspberry Pi. The system automates the processing, tagging, and organization of Obsidian notes using Google Gemini AI.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Obsidian Notes Repository                    │
│  (GitHub: christopherjohnkelly/obsidian-notes)                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 00. Inbox/0. Capture/                                    │   │
│  │   └─ Raw notes (user creates via Obsidian/Git push)      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                        │                                        │
│                        │ Git Push Event                         │
│                        ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ .github/workflows/ingest.yml                             │   │
│  │   - Trigger: push to 00. Inbox/0. Capture/**/*.md        │   │
│  │   - Target: runs-on: self-hosted                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        │
                        │ Job Dispatch
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              Raspberry Pi (Self-Hosted Runner)                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Docker Container (obs-librarian-runner)                  │   │
│  │                                                          │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │ GitHub Actions Runner                              │  │   │
│  │  │  - Listens for jobs                                │  │   │
│  │  │  - Checks out repository                           │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                        │                                 │   │
│  │                        ▼                                 │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │ Python Application (/home/runner/src/)             │  │   │
│  │  │                                                    │  │   │
│  │  │  1. main.py          - Orchestrator                │  │   │
│  │  │  2. processor.py     - AI processing logic         │  │   │
│  │  │  3. context_loader.py - Loads vault context        │  │   │
│  │  │  4. llm_client.py    - Gemini API client           │  │   │
│  │  │  5. yaml_parser.py   - Frontmatter parsing         │  │   │
│  │  │  6. git_ops.py       - Git commit/push             │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                        │                                 │   │
│  │                        ▼                                 │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │ Google Gemini API (via GEMINI_API_KEY)             │  │   │
│  │  │  - Analyzes note content                           │  │   │
│  │  │  - Generates metadata (title, tags, folder, etc.)  │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        │
                        │ Git Push (with processed notes)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Obsidian Notes Repository                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 00. Inbox/1. Review Queue/                               │   │
│  │   └─ Processed notes with frontmatter (status: review)   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. GitHub Actions Workflow (`.github/workflows/ingest.yml`)
- **Purpose**: Trigger automation when new notes are added to the Capture folder
- **Trigger**: `push` event to `00. Inbox/0. Capture/**/*.md` on `master` branch
- **Execution**: Runs on `self-hosted` runner (Raspberry Pi)
- **Environment**: Sets `GEMINI_API_KEY` and `OBSIDIAN_VAULT_ROOT`

### 2. Self-Hosted Runner (Docker Container)
- **Base Image**: Ubuntu 22.04
- **Architecture**: ARM64 (Raspberry Pi) or x64 (local development)
- **Components**:
  - GitHub Actions runner binary (listens for jobs)
  - Python 3.10+ with dependencies
  - Application source code at `/home/runner/src/`
  - Automatic runner registration via PAT

### 3. Python Application (`src/`)
- **main.py**: Orchestrates the pipeline (scan, process, move, commit)
- **processor.py**: Coordinates AI analysis with context loading
- **context_loader.py**: Loads system instructions, tag glossary, code registry
- **llm_client.py**: Interfaces with Google Gemini API
- **yaml_parser.py**: Extracts and parses YAML frontmatter from AI responses
- **git_ops.py**: Handles Git commit and push operations

### 4. Obsidian Vault Structure
The system expects specific vault structure:
```
vault-root/
├── 00. Inbox/
│   ├── 0. Capture/          # Input: Raw notes placed here
│   ├── 1. Review Queue/     # Output: Processed notes (status: review)
│   ├── 00. Tag Glossary.md  # Context: Tag definitions
│   └── 00. Code Registry.md # Context: Project codes
├── 30. Areas/
│   └── 4. Personal Management/
│       └── Obsidian/
│           └── Obsidian System Instructions.md  # Context: Rules
└── ...
```

## Data Flow

1. **User Action**: User creates/edits a note in `00. Inbox/0. Capture/` and pushes to GitHub
2. **Trigger**: GitHub Actions workflow detects push to Capture folder
3. **Job Dispatch**: Workflow job is dispatched to self-hosted runner
4. **Checkout**: Runner checks out the repository to `_work/obsidian-notes/obsidian-notes/`
5. **Execution**: Runner executes `python3 /home/runner/src/main.py`
6. **Processing**:
   - Scans `0. Capture/` for `.md` files
   - For each file:
     - Reads content and removes existing frontmatter
     - Loads context (system instructions, tag glossary, code registry)
     - Sends note + context to Gemini AI
     - Parses YAML frontmatter from AI response
     - Adds `status: review` to metadata
     - Moves processed note to `1. Review Queue/` with sanitized filename
7. **Commit**: Git commits and pushes all changes back to repository
8. **User Review**: User reviews processed notes in Review Queue and manually files them

## Security & Authentication

### GitHub Authentication
- **Personal Access Token (PAT)**: Used for automatic runner registration token fetching
  - Required: Classic PAT with `repo` scope
  - Stored: Environment variable `GITHUB_PAT` in `.env` file
- **Registration Token**: Auto-fetched using PAT API (expires after 1 hour)
- **GITHUB_TOKEN**: Workflow token for checkout/push (managed by GitHub Actions)

### API Keys
- **GEMINI_API_KEY**: Stored in GitHub Secrets, passed to workflow as environment variable
- **Location**: Never committed to repository

## Technology Stack

- **Containerization**: Docker, Docker Compose
- **Orchestration**: GitHub Actions (self-hosted runner)
- **Runtime**: Python 3.10+
- **AI/ML**: Google Gemini API (via `google-generativeai` SDK)
- **Markdown Processing**: `python-frontmatter` library
- **Git Operations**: `GitPython` library
- **Runner**: GitHub Actions Runner v2.311.0+ (auto-updates)

## Scalability & Extensibility

The architecture is designed to be:
- **Modular**: Each component has a single responsibility
- **Extensible**: Easy to add new processors or context loaders
- **Testable**: Components can be tested independently
- **Maintainable**: Clear separation of concerns

## Future Enhancements

Potential architectural improvements:
1. Multi-vault support (multiple Obsidian vaults)
2. Queue-based processing for high-volume scenarios
3. Webhook-based triggers (alternative to Git push)
4. Local runner mode (without GitHub Actions)
5. Multiple AI provider support (beyond Gemini)

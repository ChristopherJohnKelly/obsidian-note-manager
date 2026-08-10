# Obsidian Note Automation

An automated "Librarian" system for Obsidian notes that processes raw notes using Google Gemini AI, adds metadata, tags, and manages vault organization through two complementary pipelines.

## Overview

This system automates Obsidian vault organization through two pipelines:

### 1. Ingestion Pipeline (The Librarian)
Processes new notes dropped into the Capture folder:
1. **Detect** new notes in `00. Inbox/0. Capture/`
2. **Process** them with Google Gemini AI to extract metadata and suggest organization
3. **Generate** proposals in `00. Inbox/1. Review Queue/` for human review
4. **File** approved proposals (when user sets `librarian: file`)
5. **Commit** changes back to the repository

### 2. Maintenance Pipeline (The Night Watchman)
Scans existing vault notes for quality issues:
1. **Scan** `20. Projects/` and `30. Areas/` for quality deficits
2. **Score** notes based on missing metadata, naming violations, generic titles
3. **Filter** by cooldown period and recent modifications (conflict detection)
4. **Generate** fix proposals with AI-suggested corrections
5. **Record** scan history to prevent duplicate processing

The system runs on a **Raspberry Pi** using a **GitHub Actions self-hosted runner** in a Docker container.

## Three Modes of Operation

1. **Manual**: Direct human interaction with Obsidian; no automation.
2. **Asynchronous Automation (Night Watchman)**: Runs nightly via `cron_runner` (maintenance.yml) to audit the vault against conventions and log offenders.
3. **Event-Driven Ingestion**: Runs on push to Capture/Review Queue via `ingest_runner` (ingest.yml) to file approved proposals and ingest new notes via the LLM.

## Quick Start

1. **Setup**: Follow the [Setup Guide](docs/setup.md)
2. **Configuration**: Configure GitHub authentication and API keys
3. **Deploy**: Build and start the Docker container
4. **Verify**: Check runner status in GitHub → Settings → Actions → Runners

See the [Setup Guide](docs/setup.md) for detailed instructions.

## Architecture

The system consists of:

- **GitHub Actions Workflows**: Trigger on note pushes (ingestion) and scheduled runs (maintenance)
- **Self-Hosted Runner**: Docker container on Raspberry Pi that executes jobs
- **Python Application**: Dual-pipeline processing using Gemini AI
- **Git Operations**: Workflow steps perform `git commit` and `git push` (Python mutates files only)

For more details, see the [Architecture Overview](docs/architecture.md).

## Documentation

### Getting Started

- **[Setup Guide](docs/setup.md)** - Step-by-step installation and configuration
- **[Architecture Overview](docs/architecture.md)** - System architecture and data flow

### Reference

- **[Component Documentation](docs/components.md)** - Detailed component breakdown
- **[API Reference](docs/api-reference.md)** - Technical API documentation
- **[Code Registry](docs/code-registry.md)** - File, class, and method relationships
- **[Workflow Documentation](docs/workflows.md)** - GitHub Actions workflow details

### Troubleshooting

- **[Troubleshooting Guide](docs/troubleshooting.md)** - Common issues and solutions

## Project Structure

```
obsidian-note-manager/
├── docs/                      # Comprehensive documentation
│   ├── architecture.md        # System architecture
│   ├── setup.md               # Installation guide
│   ├── components.md          # Component details
│   ├── api-reference.md       # API documentation
│   ├── code-registry.md       # Code relationships
│   ├── troubleshooting.md     # Troubleshooting guide
│   └── workflows.md           # Workflow documentation
├── example/                   # Workflow templates for vault repo
│   ├── README.md              # How to copy workflows to your vault
│   └── workflows/
│       ├── ingest.yml         # Ingestion workflow template
│       └── maintenance.yml   # Maintenance workflow template
├── scripts/                   # Runner setup scripts
│   ├── entrypoint.sh          # Container startup script
│   ├── token_fetcher.py       # PAT-based runner registration
│   ├── test_note.md           # Development test file
│   └── requirements.txt       # Local dev dependencies
├── src_v2/                    # Application code (Clean Architecture)
│   ├── entrypoints/           # CLI and workflow entry points
│   ├── use_cases/             # Business logic
│   ├── core/                  # Domain and interfaces
│   └── infrastructure/        # External adapters
├── Dockerfile                 # Container image definition
├── docker-compose.yml        # Container orchestration
└── .env.example               # Environment template
```

## Requirements

### Hardware

- Raspberry Pi (Model 3B+ or newer)
- SD Card (32GB+)
- Internet connection

### Software

- Docker and Docker Compose
- GitHub account with repository access
- Google Gemini API key

### GitHub Configuration

- Classic Personal Access Token (PAT) with `repo` scope
- `GEMINI_API_KEY` secret in repository settings
- Workflow files in obsidian-notes repository

## Usage

### Automatic Processing (Ingestion)

1. **Add note**: Create/edit a note in `00. Inbox/0. Capture/` via Obsidian
2. **Push to GitHub**: Commit and push the note
3. **Wait for processing**: Workflow runs automatically (usually 30-60 seconds)
4. **Review**: Check `00. Inbox/1. Review Queue/` for processed proposals
5. **Approve**: Set `librarian: file` in frontmatter to execute the proposal

### Maintenance Scanning

The maintenance pipeline can run:
- **Scheduled**: Via GitHub Actions cron trigger
- **Manually**: `python3 -m src_v2.entrypoints.cron_runner` (or trigger workflow manually)

It will:
1. Scan for quality issues (missing metadata, naming violations)
2. Generate fix proposals in Review Queue
3. Track scan history to prevent duplicate processing

### Manual Testing

```bash
# Run ingestion pipeline manually (from repo root with vault checked out)
docker compose exec librarian-runner python3 -m src_v2.entrypoints.ingest_runner

# Run maintenance scan manually
docker compose exec librarian-runner python3 -m src_v2.entrypoints.cron_runner
```

## Workflow States

Notes flow through these states:

```
[0. Capture] → [Processing] → [1. Review Queue] → [Filing] → [Final Location]
     ↑                              ↓
     └── User creates note    User reviews & sets
                              librarian: file
```

Maintenance proposals follow:

```
[Vault Scan] → [Quality Issues] → [1. Review Queue] → [Filing] → [Updated Note]
     ↑                                   ↓
     └── Night Watchman           User reviews & approves
```

## Troubleshooting

Common issues and solutions:

- **Runner not appearing in GitHub**: See [Troubleshooting Guide](docs/troubleshooting.md#runner-not-appearing-in-github)
- **Workflow not triggering**: See [Troubleshooting Guide](docs/troubleshooting.md#workflow-not-triggering)
- **Gemini API errors**: See [Troubleshooting Guide](docs/troubleshooting.md#gemini-api-errors)

For more troubleshooting help, see the [Troubleshooting Guide](docs/troubleshooting.md).

## Security

- **Environment Variables**: Sensitive values stored in `.env` (excluded from Git)
- **GitHub Secrets**: API keys stored in repository secrets
- **Non-Root User**: Runner runs as non-root user in container
- **Classic PAT Required**: Must use Classic PAT with `repo` scope (not fine-grained)
- **Path Traversal Protection**: Filer validates paths to prevent escaping vault root
- **Conflict Detection**: Maintenance skips files modified within the last hour

## Contributing

This is a personal project for automating Obsidian note organization. For questions or suggestions, please open an issue.

## License

This project is for personal use only.

---

For detailed documentation, see the [docs/](docs/) folder.

## Docker Images

### obsidian-vault-worker

```bash
docker pull ghcr.io/christopherjohnkelly/obsidian-vault-worker:latest
```

```bash
docker run -d \
  -e VAULT_PATH=/vault \
  -e REPO_URL=https://github.com/your-org/your-vault \
  -e GITHUB_PAT=your_pat_here \
  -e GEMINI_API_KEY=your_gemini_key \
  -e TEMPORAL_HOST=your-temporal-host:7233 \
  ghcr.io/christopherjohnkelly/obsidian-vault-worker:latest
```

| Variable | Description |
|---|---|
| `VAULT_PATH` | Path to the Obsidian vault directory inside the container |
| `REPO_URL` | GitHub repository URL for the vault |
| `GITHUB_PAT` | GitHub Personal Access Token with `repo` scope |
| `GEMINI_API_KEY` | Google Gemini API key for AI processing |
| `TEMPORAL_HOST` | Temporal server host and port (e.g. `localhost:7233`) |

### obsidian-copilot-ui

```bash
docker pull ghcr.io/christopherjohnkelly/obsidian-copilot-ui:latest
```

```bash
docker run -d \
  -e TEMPORAL_ADDRESS=your-temporal-host:7233 \
  -e VAULT_PATH=/vault \
  -p 8000:8000 \
  ghcr.io/christopherjohnkelly/obsidian-copilot-ui:latest
```

Chainlit listens on port 8000 inside the container.

| Variable | Description |
|---|---|
| `TEMPORAL_ADDRESS` | Temporal server address (host:port) — required; the app fails at startup without it |
| `VAULT_PATH` | Vault path passed to new copilot sessions (optional, default `/vault`) |

### obsidian-github-runner

```bash
docker pull ghcr.io/christopherjohnkelly/obsidian-github-runner:latest
```

```bash
docker run -d \
  -e TEMPORAL_HOST=your-temporal-host:7233 \
  -e VAULT_PATH=/vault \
  -e CONTEXT_CODE=OBSE \
  -e REPO_OWNER=your-org \
  -e REPO_NAME=your-vault \
  -e GITHUB_TOKEN=your_token_here \
  -e PR_BRANCH=main \
  -e RUN_ID=manual-run \
  ghcr.io/christopherjohnkelly/obsidian-github-runner:latest \
  python3 trigger.py --workflow FilerIngestionWorkflow
```

The image's `CMD` is replaced by any trailing `docker run` arguments, so the
full command must be given. `--workflow` is required; valid values are
`FilerIngestionWorkflow` and `NightWatchmanWorkflow` (see
`packages/shared/workflow_names.py`). An optional `--source-path` narrows a
filer run to one file.

| Variable | Description |
|---|---|
| `TEMPORAL_HOST` | Temporal server host and port (optional, default `localhost:7233`) |
| `VAULT_PATH` | Vault path forwarded to triggered workflows |
| `CONTEXT_CODE` | Vault context code forwarded to triggered workflows |
| `REPO_OWNER` | GitHub repository owner for triggered workflows |
| `REPO_NAME` | GitHub repository name for triggered workflows |
| `GITHUB_TOKEN` | GitHub token used by triggered workflows |
| `PR_BRANCH` | Branch name used by triggered workflows |
| `RUN_ID` | Unique suffix for the workflow id (optional, default `default`) |

## Post-Merge Manual Validation

After merging changes, verify the CI/CD pipeline end-to-end:

1. **Open a test PR** — create a branch with a small change and open a pull request to trigger the CI workflow automatically.
2. **Trigger `build-push.yml` via `workflow_dispatch`** — go to Actions → Build and Push → Run workflow to manually kick off a build for all three images.
3. **Verify images in GHCR** — after the workflow completes, navigate to `ghcr.io/christopherjohnkelly` and confirm that `obsidian-vault-worker`, `obsidian-copilot-ui`, and `obsidian-github-runner` all have a freshly pushed `:latest` tag.
4. **Pull and smoke-test** — run `docker pull ghcr.io/christopherjohnkelly/obsidian-vault-worker:latest` (and the other two images) to confirm they are accessible and pull successfully.

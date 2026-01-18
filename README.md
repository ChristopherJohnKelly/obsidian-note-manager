# Obsidian Note Automation

An automated "Librarian" agent for Obsidian notes that processes raw notes using Google Gemini AI, adds metadata, tags, and moves them to a review queue.

## Overview

This system automates the organization of Obsidian notes by:

1. **Detecting** new notes in the `00. Inbox/0. Capture` folder
2. **Processing** them with Google Gemini AI to extract metadata (title, tags, type, folder)
3. **Moving** processed notes to `00. Inbox/1. Review Queue` with `status: review`
4. **Committing** changes back to the repository

The system runs on a **Raspberry Pi** using a **GitHub Actions self-hosted runner** in a Docker container.

## Quick Start

1. **Setup**: Follow the [Setup Guide](docs/setup.md)
2. **Configuration**: Configure GitHub authentication and API keys
3. **Deploy**: Build and start the Docker container
4. **Verify**: Check runner status in GitHub → Settings → Actions → Runners

See the [Setup Guide](docs/setup.md) for detailed instructions.

## Architecture

The system consists of:

- **GitHub Actions Workflow**: Triggers when notes are pushed to the Capture folder
- **Self-Hosted Runner**: Docker container on Raspberry Pi that executes jobs
- **Python Application**: Processes notes using Gemini AI
- **Git Operations**: Commits and pushes processed notes back to the repository

For more details, see the [Architecture Overview](docs/architecture.md).

## Documentation

### Getting Started

- **[Setup Guide](docs/setup.md)** - Step-by-step installation and configuration
- **[Architecture Overview](docs/architecture.md)** - System architecture and data flow

### Reference

- **[Component Documentation](docs/components.md)** - Detailed component breakdown
- **[API Reference](docs/api-reference.md)** - Technical API documentation
- **[Workflow Documentation](docs/workflows.md)** - GitHub Actions workflow details

### Troubleshooting

- **[Troubleshooting Guide](docs/troubleshooting.md)** - Common issues and solutions

## Project Structure

```
obsidian-note-manager/
├── docs/                    # Comprehensive documentation
│   ├── architecture.md      # System architecture
│   ├── setup.md             # Installation guide
│   ├── components.md        # Component details
│   ├── api-reference.md     # API documentation
│   ├── troubleshooting.md   # Troubleshooting guide
│   └── workflows.md         # Workflow documentation
├── runner-setup/            # Docker setup for self-hosted runner
│   ├── Dockerfile           # Container image definition
│   ├── docker-compose.yml   # Container orchestration
│   ├── entrypoint.sh        # Startup script
│   ├── src/                 # Python application code
│   │   ├── main.py          # Orchestrator
│   │   ├── processor.py     # AI processing logic
│   │   ├── context_loader.py # Context loading
│   │   ├── llm_client.py    # Gemini API client
│   │   ├── yaml_parser.py   # Frontmatter parsing
│   │   └── git_ops.py       # Git operations
│   └── README.md            # Quick start guide
└── .github/
    └── workflows/
        └── ingest.yml       # GitHub Actions workflow template
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
- `.github/workflows/ingest.yml` workflow file in obsidian-notes repository

## Usage

### Automatic Processing

1. **Add note**: Create/edit a note in `00. Inbox/0. Capture/` via Obsidian
2. **Push to GitHub**: Commit and push the note
3. **Wait for processing**: Workflow runs automatically (usually 30-60 seconds)
4. **Review**: Check `00. Inbox/1. Review Queue/` for processed notes

### Manual Testing

```bash
# Test Gemini API connection
docker compose exec librarian-runner python3 src/test_gemini.py

# Process a single note manually
docker compose exec librarian-runner python3 src/run_manual.py /path/to/note.md /vault/root
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

## Contributing

This is a personal project for automating Obsidian note organization. For questions or suggestions, please open an issue.

## License

This project is for personal use only.

---

For detailed documentation, see the [docs/](docs/) folder.

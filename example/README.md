# Example Workflows

These workflow files are **templates** for the repository containing your Obsidian notes vault (e.g. `obsidian-notes`). They are **not** meant to run in this `obsidian-note-manager` repository.

## Usage

Copy the workflow files to your vault repository's `.github/workflows/` directory:

```bash
# From your obsidian-notes (vault) repository
mkdir -p .github/workflows
cp /path/to/obsidian-note-manager/example/workflows/ingest.yml .github/workflows/
cp /path/to/obsidian-note-manager/example/workflows/maintenance.yml .github/workflows/
```

## Workflows

- **ingest.yml** - Triggers on pushes to `00. Inbox/0. Capture/` and `00. Inbox/1. Review Queue/`. Runs the Librarian pipeline to process new notes and file approved proposals.
- **maintenance.yml** - Runs on a schedule (daily at 2:00 AM UTC) and via manual dispatch. Runs the Night Watchman pipeline to scan the vault for quality issues and generate fix proposals.

Both workflows run on a self-hosted runner (e.g. Raspberry Pi in Docker) that has the obsidian-note-manager application installed. The workflows trigger on pushes to the vault and execute the Librarian/Night Watchman pipelines.

# Ingest Pipeline Deployment (obsidian-notes)

The ingestion pipeline uses `src_v2` (Clean Architecture). To use it in your **obsidian-notes** repository:

## Copy the Workflow

1. Copy the workflow template from this repository:
   - **Source**: `obsidian-note-manager/example/workflows/ingest.yml`
   - **Destination**: `obsidian-notes/.github/workflows/ingest.yml`

2. The workflow runs on a self-hosted runner. The obsidian-note-manager application is **pre-installed** in the Docker container. No `pip install` or checkout of obsidian-note-manager is required.

3. The workflow checks out only your vault (obsidian-notes). The Python app is already available in the container.

## What the Workflow Does

- **Run command**: `python3 -m src_v2.entrypoints.ingest_runner`
- **Git**: Commit and push are performed by **workflow steps** (not Python). The Python application only mutates files.

## Verify

After copying, push a test note to `00. Inbox/0. Capture/` and confirm the workflow runs successfully. Check the "Run Librarian" and "Commit and push changes" steps in the Actions log.

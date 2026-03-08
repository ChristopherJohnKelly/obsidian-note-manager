# Ingest Pipeline Deployment (obsidian-notes)

The ingestion pipeline has been migrated to `src_v2` (Clean Architecture). To use it in your **obsidian-notes** repository:

## Copy the Workflow

1. Copy the updated workflow file from this repository:
   - **Source**: `obsidian-note-manager/.github/workflows/ingest.yml`
   - **Destination**: `obsidian-notes/.github/workflows/ingest.yml`

2. Ensure the workflow has permission to checkout `obsidian-note-manager`. The workflow checks out both:
   - Your vault (obsidian-notes) as the workspace root
   - obsidian-note-manager as a subdirectory (from `${{ github.repository_owner }}/obsidian-note-manager`)

3. If your obsidian-note-manager repo is in a different organization, edit the `Checkout obsidian-note-manager` step and set the `repository` to your actual repo path (e.g. `your-org/obsidian-note-manager`).

## What Changed

- **Run command**: `python3 /home/runner/src/main.py` → `python3 -m src_v2.entrypoints.ingest_runner`
- **Git**: Commit and push are now performed by workflow steps (no Python Git code)
- **Dependencies**: The workflow installs obsidian-note-manager via `pip install -e obsidian-note-manager`

## Verify

After copying, push a test note to `00. Inbox/0. Capture/` and confirm the workflow runs successfully.

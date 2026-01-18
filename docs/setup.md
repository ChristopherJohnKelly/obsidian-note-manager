# Setup Guide

This guide provides step-by-step instructions for setting up the Obsidian Note Automation system on a Raspberry Pi.

## Prerequisites

### Hardware
- Raspberry Pi (Model 3B+ or newer recommended)
- SD Card (32GB+ recommended)
- Internet connection

### Software
- Raspberry Pi OS (Debian-based) or Ubuntu Server
- Docker installed
- Docker Compose installed

### Accounts & Access
- GitHub account with access to your Obsidian notes repository
- Google Cloud account (for Gemini API key)

## Installation Steps

### 1. Install Docker and Docker Compose

On Raspberry Pi OS:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose -y

# Verify installation
docker --version
docker-compose --version
```

### 2. Clone the Project Repository

```bash
# Navigate to desired directory
cd ~/

# Clone the repository
git clone https://github.com/christopherjohnkelly/obsidian-note-manager.git
cd obsidian-note-manager/runner-setup
```

### 3. Get a Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key (starts with `AIza...`)
5. **Important**: Save this key securely - you won't see it again

### 4. Get a GitHub Personal Access Token (PAT)

**Important**: You need a **Classic PAT** (not fine-grained) with `repo` scope.

1. Go to: **GitHub** → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **Generate new token (classic)**
3. Give it a name: "Raspberry Pi Runner"
4. Select expiration: "No expiration" (or custom)
5. **Select scopes**: Check `repo` scope (full control)
6. Click **Generate token**
7. Copy the token (starts with `ghp_`) - **Save it now, you won't see it again!**

### 5. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file
nano .env
```

Fill in your values:

```bash
# GitHub Configuration
GITHUB_PAT=ghp_your_personal_access_token_here
REPO_URL=https://github.com/christopherjohnkelly/obsidian-notes
RUNNER_NAME=pi-librarian

# Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (legacy - only if not using PAT)
# GITHUB_RUNNER_TOKEN=your_registration_token_here
```

**Security Note**: Never commit the `.env` file to Git. It's already in `.gitignore`.

### 6. Configure GitHub Secrets

In your **Obsidian notes repository** (not this code repository):

1. Go to: **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add secret:
   - **Name**: `GEMINI_API_KEY`
   - **Value**: Your Gemini API key (from step 3)
4. Click **Add secret**

### 7. Deploy the Workflow File

The workflow file must be in your **Obsidian notes repository**, not this code repository.

**Option A: Copy the workflow file**
```bash
# From your obsidian-notes repository
mkdir -p .github/workflows
cp /path/to/obsidian-note-manager/.github/workflows/ingest.yml .github/workflows/
git add .github/workflows/ingest.yml
git commit -m "Add Obsidian ingestion workflow"
git push
```

**Option B: Create manually**
Create `.github/workflows/ingest.yml` in your obsidian-notes repository with:
```yaml
name: Obsidian Ingestion Pipeline

on:
  push:
    paths:
      - '00. Inbox/0. Capture/**/*.md'
    branches:
      - master

permissions:
  contents: write

jobs:
  librarian:
    runs-on: self-hosted
    steps:
      - name: Checkout Vault
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Librarian
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          OBSIDIAN_VAULT_ROOT: ${{ github.workspace }}
        run: |
          echo "📂 Starting Ingestion..."
          python3 /home/runner/src/main.py
```

### 8. Build and Start the Docker Container

```bash
# Build the Docker image
docker compose build

# Start the container in detached mode
docker compose up -d

# Check logs to verify registration
docker compose logs -f
```

You should see:
```
🔑 Fetching registration token using PAT...
✅ Runner Configured. Listening for jobs...
√ Connected to GitHub
Current runner version: '2.311.0'
2026-XX-XX XX:XX:XXZ: Listening for Jobs
```

### 9. Verify Runner Registration

1. Go to your repository: `https://github.com/christopherjohnkelly/obsidian-notes`
2. Navigate to: **Settings** → **Actions** → **Runners**
3. You should see `pi-librarian` (or your `RUNNER_NAME`) listed as "Idle" (green)

## Post-Setup Verification

### Test the Pipeline

1. Create a test note in your Obsidian vault:
   ```bash
   # In your obsidian-notes repository
   echo "Test note content" > "00. Inbox/0. Capture/test-note.md"
   git add "00. Inbox/0. Capture/test-note.md"
   git commit -m "Test: Add note to Capture folder"
   git push
   ```

2. Check GitHub Actions:
   - Go to: **Actions** tab in your repository
   - You should see "Obsidian Ingestion Pipeline" workflow running
   - Wait for completion (usually 30-60 seconds)

3. Verify processed note:
   - Check `00. Inbox/1. Review Queue/` folder
   - The test note should be there with frontmatter added

### Check Container Status

```bash
# Check if container is running
docker compose ps

# View logs
docker compose logs librarian-runner

# Check runner status inside container
docker compose exec librarian-runner ps aux | grep Runner
```

## Troubleshooting

If something doesn't work:

1. **Check logs**: `docker compose logs librarian-runner`
2. **Verify environment variables**: Ensure `.env` file is correct
3. **Check runner status**: Go to GitHub → Settings → Actions → Runners
4. **Test network connectivity**: `docker compose exec librarian-runner curl -s https://api.github.com`

See [Troubleshooting Guide](./troubleshooting.md) for common issues and solutions.

## Next Steps

- Read [Architecture Overview](./architecture.md) to understand how the system works
- Check [Component Documentation](./components.md) for detailed component information
- Review [Workflow Documentation](./workflows.md) for GitHub Actions details

## Maintenance

### Updating the Runner

The runner auto-updates when GitHub releases new versions. You can manually trigger:
```bash
docker compose restart librarian-runner
```

### Updating Application Code

To update the Python application code:

```bash
# Pull latest changes
cd ~/obsidian-note-manager
git pull

# Rebuild and restart
cd runner-setup
docker compose down
docker compose build
docker compose up -d
```

### Monitoring

View real-time logs:
```bash
docker compose logs -f librarian-runner
```

## Uninstallation

To remove the runner:

```bash
# Stop and remove container
cd ~/obsidian-note-manager/runner-setup
docker compose down

# Remove runner from GitHub
# Go to: Settings → Actions → Runners → Remove runner
```

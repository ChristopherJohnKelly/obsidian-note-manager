# GitHub Actions Self-Hosted Runner (Docker)

This directory contains the Docker setup for a self-hosted GitHub Actions runner that will run on a Raspberry Pi. The runner is configured to automatically register with GitHub and listen for jobs from the obsidian-notes repository.

## Architecture

- **Base Image**: Ubuntu 22.04
- **Runner Architecture**: ARM64 (for Raspberry Pi) or x64 (for local development)
- **Python Version**: 3.11+
- **Pre-installed Dependencies**: `google-generativeai`, `python-frontmatter`, `gitpython`

## Prerequisites

- Docker and Docker Compose installed on the Raspberry Pi
- GitHub repository access (obsidian-notes)
- A registration token from GitHub (see Setup Steps)

## Setup Instructions

### Step 1: Get a Runner Registration Token

1. Go to your GitHub repository: `https://github.com/christopherjohnkelly/obsidian-notes`
2. Navigate to: **Settings** → **Actions** → **Runners** → **New self-hosted runner**
3. Look at the `config.sh` command shown in the instructions
4. Copy the token string after `--token` (this is your `GITHUB_RUNNER_TOKEN`)

**Note**: Registration tokens expire quickly (typically within 1 hour). You'll need to get a fresh token if the container is restarted after the token expires.

### Step 2: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your values:
   ```bash
   GITHUB_RUNNER_TOKEN=your_actual_token_here
   REPO_URL=https://github.com/christopherjohnkelly/obsidian-notes
   RUNNER_NAME=pi-librarian
   ```

### Step 3: Build and Run

1. Build the Docker image:
   ```bash
   docker compose build
   ```

2. Start the container:
   ```bash
   docker compose up -d
   ```

3. Check the logs to verify registration:
   ```bash
   docker compose logs -f
   ```

   You should see: `✅ Runner Configured. Listening for jobs...`

### Step 4: Verify in GitHub

1. Go to: **Settings** → **Actions** → **Runners**
2. You should see `pi-librarian` (or your custom `RUNNER_NAME`) listed as "Idle"

## Architecture Notes

### ARM64 vs x64

The Dockerfile supports both architectures:

- **ARM64** (default): For Raspberry Pi
- **x64**: For local development/testing on Intel/AMD machines

To build for x64 on a non-ARM machine, modify `docker-compose.yml`:

```yaml
build:
  context: .
  args:
    RUNNER_ARCH: x64  # Change from arm64
```

## Usage

Once the runner is registered and running, it will automatically pick up jobs from GitHub Actions workflows that target the labels:
- `self-hosted`
- `docker`
- `pi`

Example workflow configuration:
```yaml
jobs:
  process-notes:
    runs-on: [self-hosted, docker]
    steps:
      - name: Process Notes
        run: echo "Processing notes..."
```

## Troubleshooting

### Runner doesn't appear in GitHub

- Check that the registration token is valid (they expire quickly)
- Verify `REPO_URL` is correct
- Check container logs: `docker compose logs`

### Container exits immediately

- Verify all required environment variables are set in `.env`
- Check that the token hasn't expired
- Review logs for error messages

### Runner shows as "Offline"

- Check if container is running: `docker compose ps`
- Restart container: `docker compose restart`
- Check logs for connection issues

## Security Notes

- The `.env` file is excluded from git (see `.gitignore`)
- The runner runs as a non-root user (`runner`)
- Sensitive tokens are never hardcoded in the Dockerfile

## Maintenance

To update the runner version, modify `RUNNER_VERSION` in the Dockerfile and rebuild:
```bash
docker compose build --no-cache
docker compose up -d
```

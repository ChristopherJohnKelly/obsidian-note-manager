# GitHub Actions Self-Hosted Runner (Docker)

This directory contains the Docker setup for a self-hosted GitHub Actions runner that will run on a Raspberry Pi. The runner is configured to automatically register with GitHub and listen for jobs from the obsidian-notes repository.

> 📚 **For comprehensive documentation**, see the [docs/](../docs/) folder in the project root:
> - [Setup Guide](../docs/setup.md) - Detailed installation instructions
> - [Architecture Overview](../docs/architecture.md) - System architecture
> - [Component Documentation](../docs/components.md) - Component details
> - [Troubleshooting Guide](../docs/troubleshooting.md) - Common issues and solutions

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

### Step 1: Configure GitHub Authentication

You have two options for authentication:

#### Option A: Personal Access Token (RECOMMENDED)

**Note**: For runner registration token API, you need a **Classic PAT** (not fine-grained). Fine-grained PATs currently don't support the registration token endpoint.

1. Go to: **GitHub** → **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)**
2. Click **Generate new token (classic)**
3. Give it a name like "Raspberry Pi Runner"
4. Select expiration (e.g., "No expiration" or custom)
5. **Select scopes**: Check `repo` scope (full control) - this is required for repo-level runner registration
6. Click **Generate token** and copy it (starts with `ghp_`, you won't see it again!)
7. Set `GITHUB_PAT` in your `.env` file

**Benefits**: Token doesn't expire quickly, runner automatically fetches registration tokens when needed.

**Important**: Fine-grained PATs with "Actions: Read and write" permission do NOT work with the registration token API endpoint. You must use a Classic PAT with `repo` scope for this feature.

#### Option B: Direct Registration Token (LEGACY)

1. Go to your GitHub repository: `https://github.com/christopherjohnkelly/obsidian-notes`
2. Navigate to: **Settings** → **Actions** → **Runners** → **New self-hosted runner**
3. Look at the `config.sh` command shown in the instructions
4. Copy the token string after `--token` (this is your `GITHUB_RUNNER_TOKEN`)

**Note**: Registration tokens expire quickly (typically within 1 hour). You'll need to get a fresh token if the container is restarted after the token expires. **Use Option A instead for automatic token management.**

### Step 2: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your values:
   
   **Using PAT (recommended)**:
   ```bash
   GITHUB_PAT=ghp_your_personal_access_token_here
   REPO_URL=https://github.com/christopherjohnkelly/obsidian-notes
   RUNNER_NAME=pi-librarian
   GEMINI_API_KEY=your_gemini_api_key_here
   ```
   
   **Using registration token (legacy)**:
   ```bash
   GITHUB_RUNNER_TOKEN=your_registration_token_here
   REPO_URL=https://github.com/christopherjohnkelly/obsidian-notes
   RUNNER_NAME=pi-librarian
   GEMINI_API_KEY=your_gemini_api_key_here
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

   **Using PAT**: You should see: `🔑 Fetching registration token using PAT...` followed by `✅ Runner Configured. Listening for jobs...`
   
   **Using registration token**: You should see: `✅ Runner Configured. Listening for jobs...`
   
   **Subsequent starts**: If `.runner` config exists, you'll see: `✅ Runner already configured. Starting runner...`

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

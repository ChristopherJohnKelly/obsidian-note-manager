# Deployment Guide

## Prerequisites

- Docker and Docker Compose installed on the target host
- Access to GitHub Container Registry (`ghcr.io`)
- `.env` file populated from `.env.example`

## 1. Pull Images

```bash
docker compose -f docker-compose.prod.yml pull
```

## 2. Fill in Environment Variables

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:
- `GITHUB_PAT` — personal access token with `repo` scope
- `GEMINI_API_KEY` — Google Gemini API key

## 3. Start the Stack

```bash
docker compose -f docker-compose.prod.yml up -d
```

## 4. Verify Services

**Temporal UI** — available at http://localhost:8080

**Chainlit (Copilot UI)** — available at http://localhost:8000

**Structural validation** (run after any compose file change):

```bash
docker compose config
# or with explicit file:
docker compose -f docker-compose.prod.yml config
```

**Service status**:

```bash
docker compose -f docker-compose.prod.yml ps
```

**Per-service health checks**:

```bash
# vault-worker
docker compose -f docker-compose.prod.yml logs vault-worker --tail 20

# copilot-worker (if present)
docker compose -f docker-compose.prod.yml logs copilot-ui --tail 20

# github-runner
docker compose -f docker-compose.prod.yml logs github-runner --tail 20
```

Check for `vault-default` namespace in Temporal UI to confirm vault-worker registered successfully.

## Health Check Limitations

End-to-end workflow validation (trigger.py, data-converter wiring) is a post-merge manual step — those components are not covered by this deployment guide.

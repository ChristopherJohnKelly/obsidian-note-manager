---
type: bubble
status: pending
step_id: S16
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior DevOps Engineer writing the production deployment configuration.
**Objective:** Write `docker-compose.prod.yml` — the complete stack definition for the Ubuntu VM. All three custom images are pulled from GHCR. Temporal infra images are pulled from upstream. PostgreSQL persistence is configured. All environment variables are documented.
**Constraints:**
- Custom images use GHCR tags, never `build: .` — the VM does not build images locally
- Postgres data must persist across container restarts via a named volume
- No secrets hardcoded — all sensitive values come from a `.env` file
- The Temporal server must use PostgreSQL (not SQLite) and not Elasticsearch
- Service startup order must be enforced: `postgres` → `temporal-server` → `vault-worker` (after VaultInitWorkflow) → `copilot-ui` and `github-runner`

---

## 1. Context

**Feature:** TRD Section 3A (Container Roster), Section 7 (Vault Synchronisation), Section 8 (Deployment Port Reference)
**Depends On:** S09 (VaultManagerWorkflow), S13 (github-runner Dockerfile), S14 (copilot-ui Dockerfile), S15 (CI/CD — images published to GHCR)
**Current State:** All images are published to GHCR. No production compose file exists.
**Target State:** `docker-compose.prod.yml` and `.env.example` committed. A human operator can deploy the full stack on the Ubuntu VM with `docker compose -f docker-compose.prod.yml up -d` after filling in `.env`.

---

## 2. Input

- TRD Section 3A — container roster and image names
- TRD Section 8 — port reference table
- TRD Section 7 — `VAULT_PATH`, `REPO_URL`, `GITHUB_PAT` environment variables
- `.github/workflows/build-push.yml` — GHCR image names from S15

---

## 3. Required Output

- [ ] `docker-compose.prod.yml` — full stack definition
- [ ] `.env.example` — all required environment variables with descriptions
- [ ] `docs/deployment.md` — step-by-step operator guide: pull images, fill `.env`, start stack, verify health

---

## 4. Acceptance Criteria

- [ ] `docker compose -f docker-compose.prod.yml config` validates without error (no missing required fields)
- [ ] `postgres` service uses a named volume for data persistence; data survives `docker compose restart`
- [ ] `temporal-server` is configured to use PostgreSQL via `TEMPORAL_DB_PLUGIN=postgres12` (or equivalent env for the chosen Temporal image)
- [ ] `vault-worker` has `VAULT_PATH`, `REPO_URL`, `GITHUB_PAT`, `GEMINI_API_KEY`, `TEMPORAL_HOST` as required env vars
- [ ] `copilot-ui` has `TEMPORAL_HOST` only — no vault or LLM secrets
- [ ] `github-runner` has `GITHUB_PAT`, `REPO_URL`, `TEMPORAL_HOST`, `RUNNER_NAME` — no vault or LLM secrets
- [ ] `temporal-ui` is accessible on host port 8080; `copilot-ui` on host port 8000; all other ports are internal only
- [ ] `.env.example` lists every variable used across all services with a one-line description

---

## 5. Scope Boundary

**May modify:** `docker-compose.prod.yml`, `.env.example`, `docs/deployment.md`, `.gitignore` (to exclude `.env`)
**Must not modify:** Any application code, Dockerfiles, GitHub Actions workflows, `packages/`, `tests/`

---

## 6. TDD Constraints

This bubble has no unit tests. Validation is via `docker compose config` (syntax check) and a manual deployment test on the Ubuntu VM. Document the manual validation steps in `docs/deployment.md`.

---

## 7. Step-by-Step Plan

1. Write `docker-compose.prod.yml` with all six services. Run `docker compose -f docker-compose.prod.yml config` — fix any syntax errors.
2. Write `.env.example` listing all variables.
3. Test locally with real `.env` (redacted for commit): `docker compose pull` then `docker compose up -d`. Confirm all containers start and pass health checks.
4. Verify Temporal UI is reachable at `http://localhost:8080`.
5. Verify Chainlit is reachable at `http://localhost:8000`.
6. Write `docs/deployment.md`.
7. Ensure `.env` is in `.gitignore`. Commit `.env.example` only.

---

## 8. Reference Material

### docker-compose.prod.yml skeleton

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: temporal
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: temporal
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U temporal"]
      interval: 10s
      retries: 5

  temporal-server:
    image: temporalio/auto-setup:latest
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DB: postgres12
      DB_PORT: 5432
      POSTGRES_USER: temporal
      POSTGRES_PWD: ${POSTGRES_PASSWORD}
      POSTGRES_SEEDS: postgres
      # Advanced Visibility: use PostgreSQL instead of Elasticsearch.
      # Required for list_workflows with status/type filters (used by copilot-ui
      # to discover pending FilerIngestionWorkflow proposals).
      VISIBILITY_DBNAME: temporal_visibility
      VISIBILITY_DB_PLUGIN: postgres12
    # Port 7233 (gRPC) is internal only — SDK clients connect via Docker network name.
    # Do not expose to host in production (TRD Section 8).
    expose:
      - "7233"

  temporal-ui:
    image: temporalio/ui:latest
    depends_on: [temporal-server]
    environment:
      TEMPORAL_ADDRESS: temporal-server:7233
    ports:
      - "8080:8080"

  vault-worker:
    image: ghcr.io/christopherjohnkelly/obsidian-vault-worker:latest
    depends_on: [temporal-server]
    environment:
      TEMPORAL_HOST: temporal-server:7233
      VAULT_PATH: ${VAULT_PATH}
      REPO_URL: ${REPO_URL}
      GITHUB_PAT: ${GITHUB_PAT}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    volumes:
      - vault-data:${VAULT_PATH}
    restart: unless-stopped

  copilot-ui:
    image: ghcr.io/christopherjohnkelly/obsidian-copilot-ui:latest
    depends_on: [temporal-server]
    environment:
      TEMPORAL_HOST: temporal-server:7233
    ports:
      - "8000:8000"
    restart: unless-stopped

  github-runner:
    image: ghcr.io/christopherjohnkelly/obsidian-github-runner:latest
    depends_on: [temporal-server]
    environment:
      TEMPORAL_HOST: temporal-server:7233
      REPO_URL: ${REPO_URL}
      GITHUB_PAT: ${GITHUB_PAT}
      RUNNER_NAME: ${RUNNER_NAME:-obsidian-runner}
    restart: unless-stopped

volumes:
  postgres-data:
  vault-data:
```

### .env.example

```bash
# Postgres
POSTGRES_PASSWORD=changeme

# Git / GitHub
REPO_URL=https://github.com/ChristopherJohnKelly/obsidian-notes
GITHUB_PAT=ghp_...              # PAT with repo scope

# Vault
VAULT_PATH=/home/worker/vault   # Path inside the vault-worker container

# LLM
GEMINI_API_KEY=AIza...

# Runner
RUNNER_NAME=obsidian-runner     # Display name in GitHub Actions
```

### Deployment update procedure (for docs/deployment.md)

```bash
# Pull latest images and restart
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---
type: bubble
status: pending
step_id: S21
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior DevOps Engineer preparing a Docker Compose stack for its first production deployment.
**Objective:** Bring `docker-compose.prod.yml`, `.env.example` and `docs/deployment.md` into line with S19 and S20, pin every upstream image, and give the vault-worker's commits a named author, so the stack can be deployed first against a throwaway copy of the vault and then against the real one.
**Constraints:**
- Read before writing: `docker-compose.prod.yml`, `.env.example`, `docs/deployment.md`, `tests/ci/test_docker_compose_prod.py`, `tests/ci/test_deployment_docs.py`, and the environment variables that `apps/vault_worker/__main__.py`, `apps/vault_worker/worker.py`, `apps/copilot_ui/app.py`, `apps/github_runner/trigger.py` and `apps/github_runner/entrypoint.sh` actually read after S19 and S20. Every variable a service needs must come from that reading, not from memory (S16 was rejected twice for this).
- Before pinning the Temporal images, check upstream's current guidance on `temporalio/auto-setup` versus `temporalio/server` with a schema-setup step, and record what you found and the tags chosen in `LEARNINGS.md`.
- Compose changes only. Do not change application code.

---

## 1. Context

**Feature:** TRD Section 6 Phase 5 (CI/CD and Deployment), Section 7 (vault synchronisation), Section 8 (ports).
**Depends On:** S19, S20.
**Current State:** Found in the pre-deployment review of 1 Nov 2026.
- `github-runner` has no `VAULT_PATH`, so workflows it starts receive an empty vault path (S20 makes the trigger refuse to start instead).
- `.env.example` sets `PR_BRANCH=main`; the vault's default branch is `master`, and after S19 the Night Watchman derives its own branch per run.
- `temporalio/auto-setup:latest` and `temporalio/ui:latest` are unpinned, so a routine `docker compose pull` can change Temporal's major version under a populated Postgres.
- Commits made by vault-worker have no configured author, so they record the container's default user and hostname.
- `docs/deployment.md` does not cover logging in to GHCR for private images, the runner label from S20, a trial against a throwaway repository, or rollback.
**Target State:** A compose file whose every service has exactly the variables its code reads, pinned upstream images, a named commit author, and a deployment guide that covers trial, cutover and rollback.

---

## 2. Input

- `docker-compose.prod.yml`, `.env.example`, `docs/deployment.md`
- The env-reading code listed under Constraints
- `tests/ci/test_docker_compose_prod.py`, `tests/ci/test_deployment_docs.py`
- `deploy/vault-workflows/README.md` (from S20)

---

## 3. Required Output

- [ ] `docker-compose.prod.yml` updated
- [ ] `.env.example` updated
- [ ] `docs/deployment.md` updated
- [ ] Tests updated or added in `tests/ci/`
- [ ] `LEARNINGS.md` entry on the Temporal image choice
- [ ] `scripts/run_s21_tests.sh`

---

## 4. Acceptance Criteria

- [ ] **Env completeness, both directions.** A test collects every `os.environ[...]` / `os.environ.get(...)` / `$VAR` read by each service's code and entrypoint, and asserts the matching compose service provides each required one; and asserts no custom service (vault-worker, copilot-ui, github-runner) is given a variable its code never reads. The test must fail today on `github-runner` missing `VAULT_PATH`.
- [ ] **Same vault path.** `vault-worker` and `github-runner` take `VAULT_PATH` from the same `.env` variable.
- [ ] **Branches.** `.env.example` sets `BASE_BRANCH=master` and contains no variable S19 made redundant.
- [ ] **Runner label.** `github-runner` passes `RUNNER_LABELS` (default `obsidian-temporal`), and `RUNNER_NAME` defaults to a name that does not clash with the V1 runner's.
- [ ] **Pinned images.** No service uses a `:latest` tag or an untagged upstream image. A test enforces it. The custom GHCR images are exempt only if `docs/deployment.md` explains how to deploy a specific `${{ github.sha }}` tag instead.
- [ ] **Commit author.** `vault-worker` sets `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` (defaults "Obsidian Librarian" and `librarian@automation.local`, matching V1). A test proves GitPython's `index.commit` picks these up, using a temporary repository.
- [ ] **Deployment guide** covers, in order: GHCR login when the packages are private; a trial run with `REPO_URL` pointing at a throwaway copy of the vault; switching `REPO_URL` to the real vault (stop the stack, remove the `vault-data` volume, start again, since VaultManager refuses a clone of a different repo); copying `deploy/vault-workflows/` into the vault; stopping the V1 runners; and rollback (`docker compose -f docker-compose.prod.yml down`, restore the V1 workflow files, restart the V1 runner). `tests/ci/test_deployment_docs.py` checks each section exists.
- [ ] `docker compose -f docker-compose.prod.yml config` succeeds with `.env.example` copied to `.env` (tested, as S16 did).
- [ ] The full suite passes with coverage ≥ 90%.

---

## 5. Scope Boundary

**May modify:** `docker-compose.prod.yml`, `.env.example`, `docs/deployment.md`, `tests/ci/`, `LEARNINGS.md`, `scripts/run_s21_tests.sh`
**Must not modify:** anything under `apps/` or `packages/`, `.github/workflows/`, `deploy/vault-workflows/`, Dockerfiles, `docker-compose.yml` (local development)

---

## 6. TDD Constraints

Write the two-way env completeness test first and watch it fail on `github-runner`'s missing `VAULT_PATH`. Write the pinned-images test before changing any tag and watch it fail on `temporalio/auto-setup:latest`.

---

## 7. Step-by-Step Plan

1. Read the env-reading code for each service and list the variables.
2. Failing env completeness test. Fix the compose file and `.env.example`. Green.
3. Research the Temporal image guidance; record it. Failing pinned-images test. Pin. Green.
4. Failing commit-author test. Add the variables. Green.
5. Deployment guide and its test.
6. Full suite and coverage.

---

## 8. Reference Material

TRD Section 7.3: VaultManager raises a fatal error when `VAULT_PATH` holds anything other than a clone of `REPO_URL`. That is why switching from the trial repository to the real vault needs the volume removed.

## Assumptions

- The production host is the Ubuntu Docker host, with ports 8000 and 8080 free (to be confirmed by the operator before deploy).

## Open Questions

- [ ] Should copilot-ui and temporal-ui be bound to the LAN interface only, rather than all interfaces? Raised for the operator.

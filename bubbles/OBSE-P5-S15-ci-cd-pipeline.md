---
type: bubble
status: pending
step_id: S15
parent_trd: "[[TRD - Temporal SOA Migration]]"
tags: [ type/bubble ]
---

## LLM Instructions

**Role:** You are a Senior DevOps Engineer setting up a GitHub Actions CI/CD pipeline.
**Objective:** Write two GitHub Actions workflows: (1) a CI pipeline that runs the full test suite on every PR, enforcing the 90% coverage threshold; (2) a build-and-push pipeline that builds and publishes all three custom Docker images to GHCR on merge to `main`.
**Constraints:**
- Use GitHub-hosted runners (not self-hosted) for CI and image builds — the self-hosted runner is for Temporal triggering only
- Images are tagged with both `:latest` and `:{git-sha}` for traceability
- GHCR repository: `ghcr.io/christopherjohnkelly/{image-name}`
- CI must fail if coverage drops below 90%
- The build pipeline only rebuilds an image if files in its `apps/{name}/` directory changed (path filtering)

---

## 1. Context

**Feature:** TRD Section 6 Phase 5 (CI/CD & Deployment)
**Depends On:** S13 (GitHub Runner Refactor), S14 (Copilot UI Refactor) — all three custom images must have valid Dockerfiles
**Current State:** All three Dockerfiles exist. Tests pass locally. No CI pipeline yet.
**Target State:** Two GitHub Actions workflows committed; a test PR triggers CI and reports coverage; a merge to `main` triggers image builds and pushes to GHCR.

---

## 2. Input

- `apps/vault_worker/Dockerfile`
- `apps/copilot_ui/Dockerfile`
- `apps/github_runner/Dockerfile`
- `pyproject.toml` — test and coverage config

---

## 3. Required Output

- [ ] `.github/workflows/ci.yml` — test + coverage on every PR
- [ ] `.github/workflows/build-push.yml` — build + push to GHCR on merge to `main`

---

## 4. Acceptance Criteria

- [ ] `ci.yml` runs `pytest --cov --cov-fail-under=90` and fails the PR if coverage drops below threshold
- [ ] `ci.yml` uses Python 3.12 and installs all packages in editable mode using dev deps from `pyproject.toml` (not by installing pytest/pytest-asyncio/pytest-cov separately, which risks version drift from the dev environment)
- [ ] `pyproject.toml` coverage `omit` list includes `apps/copilot_ui/app.py` — Chainlit lifecycle hooks (`@cl.on_chat_start`, `@cl.on_message`, `@cl.action_callback`) cannot be unit-tested and would otherwise prevent the 90% threshold from being reached
- [ ] `build-push.yml` builds `vault-worker`, `copilot-ui`, and `github-runner` images
- [ ] Each image is tagged `latest` and `{github.sha}`
- [ ] Image builds are conditional: `vault-worker` only rebuilds if `apps/vault_worker/**` or `packages/shared/**` changed; same pattern for the other two
- [ ] GHCR login uses `GITHUB_TOKEN` (no external secrets needed for package publish)
- [ ] A README note documents: how to pull and run each image; what environment variables each container requires
- [ ] Structural tests under `tests/ci/` pin every criterion above by parsing the workflow YAML (`yaml.safe_load`) — not by string-matching raw file text. They MUST assert, at minimum: the ci job's test step invokes pytest with `--cov` and `--cov-fail-under=90`; Python version is `3.12`; the install step uses editable installs and does not install pytest directly; `[tool.coverage.run]` `omit` in `pyproject.toml` contains `apps/copilot_ui/app.py`; build-push defines builds for all three images, each tagged `latest` and `${{ github.sha }}`; each build is gated on a paths filter covering its `apps/{name}/**` (plus `packages/shared/**` where specified); GHCR login uses `GITHUB_TOKEN`; `workflow_dispatch` is among build-push triggers

---

## 5. Scope Boundary

**May modify:** `.github/workflows/ci.yml`, `.github/workflows/build-push.yml`, `README.md`, `pyproject.toml` (coverage `omit` list only), `tests/ci/`, `scripts/run_s15_tests.sh`
**Must not modify:** Any application code, Dockerfiles, `packages/`, `tests/unit/`, `tests/e2e/`, `tests/fixtures/`

---

## 6. TDD Constraints

The workflows cannot be executed locally, but their structure can and must be tested. Write structural tests in `tests/ci/` that load the YAML with `yaml.safe_load` and assert the acceptance criteria above — no live Actions run is needed to go green. String-matching on raw file text is not acceptable: a prior attempt was rejected for tautological string-match tests that asserted nothing about the parsed structure. The real-Actions validation (open a test PR, observe the run, verify images appear in GHCR) is a post-merge manual step performed by the operator — document it in `README.md`; do not attempt it in this step.

---

## 7. Step-by-Step Plan

1. Write structural tests in `tests/ci/` asserting the ci.yml criteria; watch them fail. Write `ci.yml`: checkout → setup Python 3.12 → install all packages editable → `pytest --cov --cov-fail-under=90`. Tests go green.
2. Write `build-push.yml`: trigger on `push` to `main`; use `dorny/paths-filter` action for path-based conditional builds; login to GHCR with `GITHUB_TOKEN`; build + push each image with two tags.
3. Add the `on: workflow_dispatch` trigger to `build-push.yml` so it can be triggered manually for initial validation.
4. Update `README.md` with image pull instructions and required environment variables per container.
5. Add a README section documenting the post-merge manual validation for the operator: open a test PR to watch CI run, trigger build-push via `workflow_dispatch`, verify all three images appear in GHCR.

---

## 8. Reference Material

### ci.yml

```yaml
name: CI
on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install packages
        run: |
          pip install -e "packages/shared[dev]"   # installs pytest, pytest-asyncio, pytest-cov from pyproject.toml dev deps
          pip install -e apps/vault_worker
          pip install -e apps/copilot_ui
          # Do not pip install pytest separately — use the version pinned in pyproject.toml dev deps
      - name: Test with coverage
        # copilot-ui/app.py (Chainlit lifecycle hooks) is untestable and must be in the omit list
        # in pyproject.toml [tool.coverage.run] omit — verify before raising threshold to 90
        run: pytest --cov=apps --cov=packages --cov-fail-under=90
```

### build-push.yml (abbreviated)

```yaml
name: Build & Push Images
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-vault-worker:
    runs-on: ubuntu-latest
    permissions:
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            changed:
              - 'apps/vault_worker/**'
              - 'packages/shared/**'
      - if: steps.filter.outputs.changed == 'true'
        name: Build and push vault-worker
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker build -t ghcr.io/christopherjohnkelly/obsidian-vault-worker:latest \
                       -t ghcr.io/christopherjohnkelly/obsidian-vault-worker:${{ github.sha }} \
                       apps/vault_worker/
          docker push ghcr.io/christopherjohnkelly/obsidian-vault-worker --all-tags
```

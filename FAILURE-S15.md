# FAILURE-S15 — 2026-08-10T01:50:20Z

## Rejection Reason
README documents `ghcr.io/christopherjohnkelly/{vault-worker,copilot-ui,github-runner}` but build-push.yml publishes `obsidian-`prefixed images (README.md:211,230,247 vs build-push.yml:31,56,80); tests/ci/test_readme_docker_docs.py hardcodes the wrong names, pinning the defect

## Failed Check
serena

## Attempt
1 of max 5 (escalates to status=support at 3)

## PR
#39 — step branch `pr/S15` @ 9ff075a

## Files changed on step branch vs feature
- .github/workflows/build-push.yml
- .github/workflows/ci.yml
- PLAN.md
- README.md
- scripts/run_s15_tests.sh
- tests/ci/__init__.py
- tests/ci/test_build_push_workflow.py
- tests/ci/test_ci_workflow.py
- tests/ci/test_pyproject_coverage_omit.py
- tests/ci/test_readme_docker_docs.py

## Next status
queued — step branch rebriefed to prepare commit + new CONTEXT; will be re-attempted automatically

## What to fix
Address the rejection reason above before re-attempting this step. If prior
attempt sections exist above, re-read them — the same check failing twice
means the prior guidance was not applied or was insufficient.

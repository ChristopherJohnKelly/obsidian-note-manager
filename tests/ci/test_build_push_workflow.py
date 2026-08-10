import os
import re
import yaml
import pytest

WORKFLOW_PATH = ".github/workflows/build-push.yml"

JOBS = [
    {
        "job_id": "build-vault-worker",
        "image_name": "obsidian-vault-worker",
        "app_dir": "vault_worker",
        "filter_paths": ["apps/vault_worker/**", "packages/shared/**"],
        "build_context": ".",
        "dockerfile_flag": "apps/vault_worker/Dockerfile",
    },
    {
        "job_id": "build-copilot-ui",
        "image_name": "obsidian-copilot-ui",
        "app_dir": "copilot_ui",
        "filter_paths": ["apps/copilot_ui/**", "packages/shared/**"],
        "build_context": ".",
        "dockerfile_flag": "apps/copilot_ui/Dockerfile",
    },
    {
        "job_id": "build-github-runner",
        "image_name": "obsidian-github-runner",
        "app_dir": "github_runner",
        "filter_paths": ["apps/github_runner/**"],
        "build_context": "apps/github_runner/",
        "dockerfile_flag": None,
    },
]

GHCR_OWNER = "christopherjohnkelly"


@pytest.fixture(scope="module")
def workflow():
    with open(WORKFLOW_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def jobs(workflow):
    return workflow.get("jobs", {})


def test_workflow_file_exists():
    assert os.path.exists(WORKFLOW_PATH), f"{WORKFLOW_PATH} not found"


def test_top_level_on_push_main(workflow):
    on = workflow.get("on") or workflow.get(True)
    assert on is not None, "top-level 'on' key missing"
    push = on.get("push", {}) or {}
    branches = push.get("branches", [])
    assert "main" in branches, f"push.branches must include 'main', got {branches}"


def test_top_level_on_workflow_dispatch(workflow):
    on = workflow.get("on") or workflow.get(True)
    assert on is not None, "top-level 'on' key missing"
    assert "workflow_dispatch" in on, "workflow_dispatch trigger missing from 'on'"


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_job_runs_on(jobs, spec):
    job = jobs.get(spec["job_id"])
    assert job is not None, f"job '{spec['job_id']}' not found"
    assert job.get("runs-on") == "ubuntu-latest"


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_job_permissions_packages_write(jobs, spec):
    job = jobs[spec["job_id"]]
    perms = job.get("permissions", {}) or {}
    assert perms.get("packages") == "write", (
        f"job '{spec['job_id']}' must have permissions.packages: write"
    )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_job_has_checkout_step(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    uses_values = [s.get("uses", "") for s in steps]
    assert any("actions/checkout@v4" in u for u in uses_values), (
        f"job '{spec['job_id']}' missing actions/checkout@v4 step"
    )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_job_has_paths_filter_step(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    filter_steps = [
        s for s in steps
        if "dorny/paths-filter" in s.get("uses", "") and s.get("id") == "filter"
    ]
    assert len(filter_steps) == 1, (
        f"job '{spec['job_id']}' must have exactly one dorny/paths-filter@v3 step with id: filter"
    )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_paths_filter_changed_key(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    filter_step = next(
        s for s in steps
        if "dorny/paths-filter" in s.get("uses", "") and s.get("id") == "filter"
    )
    with_block = filter_step.get("with", {}) or {}
    raw_filters = with_block.get("filters", "")
    # filters may be a YAML string (multi-line scalar) or already parsed
    if isinstance(raw_filters, str):
        parsed_filters = yaml.safe_load(raw_filters)
    else:
        parsed_filters = raw_filters
    assert "changed" in parsed_filters, (
        f"job '{spec['job_id']}' paths-filter must have a 'changed' key"
    )
    changed_list = parsed_filters["changed"]
    assert isinstance(changed_list, list), (
        f"job '{spec['job_id']}' paths-filter 'changed' must be a list"
    )
    for expected_path in spec["filter_paths"]:
        assert expected_path in changed_list, (
            f"job '{spec['job_id']}' 'changed' filter missing '{expected_path}', got {changed_list}"
        )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_build_step_if_expression(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    # The build/push step is the one after the filter step that has the if expression
    gated_build_steps = [
        s for s in steps
        if s.get("if") == "steps.filter.outputs.changed == 'true'"
        and "docker build" in (s.get("run") or "")
        and "docker push" in (s.get("run") or "")
    ]
    assert len(gated_build_steps) >= 1, (
        f"job '{spec['job_id']}': the docker build/push step itself must carry "
        "if: steps.filter.outputs.changed == 'true' — a gate on any other step "
        "does not prevent unconditional builds"
    )


def _find_build_push_step(steps):
    """Return the step whose run block contains docker build/push logic."""
    for s in steps:
        run = s.get("run", "") or ""
        if "docker build" in run or "docker push" in run:
            return s
    return None


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_build_step_tags_latest_and_sha(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    build_step = _find_build_push_step(steps)
    assert build_step is not None, f"job '{spec['job_id']}' has no docker build/push step"
    run = build_step.get("run", "")
    image_base = f"ghcr.io/{GHCR_OWNER}/{spec['image_name']}"
    assert f"{image_base}:latest" in run, (
        f"job '{spec['job_id']}' run block missing '{image_base}:latest'"
    )
    assert f"{image_base}:${{{{ github.sha }}}}" in run, (
        f"job '{spec['job_id']}' run block missing '{image_base}:${{{{ github.sha }}}}'"
    )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_build_step_actually_pushes(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    build_step = _find_build_push_step(steps)
    assert build_step is not None, f"job '{spec['job_id']}' has no docker build/push step"
    run = build_step.get("run", "")
    push_present = (
        "docker push" in run
        or "--all-tags" in run
        or "push: true" in run
    )
    assert push_present, (
        f"job '{spec['job_id']}' build step must push the image "
        "(docker push / --all-tags / push: true)"
    )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_ghcr_login_uses_github_token(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    login_found = False
    for s in steps:
        run = s.get("run", "") or ""
        if "docker login" in run and "ghcr.io" in run and "secrets.GITHUB_TOKEN" in run:
            login_found = True
            break
        # also accept action-based login
        with_block = s.get("with", {}) or {}
        uses = s.get("uses", "") or ""
        if ("ghcr.io" in str(with_block) or "ghcr.io" in uses) and \
                "secrets.GITHUB_TOKEN" in str(with_block):
            login_found = True
            break
    assert login_found, (
        f"job '{spec['job_id']}' must have a GHCR login step using ${{{{ secrets.GITHUB_TOKEN }}}}"
    )


@pytest.mark.parametrize("spec", JOBS, ids=[s["job_id"] for s in JOBS])
def test_build_context_and_dockerfile(jobs, spec):
    job = jobs[spec["job_id"]]
    steps = job.get("steps", [])
    build_step = _find_build_push_step(steps)
    assert build_step is not None, f"job '{spec['job_id']}' has no docker build/push step"
    run = build_step.get("run", "")

    # Extract the docker build invocation line(s)
    build_lines = [ln for ln in run.splitlines() if "docker build" in ln]
    assert build_lines, f"job '{spec['job_id']}' no 'docker build' line found in run block"
    build_cmd = " ".join(build_lines)

    # Check -f / context
    if spec["dockerfile_flag"] is not None:
        # vault-worker and copilot-ui: context=. and -f apps/{name}/Dockerfile
        assert f"-f {spec['dockerfile_flag']}" in build_cmd or \
               f"-f {spec['dockerfile_flag']}" in run, (
            f"job '{spec['job_id']}' docker build must have -f {spec['dockerfile_flag']}"
        )
        # Context must be repo root; the last non-flag token in docker build is typically context
        # Accept ` .` (space-dot) or end-of-line dot as the context argument
        assert re.search(r"\s\.\s*$|\s\.\s", build_cmd) is not None or build_cmd.endswith(" ."), (
            f"job '{spec['job_id']}' docker build context must be '.' (repo root), cmd: {build_cmd}"
        )
        # Dockerfile must exist on disk
        assert os.path.exists(spec["dockerfile_flag"]), (
            f"Dockerfile '{spec['dockerfile_flag']}' not found on disk"
        )
    else:
        # github-runner: context=apps/github_runner/, no -f or -f Dockerfile
        expected_ctx = spec["build_context"]
        assert expected_ctx in build_cmd, (
            f"job '{spec['job_id']}' docker build context must be '{expected_ctx}', cmd: {build_cmd}"
        )
        # Should not have a -f pointing outside the context dir
        f_match = re.search(r"-f\s+(\S+)", build_cmd)
        if f_match:
            f_val = f_match.group(1)
            assert f_val == "Dockerfile" or f_val.startswith(expected_ctx), (
                f"job '{spec['job_id']}' unexpected -f flag: {f_val}"
            )
        # Dockerfile must exist on disk
        dockerfile_path = os.path.join(expected_ctx, "Dockerfile")
        assert os.path.exists(dockerfile_path), (
            f"Dockerfile '{dockerfile_path}' not found on disk"
        )

import tomllib
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def _load_ci():
    with open(CI_YML) as f:
        data = yaml.safe_load(f)
    # yaml.safe_load (YAML 1.1) coerces bare 'on' key to boolean True
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def _load_pyproject():
    with open(PYPROJECT_TOML, "rb") as f:
        return tomllib.load(f)


def _find_install_step(steps):
    for step in steps:
        run = step.get("run", "")
        if "pip install" in run and ("[dev]" in run or "vault_worker" in run or "copilot_ui" in run):
            return run
    raise AssertionError("No install step found in ci.yml jobs.test.steps")


def _find_pytest_step(steps):
    for step in steps:
        run = step.get("run", "")
        if "pytest" in run:
            return run
    raise AssertionError("No pytest step found in ci.yml jobs.test.steps")


def test_ci_triggers_on_pull_request_main():
    ci = _load_ci()
    branches = ci["on"]["pull_request"]["branches"]
    assert "main" in branches


def test_ci_job_runs_on_ubuntu_latest():
    ci = _load_ci()
    assert ci["jobs"]["test"]["runs-on"] == "ubuntu-latest"


def test_ci_has_exactly_one_setup_python_v5_step():
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    setup_steps = [
        s for s in steps
        if isinstance(s.get("uses"), str) and s["uses"].startswith("actions/setup-python@v5")
    ]
    assert len(setup_steps) == 1, (
        f"Expected exactly 1 actions/setup-python@v5 step, found {len(setup_steps)}"
    )
    assert str(setup_steps[0]["with"]["python-version"]) == "3.12"


def test_install_step_contains_required_editable_installs():
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    run = _find_install_step(steps)
    assert ('pip install -e ".[dev]"' in run or "pip install -e '.[dev]'" in run), (
        "Install step must contain: pip install -e \".[dev]\""
    )
    assert "pip install -e packages/shared" in run, (
        "Install step must install packages/shared before apps that depend on obsidian-shared"
    )
    assert "pip install -r apps/vault_worker/requirements.txt" in run, (
        "vault_worker is not a package (no pyproject); its deps come from requirements.txt"
    )
    assert "pip install -e apps/copilot_ui" in run, (
        "Install step must contain: pip install -e apps/copilot_ui"
    )


def test_install_step_does_not_install_test_deps_explicitly():
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    run = _find_install_step(steps)
    forbidden_prefixes = (
        "pip install pytest",
        "pip install pytest-cov",
        "pip install pytest-asyncio",
        "pip install pytest-timeout",
    )
    for line in run.splitlines():
        stripped = line.strip()
        for prefix in forbidden_prefixes:
            assert not stripped.startswith(prefix), (
                f"Install step must not install {prefix!r} directly; "
                "it must come from the [dev] extra"
            )


def test_pytest_step_has_exact_cov_flags():
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    run = _find_pytest_step(steps)
    tokens = run.split()
    assert "--cov=apps" in tokens, "pytest step must include --cov=apps"
    assert "--cov=packages" in tokens, "pytest step must include --cov=packages"
    assert "--cov-fail-under=90" in tokens, "pytest step must include --cov-fail-under=90"


def test_pytest_step_has_no_forbidden_cov_flags():
    ci = _load_ci()
    steps = ci["jobs"]["test"]["steps"]
    run = _find_pytest_step(steps)
    tokens = run.split()
    allowed_cov = {"--cov=apps", "--cov=packages", "--cov-fail-under=90"}
    for token in tokens:
        if token.startswith("--cov") and token not in allowed_cov:
            raise AssertionError(
                f"Forbidden coverage flag {token!r} in pytest step. "
                f"Allowed flags: {allowed_cov}"
            )


def test_pyproject_omits_copilot_ui_app():
    data = _load_pyproject()
    omit_list = data["tool"]["coverage"]["run"]["omit"]
    assert "apps/copilot_ui/app.py" in omit_list, (
        "pyproject.toml [tool.coverage.run] omit must include 'apps/copilot_ui/app.py'"
    )

"""Test CI workflow configuration structure."""
from pathlib import Path


def test_ci_workflow_exists():
    """CI workflow file must exist at .github/workflows/ci.yml."""
    workflow_path = Path(".github/workflows/ci.yml")
    content = workflow_path.read_text()  # Raises FileNotFoundError if missing
    assert content, "CI workflow file is empty"


def test_ci_workflow_python_312():
    """CI workflow must specify Python 3.12."""
    content = Path(".github/workflows/ci.yml").read_text()
    assert "python-version" in content, "Missing python-version configuration"
    assert "3.12" in content, "Must pin Python 3.12"


def test_ci_workflow_editable_installs():
    """CI workflow must use editable installs for all packages."""
    content = Path(".github/workflows/ci.yml").read_text()
    assert "pip install -e" in content, "Missing editable install command"
    assert "packages/shared[dev]" in content, "Must install packages/shared[dev]"
    assert "apps/vault_worker" in content, "Must install apps/vault_worker"
    assert "apps/copilot_ui" in content, "Must install apps/copilot_ui"


def test_ci_workflow_pytest_coverage():
    """CI workflow must run pytest with coverage threshold."""
    content = Path(".github/workflows/ci.yml").read_text()
    assert "pytest" in content, "Missing pytest command"
    assert "--cov-fail-under=90" in content, "Must set coverage threshold to 90%"


def test_ci_workflow_trigger_on_pull_request():
    """CI workflow must trigger on pull_request targeting main."""
    content = Path(".github/workflows/ci.yml").read_text()
    assert "pull_request" in content, "Missing pull_request trigger"
    assert "main" in content, "Must target main branch"


def test_ci_workflow_runner():
    """CI workflow must run on ubuntu-latest."""
    content = Path(".github/workflows/ci.yml").read_text()
    assert "ubuntu-latest" in content, "Must run on ubuntu-latest"

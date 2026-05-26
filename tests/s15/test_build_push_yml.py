"""
Test assertions for .github/workflows/build-push.yml structure.

Tests pin: 3 image jobs, paths-filter, GHCR login, latest+sha tags.
"""
import pathlib


def test_build_push_yml_exists():
    """Build-push workflow file must exist."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    assert workflow_file.exists(), "File .github/workflows/build-push.yml not found"


def test_build_push_yml_has_push_trigger():
    """Workflow must trigger on push to main branch."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "push:" in content
    assert "branches:" in content
    assert "- main" in content or "branches: [main]" in content


def test_build_push_yml_has_workflow_dispatch():
    """Workflow must support manual triggering."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "workflow_dispatch" in content


def test_build_push_yml_has_paths_filter_action():
    """Workflow must use dorny/paths-filter@v3 for change detection."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "dorny/paths-filter@v3" in content


def test_build_push_yml_has_all_image_names():
    """Workflow must reference all three Docker image names (hyphenated form)."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "obsidian-vault-worker" in content
    assert "obsidian-copilot-ui" in content
    assert "obsidian-github-runner" in content


def test_build_push_yml_has_all_source_path_filters():
    """Workflow must filter on Python package dirs (underscore form) and shared."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "apps/vault_worker/**" in content
    assert "apps/copilot_ui/**" in content
    assert "apps/github_runner/**" in content
    assert "packages/shared/**" in content


def test_build_push_yml_has_ghcr_registry():
    """Workflow must push to GHCR with correct registry prefix."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "ghcr.io/christopherjohnkelly/" in content


def test_build_push_yml_has_github_token():
    """Workflow must authenticate to GHCR using GITHUB_TOKEN secret."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "secrets.GITHUB_TOKEN" in content


def test_build_push_yml_has_latest_tag():
    """Workflow must tag images with :latest."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert ":latest" in content


def test_build_push_yml_has_sha_tag():
    """Workflow must tag images with commit SHA."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "${{ github.sha }}" in content


def test_build_push_yml_has_packages_write_permission():
    """Workflow must declare packages: write permission."""
    workflow_file = pathlib.Path(".github/workflows/build-push.yml")
    content = workflow_file.read_text()
    assert "permissions:" in content
    assert "packages: write" in content

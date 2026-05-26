"""Test that README.md documents pulling and running the three published Docker images."""

import pathlib


def test_readme_contains_image_references():
    """README must list all three published image references."""
    readme = pathlib.Path("README.md").read_text()

    assert "ghcr.io/christopherjohnkelly/obsidian-vault-worker" in readme
    assert "obsidian-copilot-ui" in readme
    assert "obsidian-github-runner" in readme


def test_readme_contains_docker_usage_snippet():
    """README must show how to pull or run the images."""
    readme = pathlib.Path("README.md").read_text()

    has_pull = "docker pull" in readme
    has_run = "docker run" in readme
    assert has_pull or has_run, "README must contain either 'docker pull' or 'docker run'"


def test_readme_contains_environment_section():
    """README must document environment variables (via 'Environment' keyword)."""
    readme = pathlib.Path("README.md").read_text()

    assert "Environment" in readme, "README must contain 'Environment' keyword for env-var documentation"


def test_readme_contains_required_env_vars():
    """README must document all required environment variable names."""
    readme = pathlib.Path("README.md").read_text()

    # TEMPORAL_ADDRESS or TEMPORAL_HOST for the workflow orchestrator
    has_temporal = "TEMPORAL_ADDRESS" in readme or "TEMPORAL_HOST" in readme
    assert has_temporal, "README must contain TEMPORAL_ADDRESS or TEMPORAL_HOST"

    # Gemini AI key
    assert "GEMINI_API_KEY" in readme, "README must contain GEMINI_API_KEY"

    # Obsidian vault path
    assert "OBSIDIAN_VAULT_PATH" in readme, "README must contain OBSIDIAN_VAULT_PATH"

    # GitHub token for runner
    has_github_token = "GH_TOKEN" in readme or "GITHUB_TOKEN" in readme
    assert has_github_token, "README must contain GH_TOKEN or GITHUB_TOKEN"

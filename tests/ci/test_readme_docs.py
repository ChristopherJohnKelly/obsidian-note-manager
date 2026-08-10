"""
Tests that README.md contains per-image Docker documentation and a post-merge
manual-validation section for all three GHCR images.
"""
import re
from pathlib import Path

README_PATH = Path(__file__).parents[2] / "README.md"

IMAGES = [
    "obsidian-vault-worker",
    "obsidian-copilot-ui",
    "obsidian-github-runner",
]

IMAGE_ENV_VARS = {
    "obsidian-vault-worker": [
        "VAULT_PATH",
        "REPO_URL",
        "GITHUB_PAT",
        "GEMINI_API_KEY",
        "TEMPORAL_HOST",
    ],
    "obsidian-copilot-ui": [
        "TEMPORAL_ADDRESS",
        "VAULT_PATH",
    ],
    "obsidian-github-runner": [
        "TEMPORAL_HOST",
        "VAULT_PATH",
        "CONTEXT_CODE",
        "REPO_OWNER",
        "REPO_NAME",
        "GITHUB_TOKEN",
        "PR_BRANCH",
        "RUN_ID",
    ],
}

REGISTRY = "ghcr.io/christopherjohnkelly"


def _load_readme() -> str:
    assert README_PATH.exists(), f"README.md not found at {README_PATH}"
    return README_PATH.read_text(encoding="utf-8")


def _extract_image_section(readme: str, image: str) -> str:
    """
    Return the text between the docker pull line for `image` and the next
    image's docker pull line (or the next top-level ## heading, or EOF).
    """
    pull_marker = f"docker pull {REGISTRY}/{image}"
    start = readme.find(pull_marker)
    assert start != -1, (
        f"README.md is missing a 'docker pull {REGISTRY}/{image}' line"
    )

    # Find next boundary: another image's pull line or a top-level ## heading
    other_pull_pattern = re.compile(
        r"docker pull " + re.escape(REGISTRY) + r"/obsidian-(?:"
        + "|".join(img.replace("obsidian-", "") for img in IMAGES if img != image)
        + r")"
    )
    heading_pattern = re.compile(r"^## ", re.MULTILINE)

    end = len(readme)
    for pattern in (other_pull_pattern, heading_pattern):
        m = pattern.search(readme, start + len(pull_marker))
        if m and m.start() < end:
            end = m.start()

    return readme[start:end]


def test_github_runner_run_example_passes_workflow_arg():
    """trigger.py requires --workflow (argparse, exit 2 without it)."""
    readme = _load_readme()
    section = _extract_image_section(readme, "obsidian-github-runner")
    assert "python3 trigger.py --workflow" in section, (
        "CMD-only image: the run example must supply the full command, "
        "python3 trigger.py --workflow ..."
    )
    assert ("FilerIngestionWorkflow" in section or "NightWatchmanWorkflow" in section), (
        "run example must use a valid --workflow value from workflow_names.py"
    )


def test_readme_exists():
    _load_readme()


def test_vault_worker_docker_pull():
    readme = _load_readme()
    image = "obsidian-vault-worker"
    expected = f"docker pull {REGISTRY}/{image}:latest"
    assert expected in readme, (
        f"README.md missing: {expected}"
    )


def test_copilot_ui_docker_pull():
    readme = _load_readme()
    image = "obsidian-copilot-ui"
    expected = f"docker pull {REGISTRY}/{image}:latest"
    assert expected in readme, (
        f"README.md missing: {expected}"
    )


def test_github_runner_docker_pull():
    readme = _load_readme()
    image = "obsidian-github-runner"
    expected = f"docker pull {REGISTRY}/{image}:latest"
    assert expected in readme, (
        f"README.md missing: {expected}"
    )


def test_vault_worker_docker_run():
    readme = _load_readme()
    image = "obsidian-vault-worker"
    section = _extract_image_section(readme, image)
    assert f"docker run " in section and f"{REGISTRY}/{image}" in section, (
        f"README.md section for {image} missing a 'docker run' line referencing {REGISTRY}/{image}"
    )


def test_copilot_ui_docker_run():
    readme = _load_readme()
    image = "obsidian-copilot-ui"
    section = _extract_image_section(readme, image)
    assert f"docker run " in section and f"{REGISTRY}/{image}" in section, (
        f"README.md section for {image} missing a 'docker run' line referencing {REGISTRY}/{image}"
    )


def test_github_runner_docker_run():
    readme = _load_readme()
    image = "obsidian-github-runner"
    section = _extract_image_section(readme, image)
    assert f"docker run " in section and f"{REGISTRY}/{image}" in section, (
        f"README.md section for {image} missing a 'docker run' line referencing {REGISTRY}/{image}"
    )


def test_vault_worker_env_vars():
    readme = _load_readme()
    image = "obsidian-vault-worker"
    section = _extract_image_section(readme, image)
    for var in IMAGE_ENV_VARS[image]:
        assert var in section, (
            f"README.md section for {image} missing env var: {var}"
        )


def test_copilot_ui_env_vars():
    readme = _load_readme()
    image = "obsidian-copilot-ui"
    section = _extract_image_section(readme, image)
    for var in IMAGE_ENV_VARS[image]:
        assert var in section, (
            f"README.md section for {image} missing env var: {var}"
        )


def test_github_runner_env_vars():
    readme = _load_readme()
    image = "obsidian-github-runner"
    section = _extract_image_section(readme, image)
    for var in IMAGE_ENV_VARS[image]:
        assert var in section, (
            f"README.md section for {image} missing env var: {var}"
        )


def test_post_merge_manual_validation_section():
    readme = _load_readme()
    # Find a heading matching /manual validation|post-?merge/i
    heading_pattern = re.compile(
        r"^#{1,6}\s+.*(manual\s+validation|post-?merge).*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = heading_pattern.search(readme)
    assert m is not None, (
        "README.md missing a heading matching 'manual validation' or 'post-merge'"
    )
    # Extract body under that heading (up to the next same-or-higher-level heading or EOF)
    heading_line = m.group(0)
    heading_level = len(heading_line) - len(heading_line.lstrip("#"))
    body_start = m.end()
    next_heading = re.compile(
        r"^#{1," + str(heading_level) + r"}\s", re.MULTILINE
    )
    nm = next_heading.search(readme, body_start)
    body = readme[body_start: nm.start() if nm else len(readme)]
    assert "workflow_dispatch" in body, (
        "Post-merge/manual-validation section in README.md missing 'workflow_dispatch'"
    )

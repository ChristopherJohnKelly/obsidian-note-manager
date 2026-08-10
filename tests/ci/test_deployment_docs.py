"""C4: .env.example coverage, docs/deployment.md, and .gitignore assertion."""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent


def test_env_example_exists():
    assert (REPO_ROOT / ".env.example").exists(), ".env.example not found"


def test_env_example_covers_every_compose_var():
    compose_text = (REPO_ROOT / "docker-compose.prod.yml").read_text()
    referenced = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", compose_text))

    env_example = (REPO_ROOT / ".env.example").read_text()
    defined = set()
    for line in env_example.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            defined.add(stripped.split("=", 1)[0])

    missing = referenced - defined
    assert not missing, (
        f"docker-compose.prod.yml references vars not in .env.example: {sorted(missing)}"
    )


def test_gitignore_covers_env():
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    standalone_env_lines = [
        line.strip() for line in gitignore.splitlines() if line.strip() == ".env"
    ]
    assert standalone_env_lines, ".gitignore does not contain a standalone '.env' line"


def test_deployment_doc_exists():
    assert (REPO_ROOT / "docs" / "deployment.md").exists(), "docs/deployment.md not found"


def test_deployment_doc_sections():
    doc = (REPO_ROOT / "docs" / "deployment.md").read_text()
    required = [
        ("pull", "image pull step"),
        (".env", "env file reference"),
        ("up -d", "stack start command"),
        ("8080", "Temporal UI port"),
        ("8000", "Chainlit port"),
        ("docker compose config", "post-merge structural validation"),
    ]
    for substring, label in required:
        assert substring in doc, f"docs/deployment.md missing {label!r} (expected substring {substring!r})"

    health_check = "vault-default" in doc or any(
        svc in doc for svc in ["copilot-worker", "librarian-worker", "github-runner"]
    )
    assert health_check, (
        "docs/deployment.md missing per-service or 'vault-default' health/verify section"
    )

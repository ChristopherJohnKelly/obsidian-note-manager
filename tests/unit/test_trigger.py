"""Tests for the trigger module CLI."""
import ast
import pathlib
import re
import pytest
from unittest.mock import AsyncMock
from apps.github_runner import trigger


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the global client after each test."""
    yield
    trigger.configure_client(None)


def test_unknown_workflow_returns_1_with_stderr_message(capsys):
    """Test that unknown --workflow argument returns 1 with error message to stderr."""
    exit_code = trigger.main(["--workflow", "UnknownWorkflow"])
    assert exit_code == 1

    captured = capsys.readouterr()
    assert "Unknown workflow: UnknownWorkflow" in captured.err


def test_vault_manager_workflow_not_in_workflows():
    """Test that VaultManagerWorkflow is not exported in WORKFLOWS dict."""
    # Ensure VaultManagerWorkflow is not a key in the WORKFLOWS dict
    assert "VaultManagerWorkflow" not in trigger.WORKFLOWS
    # Also ensure the constant itself is not exported at module level
    assert not hasattr(trigger, "VAULT_MANAGER_WORKFLOW")


def test_nightwatchman_workflow_starts_with_mock_client():
    """Test that NightWatchmanWorkflow is started via injected mock client."""
    mock_client = AsyncMock()

    trigger.configure_client(mock_client)

    exit_code = trigger.main(["--workflow", "NightWatchmanWorkflow"])

    assert exit_code == 0
    # Assert that start_workflow was awaited with the workflow name as first positional arg
    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[0][0] == "NightWatchmanWorkflow"


def test_filer_ingestion_workflow_starts_with_source_path():
    """Test that FilerIngestionWorkflow is started with correct input including source_path."""
    mock_client = AsyncMock()

    trigger.configure_client(mock_client)

    source_path = "00. Inbox/0. Capture/note.md"
    exit_code = trigger.main(["--workflow", "FilerIngestionWorkflow", "--source-path", source_path])

    assert exit_code == 0
    # Assert that start_workflow was called
    mock_client.start_workflow.assert_called_once()
    call_args = mock_client.start_workflow.call_args
    assert call_args[0][0] == "FilerIngestionWorkflow"
    # Check that the input object has the correct source_path
    input_obj = call_args[0][1]
    assert input_obj.source_path == source_path


def test_trigger_py_imports_no_forbidden_modules():
    """Assert trigger.py does not import git, frontmatter, generativeai, or vault_worker."""
    # Read trigger.py source
    trigger_file = pathlib.Path(__file__).parent.parent.parent / 'apps' / 'github_runner' / 'trigger.py'
    source = trigger_file.read_text()

    # Parse and walk AST to collect all imported modules
    tree = ast.parse(source)
    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)

    # Define forbidden import roots (AC4)
    forbidden_prefixes = {
        'git',
        'frontmatter',
        'generativeai',
        'google.generativeai',
        'apps.vault_worker',
    }

    # Find violations
    violations = []
    for module in imported_modules:
        for prefix in forbidden_prefixes:
            if module.startswith(prefix):
                violations.append(module)

    assert not violations, f"trigger.py imports forbidden modules: {violations}"


def test_requirements_txt_exists_and_has_minimal_deps():
    """Assert requirements.txt exists and contains only temporalio and python-dotenv."""
    requirements_file = pathlib.Path(__file__).parent.parent.parent / 'apps' / 'github_runner' / 'requirements.txt'

    # Will raise FileNotFoundError if file doesn't exist (expected RED)
    content = requirements_file.read_text()

    # Assert required dependencies are present
    assert 'temporalio' in content, "requirements.txt must contain temporalio"
    assert 'python-dotenv' in content, "requirements.txt must contain python-dotenv"

    # Assert no vault, git, or Gemini dependencies
    forbidden_deps = ['gitpython', 'GitPython', 'google-generativeai', 'frontmatter']
    for dep in forbidden_deps:
        assert dep not in content.lower(), f"requirements.txt must not contain {dep}"


def test_dockerfile_exists_and_references_trigger_and_requirements():
    """Assert Dockerfile exists and references trigger.py and requirements.txt."""
    dockerfile = pathlib.Path(__file__).parent.parent.parent / 'apps' / 'github_runner' / 'Dockerfile'

    # Will raise FileNotFoundError if file doesn't exist (expected RED)
    content = dockerfile.read_text()

    # Assert references to key files
    assert 'trigger.py' in content, "Dockerfile must reference trigger.py"
    assert 'requirements.txt' in content, "Dockerfile must reference requirements.txt"

    # Assert no vault, git, or Gemini dependencies (case-insensitive)
    content_lower = content.lower()
    forbidden_patterns = ['src_v2', 'gitpython', 'gemini']
    for pattern in forbidden_patterns:
        assert pattern not in content_lower, f"Dockerfile must not contain {pattern}"


def test_ingest_yml_exists_and_has_required_content():
    """Assert .github/workflows/ingest.yml exists with required content and no forbidden patterns."""
    ingest_yml = pathlib.Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'ingest.yml'

    # Will raise FileNotFoundError if file doesn't exist (expected RED)
    content = ingest_yml.read_text()

    # Assert required content is present
    assert 'trigger.py' in content, "ingest.yml must reference trigger.py"
    assert '--workflow FilerIngestionWorkflow' in content, "ingest.yml must contain --workflow FilerIngestionWorkflow"
    assert '--source-path' in content, "ingest.yml must contain --source-path"

    # Assert no vault checkout or forbidden environment variables
    forbidden_patterns = ['actions/checkout', 'OBSIDIAN_VAULT_ROOT', 'GEMINI_API_KEY', 'src_v2']
    for pattern in forbidden_patterns:
        assert pattern not in content, f"ingest.yml must not contain {pattern}"


def test_watchman_yml_exists_and_has_required_content():
    """Assert .github/workflows/watchman.yml exists with cron schedule and required workflow."""
    watchman_yml = pathlib.Path(__file__).parent.parent.parent / '.github' / 'workflows' / 'watchman.yml'

    # Will raise FileNotFoundError if file doesn't exist (expected RED)
    content = watchman_yml.read_text()

    # Assert cron pattern: 0 2 * * * (matches with optional quotes)
    cron_pattern = r"cron:\s*['\"]?0 2 \* \* \*"
    assert re.search(cron_pattern, content), "watchman.yml must contain cron schedule '0 2 * * *'"

    # Assert required workflow
    assert '--workflow NightWatchmanWorkflow' in content, "watchman.yml must contain --workflow NightWatchmanWorkflow"


def test_trigger_py_is_self_contained():
    """Assert trigger.py has no imports from packages.* module."""
    # Read trigger.py source
    trigger_file = pathlib.Path(__file__).parent.parent.parent / 'apps' / 'github_runner' / 'trigger.py'
    source = trigger_file.read_text()

    # Parse and walk AST to collect all imported modules
    tree = ast.parse(source)
    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)

    # Assert no packages.* imports
    packages_imports = [m for m in imported_modules if m.startswith('packages')]
    assert not packages_imports, f"trigger.py must not import from packages.*: {packages_imports}"

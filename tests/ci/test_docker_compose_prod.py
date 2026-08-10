import os
import pytest
import yaml


@pytest.fixture(scope="module")
def compose():
    with open("docker-compose.prod.yml") as f:
        return yaml.safe_load(f)


def test_compose_file_exists():
    assert os.path.exists("docker-compose.prod.yml")


def test_all_six_services_present(compose):
    required = {"postgres", "temporal-server", "temporal-ui", "vault-worker", "copilot-ui", "github-runner"}
    assert set(compose["services"].keys()) >= required


def test_custom_services_use_ghcr_images(compose):
    for svc in ("vault-worker", "copilot-ui", "github-runner"):
        image = compose["services"][svc]["image"]
        assert image.startswith(f"ghcr.io/christopherjohnkelly/obsidian-{svc}"), (
            f"Service {svc!r} has image {image!r}, expected ghcr.io/christopherjohnkelly/obsidian-{svc}:..."
        )


def test_no_service_uses_build(compose):
    for svc, cfg in compose["services"].items():
        assert "build" not in cfg, f"Service {svc!r} must not use 'build:'"


def test_no_elasticsearch_service(compose):
    keys = set(compose["services"].keys())
    assert "elasticsearch" not in keys
    elastic_services = [k for k in keys if "elastic" in k]
    assert not elastic_services, f"Found elasticsearch-like services: {elastic_services}"


def test_temporal_server_postgres_plugin(compose):
    env = compose["services"]["temporal-server"]["environment"]
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    assert env["DB"] == "postgres12", f"Expected DB=postgres12, got {env.get('DB')!r}"
    assert env["VISIBILITY_DB_PLUGIN"] == "postgres12", (
        f"Expected VISIBILITY_DB_PLUGIN=postgres12, got {env.get('VISIBILITY_DB_PLUGIN')!r}"
    )


# --- C2: per-service env-var correctness ---

def env_of(svc, compose=None):
    """Return the environment for a service as a dict, handling both list and dict forms."""
    if compose is None:
        with open("docker-compose.prod.yml") as f:
            import yaml
            compose = yaml.safe_load(f)
    raw = compose["services"][svc].get("environment", {})
    if isinstance(raw, list):
        return dict(item.split("=", 1) for item in raw)
    if raw is None:
        return {}
    return dict(raw)


def test_vault_worker_env_exact_five(compose):
    keys = set(env_of("vault-worker", compose).keys())
    expected = {"TEMPORAL_HOST", "VAULT_PATH", "REPO_URL", "GITHUB_PAT", "GEMINI_API_KEY"}
    assert keys == expected, (
        f"vault-worker env keys {keys!r} != expected {expected!r}"
    )


def test_copilot_ui_env_has_temporal_address(compose):
    keys = env_of("copilot-ui", compose)
    assert "TEMPORAL_ADDRESS" in keys, (
        f"copilot-ui env missing TEMPORAL_ADDRESS (apps/copilot_ui/app.py reads it); got keys={set(keys)!r}"
    )


def test_copilot_ui_env_has_no_vault_or_llm_secrets(compose):
    prohibited = {"VAULT_PATH", "GITHUB_PAT", "GEMINI_API_KEY", "REPO_URL"}
    present = prohibited & set(env_of("copilot-ui", compose).keys())
    assert not present, (
        f"copilot-ui env must not contain vault/LLM secrets, but found: {present!r}"
    )


def test_temporal_ui_has_temporal_address(compose):
    keys = env_of("temporal-ui", compose)
    assert "TEMPORAL_ADDRESS" in keys, (
        f"temporal-ui env missing TEMPORAL_ADDRESS; got keys={set(keys)!r}"
    )


def test_github_runner_env_includes_required(compose):
    keys = set(env_of("github-runner", compose).keys())
    required = {"TEMPORAL_HOST", "GITHUB_PAT", "REPO_URL", "RUNNER_NAME"}
    missing = required - keys
    assert not missing, f"github-runner env missing required keys: {missing!r}"
    prohibited = {"VAULT_PATH", "GEMINI_API_KEY"}
    present = prohibited & keys
    assert not present, f"github-runner env must not contain: {present!r}"

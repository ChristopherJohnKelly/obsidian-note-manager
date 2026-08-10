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


# --- C3: ports, volumes, depends_on ---

def _normalise_port(port_entry):
    """Return (host_port, container_port) as ints from string or dict form."""
    if isinstance(port_entry, str):
        parts = port_entry.split(":")
        return int(parts[0]), int(parts[1])
    # dict form: {published: ..., target: ...}
    return int(port_entry["published"]), int(port_entry["target"])


def test_only_temporal_ui_and_copilot_ui_publish_host_ports(compose):
    no_ports_services = {"postgres", "temporal-server", "vault-worker", "github-runner"}
    for svc in no_ports_services:
        cfg = compose["services"][svc]
        assert "ports" not in cfg, (
            f"Service {svc!r} must not have a 'ports' key (expose-only or none), but found: {cfg['ports']!r}"
        )

    temporal_ui_ports = compose["services"]["temporal-ui"].get("ports", [])
    assert temporal_ui_ports, "temporal-ui must declare ports"
    normalised = [_normalise_port(p) for p in temporal_ui_ports]
    assert (8080, 8080) in normalised, (
        f"temporal-ui must publish 8080:8080, got ports: {temporal_ui_ports!r}"
    )

    copilot_ui_ports = compose["services"]["copilot-ui"].get("ports", [])
    assert copilot_ui_ports, "copilot-ui must declare ports"
    normalised = [_normalise_port(p) for p in copilot_ui_ports]
    assert (8000, 8000) in normalised, (
        f"copilot-ui must publish 8000:8000, got ports: {copilot_ui_ports!r}"
    )


def test_postgres_named_volume(compose):
    pg_volumes = compose["services"]["postgres"].get("volumes", [])
    assert pg_volumes, "postgres service must declare a 'volumes' key"
    found = any(
        (isinstance(v, str) and v.startswith("postgres-data:"))
        for v in pg_volumes
    )
    assert found, (
        f"postgres service must mount 'postgres-data:/var/lib/postgresql/data', got: {pg_volumes!r}"
    )

    top_volumes = compose.get("volumes", {})
    assert "postgres-data" in top_volumes, (
        f"Top-level 'volumes' must declare 'postgres-data', got: {list(top_volumes.keys())!r}"
    )


def _depends_on_names(service_cfg):
    """Return the set of dependency names from depends_on (list or dict form)."""
    dep = service_cfg.get("depends_on")
    if dep is None:
        return set()
    if isinstance(dep, list):
        return set(dep)
    # dict form: {service_name: {condition: ...}}
    return set(dep.keys())


def test_depends_on_wiring(compose):
    temporal_server_deps = _depends_on_names(compose["services"]["temporal-server"])
    assert "postgres" in temporal_server_deps, (
        f"temporal-server must depend on postgres, got depends_on: {temporal_server_deps!r}"
    )

    for svc in ("temporal-ui", "vault-worker", "copilot-ui", "github-runner"):
        deps = _depends_on_names(compose["services"][svc])
        assert "temporal-server" in deps, (
            f"Service {svc!r} must depend on temporal-server, got depends_on: {deps!r}"
        )

# --- C5: credentials, templating, and .env.example coverage ---
# Added after the attempt-3 rejection: postgres shipped with no credentials
# (container exits at boot), temporal-server could not reach the DB, the
# vault-data volume was dropped, and no check tied ${VAR} references to
# .env.example entries.

def test_postgres_credentials_templated(compose):
    env = env_of("postgres", compose)
    assert env.get("POSTGRES_PASSWORD") == "${POSTGRES_PASSWORD}", (
        f"postgres POSTGRES_PASSWORD must be templated from .env, got {env.get('POSTGRES_PASSWORD')!r}"
    )
    assert env.get("POSTGRES_USER") == "temporal"
    assert "POSTGRES_DB" in env


def test_temporal_server_db_connectivity(compose):
    env = env_of("temporal-server", compose)
    assert env.get("POSTGRES_SEEDS") == "postgres", (
        f"temporal-server must point at the postgres service, got {env.get('POSTGRES_SEEDS')!r}"
    )
    assert env.get("POSTGRES_USER") == "temporal"
    assert env.get("POSTGRES_PWD") == "${POSTGRES_PASSWORD}", (
        f"temporal-server POSTGRES_PWD must be templated from .env, got {env.get('POSTGRES_PWD')!r}"
    )
    assert "DB_PORT" in env


def test_vault_worker_named_volume(compose):
    vw_volumes = compose["services"]["vault-worker"].get("volumes", [])
    assert any(
        isinstance(v, str) and v.startswith("vault-data:") for v in vw_volumes
    ), f"vault-worker must mount the vault-data named volume (TRD 7.2), got: {vw_volumes!r}"
    assert "vault-data" in compose.get("volumes", {}), (
        "Top-level volumes must declare vault-data"
    )


def test_every_compose_var_has_env_example_entry():
    """Every ${VAR} referenced in the compose file must be documented."""
    import pathlib
    import re as _re

    compose_text = pathlib.Path("docker-compose.prod.yml").read_text()
    env_example = pathlib.Path(".env.example").read_text()
    referenced = set(_re.findall(r"\$\{([A-Z_]+)(?::-[^}]*)?\}", compose_text))
    assert referenced, "expected ${VAR} references in docker-compose.prod.yml"
    documented = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    missing = referenced - documented
    assert not missing, (
        f".env.example is missing entries for compose variables: {sorted(missing)!r}"
    )


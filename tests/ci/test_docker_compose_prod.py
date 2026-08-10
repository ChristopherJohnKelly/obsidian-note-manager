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

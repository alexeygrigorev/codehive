"""Tests for docker-compose.yml structure and .env.example (issue #02)."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


class TestDockerComposeStructure:
    """Validate docker-compose.yml content without running Docker."""

    def test_compose_file_exists(self):
        assert COMPOSE_FILE.exists(), "docker-compose.yml must exist at repo root"

    def test_compose_parses_valid_yaml(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        assert isinstance(data, dict)

    def test_postgres_service_defined(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        assert "postgres" in data["services"]

    def test_postgres_image(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        assert data["services"]["postgres"]["image"] == "postgres:16"

    def test_postgres_healthcheck(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        hc = data["services"]["postgres"]["healthcheck"]
        assert hc is not None
        # pg_isready should appear in the test command
        test_cmd = " ".join(hc["test"]) if isinstance(hc["test"], list) else hc["test"]
        assert "pg_isready" in test_cmd

    def test_postgres_port(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        ports = data["services"]["postgres"]["ports"]
        assert any("5432" in str(p) for p in ports)

    def test_postgres_named_volume(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        volumes = data["services"]["postgres"].get("volumes", [])
        assert len(volumes) > 0, "Postgres should use a named volume for data persistence"
        # Top-level volumes section should define the named volume
        top_volumes = data.get("volumes", {})
        assert len(top_volumes) > 0, "Named volume must be defined at top level"

    def test_redis_service_defined(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        assert "redis" in data["services"]

    def test_redis_image(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        assert data["services"]["redis"]["image"] == "redis:7"

    def test_redis_healthcheck(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        hc = data["services"]["redis"]["healthcheck"]
        assert hc is not None
        test_cmd = " ".join(hc["test"]) if isinstance(hc["test"], list) else hc["test"]
        assert "redis-cli" in test_cmd and "ping" in test_cmd

    def test_redis_port(self):
        data = yaml.safe_load(COMPOSE_FILE.read_text())
        ports = data["services"]["redis"]["ports"]
        assert any("6379" in str(p) for p in ports)


class TestEnvExample:
    """Validate .env.example file."""

    def test_env_example_exists(self):
        assert ENV_EXAMPLE.exists(), ".env.example must exist at repo root"

    def test_env_example_contains_required_vars(self):
        content = ENV_EXAMPLE.read_text()
        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_DB",
        ]
        for var in required_vars:
            assert var in content, f".env.example must contain {var}"

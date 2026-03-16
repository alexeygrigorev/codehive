"""Tests for backend Dockerfile, docker-entrypoint.sh, .dockerignore, and docker-compose.prod.yml (issue #57a)."""

import os
import stat
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
DOCKERFILE = BACKEND_DIR / "Dockerfile"
DOCKERIGNORE = BACKEND_DIR / ".dockerignore"
ENTRYPOINT = BACKEND_DIR / "docker-entrypoint.sh"
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


class TestDockerfile:
    """Validate backend/Dockerfile structure."""

    def test_dockerfile_exists(self):
        assert DOCKERFILE.exists(), "backend/Dockerfile must exist"

    def test_multistage_build(self):
        content = DOCKERFILE.read_text()
        from_count = sum(1 for line in content.splitlines() if line.strip().startswith("FROM "))
        assert from_count >= 2, (
            f"Dockerfile must have at least 2 FROM statements, found {from_count}"
        )

    def test_uses_python_312_slim(self):
        content = DOCKERFILE.read_text()
        assert "python:3.12-slim" in content

    def test_installs_uv(self):
        content = DOCKERFILE.read_text()
        assert "uv" in content.lower(), "Dockerfile should install/use uv"

    def test_copies_lock_file(self):
        content = DOCKERFILE.read_text()
        assert "uv.lock" in content, "Dockerfile should copy uv.lock for reproducible builds"

    def test_copies_pyproject(self):
        content = DOCKERFILE.read_text()
        assert "pyproject.toml" in content

    def test_non_root_user(self):
        content = DOCKERFILE.read_text()
        assert "USER" in content, "Dockerfile should switch to a non-root user"
        # Should not be USER root
        user_lines = [
            line.strip() for line in content.splitlines() if line.strip().startswith("USER ")
        ]
        assert len(user_lines) > 0
        assert user_lines[-1] != "USER root", "Final USER should not be root"

    def test_exposes_port_7433(self):
        content = DOCKERFILE.read_text()
        assert "EXPOSE 7433" in content

    def test_healthcheck_defined(self):
        content = DOCKERFILE.read_text()
        assert "HEALTHCHECK" in content

    def test_healthcheck_hits_health_endpoint(self):
        content = DOCKERFILE.read_text()
        assert "/api/health" in content, "Healthcheck should target /api/health"

    def test_entrypoint_references_entrypoint_script(self):
        content = DOCKERFILE.read_text()
        assert "docker-entrypoint.sh" in content

    def test_no_dev_dependencies(self):
        content = DOCKERFILE.read_text()
        assert "--no-dev" in content, "Production build should exclude dev dependencies"

    def test_copies_alembic_ini(self):
        content = DOCKERFILE.read_text()
        assert "alembic.ini" in content, "Dockerfile should copy alembic.ini for migrations"


class TestEntrypoint:
    """Validate docker-entrypoint.sh."""

    def test_entrypoint_exists(self):
        assert ENTRYPOINT.exists(), "backend/docker-entrypoint.sh must exist"

    def test_entrypoint_is_executable(self):
        mode = os.stat(ENTRYPOINT).st_mode
        assert mode & stat.S_IXUSR, "docker-entrypoint.sh must be executable"

    def test_runs_alembic_upgrade(self):
        content = ENTRYPOINT.read_text()
        assert "alembic upgrade head" in content, "Entrypoint must run alembic upgrade head"

    def test_starts_uvicorn_with_factory(self):
        content = ENTRYPOINT.read_text()
        assert "uvicorn" in content
        assert "--factory" in content, "Uvicorn must use --factory flag for app factory"
        assert "codehive.api.app:create_app" in content

    def test_uses_exec(self):
        content = ENTRYPOINT.read_text()
        assert "exec uvicorn" in content, "Entrypoint must use exec so uvicorn is PID 1"

    def test_binds_to_all_interfaces(self):
        content = ENTRYPOINT.read_text()
        assert "0.0.0.0" in content, "Uvicorn must bind to 0.0.0.0 inside container"

    def test_has_shebang(self):
        content = ENTRYPOINT.read_text()
        assert content.startswith("#!/bin/bash") or content.startswith("#!/bin/sh")

    def test_set_e(self):
        content = ENTRYPOINT.read_text()
        assert "set -e" in content, "Entrypoint should use set -e for fail-fast"


class TestDockerignore:
    """Validate backend/.dockerignore."""

    def test_dockerignore_exists(self):
        assert DOCKERIGNORE.exists(), "backend/.dockerignore must exist"

    def test_excludes_pycache(self):
        content = DOCKERIGNORE.read_text()
        assert "__pycache__" in content

    def test_excludes_venv(self):
        content = DOCKERIGNORE.read_text()
        assert ".venv" in content

    def test_excludes_tests(self):
        content = DOCKERIGNORE.read_text()
        assert "tests/" in content or "tests" in content.splitlines()


class TestComposeProd:
    """Validate docker-compose.prod.yml structure."""

    def test_compose_prod_exists(self):
        assert COMPOSE_PROD.exists(), "docker-compose.prod.yml must exist at repo root"

    def test_compose_parses_valid_yaml(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert isinstance(data, dict)

    def test_backend_service_defined(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert "backend" in data["services"]

    def test_postgres_service_defined(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert "postgres" in data["services"]

    def test_redis_service_defined(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert "redis" in data["services"]

    def test_backend_builds_from_dockerfile(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        backend = data["services"]["backend"]
        build = backend.get("build", {})
        assert "context" in build or "dockerfile" in build

    def test_backend_depends_on_postgres_healthy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        depends = data["services"]["backend"].get("depends_on", {})
        assert "postgres" in depends
        pg_dep = depends["postgres"]
        assert pg_dep.get("condition") == "service_healthy"

    def test_backend_depends_on_redis_healthy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        depends = data["services"]["backend"].get("depends_on", {})
        assert "redis" in depends
        redis_dep = depends["redis"]
        assert redis_dep.get("condition") == "service_healthy"

    def test_postgres_healthcheck(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        hc = data["services"]["postgres"].get("healthcheck")
        assert hc is not None
        test_cmd = " ".join(hc["test"]) if isinstance(hc["test"], list) else hc["test"]
        assert "pg_isready" in test_cmd

    def test_redis_healthcheck(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        hc = data["services"]["redis"].get("healthcheck")
        assert hc is not None
        test_cmd = " ".join(hc["test"]) if isinstance(hc["test"], list) else hc["test"]
        assert "redis-cli" in test_cmd and "ping" in test_cmd

    def test_postgres_named_volume(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        volumes = data["services"]["postgres"].get("volumes", [])
        assert len(volumes) > 0
        top_volumes = data.get("volumes", {})
        assert len(top_volumes) > 0

    def test_backend_restart_policy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert data["services"]["backend"].get("restart") == "unless-stopped"

    def test_postgres_restart_policy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert data["services"]["postgres"].get("restart") == "unless-stopped"

    def test_redis_restart_policy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert data["services"]["redis"].get("restart") == "unless-stopped"

    def test_shared_network(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        # All services should be on the same network
        networks = data.get("networks", {})
        assert len(networks) > 0, "Should define at least one network"
        # Check all services reference a network
        for svc_name in ["backend", "postgres", "redis"]:
            svc = data["services"][svc_name]
            assert "networks" in svc, f"{svc_name} should have networks configured"

    def test_backend_exposes_port_7433(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        ports = data["services"]["backend"].get("ports", [])
        assert any("7433" in str(p) for p in ports)

    def test_postgres_image_version(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert data["services"]["postgres"]["image"] == "postgres:16"

    def test_redis_image_version(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert data["services"]["redis"]["image"] == "redis:7"


class TestEnvExampleProd:
    """Validate .env.example has production compose hints."""

    def test_env_example_has_postgres_hostname(self):
        content = ENV_EXAMPLE.read_text()
        assert "@postgres:" in content, (
            ".env.example should contain a CODEHIVE_DATABASE_URL with @postgres: hostname"
        )

    def test_env_example_has_redis_hostname(self):
        content = ENV_EXAMPLE.read_text()
        assert "redis://redis:" in content, (
            ".env.example should contain a CODEHIVE_REDIS_URL with redis: hostname"
        )

    def test_env_example_has_production_section(self):
        content = ENV_EXAMPLE.read_text()
        assert "prod" in content.lower(), ".env.example should mention production compose"

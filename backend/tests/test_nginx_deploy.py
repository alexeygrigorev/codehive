"""Tests for frontend Dockerfile, nginx.conf, .env.production, and compose frontend service (issue #57b)."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = REPO_ROOT / "web"
DOCKERFILE = WEB_DIR / "Dockerfile"
NGINX_CONF = WEB_DIR / "nginx.conf"
ENV_PRODUCTION = WEB_DIR / ".env.production"
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"


class TestFrontendDockerfile:
    """Validate web/Dockerfile structure."""

    def test_dockerfile_exists(self):
        assert DOCKERFILE.exists(), "web/Dockerfile must exist"

    def test_multistage_build_two_stages(self):
        content = DOCKERFILE.read_text()
        from_lines = [
            line.strip() for line in content.splitlines() if line.strip().startswith("FROM ")
        ]
        assert len(from_lines) >= 2, (
            f"Dockerfile must have at least 2 FROM statements (builder + runtime), found {len(from_lines)}"
        )

    def test_builder_stage_uses_node_20_alpine(self):
        content = DOCKERFILE.read_text()
        assert "node:20-alpine" in content, "Builder stage must use node:20-alpine"

    def test_runtime_stage_uses_nginx_alpine(self):
        content = DOCKERFILE.read_text()
        assert "nginx:alpine" in content, "Runtime stage must use nginx:alpine"

    def test_builder_runs_npm_ci(self):
        content = DOCKERFILE.read_text()
        assert "npm ci" in content, (
            "Builder stage must use npm ci (not npm install) for reproducible builds"
        )

    def test_builder_runs_npm_run_build(self):
        content = DOCKERFILE.read_text()
        assert "npm run build" in content, "Builder stage must run npm run build"

    def test_copies_from_builder(self):
        content = DOCKERFILE.read_text()
        assert "--from=builder" in content, (
            "Runtime stage must copy build output from builder stage"
        )

    def test_copies_dist_to_nginx_html(self):
        content = DOCKERFILE.read_text()
        assert "/usr/share/nginx/html" in content, (
            "Runtime stage must copy dist to /usr/share/nginx/html"
        )

    def test_copies_nginx_conf(self):
        content = DOCKERFILE.read_text()
        assert "nginx.conf" in content, "Dockerfile must copy nginx.conf"

    def test_exposes_port_80(self):
        content = DOCKERFILE.read_text()
        assert "EXPOSE 80" in content, "Dockerfile must expose port 80"


class TestNginxConfig:
    """Validate web/nginx.conf correctness."""

    def test_nginx_conf_exists(self):
        assert NGINX_CONF.exists(), "web/nginx.conf must exist"

    def test_spa_fallback(self):
        content = NGINX_CONF.read_text()
        assert "try_files $uri $uri/ /index.html" in content, (
            "nginx.conf must have SPA fallback: try_files $uri $uri/ /index.html"
        )

    def test_api_proxy_pass(self):
        content = NGINX_CONF.read_text()
        assert "proxy_pass http://backend:7433" in content, (
            "nginx.conf must proxy /api/ to http://backend:7433"
        )

    def test_api_location_block(self):
        content = NGINX_CONF.read_text()
        assert "location /api/" in content, "nginx.conf must have a location /api/ block"

    def test_ws_location_block(self):
        content = NGINX_CONF.read_text()
        assert "location /ws/" in content, "nginx.conf must have a location /ws/ block"

    def test_ws_proxy_pass(self):
        content = NGINX_CONF.read_text()
        # Find the ws location block and check proxy_pass within it
        assert "proxy_pass http://backend:7433/ws/" in content, (
            "WebSocket location must proxy to http://backend:7433/ws/"
        )

    def test_ws_http_version(self):
        content = NGINX_CONF.read_text()
        assert "proxy_http_version 1.1" in content, (
            "WebSocket proxy must use proxy_http_version 1.1"
        )

    def test_ws_upgrade_header(self):
        content = NGINX_CONF.read_text()
        assert "proxy_set_header Upgrade" in content, "WebSocket proxy must set Upgrade header"

    def test_ws_connection_upgrade(self):
        content = NGINX_CONF.read_text()
        assert 'proxy_set_header Connection "upgrade"' in content, (
            'WebSocket proxy must set Connection "upgrade" header'
        )

    def test_gzip_enabled(self):
        content = NGINX_CONF.read_text()
        assert "gzip on" in content, "nginx.conf must enable gzip compression"

    def test_gzip_types(self):
        content = NGINX_CONF.read_text()
        assert "gzip_types" in content, "nginx.conf must specify gzip_types"
        for mime_type in ["text/html", "application/javascript", "text/css", "application/json"]:
            assert mime_type in content, f"gzip_types must include {mime_type}"

    def test_security_header_x_frame_options(self):
        content = NGINX_CONF.read_text()
        assert "X-Frame-Options" in content, "nginx.conf must add X-Frame-Options header"
        assert "DENY" in content, "X-Frame-Options should be DENY"

    def test_security_header_x_content_type_options(self):
        content = NGINX_CONF.read_text()
        assert "X-Content-Type-Options" in content, (
            "nginx.conf must add X-Content-Type-Options header"
        )
        assert "nosniff" in content, "X-Content-Type-Options should be nosniff"

    def test_security_header_x_xss_protection(self):
        content = NGINX_CONF.read_text()
        assert "X-XSS-Protection" in content, "nginx.conf must add X-XSS-Protection header"


class TestEnvProduction:
    """Validate web/.env.production."""

    def test_env_production_exists(self):
        assert ENV_PRODUCTION.exists(), "web/.env.production must exist"

    def test_vite_api_url_empty(self):
        content = ENV_PRODUCTION.read_text()
        assert "VITE_API_URL=" in content, "VITE_API_URL must be defined"
        # Extract the value - it should be empty
        for line in content.splitlines():
            if line.startswith("VITE_API_URL="):
                value = line.split("=", 1)[1].strip()
                assert value == "", f"VITE_API_URL should be empty, got '{value}'"
                break


class TestComposeFrontendService:
    """Validate frontend service in docker-compose.prod.yml."""

    def test_frontend_service_defined(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert "frontend" in data["services"], (
            "docker-compose.prod.yml must define a frontend service"
        )

    def test_frontend_builds_from_web_dockerfile(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        frontend = data["services"]["frontend"]
        build = frontend.get("build", {})
        assert "context" in build, "frontend service must have a build context"
        assert "web" in build["context"], "frontend build context should reference ./web"

    def test_frontend_depends_on_backend(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        depends = data["services"]["frontend"].get("depends_on", {})
        assert "backend" in depends, "frontend must depend on backend"

    def test_frontend_depends_on_backend_healthy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        depends = data["services"]["frontend"].get("depends_on", {})
        backend_dep = depends.get("backend", {})
        assert backend_dep.get("condition") == "service_healthy", (
            "frontend should depend on backend with condition: service_healthy"
        )

    def test_frontend_maps_port_80(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        ports = data["services"]["frontend"].get("ports", [])
        assert any("80" in str(p) for p in ports), "frontend service must map port 80"

    def test_frontend_on_codehive_network(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        networks = data["services"]["frontend"].get("networks", [])
        assert "codehive" in networks, "frontend service must join the codehive network"

    def test_frontend_restart_policy(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        assert data["services"]["frontend"].get("restart") == "unless-stopped"

    def test_all_four_services_present(self):
        data = yaml.safe_load(COMPOSE_PROD.read_text())
        expected = {"backend", "postgres", "redis", "frontend"}
        actual = set(data["services"].keys())
        assert expected.issubset(actual), (
            f"docker-compose.prod.yml must have all 4 services. Missing: {expected - actual}"
        )

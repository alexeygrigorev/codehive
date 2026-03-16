"""Tests for CORS configuration (issue #68)."""

from fastapi.testclient import TestClient

from codehive.config import Settings


class TestCorsSettingsParsing:
    """Unit tests for cors_origins setting parsing."""

    def test_default_cors_origins(self):
        """Default cors_origins equals ['http://localhost:5173'] when env var is unset."""
        settings = Settings()
        assert settings.cors_origins == ["http://localhost:5173"]

    def test_cors_origins_comma_separated(self, monkeypatch):
        """Setting CODEHIVE_CORS_ORIGINS to a comma-separated string produces the correct list."""
        monkeypatch.setenv("CODEHIVE_CORS_ORIGINS", "http://example.com,http://other.com")
        settings = Settings()
        assert settings.cors_origins == ["http://example.com", "http://other.com"]

    def test_cors_origins_single_value(self, monkeypatch):
        """A single origin without commas works correctly."""
        monkeypatch.setenv("CODEHIVE_CORS_ORIGINS", "http://single.example.com")
        settings = Settings()
        assert settings.cors_origins == ["http://single.example.com"]

    def test_cors_origins_strips_whitespace(self, monkeypatch):
        """Whitespace around origins is stripped."""
        monkeypatch.setenv("CODEHIVE_CORS_ORIGINS", " http://a.com , http://b.com ")
        settings = Settings()
        assert settings.cors_origins == ["http://a.com", "http://b.com"]


class TestCorsMiddlewareBehavior:
    """Integration tests for CORS middleware on the FastAPI app."""

    def _make_client(self, monkeypatch=None, origins=None):
        """Create a TestClient, optionally overriding CORS origins."""
        if origins and monkeypatch:
            monkeypatch.setenv("CODEHIVE_CORS_ORIGINS", origins)
        from codehive.api.app import create_app

        return TestClient(create_app())

    def test_preflight_allowed_origin(self):
        """OPTIONS /api/health with allowed origin returns correct CORS headers."""
        from codehive.api.app import create_app

        client = TestClient(create_app())
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["access-control-allow-credentials"] == "true"
        allow_methods = response.headers["access-control-allow-methods"]
        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]:
            assert method in allow_methods

    def test_simple_request_allowed_origin(self):
        """GET /api/health with allowed origin returns Access-Control-Allow-Origin."""
        from codehive.api.app import create_app

        client = TestClient(create_app())
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    def test_disallowed_origin(self):
        """GET /api/health with disallowed origin does NOT return Access-Control-Allow-Origin."""
        from codehive.api.app import create_app

        client = TestClient(create_app())
        response = client.get(
            "/api/health",
            headers={"Origin": "http://evil.com"},
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers

    def test_custom_origin_via_env(self, monkeypatch):
        """Custom origins via env var are respected."""
        monkeypatch.setenv("CODEHIVE_CORS_ORIGINS", "http://custom.dev")
        from codehive.api.app import create_app

        client = TestClient(create_app())
        response = client.get(
            "/api/health",
            headers={"Origin": "http://custom.dev"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://custom.dev"

        # The default origin should no longer be allowed
        response2 = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert "access-control-allow-origin" not in response2.headers

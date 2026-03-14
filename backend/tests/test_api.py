"""Tests for codehive.api.app."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from codehive.__version__ import __version__
from codehive.api.app import create_app


class TestAppFactory:
    def test_create_app_returns_fastapi(self):
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_health_route(self):
        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/api/health" in routes


class TestHealthEndpoint:
    def setup_method(self):
        self.client = TestClient(create_app())

    def test_health_status_code(self):
        response = self.client.get("/api/health")
        assert response.status_code == 200

    def test_health_response_status(self):
        response = self.client.get("/api/health")
        assert response.json()["status"] == "ok"

    def test_health_response_version(self):
        response = self.client.get("/api/health")
        assert response.json()["version"] == __version__


class TestUnknownRoutes:
    def test_unknown_route_returns_404(self):
        client = TestClient(create_app())
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

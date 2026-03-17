"""Tests for unified error handling (issue #69)."""

import logging
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from codehive.__version__ import __version__
from codehive.api.app import create_app
from codehive.api.errors import ErrorResponse, register_error_handling


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with error handling and test routes."""
    app = FastAPI()
    register_error_handling(app)

    @app.get("/ok")
    async def ok_route():
        return {"msg": "ok"}

    @app.get("/boom")
    async def boom_route():
        raise RuntimeError("boom")

    @app.get("/http-error")
    async def http_error_route():
        raise HTTPException(status_code=403, detail="forbidden action")

    class ItemBody(BaseModel):
        count: int

    @app.post("/items")
    async def create_item(body: ItemBody):
        return {"count": body.count}

    return app


# ---------------------------------------------------------------------------
# Unit: ErrorResponse schema
# ---------------------------------------------------------------------------


class TestErrorResponseSchema:
    def test_serialization(self):
        rid = str(uuid.uuid4())
        resp = ErrorResponse(
            error="not_found",
            detail="Resource not found",
            request_id=rid,
            status_code=404,
        )
        data = resp.model_dump()
        assert data == {
            "error": "not_found",
            "detail": "Resource not found",
            "request_id": rid,
            "status_code": 404,
        }

    def test_request_id_accepts_uuid(self):
        rid = str(uuid.uuid4())
        resp = ErrorResponse(
            error="internal_error",
            detail="oops",
            request_id=rid,
            status_code=500,
        )
        # Should not raise; just verify it round-trips
        assert resp.request_id == rid

    def test_detail_accepts_list(self):
        resp = ErrorResponse(
            error="validation_error",
            detail=[{"loc": ["body", "count"], "msg": "not an int"}],
            request_id=str(uuid.uuid4()),
            status_code=422,
        )
        assert isinstance(resp.detail, list)


# ---------------------------------------------------------------------------
# Unit: Request ID middleware
# ---------------------------------------------------------------------------


class TestRequestIDMiddleware:
    def setup_method(self):
        self.client = TestClient(_make_test_app())

    def test_generates_request_id_when_absent(self):
        resp = self.client.get("/ok")
        rid = resp.headers.get("X-Request-ID")
        assert rid is not None
        # Should be a valid UUID
        uuid.UUID(rid)

    def test_echoes_client_request_id(self):
        resp = self.client.get("/ok", headers={"X-Request-ID": "abc-123"})
        assert resp.headers["X-Request-ID"] == "abc-123"

    def test_request_id_on_error_response(self):
        resp = self.client.get("/http-error", headers={"X-Request-ID": "err-id-1"})
        assert resp.headers["X-Request-ID"] == "err-id-1"
        assert resp.json()["request_id"] == "err-id-1"


# ---------------------------------------------------------------------------
# Integration: HTTPException formatting
# ---------------------------------------------------------------------------


class TestHTTPExceptionFormatting:
    def setup_method(self):
        self.client = TestClient(_make_test_app())

    def test_http_exception_returns_error_response(self):
        resp = self.client.get("/http-error")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"] == "forbidden"
        assert body["detail"] == "forbidden action"
        assert body["status_code"] == 403
        assert "request_id" in body

    def test_404_returns_error_response(self):
        resp = self.client.get("/no-such-route")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "not_found"
        assert body["status_code"] == 404
        assert "request_id" in body


# ---------------------------------------------------------------------------
# Integration: Validation error formatting
# ---------------------------------------------------------------------------


class TestValidationErrorFormatting:
    def setup_method(self):
        self.client = TestClient(_make_test_app())

    def test_invalid_body_returns_422(self):
        resp = self.client.post("/items", json={"count": "not-a-number"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "validation_error"
        assert body["status_code"] == 422
        assert isinstance(body["detail"], list)
        assert "request_id" in body


# ---------------------------------------------------------------------------
# Integration: Unhandled exception (500)
# ---------------------------------------------------------------------------


class TestUnhandledException:
    def setup_method(self):
        self.client = TestClient(_make_test_app(), raise_server_exceptions=False)

    def test_500_returns_safe_error_response(self):
        resp = self.client.get("/boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "internal_error"
        assert body["status_code"] == 500
        assert "request_id" in body
        # Must NOT contain the actual exception message or traceback
        assert "boom" not in body["detail"]
        assert "Traceback" not in body["detail"]

    def test_500_logs_traceback(self, caplog):
        with caplog.at_level(logging.ERROR, logger="codehive.api.errors"):
            self.client.get("/boom")
        assert "boom" in caplog.text
        assert "RuntimeError" in caplog.text


# ---------------------------------------------------------------------------
# Integration: Health endpoint unaffected (uses real app)
# ---------------------------------------------------------------------------


class TestHealthEndpointUnaffected:
    def setup_method(self):
        self.client = TestClient(create_app())

    def test_health_returns_200(self):
        resp = self.client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"] == __version__
        # Health response should NOT be wrapped in ErrorResponse
        assert "error" not in body

    def test_health_has_request_id_header(self):
        resp = self.client.get("/api/health")
        rid = resp.headers.get("X-Request-ID")
        assert rid is not None
        uuid.UUID(rid)


# ---------------------------------------------------------------------------
# Integration: Real app 401 (protected route without auth)
# ---------------------------------------------------------------------------


class TestRealAppAuthError:
    def setup_method(self, monkeypatch=None):
        import os

        os.environ["CODEHIVE_AUTH_ENABLED"] = "true"
        self.client = TestClient(create_app())

    def teardown_method(self):
        import os

        os.environ.pop("CODEHIVE_AUTH_ENABLED", None)

    def test_protected_route_without_auth_returns_error_response(self):
        resp = self.client.get("/api/projects")
        assert resp.status_code in (401, 403)
        body = resp.json()
        assert body["error"] in ("auth_error", "forbidden")
        assert "request_id" in body
        assert body["status_code"] == resp.status_code

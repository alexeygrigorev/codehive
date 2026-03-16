"""Tests for structured logging configuration (issue #74)."""

import json
import logging
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from codehive.api.errors import register_error_handling
from codehive.config import Settings
from codehive.logging import (
    HumanReadableFormatter,
    JSONFormatter,
    configure_logging,
    request_id_var,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    msg: str = "test message",
    level: int = logging.INFO,
    name: str = "codehive.test",
    exc_info: tuple | None = None,
    **extras: object,
) -> logging.LogRecord:
    """Create a LogRecord for testing formatters."""
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=exc_info,
    )
    for key, value in extras.items():
        setattr(record, key, value)
    return record


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with error handling and a logging route."""
    app = FastAPI()
    register_error_handling(app)

    test_logger = logging.getLogger("codehive.test_route")

    @app.get("/log-something")
    async def log_something():
        test_logger.info("handled request")
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("test explosion")

    return app


# ---------------------------------------------------------------------------
# Unit: JSON formatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    def test_basic_fields(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "codehive.test"
        assert data["message"] == "test message"
        assert "timestamp" in data

    def test_request_id_from_extra(self):
        formatter = JSONFormatter()
        record = _make_record(request_id="abc-123")
        output = formatter.format(record)
        data = json.loads(output)
        assert data["request_id"] == "abc-123"

    def test_exception_traceback(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("something broke")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
        record = _make_record(exc_info=exc_info)
        output = formatter.format(record)
        data = json.loads(output)
        assert "traceback" in data
        assert "ValueError" in data["traceback"]
        assert "something broke" in data["traceback"]

    def test_timestamp_iso8601(self):
        formatter = JSONFormatter()
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        # ISO 8601 pattern: YYYY-MM-DDTHH:MM:SS
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", data["timestamp"])

    def test_single_line_output(self):
        formatter = JSONFormatter()
        record = _make_record(msg="line one\nline two")
        output = formatter.format(record)
        # json.dumps produces a single line by default
        assert "\n" not in output
        json.loads(output)  # still valid JSON


# ---------------------------------------------------------------------------
# Unit: Human-readable formatter
# ---------------------------------------------------------------------------


class TestHumanReadableFormatter:
    def test_not_json(self):
        formatter = HumanReadableFormatter()
        record = _make_record()
        output = formatter.format(record)
        # Should NOT be valid JSON
        try:
            json.loads(output)
            assert False, "Output should not be valid JSON"
        except json.JSONDecodeError:
            pass
        assert "INFO" in output
        assert "test message" in output

    def test_includes_request_id(self):
        formatter = HumanReadableFormatter()
        record = _make_record(request_id="rid-456")
        output = formatter.format(record)
        assert "rid-456" in output


# ---------------------------------------------------------------------------
# Unit: Request ID ContextVar
# ---------------------------------------------------------------------------


class TestRequestIDContextVar:
    def test_contextvar_in_json_output(self):
        formatter = JSONFormatter()
        token = request_id_var.set("ctx-var-id")
        try:
            record = _make_record()
            output = formatter.format(record)
            data = json.loads(output)
            assert data["request_id"] == "ctx-var-id"
        finally:
            request_id_var.reset(token)

    def test_no_contextvar_no_crash(self):
        formatter = JSONFormatter()
        # Ensure ContextVar is not set (default is None)
        record = _make_record()
        output = formatter.format(record)
        data = json.loads(output)
        assert "request_id" not in data


# ---------------------------------------------------------------------------
# Unit: configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def teardown_method(self):
        """Reset root logger after each test."""
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.WARNING)

    def test_sets_debug_level(self):
        settings = Settings(log_level="DEBUG", log_json=True, log_file="")
        configure_logging(settings)
        assert logging.getLogger().level == logging.DEBUG

    def test_sets_error_level(self):
        settings = Settings(log_level="ERROR", log_json=True, log_file="")
        configure_logging(settings)
        assert logging.getLogger().level == logging.ERROR

    def test_log_file(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        settings = Settings(log_level="INFO", log_json=True, log_file=log_file)
        configure_logging(settings)

        test_logger = logging.getLogger("codehive.file_test")
        test_logger.info("file log message")

        # Flush handlers
        for handler in logging.getLogger().handlers:
            handler.flush()

        content = open(log_file).read()
        assert "file log message" in content
        data = json.loads(content.strip())
        assert data["message"] == "file log message"

    def test_quiets_noisy_loggers(self):
        settings = Settings(log_level="DEBUG", log_json=True, log_file="")
        configure_logging(settings)
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING


# ---------------------------------------------------------------------------
# Integration: Request ID in logs during HTTP request
# ---------------------------------------------------------------------------


class TestRequestIDInHTTPLogs:
    def test_request_id_in_log_output(self, capfd):
        settings = Settings(log_level="DEBUG", log_json=True, log_file="")
        configure_logging(settings)

        app = _make_test_app()
        client = TestClient(app)

        resp = client.get("/log-something")
        assert resp.status_code == 200
        request_id = resp.headers["X-Request-ID"]

        # Capture stderr (where logs go)
        captured = capfd.readouterr()
        # Find the line with our log message
        found = False
        for line in captured.err.strip().split("\n"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("message") == "handled request":
                assert data["request_id"] == request_id
                found = True
                break
        assert found, f"Expected log line not found. stderr was:\n{captured.err}"

    def test_500_traceback_includes_request_id(self, capfd):
        settings = Settings(log_level="DEBUG", log_json=True, log_file="")
        configure_logging(settings)

        app = _make_test_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/boom")
        assert resp.status_code == 500
        request_id = resp.headers["X-Request-ID"]

        captured = capfd.readouterr()
        found = False
        for line in captured.err.strip().split("\n"):
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "Unhandled exception" in data.get("message", ""):
                assert data.get("request_id") == request_id
                assert "RuntimeError" in data.get("message", "")
                found = True
                break
        assert found, f"Expected traceback log not found. stderr was:\n{captured.err}"


# ---------------------------------------------------------------------------
# Integration: Settings from environment
# ---------------------------------------------------------------------------


class TestSettingsFromEnv:
    def test_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_LOG_LEVEL", "WARNING")
        settings = Settings()
        assert settings.log_level == "WARNING"

    def test_log_json_from_env(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_LOG_JSON", "false")
        settings = Settings()
        assert settings.log_json is False

    def test_log_file_from_env(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_LOG_FILE", "/tmp/codehive-test.log")
        settings = Settings()
        assert settings.log_file == "/tmp/codehive-test.log"

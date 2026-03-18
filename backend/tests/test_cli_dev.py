"""Tests for the `codehive dev` CLI command."""

import os
from io import StringIO

import pytest

from codehive.cli import main


def _run_cli(args: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, int]:
    """Run the CLI with given args, capture stdout, return (output, exit_code)."""
    monkeypatch.setattr("sys.argv", ["codehive"] + args)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    err = StringIO()
    monkeypatch.setattr("sys.stderr", err)
    try:
        main()
        return out.getvalue(), 0
    except SystemExit as e:
        return out.getvalue() + err.getvalue(), e.code or 0


class TestDevCommand:
    """Tests for codehive dev."""

    def test_dev_no_backend_no_frontend_exits_cleanly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both --no-backend and --no-frontend are given, nothing starts."""
        output, code = _run_cli(["dev", "--no-backend", "--no-frontend"], monkeypatch)
        assert "Nothing to start" in output
        assert code == 0

    def test_dev_starts_backend_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify backend subprocess is launched with correct uvicorn args."""
        launched_cmds: list[list[str]] = []

        class FakeProc:
            stdout = iter([])  # empty iterator, no output
            pid = 12345

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float = 5) -> None:
                pass

            def kill(self) -> None:
                pass

            def poll(self) -> int:
                return 0  # immediately "exit"

        def fake_popen(cmd: list[str], **kwargs: object) -> FakeProc:
            launched_cmds.append(cmd)
            return FakeProc()

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        # Skip signal registration in test
        monkeypatch.setattr("signal.signal", lambda *a: None)

        output, code = _run_cli(["dev", "--no-frontend"], monkeypatch)

        # Should have launched exactly one subprocess (backend)
        assert len(launched_cmds) == 1
        cmd = launched_cmds[0]
        assert "uvicorn" in " ".join(cmd)
        assert "codehive.api.app:create_app" in cmd
        assert "--reload" in cmd
        assert "--factory" in cmd

    def test_dev_starts_frontend_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify frontend subprocess is launched in the web directory."""
        launched: list[dict[str, object]] = []

        class FakeProc:
            stdout = iter([])
            pid = 12345

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float = 5) -> None:
                pass

            def kill(self) -> None:
                pass

            def poll(self) -> int:
                return 0

        def fake_popen(cmd: list[str], **kwargs: object) -> FakeProc:
            launched.append({"cmd": cmd, "kwargs": kwargs})
            return FakeProc()

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("signal.signal", lambda *a: None)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        output, code = _run_cli(["dev", "--no-backend"], monkeypatch)

        # Should have launched exactly one subprocess (frontend)
        assert len(launched) == 1
        call = launched[0]
        cmd = call["cmd"]
        assert "vite" in " ".join(str(c) for c in cmd)
        # cwd should point to a web/ directory
        cwd = call["kwargs"].get("cwd", "")
        assert str(cwd).endswith("web")

    def test_dev_starts_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify both backend and frontend are launched."""
        launched_cmds: list[list[str]] = []

        class FakeProc:
            stdout = iter([])
            pid = 12345

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float = 5) -> None:
                pass

            def kill(self) -> None:
                pass

            def poll(self) -> int:
                return 0

        def fake_popen(cmd: list[str], **kwargs: object) -> FakeProc:
            launched_cmds.append(cmd)
            return FakeProc()

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("signal.signal", lambda *a: None)
        monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

        output, code = _run_cli(["dev"], monkeypatch)

        # Should have launched two subprocesses
        assert len(launched_cmds) == 2
        joined = [" ".join(c) for c in launched_cmds]
        assert any("uvicorn" in j for j in joined)
        assert any("vite" in j for j in joined)

    def test_dev_custom_host_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify --host and --port are forwarded to backend."""
        launched_cmds: list[list[str]] = []

        class FakeProc:
            stdout = iter([])
            pid = 12345

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float = 5) -> None:
                pass

            def kill(self) -> None:
                pass

            def poll(self) -> int:
                return 0

        def fake_popen(cmd: list[str], **kwargs: object) -> FakeProc:
            launched_cmds.append(cmd)
            return FakeProc()

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("signal.signal", lambda *a: None)

        output, code = _run_cli(
            ["dev", "--no-frontend", "--host", "0.0.0.0", "--port", "9999"],
            monkeypatch,
        )

        assert len(launched_cmds) == 1
        cmd = launched_cmds[0]
        assert "--host" in cmd
        host_idx = cmd.index("--host")
        assert cmd[host_idx + 1] == "0.0.0.0"
        assert "--port" in cmd
        port_idx = cmd.index("--port")
        assert cmd[port_idx + 1] == "9999"

    def test_dev_missing_web_dir_warns(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """If web/ dir does not exist, a warning is shown and only backend starts."""
        launched_cmds: list[list[str]] = []

        class FakeProc:
            stdout = iter([])
            pid = 12345

            def terminate(self) -> None:
                pass

            def wait(self, timeout: float = 5) -> None:
                pass

            def kill(self) -> None:
                pass

            def poll(self) -> int:
                return 0

        def fake_popen(cmd: list[str], **kwargs: object) -> FakeProc:
            launched_cmds.append(cmd)
            return FakeProc()

        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("signal.signal", lambda *a: None)

        # Point to a non-existent web dir by patching os.path in _dev
        original_isdir = os.path.isdir

        def fake_isdir(path: str) -> bool:
            if path.endswith("web"):
                return False
            return original_isdir(path)

        monkeypatch.setattr("os.path.isdir", fake_isdir)

        output, code = _run_cli(["dev"], monkeypatch)

        # Only backend should have been started
        assert len(launched_cmds) == 1
        assert "uvicorn" in " ".join(launched_cmds[0])

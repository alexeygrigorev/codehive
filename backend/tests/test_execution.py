"""Tests for codehive.execution: shell, file_ops, git_ops, diff."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codehive.execution import (
    DiffService,
    FileOps,
    GitOps,
    SandboxViolationError,
    ShellResult,
    ShellRunner,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Unit: Shell Runner
# ---------------------------------------------------------------------------


class TestShellRunner:
    @pytest.mark.asyncio
    async def test_echo_hello(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("echo hello", working_dir=tmp_path)
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_command_failure(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("exit 1", working_dir=tmp_path)
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("sleep 30", working_dir=tmp_path, timeout_seconds=0.5)
        assert result.timed_out is True

    @pytest.mark.asyncio
    async def test_working_directory(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("pwd", working_dir=tmp_path)
        assert result.exit_code == 0
        assert str(tmp_path.resolve()) in result.stdout.strip()

    @pytest.mark.asyncio
    async def test_streaming_output(self, tmp_path: Path):
        runner = ShellRunner()
        lines: list[str] = []
        async for line in runner.run_streaming(
            'echo "line1" && echo "line2" && echo "line3"',
            working_dir=tmp_path,
        ):
            lines.append(line)
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[1] == "line2"
        assert lines[2] == "line3"

    @pytest.mark.asyncio
    async def test_nonexistent_working_dir(self, tmp_path: Path):
        runner = ShellRunner()
        with pytest.raises(FileNotFoundError):
            await runner.run("echo hello", working_dir=tmp_path / "nonexistent")

    @pytest.mark.asyncio
    async def test_nonexistent_working_dir_streaming(self, tmp_path: Path):
        runner = ShellRunner()
        with pytest.raises(FileNotFoundError):
            async for _ in runner.run_streaming("echo hello", working_dir=tmp_path / "nonexistent"):
                pass

    @pytest.mark.asyncio
    async def test_command_as_list(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run(["echo", "hello"], working_dir=tmp_path)
        assert result.exit_code == 0
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_stderr_captured(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("echo error >&2", working_dir=tmp_path)
        assert "error" in result.stderr

    @pytest.mark.asyncio
    async def test_result_is_shell_result(self, tmp_path: Path):
        runner = ShellRunner()
        result = await runner.run("echo test", working_dir=tmp_path)
        assert isinstance(result, ShellResult)


# ---------------------------------------------------------------------------
# Unit: File Operations -- sandbox enforcement
# ---------------------------------------------------------------------------


class TestFileOps:
    @pytest.mark.asyncio
    async def test_read_file(self, tmp_path: Path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file.txt").write_text("hello world")
        ops = FileOps(tmp_path)
        content = await ops.read_file("subdir/file.txt")
        assert content == "hello world"

    @pytest.mark.asyncio
    async def test_read_file_escape_raises(self, tmp_path: Path):
        ops = FileOps(tmp_path)
        with pytest.raises(SandboxViolationError):
            await ops.read_file("../../etc/passwd")

    @pytest.mark.asyncio
    async def test_read_symlink_outside_raises(self, tmp_path: Path):
        # Create a file outside the sandbox
        outside = tmp_path.parent / "outside_file.txt"
        outside.write_text("secret")
        # Create a symlink inside the sandbox pointing outside
        link = tmp_path / "link.txt"
        link.symlink_to(outside)
        ops = FileOps(tmp_path)
        with pytest.raises(SandboxViolationError):
            await ops.read_file("link.txt")
        # Cleanup
        outside.unlink()

    @pytest.mark.asyncio
    async def test_write_file_creates_parents(self, tmp_path: Path):
        ops = FileOps(tmp_path)
        await ops.write_file("new_dir/new_file.txt", "content")
        assert (tmp_path / "new_dir" / "new_file.txt").read_text() == "content"

    @pytest.mark.asyncio
    async def test_write_file_escape_raises(self, tmp_path: Path):
        ops = FileOps(tmp_path)
        with pytest.raises(SandboxViolationError):
            await ops.write_file("../outside.txt", "content")

    @pytest.mark.asyncio
    async def test_edit_file_replaces_text(self, tmp_path: Path):
        (tmp_path / "file.txt").write_text("hello old world")
        ops = FileOps(tmp_path)
        result = await ops.edit_file("file.txt", "old", "new")
        assert result == "hello new world"
        assert (tmp_path / "file.txt").read_text() == "hello new world"

    @pytest.mark.asyncio
    async def test_edit_file_text_not_found(self, tmp_path: Path):
        (tmp_path / "file.txt").write_text("hello world")
        ops = FileOps(tmp_path)
        with pytest.raises(ValueError, match="Text not found"):
            await ops.edit_file("file.txt", "nonexistent", "new")

    @pytest.mark.asyncio
    async def test_list_files_glob(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")
        ops = FileOps(tmp_path)
        py_files = await ops.list_files(".", "*.py")
        assert len(py_files) == 2
        assert all(f.endswith(".py") for f in py_files)

    @pytest.mark.asyncio
    async def test_list_files_escape_raises(self, tmp_path: Path):
        ops = FileOps(tmp_path)
        with pytest.raises(SandboxViolationError):
            await ops.list_files("../../", "*")

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path: Path):
        ops = FileOps(tmp_path)
        with pytest.raises(FileNotFoundError):
            await ops.read_file("nope.txt")


# ---------------------------------------------------------------------------
# Unit: Git Operations
# ---------------------------------------------------------------------------


class TestGitOps:
    @pytest.mark.asyncio
    async def test_status_modified(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# modified\n")
        git = GitOps(tmp_path)
        statuses = await git.status()
        paths = [s.path for s in statuses]
        assert "README.md" in paths

    @pytest.mark.asyncio
    async def test_status_untracked(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "new_file.txt").write_text("new")
        git = GitOps(tmp_path)
        statuses = await git.status()
        untracked = [s for s in statuses if s.status == "untracked"]
        assert any("new_file.txt" in s.path for s in untracked)

    @pytest.mark.asyncio
    async def test_diff_unstaged(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# changed\n")
        git = GitOps(tmp_path)
        diff_text = await git.diff()
        assert "changed" in diff_text
        assert "---" in diff_text

    @pytest.mark.asyncio
    async def test_diff_against_head(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# v2\n")
        # Stage the change to test diff against HEAD
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
        git = GitOps(tmp_path)
        diff_text = await git.diff("HEAD")
        assert "v2" in diff_text

    @pytest.mark.asyncio
    async def test_commit_returns_sha(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "new.txt").write_text("data")
        git = GitOps(tmp_path)
        sha = await git.commit("test commit", None)
        assert len(sha) == 40
        assert all(c in "0123456789abcdef" for c in sha)

    @pytest.mark.asyncio
    async def test_log_returns_commits(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        git = GitOps(tmp_path)
        commits = await git.log(3)
        assert len(commits) >= 1
        assert commits[0].sha
        assert commits[0].message == "init"
        assert commits[0].author == "Test"
        assert commits[0].timestamp

    @pytest.mark.asyncio
    async def test_branch_creates_branch(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        git = GitOps(tmp_path)
        await git.branch("feature-x")
        result = subprocess.run(["git", "branch"], cwd=tmp_path, capture_output=True, text=True)
        assert "feature-x" in result.stdout

    @pytest.mark.asyncio
    async def test_checkout_switches_branch(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        git = GitOps(tmp_path)
        await git.branch("feature-x")
        await git.checkout("feature-x")
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "feature-x"


# ---------------------------------------------------------------------------
# Unit: Diff Service
# ---------------------------------------------------------------------------


class TestDiffService:
    def test_compute_diff_different(self):
        svc = DiffService()
        diff_text = svc.compute_diff("file.py", "old line\n", "new line\n")
        assert "-old line" in diff_text
        assert "+new line" in diff_text

    def test_compute_diff_identical(self):
        svc = DiffService()
        diff_text = svc.compute_diff("file.py", "same\n", "same\n")
        assert diff_text == ""

    def test_track_and_get_changes(self):
        svc = DiffService()
        svc.track_change("sess-1", "a.py", "diff-a")
        changes = svc.get_session_changes("sess-1")
        assert changes == {"a.py": "diff-a"}

    def test_track_multiple_changes(self):
        svc = DiffService()
        svc.track_change("sess-1", "a.py", "diff-a")
        svc.track_change("sess-1", "b.py", "diff-b")
        changes = svc.get_session_changes("sess-1")
        assert len(changes) == 2
        assert changes["a.py"] == "diff-a"
        assert changes["b.py"] == "diff-b"

    def test_sessions_isolated(self):
        svc = DiffService()
        svc.track_change("sess-1", "a.py", "diff-a")
        svc.track_change("sess-2", "b.py", "diff-b")
        assert svc.get_session_changes("sess-1") == {"a.py": "diff-a"}
        assert svc.get_session_changes("sess-2") == {"b.py": "diff-b"}

    def test_get_empty_session(self):
        svc = DiffService()
        assert svc.get_session_changes("nonexistent") == {}

    @pytest.mark.asyncio
    async def test_compute_repo_diff(self, tmp_path: Path):
        _init_git_repo(tmp_path)
        (tmp_path / "README.md").write_text("# changed\n")
        svc = DiffService()
        diff_text = await svc.compute_repo_diff(tmp_path)
        assert "changed" in diff_text


# ---------------------------------------------------------------------------
# Integration: Cross-module
# ---------------------------------------------------------------------------


class TestIntegration:
    @pytest.mark.asyncio
    async def test_shell_runner_git_command(self, tmp_path: Path):
        """Use ShellRunner to run a git command, verify consistency with GitOps."""
        _init_git_repo(tmp_path)
        runner = ShellRunner()
        result = await runner.run("git log --oneline", working_dir=tmp_path)
        assert result.exit_code == 0
        assert "init" in result.stdout

    @pytest.mark.asyncio
    async def test_file_ops_then_git_status(self, tmp_path: Path):
        """Write a file via FileOps, then verify it shows in GitOps status."""
        _init_git_repo(tmp_path)
        ops = FileOps(tmp_path)
        await ops.write_file("new_file.txt", "hello")
        git = GitOps(tmp_path)
        statuses = await git.status()
        paths = [s.path for s in statuses]
        assert "new_file.txt" in paths

    @pytest.mark.asyncio
    async def test_file_ops_edit_then_diff(self, tmp_path: Path):
        """Edit a file via FileOps, then compute diff via DiffService."""
        (tmp_path / "file.txt").write_text("before\n")
        ops = FileOps(tmp_path)
        original = await ops.read_file("file.txt")
        await ops.edit_file("file.txt", "before", "after")
        current = await ops.read_file("file.txt")
        svc = DiffService()
        diff_text = svc.compute_diff("file.txt", original, current)
        assert "-before" in diff_text
        assert "+after" in diff_text

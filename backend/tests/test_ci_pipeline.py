"""Tests for .github/workflows/test.yml CI pipeline (issue #80)."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "test.yml"


class TestWorkflowSyntax:
    """Validate workflow YAML structure."""

    def test_workflow_file_exists(self):
        assert WORKFLOW_FILE.exists(), ".github/workflows/test.yml must exist"

    def test_workflow_parses_valid_yaml(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        assert isinstance(data, dict)

    def test_trigger_events_include_push_and_pull_request(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        # PyYAML parses the 'on' key as boolean True, so check both
        triggers = data.get("on") or data.get(True)
        assert triggers is not None, "Workflow must have 'on' trigger configuration"
        if isinstance(triggers, list):
            assert "push" in triggers
            assert "pull_request" in triggers
        elif isinstance(triggers, dict):
            assert "push" in triggers
            assert "pull_request" in triggers
        else:
            raise AssertionError(f"Unexpected trigger format: {triggers}")

    def test_exactly_three_jobs(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        expected_jobs = {"backend", "frontend", "mobile"}
        actual_jobs = set(data["jobs"].keys())
        assert expected_jobs == actual_jobs, f"Expected jobs {expected_jobs}, got {actual_jobs}"

    def test_all_jobs_run_in_parallel(self):
        """Verify no job has a 'needs' key, meaning all run in parallel."""
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        for job_name, job_config in data["jobs"].items():
            assert "needs" not in job_config, (
                f"Job '{job_name}' has 'needs' dependency, but all jobs should run in parallel"
            )


class TestMobileJob:
    """Validate mobile job structure."""

    def _get_mobile_job(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        return data["jobs"]["mobile"]

    def test_runs_on_ubuntu_latest(self):
        job = self._get_mobile_job()
        assert job["runs-on"] == "ubuntu-latest"

    def test_working_directory_is_mobile(self):
        job = self._get_mobile_job()
        wd = job.get("defaults", {}).get("run", {}).get("working-directory")
        assert wd == "mobile", f"Expected working-directory 'mobile', got '{wd}'"

    def test_uses_setup_node_v4(self):
        job = self._get_mobile_job()
        steps = job["steps"]
        setup_node_steps = [
            s for s in steps if s.get("uses", "").startswith("actions/setup-node@v4")
        ]
        assert len(setup_node_steps) >= 1, "Mobile job must use actions/setup-node@v4"

    def test_node_version_20(self):
        job = self._get_mobile_job()
        steps = job["steps"]
        for step in steps:
            if step.get("uses", "").startswith("actions/setup-node"):
                assert step["with"]["node-version"] == "20", "Mobile job must use node-version 20"
                break
        else:
            raise AssertionError("No setup-node step found")

    def test_runs_npm_ci(self):
        job = self._get_mobile_job()
        run_commands = [s.get("run", "") for s in job["steps"]]
        assert any("npm ci" in cmd for cmd in run_commands), "Mobile job must run 'npm ci'"

    def test_runs_jest_ci(self):
        job = self._get_mobile_job()
        run_commands = [s.get("run", "") for s in job["steps"]]
        assert any("npx jest --ci" in cmd for cmd in run_commands), (
            "Mobile job must run 'npx jest --ci'"
        )

    def test_uses_checkout(self):
        job = self._get_mobile_job()
        checkout_steps = [
            s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@v4")
        ]
        assert len(checkout_steps) >= 1, "Mobile job must use actions/checkout@v4"


class TestExistingJobsUnchanged:
    """Verify existing backend and frontend jobs are still present and unchanged."""

    def test_backend_job_exists(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        assert "backend" in data["jobs"]

    def test_backend_has_python_matrix(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        backend = data["jobs"]["backend"]
        matrix = backend.get("strategy", {}).get("matrix", {})
        assert "python-version" in matrix

    def test_frontend_job_exists(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        assert "frontend" in data["jobs"]

    def test_frontend_working_directory_is_web(self):
        data = yaml.safe_load(WORKFLOW_FILE.read_text())
        frontend = data["jobs"]["frontend"]
        wd = frontend.get("defaults", {}).get("run", {}).get("working-directory")
        assert wd == "web"

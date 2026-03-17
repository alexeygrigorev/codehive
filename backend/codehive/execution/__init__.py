"""Execution layer: shell runner, file ops, git ops, and diff computation."""

from codehive.execution.diff import DiffService
from codehive.execution.file_ops import FileOps, SandboxViolationError
from codehive.execution.git_ops import CommitInfo, FileStatus, GitOps, GitOpsError
from codehive.execution.policy import (
    CommandPolicy,
    CommandPolicyViolation,
    PolicyResult,
    PolicyRule,
    PolicyVerdict,
)
from codehive.execution.sandbox import Sandbox
from codehive.execution.shell import ShellResult, ShellRunner
from codehive.execution.ssh import (
    SSHConnectionError,
    SSHConnectionManager,
    SSHTargetConfig,
    SSHTargetNotConnectedError,
)

__all__ = [
    "CommandPolicy",
    "CommandPolicyViolation",
    "CommitInfo",
    "DiffService",
    "FileOps",
    "FileStatus",
    "GitOps",
    "GitOpsError",
    "PolicyResult",
    "PolicyRule",
    "PolicyVerdict",
    "Sandbox",
    "SandboxViolationError",
    "SSHConnectionError",
    "SSHConnectionManager",
    "SSHTargetConfig",
    "SSHTargetNotConnectedError",
    "ShellResult",
    "ShellRunner",
]

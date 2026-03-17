"""Command policy engine: allowlist/denylist rules for shell command enforcement."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class PolicyVerdict(Enum):
    """Result of evaluating a command against the policy."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PolicyResult:
    """Result of checking a command against the policy.

    Attributes:
        verdict: The policy verdict (ALLOW, DENY, or ASK).
        reason: Human-readable explanation of why the command was flagged.
        matched_rule: The rule that matched, or None if default-deny.
    """

    verdict: PolicyVerdict
    reason: str
    matched_rule: PolicyRule | None = None


class CommandPolicyViolation(Exception):
    """Raised when a command is denied or needs approval per policy.

    Attributes:
        command: The command that was checked.
        verdict: The policy verdict (DENY or ASK).
        reason: Human-readable explanation of why the command was flagged.
        needs_approval: True when the verdict is ASK (caller should prompt user).
    """

    def __init__(self, command: str, verdict: PolicyVerdict, reason: str = "") -> None:
        self.command = command
        self.verdict = verdict
        self.reason = reason
        self.needs_approval = verdict == PolicyVerdict.ASK
        action = "needs approval" if self.needs_approval else "denied by policy"
        msg = f"Command {action}: {command}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)


@dataclass
class PolicyRule:
    """A single policy rule matching commands by regex pattern.

    Attributes:
        pattern: Regex pattern to match against the command string.
        category: Classification of the command (read_only, write, destructive, network).
        verdict: What to do when the pattern matches.
        reason: Human-readable explanation of why the command is flagged.
    """

    pattern: str
    category: str
    verdict: PolicyVerdict
    reason: str = ""

    def __post_init__(self) -> None:
        self._compiled = re.compile(self.pattern)

    def matches(self, command: str) -> bool:
        """Check if the command matches this rule's pattern."""
        return bool(self._compiled.search(command))


@dataclass
class CommandPolicy:
    """Evaluates shell commands against an ordered list of rules.

    Rules are checked in order; the first matching rule determines the verdict.
    If no rule matches, the default verdict is DENY (default-deny policy).
    """

    rules: list[PolicyRule] = field(default_factory=list)

    def check(self, command: str) -> PolicyResult:
        """Evaluate a command against the rules.

        Args:
            command: The shell command string to check.

        Returns:
            A PolicyResult with the verdict, reason, and matched rule.
        """
        for rule in self.rules:
            if rule.matches(command):
                return PolicyResult(
                    verdict=rule.verdict,
                    reason=rule.reason,
                    matched_rule=rule,
                )
        return PolicyResult(
            verdict=PolicyVerdict.DENY,
            reason="No matching rule (default deny)",
            matched_rule=None,
        )

    @classmethod
    def permissive(cls) -> CommandPolicy:
        """Create a permissive policy that allows all commands.

        Used when guardrails are disabled.
        """
        return cls(
            rules=[
                PolicyRule(
                    pattern=r".*",
                    category="any",
                    verdict=PolicyVerdict.ALLOW,
                    reason="Guardrails disabled",
                ),
            ]
        )

    @classmethod
    def default(cls) -> CommandPolicy:
        """Create a default policy preset with comprehensive rules.

        Rules are ordered: DENY first, then ASK, then ALLOW.
        The first matching rule wins. Unknown commands are denied by default.
        """
        rules = [
            # =================================================================
            # DENY -- almost never valid for an agent
            # =================================================================
            PolicyRule(
                pattern=r"curl\s.*\|\s*(sh|bash)",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="Pipe-to-shell executes untrusted remote code",
            ),
            PolicyRule(
                pattern=r"wget\s.*\|\s*(sh|bash)",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="Pipe-to-shell executes untrusted remote code",
            ),
            PolicyRule(
                pattern=r"\bsudo\b",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="Elevated privileges not allowed",
            ),
            PolicyRule(
                pattern=r"chmod\s+777",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="World-writable permissions are unsafe",
            ),
            PolicyRule(
                pattern=r"\b(shutdown|reboot|halt)\b",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="System power commands not allowed",
            ),
            PolicyRule(
                pattern=r"\b(mkfs|fdisk)\b",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="Disk partitioning/formatting not allowed",
            ),
            PolicyRule(
                pattern=r"\bdd\b",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="Raw disk operations not allowed",
            ),
            PolicyRule(
                pattern=r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?|"
                r"-[a-zA-Z]*f[a-zA-Z]*\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?)/(\s|$|\*)",
                category="destructive",
                verdict=PolicyVerdict.DENY,
                reason="Removing root filesystem is catastrophic",
            ),
            # =================================================================
            # ASK -- sometimes valid but dangerous
            # =================================================================
            # Git destructive operations
            PolicyRule(
                pattern=r"\bgit\s+push\b",
                category="network",
                verdict=PolicyVerdict.ASK,
                reason="Pushes commits to remote repository",
            ),
            PolicyRule(
                pattern=r"\bgit\s+reset\s+--hard\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Discards uncommitted changes permanently",
            ),
            PolicyRule(
                pattern=r"\bgit\s+clean\s+-[a-zA-Z]*f",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Removes untracked files permanently",
            ),
            PolicyRule(
                pattern=r"\bgit\s+checkout\s+--\s+\.",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Discards all unstaged changes",
            ),
            PolicyRule(
                pattern=r"\bgit\s+restore\s+\.",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Discards all unstaged changes",
            ),
            PolicyRule(
                pattern=r"\bgit\s+branch\s+-D\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Force-deletes a branch without merge check",
            ),
            PolicyRule(
                pattern=r"\bgit\s+stash\s+(drop|clear)\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Permanently removes stashed changes",
            ),
            # rm -rf / rm -r (non-root, already caught root above)
            PolicyRule(
                pattern=r"\brm\s+-[a-zA-Z]*r",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Recursive file removal",
            ),
            # Process management
            PolicyRule(
                pattern=r"\b(kill|killall|pkill)\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Terminates running processes",
            ),
            # Docker destructive operations
            PolicyRule(
                pattern=r"\bdocker\s+(rm|rmi)\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Removes Docker containers or images",
            ),
            PolicyRule(
                pattern=r"\bdocker\s+system\s+prune\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Removes unused Docker resources",
            ),
            PolicyRule(
                pattern=r"\bdocker\s+compose\s+down\s+-[a-zA-Z]*v",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Stops containers and removes volumes",
            ),
            # SQL destructive operations
            PolicyRule(
                pattern=r"\b(DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE)\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Destructive SQL operation",
            ),
            # Firewall / network
            PolicyRule(
                pattern=r"\b(iptables|ufw)\b",
                category="network",
                verdict=PolicyVerdict.ASK,
                reason="Modifies firewall rules",
            ),
            # System services
            PolicyRule(
                pattern=r"\bsystemctl\s+(stop|disable)\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Stops or disables system services",
            ),
            # Permission changes (general, after chmod 777 DENY above)
            PolicyRule(
                pattern=r"\b(chmod|chown)\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
                reason="Changes file permissions or ownership",
            ),
            # =================================================================
            # ALLOW -- safe read-only and build commands
            # =================================================================
            # Read-only filesystem commands
            PolicyRule(
                pattern=r"^ls\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="List directory contents",
            ),
            PolicyRule(
                pattern=r"^cat\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Display file contents",
            ),
            PolicyRule(
                pattern=r"^grep\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Search file contents",
            ),
            PolicyRule(
                pattern=r"^find\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Find files",
            ),
            PolicyRule(
                pattern=r"^echo\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Print text",
            ),
            PolicyRule(
                pattern=r"^pwd$",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Print working directory",
            ),
            PolicyRule(
                pattern=r"^(head|tail|wc|sort|uniq|diff|tree|file|which|type)\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Read-only text processing or file info",
            ),
            # Git read-only commands
            PolicyRule(
                pattern=r"^git\s+(status|log|diff|show|branch)\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="Git read-only operation",
            ),
            # Git safe write commands
            PolicyRule(
                pattern=r"^git\s+(add|commit)\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Git local write operation",
            ),
            PolicyRule(
                pattern=r"^git\s+stash\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Git stash operation",
            ),
            # Build/test commands
            PolicyRule(
                pattern=r"^python\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Run Python",
            ),
            PolicyRule(
                pattern=r"^pytest\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Run pytest",
            ),
            PolicyRule(
                pattern=r"^uv\s+run\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Run command via uv",
            ),
            PolicyRule(
                pattern=r"^npm\s+(test|list|info)\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="NPM command",
            ),
            PolicyRule(
                pattern=r"^pip\s+(list|show)\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
                reason="List or show pip packages",
            ),
            # Linters and formatters
            PolicyRule(
                pattern=r"^(ruff|black|mypy|flake8|eslint)\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Code linting or formatting",
            ),
            # Benign write operations
            PolicyRule(
                pattern=r"^(cd|mkdir|touch)\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
                reason="Benign filesystem operation",
            ),
        ]
        return cls(rules=rules)

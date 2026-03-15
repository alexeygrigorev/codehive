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


class CommandPolicyViolation(Exception):
    """Raised when a command is denied or needs approval per policy.

    Attributes:
        command: The command that was checked.
        verdict: The policy verdict (DENY or ASK).
        needs_approval: True when the verdict is ASK (caller should prompt user).
    """

    def __init__(self, command: str, verdict: PolicyVerdict) -> None:
        self.command = command
        self.verdict = verdict
        self.needs_approval = verdict == PolicyVerdict.ASK
        action = "needs approval" if self.needs_approval else "denied by policy"
        super().__init__(f"Command {action}: {command}")


@dataclass
class PolicyRule:
    """A single policy rule matching commands by regex pattern.

    Attributes:
        pattern: Regex pattern to match against the command string.
        category: Classification of the command (read_only, write, destructive, network).
        verdict: What to do when the pattern matches.
    """

    pattern: str
    category: str
    verdict: PolicyVerdict

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

    def check(self, command: str) -> PolicyVerdict:
        """Evaluate a command against the rules.

        Args:
            command: The shell command string to check.

        Returns:
            The verdict from the first matching rule, or DENY if none match.
        """
        for rule in self.rules:
            if rule.matches(command):
                return rule.verdict
        return PolicyVerdict.DENY

    @classmethod
    def default(cls) -> CommandPolicy:
        """Create a default policy preset with sensible rules.

        - Allows common read-only commands
        - Allows common build/test commands
        - Returns ASK for git push, rm -rf
        - Denies dangerous commands (pipe-to-shell, sudo, chmod 777)
        """
        rules = [
            # Deny obviously dangerous commands first (high priority)
            PolicyRule(
                pattern=r"curl\s.*\|\s*(sh|bash)",
                category="destructive",
                verdict=PolicyVerdict.DENY,
            ),
            PolicyRule(
                pattern=r"wget\s.*\|\s*(sh|bash)",
                category="destructive",
                verdict=PolicyVerdict.DENY,
            ),
            PolicyRule(
                pattern=r"\bsudo\b",
                category="destructive",
                verdict=PolicyVerdict.DENY,
            ),
            PolicyRule(
                pattern=r"chmod\s+777",
                category="destructive",
                verdict=PolicyVerdict.DENY,
            ),
            # ASK for potentially destructive operations
            PolicyRule(
                pattern=r"\bgit\s+push\b",
                category="network",
                verdict=PolicyVerdict.ASK,
            ),
            PolicyRule(
                pattern=r"\brm\s+-rf\b",
                category="destructive",
                verdict=PolicyVerdict.ASK,
            ),
            # Allow read-only commands
            PolicyRule(
                pattern=r"^ls\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^cat\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^grep\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^find\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^echo\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^pwd$",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^git\s+status\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^git\s+log\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^git\s+diff\b",
                category="read_only",
                verdict=PolicyVerdict.ALLOW,
            ),
            # Allow build/test commands
            PolicyRule(
                pattern=r"^python\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^pytest\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^uv\s+run\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
            ),
            PolicyRule(
                pattern=r"^npm\s+test\b",
                category="write",
                verdict=PolicyVerdict.ALLOW,
            ),
        ]
        return cls(rules=rules)

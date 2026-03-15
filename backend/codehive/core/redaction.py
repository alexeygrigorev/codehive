"""Secret redaction engine for logs, output, and event data."""

from __future__ import annotations

import re
from typing import Any

# Compiled patterns for common secret formats
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Anthropic API keys: sk-ant-api03-...
    (re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_-]{20,}"), "sk-ant-***REDACTED***"),
    # OpenAI-style keys: sk-proj-..., sk-...  (at least 20 chars after prefix)
    (re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"), "sk-***REDACTED***"),
    # GitHub PATs: ghp_, gho_, github_pat_
    (re.compile(r"(?:ghp|gho|ghs|ghr)_[A-Za-z0-9]{30,}"), "ghp_***REDACTED***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{30,}"), "github_pat_***REDACTED***"),
    # AWS access key IDs: AKIA...
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***REDACTED***"),
    # Bearer tokens (JWT-like)
    (
        re.compile(r"Bearer\s+[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        "Bearer ***REDACTED***",
    ),
    # URL-embedded passwords: ://user:password@host
    (re.compile(r"(://[^:]+:)[^@]+(@)"), r"\1***REDACTED***\2"),
    # Environment variable assignments with secret-like names
    (
        re.compile(
            r"((?:export\s+)?(?:SECRET|TOKEN|PASSWORD|API_KEY|APIKEY|API_SECRET)"
            r"[A-Za-z0-9_]*\s*=\s*)(\S+)"
        ),
        r"\1***REDACTED***",
    ),
]

# Minimum length for explicit secret values to avoid false positives
_MIN_SECRET_LENGTH = 4


class SecretRedactor:
    """Redacts secrets from text, dicts, and lists.

    Accepts a list of known secret values and also applies regex-based
    pattern detection for common secret formats.

    Thread-safe and stateless per call -- safe for concurrent async use.
    """

    def __init__(self, secrets: list[str] | None = None) -> None:
        """Initialize with optional explicit secret values.

        Args:
            secrets: Strings that should always be redacted.
                     Values of 3 characters or fewer are ignored.
        """
        self._secrets: list[str] = []
        if secrets:
            self._secrets = [s for s in secrets if len(s) >= _MIN_SECRET_LENGTH]

    def redact(self, text: str) -> str:
        """Replace all known secrets and detected patterns in *text*.

        Returns the redacted string.
        """
        # First, replace explicit secret values (longest first to avoid partial matches)
        result = text
        for secret in sorted(self._secrets, key=len, reverse=True):
            result = result.replace(secret, "***REDACTED***")

        # Then apply regex patterns
        for pattern, replacement in _SECRET_PATTERNS:
            result = pattern.sub(replacement, result)

        return result

    def redact_dict(self, data: Any) -> Any:
        """Recursively redact all string values in a dict/list structure.

        Non-string leaf values (int, bool, None, etc.) are left unchanged.
        """
        if isinstance(data, dict):
            return {k: self.redact_dict(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.redact_dict(item) for item in data]
        if isinstance(data, str):
            return self.redact(data)
        return data

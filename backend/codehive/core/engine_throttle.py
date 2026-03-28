"""In-memory engine throttle tracker for rate-limit-aware engine selection.

Tracks per-engine throttle state with automatic expiry based on ``resets_at``
epoch timestamps.  Uses :func:`time.monotonic` internally for expiry checks
to avoid clock-skew issues, but stores the wall-clock ``resets_at`` for API
display.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class _ThrottleEntry:
    """Internal record for a single throttled engine."""

    # monotonic deadline -- throttle expires when monotonic() >= this
    mono_deadline: float
    # wall-clock resets_at (epoch seconds) -- for API display only
    resets_at_epoch: int


class EngineThrottleTracker:
    """Per-engine throttle state with automatic expiry.

    All public methods are safe to call from any coroutine on the same
    event-loop (no locks needed -- single-threaded asyncio).
    """

    def __init__(self) -> None:
        self._entries: dict[str, _ThrottleEntry] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mark_throttled(self, engine: str, resets_at: int) -> None:
        """Mark *engine* as throttled until the ``resets_at`` epoch timestamp.

        If ``resets_at`` is already in the past the entry is still recorded
        but :meth:`is_available` will immediately return ``True``.
        """
        now_wall = time.time()
        now_mono = time.monotonic()
        remaining = resets_at - now_wall
        mono_deadline = now_mono + remaining
        self._entries[engine] = _ThrottleEntry(
            mono_deadline=mono_deadline,
            resets_at_epoch=resets_at,
        )

    def is_available(self, engine: str) -> bool:
        """Return ``True`` when *engine* is not throttled or its throttle expired."""
        entry = self._entries.get(engine)
        if entry is None:
            return True
        if time.monotonic() >= entry.mono_deadline:
            # Expired -- clean up
            del self._entries[engine]
            return True
        return False

    def get_available(self, engines: list[str]) -> str | None:
        """Return the first non-throttled engine from *engines*, or ``None``."""
        for engine in engines:
            if self.is_available(engine):
                return engine
        return None

    def get_status(self) -> dict[str, dict[str, object]]:
        """Return a dict of engine states for API display.

        Each entry has::

            {
                "available": bool,
                "throttled_until": "ISO-8601 string" | None,
                "reason": str,
            }
        """
        now_mono = time.monotonic()
        result: dict[str, dict[str, object]] = {}
        to_remove: list[str] = []

        for engine, entry in self._entries.items():
            if now_mono >= entry.mono_deadline:
                to_remove.append(engine)
                result[engine] = {
                    "available": True,
                    "throttled_until": None,
                    "reason": "throttle expired",
                }
            else:
                throttled_until = datetime.fromtimestamp(
                    entry.resets_at_epoch, tz=timezone.utc
                ).isoformat()
                result[engine] = {
                    "available": False,
                    "throttled_until": throttled_until,
                    "reason": "rate limit throttled",
                }

        for engine in to_remove:
            del self._entries[engine]

        return result

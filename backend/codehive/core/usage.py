"""Usage tracking and cost estimation utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

# Chat-relevant event types that should be persisted during streaming.
CHAT_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "message.created",
        "message.delta",
        "tool.call.started",
        "tool.call.finished",
        "error",
        "approval.required",
        "subagent.spawned",
        "subagent.report",
        "context.compacted",
    }
)

# Prices per million tokens: (input_price, output_price) in USD.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-opus-4-20250514": (15.0, 75.0),
    "claude-haiku-3-20250307": (0.25, 1.25),
    # Short aliases map to the same prices
    "claude-sonnet-4": (3.0, 15.0),
    "claude-opus-4": (15.0, 75.0),
    "claude-haiku-3": (0.25, 1.25),
    # Legacy models
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
}

# Default fallback price if model is unknown
_DEFAULT_PRICE: tuple[float, float] = (3.0, 15.0)

# Context window sizes (in tokens) for known models.
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-sonnet-4-20250514": 200_000,
    "claude-opus-4-20250514": 200_000,
    "claude-haiku-3-20250307": 200_000,
    # Short aliases
    "claude-sonnet-4": 200_000,
    "claude-opus-4": 200_000,
    "claude-haiku-3": 200_000,
    # Legacy models
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
    # OpenAI / Codex
    "codex-mini-latest": 200_000,
    "codex-mini": 200_000,
}

# Default context window when model is unknown
_DEFAULT_CONTEXT_WINDOW: int = 200_000


def get_context_window(model: str) -> int:
    """Return the context window size for a model.

    Falls back to ``_DEFAULT_CONTEXT_WINDOW`` for unknown models, using
    the same prefix-matching logic as :func:`estimate_cost`.
    """
    window = MODEL_CONTEXT_WINDOWS.get(model)
    if window is not None:
        return window

    for key, val in MODEL_CONTEXT_WINDOWS.items():
        if model.startswith(key) or key.startswith(model):
            return val

    return _DEFAULT_CONTEXT_WINDOW


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a given model and token counts.

    Returns 0.0 when both token counts are 0.  Uses a fallback price
    for unknown models so the user still gets an estimate.
    """
    if input_tokens == 0 and output_tokens == 0:
        return 0.0

    # Try exact match, then prefix match
    prices = MODEL_PRICES.get(model)
    if prices is None:
        # Try matching by prefix (e.g. "claude-sonnet-4-20250514" matches "claude-sonnet-4")
        for key, val in MODEL_PRICES.items():
            if model.startswith(key) or key.startswith(model):
                prices = val
                break

    if prices is None:
        prices = _DEFAULT_PRICE

    input_price, output_price = prices
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return round(cost, 6)


async def persist_usage_event(
    db: AsyncSession,
    session_id: uuid.UUID | None,
    event: dict,
) -> None:
    """Inspect an engine event and persist rate-limit / model-usage snapshots.

    Handles two event types:

    * ``rate_limit.updated`` -- writes a single :class:`RateLimitSnapshot` row.
    * ``usage.model_breakdown`` -- writes one :class:`ModelUsageSnapshot` row
      per model entry in ``event["models"]``.

    For any other event type the function is a silent no-op so callers can
    safely pass every event through without filtering.
    """
    from codehive.db.models import ModelUsageSnapshot, RateLimitSnapshot

    event_type = event.get("type")

    if event_type == "rate_limit.updated":
        snap = RateLimitSnapshot(
            session_id=session_id,
            rate_limit_type=event.get("rate_limit_type", "unknown"),
            utilization=float(event.get("utilization", 0)),
            resets_at=int(event.get("resets_at", 0)),
            is_using_overage=bool(event.get("is_using_overage", False)),
            surpassed_threshold=event.get("surpassed_threshold"),
        )
        db.add(snap)
        await db.flush()
        return

    if event_type == "usage.model_breakdown":
        models = event.get("models", [])
        for m in models:
            snap = ModelUsageSnapshot(
                session_id=session_id,
                model=m.get("model", "unknown"),
                input_tokens=int(m.get("input_tokens", 0)),
                output_tokens=int(m.get("output_tokens", 0)),
                cache_read_tokens=int(m.get("cache_read_tokens", 0)),
                cache_creation_tokens=int(m.get("cache_creation_tokens", 0)),
                cost_usd=float(m.get("cost_usd", 0)),
                context_window=m.get("context_window"),
            )
            db.add(snap)
        if models:
            await db.flush()
        return


async def persist_chat_event(
    db: AsyncSession,
    session_id: uuid.UUID,
    event: dict,
) -> uuid.UUID | None:
    """Persist a chat-relevant engine event to the ``events`` table.

    Only events whose ``type`` is in :data:`CHAT_EVENT_TYPES` are
    persisted.  Returns the generated DB event ``id`` on success, or
    ``None`` if the event type is not chat-relevant.
    """
    event_type = event.get("type", "")
    if event_type not in CHAT_EVENT_TYPES:
        return None

    from codehive.db.models import Event

    # Build a clean data dict (everything except 'type' and 'session_id' top-level keys)
    data = {k: v for k, v in event.items() if k not in ("type",)}

    db_event = Event(
        session_id=session_id,
        type=event_type,
        data=data,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(db_event)
    await db.flush()
    await db.refresh(db_event)
    return db_event.id


async def get_context_usage(
    db: AsyncSession,
    session_id: uuid.UUID,
) -> dict[str, object]:
    """Return context window usage for a session.

    Looks up the most recent ``UsageRecord`` for the session and uses its
    ``input_tokens`` as the current context utilisation (the Anthropic and
    OpenAI APIs report total input tokens per request, which reflects how
    full the context window is).

    Returns a dict compatible with the ``ContextUsageResponse`` schema.
    """
    from sqlalchemy import select

    from codehive.db.models import UsageRecord
    from codehive.db.models import Session as SessionModel

    # Get the session to determine the model
    sess_result = await db.execute(select(SessionModel).where(SessionModel.id == session_id))
    session = sess_result.scalar_one_or_none()
    if session is None:
        return {
            "used_tokens": 0,
            "context_window": _DEFAULT_CONTEXT_WINDOW,
            "usage_percent": 0.0,
            "model": "unknown",
            "estimated": True,
        }

    model = (session.config or {}).get("model", "") or ""
    engine = session.engine or ""

    # CLI engines don't produce UsageRecords
    is_cli_engine = engine in ("claude_code", "codex_cli")

    # Get the most recent usage record
    query = (
        select(UsageRecord)
        .where(UsageRecord.session_id == session_id)
        .order_by(UsageRecord.created_at.desc())
        .limit(1)
    )
    result = await db.execute(query)
    latest = result.scalar_one_or_none()

    if latest is not None:
        used_tokens = latest.input_tokens
        record_model = latest.model
    else:
        used_tokens = 0
        record_model = model

    # Use the model from the record if available, else from session config
    effective_model = record_model or model
    context_window = get_context_window(effective_model)
    usage_percent = round((used_tokens / context_window) * 100, 1) if context_window > 0 else 0.0

    return {
        "used_tokens": used_tokens,
        "context_window": context_window,
        "usage_percent": usage_percent,
        "model": effective_model,
        "estimated": is_cli_engine,
    }

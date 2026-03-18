"""Usage tracking and cost estimation utilities."""

from __future__ import annotations

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

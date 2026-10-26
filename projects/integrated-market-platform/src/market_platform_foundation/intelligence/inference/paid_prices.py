"""Pinned list prices for every paid catalog model, used by the hard dollar caps.

A price is per million tokens, standard tier (no batch, flex or priority discounts), checked by hand against the
vendor's own pricing page on the date stated. Thinking is billed as output on all three vendors. A model with no
pinned price cannot be selected as a paid engine: a dollar cap cannot be enforced on a price IMP does not know.

A long-prompt tier applies to the whole request once the prompt is above ``long_above`` input tokens. A dated
price change is a second row with its own ``valid_from``; the row in force on the UTC day of the call is used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

MICRO = 1_000_000          # micro-dollars per dollar
ANTHROPIC_SOURCE = "https://docs.claude.com/en/docs/about-claude/pricing"
OPENAI_SOURCE = "https://developers.openai.com/api/docs/pricing"
GEMINI_SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"


@dataclass(frozen=True, slots=True)
class ModelPrice:
    model: str
    input_per_mtok: float
    output_per_mtok: float
    source: str
    checked: str                          # date the price was read from ``source``
    long_above: int | None = None         # prompt tokens above which the long tier applies
    long_input_per_mtok: float | None = None
    long_output_per_mtok: float | None = None
    valid_from: date | None = None
    valid_until: date | None = None       # last day this row applies

    def rates(self, input_tokens: int) -> tuple[float, float]:
        if self.long_above is not None and input_tokens > self.long_above:
            return float(self.long_input_per_mtok or 0), float(self.long_output_per_mtok or 0)
        return self.input_per_mtok, self.output_per_mtok

    def applies(self, day: date) -> bool:
        return (self.valid_from is None or day >= self.valid_from) and (self.valid_until is None or day <= self.valid_until)


PRICES: tuple[ModelPrice, ...] = (
    ModelPrice("claude-haiku-5-5", 0.10, 0.50, ANTHROPIC_SOURCE, "2026-10-06", 100_000, 0.50, 2.50),
    ModelPrice("claude-haiku-4-5-20251001", 1.00, 5.00, ANTHROPIC_SOURCE, "2026-10-06"),
    ModelPrice("claude-sonnet-5-5", 2.00, 10.00, ANTHROPIC_SOURCE, "2026-10-06"),
    ModelPrice("claude-opus-5-5", 4.00, 20.00, ANTHROPIC_SOURCE, "2026-10-06"),
    ModelPrice("gpt-6-luna", 0.10, 0.50, OPENAI_SOURCE, "2026-10-24", 272_000, 0.20, 0.75),
    ModelPrice("gpt-6.1-sol", 2.00, 10.00, OPENAI_SOURCE, "2026-10-24", 272_000, 4.00, 15.00),
    ModelPrice("gpt-6-astra", 10.00, 50.00, OPENAI_SOURCE, "2026-10-24", 272_000, 20.00, 75.00),
    # Google lists the 2026 price and the higher one from 2027-01-01.
    ModelPrice("gemini-3.8-flash", 0.75, 3.75, GEMINI_SOURCE, "2026-10-24", valid_until=date(2026, 12, 31)),
    ModelPrice("gemini-3.8-flash", 1.50, 7.50, GEMINI_SOURCE, "2026-10-24", valid_from=date(2027, 1, 1)),
    ModelPrice("gemini-3.5-flash-lite", 0.30, 2.50, GEMINI_SOURCE, "2026-10-24"),
)


def price_for(model: str | None, day: date) -> ModelPrice | None:
    """The pinned price row in force on ``day``, or None when IMP has no verified price for the model."""

    return next((row for row in PRICES if row.model == model and row.applies(day)), None)


def cost_micro(model: str | None, input_tokens: int, output_tokens: int, day: date) -> int | None:
    """List cost of one call in micro-dollars, rounded up; None for a model without a pinned price."""

    row = price_for(model, day)
    if row is None:
        return None
    input_tokens, output_tokens = max(0, int(input_tokens)), max(0, int(output_tokens))
    input_rate, output_rate = row.rates(input_tokens)
    # Rates are dollars per million tokens, so dollars x 1e6 / 1e6 tokens is micro-dollars per token.
    return math.ceil(input_tokens * input_rate + output_tokens * output_rate)


def price_schedule(model: str | None, day: date) -> dict | None:
    """The row in the ``token_cost.estimated_cost`` shape, so cost previews use the same pinned price."""

    row = price_for(model, day)
    if row is None:
        return None
    rates = row.rates(0)
    until = (row.valid_until or date(day.year + 1, day.month, 1)).isoformat()
    return {"model_id": row.model, "currency": "USD", "source": row.source, "verified_at": row.checked + "T00:00:00Z",
            "valid_until": until + "T23:59:59Z", "input_per_million": rates[0], "output_per_million": rates[1]}


__all__ = ["MICRO", "ModelPrice", "PRICES", "cost_micro", "price_for", "price_schedule"]

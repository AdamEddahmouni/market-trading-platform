"""Deterministic prompt-to-intent routing for grounded assistant (no ML)."""

from __future__ import annotations

from typing import Literal

AssistantIntent = Literal[
    "explain",
    "quality",
    "strategy",
    "conflict",
    "what_changed",
    "show_source",
    "institutional",
    "instrument",
    "summary",
]


def route_intent(prompt: str) -> AssistantIntent:
    """Map a user prompt to a grounded retrieval intent."""
    normalized = prompt.lower().strip()
    if not normalized:
        return "summary"

    if any(token in normalized for token in ("conflict", "disagree", "contradict", "conflicting")):
        return "conflict"
    if any(token in normalized for token in ("what changed", "what's changed", "delta", "transition")):
        return "what_changed"
    if any(token in normalized for token in ("source", "provenance", "citation", "show source")):
        return "show_source"
    if any(token in normalized for token in ("quality", "data health", "stale", "degraded")):
        return "quality"
    if any(token in normalized for token in ("signal", "strategy", "forecast", "model")):
        return "strategy"
    if any(
        token in normalized
        for token in (
            "whale",
            "institutional",
            "disclosure",
            "order flow",
            "order-flow",
            "options",
            "futures",
            "catalyst",
            "squeeze",
            "large print",
            "order book",
            "fund",
            "etf",
        )
    ):
        return "institutional"
    if any(token in normalized for token in ("why", "explain", "what does", "what is", "here")):
        return "explain"
    if any(token in normalized for token in ("biya", "nvda", "es", "boxl", "avtx")):
        return "instrument"
    return "summary"

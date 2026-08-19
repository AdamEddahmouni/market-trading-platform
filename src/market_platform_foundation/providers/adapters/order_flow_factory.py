"""Order-flow provider factory — fixture default, recorded replay when IMP_ORDER_FLOW_LIVE=1."""

from __future__ import annotations

import os
from pathlib import Path

from .fixture_order_flow import DEFAULT_ORDER_FLOW_FIXTURE, FixtureOrderFlowProvider
from .recorded_order_flow import RecordedOrderFlowProvider


def build_order_flow_provider(*, fixture_path: Path | None = None) -> FixtureOrderFlowProvider:
    """Select fixture or recorded-replay order-flow provider."""
    path = fixture_path or DEFAULT_ORDER_FLOW_FIXTURE
    if os.environ.get("IMP_ORDER_FLOW_LIVE") == "1":
        return RecordedOrderFlowProvider(fixture_path=path)
    return FixtureOrderFlowProvider(fixture_path=path)


__all__ = [
    "build_order_flow_provider",
]

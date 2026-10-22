"""Controlled market-data fixture for OCT1-09 Paper experiment tests and harness.

Replaces only the two market-data reads of the production Paper route: the
observation clock and the completed-bar feed. Preview binding, pre-trade risk,
the bar-conservative simulator, the ledger, persistence and the experiment
service stay production code. SOFTWARE_CONTROLLED evidence, never market truth.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch

PROVIDER = "CONTROLLED_FIXTURE"
_TARGET = "market_platform_foundation.ui_api.paper_projections."


class ControlledFeed:
    def __init__(self, *, volume: int = 1_000_000) -> None:
        self.prices: dict[str, str] = {}
        self.volume = volume
        self._last_ns = 0

    def now_ns(self) -> int:
        # Strictly increasing so a bar issued after an intent is always "after" it.
        self._last_ns = max(time.time_ns(), self._last_ns + 1_000)
        return self._last_ns

    def observation_time(self, store: Any, *, instrument_id: str | None = None) -> int:
        return self.now_ns()

    def bars(self, store: Any, *, instrument_id: str | None = None) -> list[dict[str, Any]]:
        price = self.prices.get(str(instrument_id))
        if price is None:
            return []
        return [
            {
                "available_time": self.now_ns(),
                "bar_payload": {"close": price, "high": price, "low": price, "open": price, "volume": self.volume},
            }
        ]

    def mark(self, store: Any, instrument_id: str, price: str, *, quality: str = "PASS") -> None:
        """Controlled mark for one instrument, through the ledger's own mark authority."""
        from market_platform_foundation.local_state.startup import persist_ledger
        from market_platform_foundation.numeric import decimal_to_minor_units

        ledger = store.paper_ledger
        ledger.apply_live_mark(
            mark_minor=decimal_to_minor_units(price, scale=int(ledger.policy["price_scale"])),
            mark_provider=PROVIDER,
            mark_as_of_ns=self.now_ns(),
            mark_quality=quality,
            instrument_id=instrument_id,
            freshness_ms=0,
        )
        persist_ledger(ledger)

    def install(self) -> None:
        from market_platform_foundation.ui_api import paper_projections

        paper_projections._paper_observation_time = self.observation_time
        paper_projections._bars_for_paper_execution = self.bars

    @contextmanager
    def patched(self) -> Iterator["ControlledFeed"]:
        with patch(_TARGET + "_paper_observation_time", self.observation_time), patch(
            _TARGET + "_bars_for_paper_execution", self.bars
        ):
            yield self

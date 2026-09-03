"""Consumer wiring for P0 bitemporal joins."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.options_quality import OptionQualityFlag  # noqa: E402
from market_platform_foundation.futures.spec_registry import resolve_futures_spec  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.options.event_vol import build_event_vol_snapshot  # noqa: E402
from market_platform_foundation.runtime.bitemporal_store import (  # noqa: E402
    BitemporalReferenceStore,
    load_reference_records,
)
from market_platform_foundation.runtime.corporate_events import CorporateEventRegistry  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "platform" / "p0" / "p0_bitemporal_slice.json"
T_BEFORE = "2024-06-14T23:59:59.000000000Z"
T_AFTER = "2024-06-16T00:00:00.000000000Z"


def _p0_store() -> BitemporalReferenceStore:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    store = BitemporalReferenceStore()
    for record in load_reference_records(payload["records"]):
        store.append(record)
    return store


class P0ConsumerTests(unittest.TestCase):
    def test_resolve_futures_spec_default_es(self) -> None:
        spec = resolve_futures_spec("ES", date(2025, 6, 1))
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.spec_version, "es_cme_v1")

    def test_corporate_registry_uses_knowledge_visibility(self) -> None:
        registry = CorporateEventRegistry.from_extraction_summaries(
            [
                {
                    "event_id": "evt-1",
                    "canonical_event_type": "earnings_beat",
                    "event_time": "2026-08-27T20:00:00.000000000Z",
                    "available_time": "2024-06-15T00:00:00.000000000Z",
                }
            ],
            instrument_id="NVDA",
        )
        hidden = registry.query_events(
            "NVDA",
            prediction_cutoff=iso_to_epoch_ns("2024-06-14T23:59:59.000000000Z"),
        )
        visible = registry.query_events(
            "NVDA",
            prediction_cutoff=iso_to_epoch_ns("2024-06-16T00:00:00.000000000Z"),
        )
        self.assertEqual(len(hidden), 0)
        self.assertEqual(len(visible), 1)

    def test_o7_uses_joined_earnings_calendar(self) -> None:
        store = _p0_store()
        before = build_event_vol_snapshot(
            "NVDA",
            "2026-08-20T20:00:00.000000000Z",
            reference_store=store,
            knowledge_time=T_BEFORE,
        )
        after = build_event_vol_snapshot(
            "NVDA",
            "2026-08-20T20:00:00.000000000Z",
            reference_store=store,
            knowledge_time=T_AFTER,
        )
        self.assertEqual(before["event_time"], "2026-08-26T20:00:00.000000000Z")
        self.assertEqual(after["event_time"], "2026-08-27T20:00:00.000000000Z")

    def test_o7_fail_closed_when_calendar_unavailable(self) -> None:
        snapshot = build_event_vol_snapshot(
            "NVDA",
            "2026-08-19T20:30:00.000000000Z",
            reference_store=BitemporalReferenceStore(),
        )
        self.assertFalse(snapshot["available"])
        self.assertEqual(snapshot["status"], "UNAVAILABLE")
        self.assertIn(OptionQualityFlag.EARNINGS_DATE_UNKNOWN.value, snapshot["quality_flags"])


if __name__ == "__main__":
    unittest.main()

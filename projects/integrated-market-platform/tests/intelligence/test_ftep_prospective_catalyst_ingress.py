"""FTEP prospective Finviz catalyst ingress (offline mocks only)."""

from __future__ import annotations

import os
import unittest

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (
    collect_ftep_catalyst_watch,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    collect_finviz_prospective_attention_rows,
    prospective_catalyst_ingress_enabled,
)
from market_platform_foundation.local_state.paths import REPO_ROOT
from market_platform_foundation.news.timestamps import epoch_ns_from_iso


class _StubFinvizClient:
    def __init__(self, *, received_at: str, items: list[dict[str, object]]) -> None:
        self._received_at = received_at
        self._items = items

    def fetch_news(self, *, force: bool = False) -> dict[str, object]:
        return {
            "success": True,
            "error": None,
            "items": self._items,
            "received_at": self._received_at,
            "available_time_ns": 1_700_000_000_000_000_000,
        }


class FtepProspectiveCatalystIngressTests(unittest.TestCase):
    def test_gates_inactive_without_env(self) -> None:
        env = {
            "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "0",
            "IMP_FINVIZ_LIVE": "1",
            "FINVIZ_API_KEY": "test-token",
        }
        self.assertFalse(prospective_catalyst_ingress_enabled(env))
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            env=env,
        )
        self.assertTrue(result.attempted)
        self.assertFalse(result.ready)
        self.assertEqual(result.reason, "INGRESS_GATES_INACTIVE")

    def test_mock_finviz_maps_prospective_rows_with_timestamps(self) -> None:
        received = "2026-09-14T17:00:00.000000Z"
        as_of_ns = (epoch_ns_from_iso(received) or 0) + 1_000_000_000
        client = _StubFinvizClient(
            received_at=received,
            items=[
                {
                    "headline": "Apple reports quarterly earnings beat",
                    "published_time": "2026-09-14T16:55:00Z",
                    "url": "https://example.com/aapl-earnings",
                    "tickers": ["AAPL"],
                    "provider": "FINVIZ_ELITE",
                    "publisher_source": "Reuters",
                }
            ],
        )
        env = {
            "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1",
            "IMP_FINVIZ_LIVE": "1",
            "FINVIZ_API_KEY": "test-token",
        }
        result = collect_finviz_prospective_attention_rows(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            news_client=client,
            as_of_ns=as_of_ns,
            env=env,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.source_label, "live:finviz_elite_prospective")
        self.assertGreaterEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertEqual(row.get("symbol"), "AAPL")
        self.assertEqual(row.get("attention_data_kind"), "LIVE_PROSPECTIVE")
        self.assertEqual(row.get("published_time"), "2026-09-14T16:55:00Z")
        self.assertTrue(str(row.get("retrieved_time", "")).startswith("2026-09-14T17:00:00"))
        catalyst_ids = row.get("catalyst_ids") or ()
        self.assertIn("earnings", catalyst_ids)

    def test_live_ingress_fail_closed_under_fixture_smoke(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"
        payload = collect_ftep_catalyst_watch(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
            fixture_only=True,
        )
        self.assertEqual(payload["watch_mode"], "FIXTURE_SMOKE")
        self.assertEqual(payload["disposition"], "BLOCKED")
        self.assertIn("LIVE_INGRESS_UNAVAILABLE", payload["blockers"])
        self.assertEqual(payload["summary_count"], 0)
        self.assertEqual(payload["attention_data_kind"], "UNAVAILABLE")
        self.assertIsNone(payload["prospective_ingress"])

    def test_watch_live_ingress_blocked_when_gates_inactive(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"
        payload = collect_ftep_catalyst_watch(
            REPO_ROOT,
            "FTEP-V1-002",
            live_ingress=True,
        )
        if payload["watch_mode"] == "FIXTURE_SMOKE":
            self.assertIn("LIVE_INGRESS_UNAVAILABLE", payload["blockers"])
            self.assertEqual(payload["disposition"], "BLOCKED")
            self.assertEqual(payload["attention_data_kind"], "UNAVAILABLE")
        else:
            self.assertIn("PROSPECTIVE_CATALYST_INGRESS_GATES_INACTIVE", payload["blockers"])
            self.assertEqual(payload["attention_data_kind"], "UNAVAILABLE")
            self.assertEqual(payload["summary_count"], 0)


if __name__ == "__main__":
    unittest.main()

"""Discovery responses built from real engine output must pass the response secret-leak guard.

The 2026-10-07 session found ``GET /discover/mixed`` (Radar) answering 500: the guard, which is
name-based and fails closed, rejected the Finviz column inventory that the engine attaches to every
candidate. Earlier tests fed these projections a hand-written provenance without that inventory.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.discovery.engine import DiscoveryEngine  # noqa: E402
from market_platform_foundation.discovery.mixed import aggregate_candidate_sets  # noqa: E402
from market_platform_foundation.finviz.screener import parse_screener_csv  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import SecretLeakError, assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.ui_api import discovery_projections  # noqa: E402
from market_platform_foundation.ui_api.discovery_projections import build_discover_run_payload, load_latest_capture_for_screen  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "finviz"
SCREEN = "SHORT_SQUEEZE_DISCOVERY"


class StubScreener:
    configured = True

    def fetch_export(self, **kwargs):
        rows, columns, _ = parse_screener_csv((FIXTURES / "screener_sample.csv").read_text(encoding="utf-8"))
        return {"success": True, "rows": rows, "columns": list(columns), "received_at": "2026-10-07T13:30:00Z",
                "available_time_ns": 2000, "raw_response_hash": "abc"}


def engine_output() -> dict:
    return DiscoveryEngine(screener=StubScreener()).run_screen(SCREEN, persist=False).to_dict()


class DiscoveryResponseLeakGateTests(unittest.TestCase):
    def test_the_capture_record_keeps_the_column_inventory_and_the_guard_still_rejects_it(self):
        # The guard is unchanged: the full inventory is a capture record, not a response.
        captured = engine_output()
        fields = captured["candidates"][0]["provenance"]["field_inventory"]["fields"]
        self.assertTrue(any(field["source_authority_label"] == "FINVIZ_ELITE" for field in fields))
        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload(captured)

    def test_radar_candidates_built_from_real_engine_output_pass_the_guard(self):
        captured = engine_output()
        mixed = [candidate.to_dict() for candidate in aggregate_candidate_sets([captured], now_ns=3000)]
        self.assertTrue(mixed)

        assert_no_secrets_in_payload({"candidates": mixed})

        provenance = mixed[0]["provenance"][0]
        self.assertEqual(provenance["run_id"], captured["run_id"])
        inventory = provenance["candidate"]["field_inventory"]
        source = captured["candidates"][0]["provenance"]["field_inventory"]
        # The response says how many columns the export had and of which kind; the per-column table stays in the capture.
        self.assertEqual(inventory, {"field_count": source["field_count"], "categories": source["categories"]})
        self.assertEqual(provenance["candidate"]["screen_filters"], captured["candidates"][0]["provenance"]["screen_filters"])

    def test_a_screen_run_response_passes_the_guard_while_its_capture_stays_complete(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"IMP_FINVIZ_CAPTURE_DIR": directory}), \
                patch.object(discovery_projections, "DiscoveryEngine", lambda: DiscoveryEngine(screener=StubScreener())):
            payload = build_discover_run_payload(SCREEN)
            stored = load_latest_capture_for_screen(SCREEN)

        assert_no_secrets_in_payload(payload)
        candidate = payload["candidate_set"]["candidates"][0]
        self.assertEqual(set(candidate["provenance"]["field_inventory"]), {"field_count", "categories"})
        self.assertEqual(candidate["provenance"]["provider"], "FINVIZ_ELITE")
        self.assertIn("fields", stored["candidates"][0]["provenance"]["field_inventory"])

    def test_a_secret_under_any_other_provenance_key_is_still_blocked(self):
        captured = engine_output()
        captured["candidates"][0]["provenance"]["api_token"] = "live-value"
        mixed = [candidate.to_dict() for candidate in aggregate_candidate_sets([captured], now_ns=3000)]

        with self.assertRaises(SecretLeakError):
            assert_no_secrets_in_payload({"candidates": mixed})


if __name__ == "__main__":
    unittest.main()

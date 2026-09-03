"""Opt-in live EIA API tests — require EIA_API_KEY and IMP_EIA_LIVE=1."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.eia.health import (  # noqa: E402
    capability_report,
    live_probe,
    registry_audit_live,
    release_characterization,
    response_echo_audit,
)
from market_platform_foundation.eia.live import api_key_present, load_api_key  # noqa: E402
from market_platform_foundation.eia.redaction import redact_text  # noqa: E402
from market_platform_foundation.eia.registry import (  # noqa: E402
    FULL_REGISTRY,
    NATURAL_GAS_REGISTRY,
    PETROLEUM_REGISTRY,
)
from market_platform_foundation.eia.contracts import EnergyReleaseFamily  # noqa: E402
from market_platform_foundation.eia.sync import EiaSync  # noqa: E402
from market_platform_foundation.eia.transport import EiaTransport, MAX_JSON_ROWS  # noqa: E402

LIVE = os.environ.get("IMP_EIA_LIVE") == "1" and api_key_present()
FAKE_KEY = "FAKE_EIA_SECRET"


@unittest.skipUnless(LIVE, "IMP_EIA_LIVE=1 and EIA_API_KEY required")
class LiveEiaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = EiaTransport(api_key=load_api_key())
        self.api_key = load_api_key()

    def _assert_no_key_leak(self, payload: object) -> None:
        serialized = json.dumps(payload)
        self.assertNotIn(self.api_key, serialized)

    def test_auth_and_metadata(self) -> None:
        meta = self.transport.get_route_metadata("/v2/petroleum/sum/sndw")
        self.assertIn("response", meta)
        self._assert_no_key_leak(meta)
        facets = meta.get("response", {}).get("facets", [])
        facet_ids = [f.get("id") for f in facets if isinstance(f, dict)]
        self.assertIn("series", facet_ids)

    def test_response_echo_sanitization(self) -> None:
        echo = response_echo_audit(self.transport)
        self.assertEqual(echo.get("raw_api_key_echo"), "present")
        self.assertEqual(echo.get("sanitized_api_key"), "REDACTED")
        self.assertEqual(echo.get("real_key_in_sanitized_meta"), False)
        self._assert_no_key_leak(echo)
        payload = self.transport.query_data(
            PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"].route,
            params={
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"].series,
                "length": 1,
            },
        )
        self._assert_no_key_leak(payload)

    def test_petroleum_live_data(self) -> None:
        probe = live_probe(self.transport)
        self.assertTrue(probe.get("eia_api_auth_success"))
        self.assertTrue(probe.get("reachable"))
        self.assertEqual(probe.get("latest_petroleum_period"), "2026-08-14")
        self._assert_no_key_leak(probe)

    def test_natural_gas_live_data(self) -> None:
        lower48 = NATURAL_GAS_REGISTRY["LOWER48_WORKING_GAS_STORAGE"]
        payload = self.transport.query_data(
            lower48.route,
            params={
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": lower48.series,
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 1,
            },
        )
        rows = payload.get("response", {}).get("data", [])
        self.assertTrue(rows, "Lower 48 working gas should return data")
        self.assertEqual(rows[0].get("period"), "2026-08-14")
        self._assert_no_key_leak(payload)

    def test_registry_audit_live(self) -> None:
        audit = registry_audit_live(self.transport)
        self.assertEqual(len(audit), len(FULL_REGISTRY))
        observed = [item for item in audit if item.get("status") == "OBSERVED"]
        self.assertGreaterEqual(len(observed), 20)
        commercial = next(item for item in audit if item["concept"] == "COMMERCIAL_CRUDE_STOCKS")
        spr = next(item for item in audit if item["concept"] == "SPR_CRUDE_STOCKS")
        self.assertNotEqual(commercial.get("latest_value"), spr.get("latest_value"))
        self._assert_no_key_leak(audit)

    def test_release_timing_semantics(self) -> None:
        wpsr = release_characterization(EnergyReleaseFamily.WPSR, transport=self.transport, retrieved_at="2026-08-20T20:00:00Z")
        wngsr = release_characterization(EnergyReleaseFamily.WNGSR, transport=self.transport, retrieved_at="2026-08-20T20:00:00Z")
        self.assertEqual(wpsr["reference_period_end"], "2026-08-14")
        self.assertEqual(wpsr["scheduled_publication_date"], "2026-08-19")
        self.assertNotEqual(wpsr["reference_period_end"], wpsr["scheduled_release_time"])
        self.assertTrue(wpsr["period_end_not_equal_available_time"])
        self.assertEqual(wngsr["scheduled_publication_date"], "2026-08-20")

    def test_redaction_on_diagnostic(self) -> None:
        label = self.transport.diagnostic_label(
            "/v2/petroleum/sum/sndw/data",
            {"frequency": "weekly", "api_key": self.api_key},
        )
        self.assertNotIn(self.api_key, label)
        self.assertNotIn(self.api_key, redact_text(label))

    def test_pagination_bounded(self) -> None:
        self.assertLessEqual(3, MAX_JSON_ROWS)
        payload = self.transport.query_data(
            PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"].route,
            params={
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"].series,
                "length": 2,
                "offset": 0,
            },
        )
        rows = payload.get("response", {}).get("data", [])
        self.assertLessEqual(len(rows), 2)
        self._assert_no_key_leak(payload)

    def test_sync_bounded_fetch(self) -> None:
        sync = EiaSync(transport=self.transport)
        entry = PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"]
        added = sync.sync_registry_entry(entry)
        self.assertGreater(added, 0)
        self.assertLessEqual(added, 160)

    def test_capability_report_live(self) -> None:
        report = capability_report(live=True)
        self.assertEqual(report.get("classification"), "LIVE_CHARACTERIZED")
        self.assertTrue(report.get("eia_api_auth_success"))
        self.assertGreaterEqual(report.get("registry", {}).get("observed_count", 0), 20)
        self._assert_no_key_leak(report)

    def test_fake_key_redaction_regression(self) -> None:
        dirty = f"https://api.eia.gov/v2/petroleum/sum/sndw/data?api_key={FAKE_KEY}"
        self.assertNotIn(FAKE_KEY, redact_text(dirty))


if __name__ == "__main__":
    unittest.main()

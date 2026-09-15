"""Market Trackers + primary-source verification bridges."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.normalization import (  # noqa: E402
    IngestionMode,
    NormalizationContext,
)
from market_platform_foundation.intelligence.normalization.providers.market_trackers_congressional_disclosure import (  # noqa: E402
    normalize_congressional_disclosure_row,
)
from market_platform_foundation.intelligence.normalization.providers.market_trackers_sec_insider import (  # noqa: E402
    normalize_sec_insider_row,
)
from market_platform_foundation.market_trackers.congressional_disclosure.primary_verification_bridge import (  # noqa: E402
    build_adapter_prep_bundle_with_ptr_primary,
)
from market_platform_foundation.market_trackers.sec_insider.primary_verification_bridge import (  # noqa: E402
    build_adapter_prep_bundle_with_edgar_primary,
)

_MT_SEC = ROOT / "tests" / "fixtures" / "market_trackers" / "sec_insider"
_MT_CD = ROOT / "tests" / "fixtures" / "market_trackers" / "congressional_disclosure"
_SEC = ROOT / "tests" / "fixtures" / "sec_edgar"
_PTR = ROOT / "tests" / "fixtures" / "congressional_disclosure"
_PLATFORM_NS = 1_725_100_800_000_000_000
_OBSERVED = "2026-09-14T12:00:00Z"


class PublicRecordPrimarySourceBridgeTests(unittest.TestCase):
    def test_sec_bridge_feeds_edgar_primary_into_normalizer(self) -> None:
        row = json.loads((_MT_SEC / "form4_open_market_purchase.json").read_text(encoding="utf-8"))
        bundle, envelope, edgar_primary = build_adapter_prep_bundle_with_edgar_primary(
            row,
            platform_received_time_ns=_PLATFORM_NS,
            submissions_payload=(_SEC / "submissions_nvda_slice.json").read_bytes(),
            observed_time=_OBSERVED,
        )
        self.assertTrue(bundle.validation.ok)
        self.assertIn("artifact", envelope)
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_sec_insider_row(row, context=ctx, edgar_primary=edgar_primary)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        self.assertIn("PRIMARY_SOURCE_EDGAR_WINS", result.event.payload["reconcile_flags"])
        self.assertTrue(result.event.payload["clock_doctrine"]["edgar_primary_supplied"])

    def test_congressional_bridge_url_validation_and_ptr_metadata(self) -> None:
        row = json.loads((_MT_CD / "senate_stock_purchase.json").read_text(encoding="utf-8"))
        ptr_meta = json.loads((_PTR / "ptr_primary_senate_example.json").read_text(encoding="utf-8"))
        bundle, envelope, ptr_primary = build_adapter_prep_bundle_with_ptr_primary(
            row,
            platform_received_time_ns=_PLATFORM_NS,
            observed_time=_OBSERVED,
            ptr_primary_metadata=ptr_meta,
        )
        self.assertTrue(bundle.validation.ok)
        self.assertIsNotNone(ptr_primary)
        verification = envelope["verification"]
        self.assertEqual(verification["provenance"]["automation_claim"], "NOT_SUPPORTED")
        self.assertIn("PRIMARY_SOURCE_PTR_METADATA_SUPPLIED", verification["reconcile_hints"])

        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_NS,
            ingestion_mode=IngestionMode.FIXTURE,
        )
        result = normalize_congressional_disclosure_row(row, context=ctx, ptr_primary=ptr_primary)
        self.assertTrue(result.ok, result.diagnostics)
        assert result.event is not None
        self.assertIn("PRIMARY_SOURCE_PTR_WINS", result.event.payload["reconcile_flags"])

    def test_house_row_host_allowlist(self) -> None:
        row = json.loads((_MT_CD / "house_stock_sale.json").read_text(encoding="utf-8"))
        _, envelope, _ = build_adapter_prep_bundle_with_ptr_primary(
            row,
            platform_received_time_ns=_PLATFORM_NS,
            observed_time=_OBSERVED,
            ptr_primary_metadata=None,
        )
        hints = envelope["verification"]["reconcile_hints"]
        self.assertIn("HOUSE_CLERK_URL_PATTERN", hints)


if __name__ == "__main__":
    unittest.main()

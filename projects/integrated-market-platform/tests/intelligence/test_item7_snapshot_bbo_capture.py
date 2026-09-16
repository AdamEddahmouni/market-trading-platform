"""Item 7 upstream — lawful SNAPSHOT_BBO → capture envelope → grid eligibility.

SOFTWARE/CONTROLLED — fixture vendor rows only; no empirical corpus or live OpenD.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (  # noqa: E402
    canonicalize_opend_capture_envelope,
    materialize_opend_capture_jsonl,
    scan_capture_funnel,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.market_data.moomoo_snapshot_bbo import (  # noqa: E402
    BboClocks,
    OUTCOME_DERIVED_BBO_DESIGN_REQUIRED,
    OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED,
    SNAPSHOT_BBO_CAPABILITY,
    assess_snapshot_bbo,
    build_capture_envelope_from_vendor_snapshot,
)
from tests.intelligence.test_baseline_fixtures import T as DECISION_T  # noqa: E402
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
)


def _vendor_row(**overrides: object) -> dict:
    base = {
        "code": "US.NVDA",
        "last_price": 190.1,
        "update_time": "2026-09-12 15:59:00.000",
        "bid_price": 190.0,
        "ask_price": 190.2,
        "bid_vol": 100,
        "ask_vol": 200,
        "sec_status": "NORMAL",
    }
    base.update(overrides)
    return base


def _clocks() -> BboClocks:
    five_sec = 5 * 1_000_000_000
    received = DECISION_T + five_sec
    return BboClocks(
        request_time_ns=DECISION_T,
        provider_time_ns=DECISION_T,
        receive_time_ns=received,
        available_time_ns=received,
    )


class Item7SnapshotBboCaptureTests(unittest.TestCase):
    def test_validated_bbo_maps_to_snapshot_bbo_envelope(self) -> None:
        clocks = _clocks()
        mapping = build_capture_envelope_from_vendor_snapshot(_vendor_row(), clocks=clocks, sequence=42)
        self.assertIsNone(mapping.refusal_reason)
        self.assertIsNotNone(mapping.envelope)
        envelope = mapping.envelope
        assert envelope is not None
        self.assertEqual(envelope["capability"], SNAPSHOT_BBO_CAPABILITY)
        self.assertIn("BBO_VALID", envelope["quality_flags"])
        self.assertEqual(envelope["raw_payload"]["bid_price"], 190.0)
        self.assertEqual(envelope["raw_payload"]["ask_price"], 190.2)
        self.assertEqual(mapping.diagnostic.lane_outcome, OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED)

    def test_missing_bid_ask_refuses_envelope(self) -> None:
        clocks = _clocks()
        mapping = build_capture_envelope_from_vendor_snapshot(
            _vendor_row(bid_price=None, ask_price=None),
            clocks=clocks,
            sequence=1,
        )
        self.assertIsNone(mapping.envelope)
        self.assertEqual(mapping.diagnostic.lane_outcome, OUTCOME_DERIVED_BBO_DESIGN_REQUIRED)

    def test_canonicalize_aliases_only_when_bbo_valid(self) -> None:
        clocks = _clocks()
        valid = build_capture_envelope_from_vendor_snapshot(_vendor_row(), clocks=clocks, sequence=1)
        assert valid.envelope is not None
        canonical_valid = canonicalize_opend_capture_envelope(valid.envelope)
        self.assertEqual(canonical_valid["capability"], "QUOTE")
        self.assertEqual(canonical_valid["source_capability"], SNAPSHOT_BBO_CAPABILITY)

        invalid_diag = assess_snapshot_bbo(_vendor_row(bid_price=None), clocks=clocks)
        invalid_env = {
            "capability": SNAPSHOT_BBO_CAPABILITY,
            "quality_flags": list(invalid_diag.quality_flags),
        }
        canonical_invalid = canonicalize_opend_capture_envelope(invalid_env)
        self.assertEqual(canonical_invalid["capability"], SNAPSHOT_BBO_CAPABILITY)

    def test_lawful_snapshot_bbo_materializes_grid_candidate(self) -> None:
        clocks = _clocks()
        mapping = build_capture_envelope_from_vendor_snapshot(_vendor_row(), clocks=clocks, sequence=7)
        assert mapping.envelope is not None
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshot_bbo.jsonl"
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(mapping.envelope, sort_keys=True) + "\n")
            funnel = scan_capture_funnel(path, as_of_ns=AS_OF, session_start_ns=SESSION_START)
            self.assertEqual(funnel.raw_envelopes, 1)
            self.assertEqual(funnel.grid_points, 1)
            self.assertEqual(funnel.tape_eligible, 1)
            repo = InMemoryIntelligenceRepository()
            result = materialize_opend_capture_jsonl(
                path,
                repo,
                as_of_ns=AS_OF,
                session_start_ns=SESSION_START,
                use_production_ingress=False,
            )
            self.assertEqual(result.events_persisted, 1)
            self.assertEqual(result.funnel.grid_points, 1)


if __name__ == "__main__":
    unittest.main()

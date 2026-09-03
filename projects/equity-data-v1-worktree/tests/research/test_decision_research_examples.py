"""Task 4 — PIT-gated decision-example builder + fixture tests.

Pins the deterministic SS-family example fixture:
- byte-for-byte parity between the committed fixture and the builder output
- no-RNG determinism (identical bytes on repeat builds)
- every emitted example is PIT-valid (validate_temporal_example clean) and
  Finviz-scope clean (reject_historical_finviz_screen_without_capture)
- the measured donor-lane caps (CATALYST=2, MARKET_CONTEXT=1, ORDER_FLOW_CVD=0
  on the admitted fixture scope) so a future donor-slice change forces an
  explicit, reviewed fixture update rather than a silent cap drift
- adversarial rejection: feature-after-decision, outcome-before-decision,
  retroactive Finviz without capture, declared-only families never built
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import canonical_bytes
from market_platform_foundation.research.decision_research.examples import (
    DECLARED_ONLY_FAMILIES,
    build_ss_family_examples,
    examples_root_hash,
    load_donor_rows,
    validate_examples,
)
from market_platform_foundation.research.decision_research.pit_gate import (
    reject_historical_finviz_screen_without_capture,
    validate_temporal_example,
)

FIXTURE = ROOT / "tests" / "fixtures" / "research" / "ss_family_examples.json"

# Recorded at 2026-08-22 (Task 4). Binds the root hash + measured caps; a
# deliberate donor-slice change must update these together.
EXPECTED_ROOT_HASH = "D4F020327A3764471294ABB9C0A7888F3C6BD7F2814BCD971A63207C993E9115"
EXPECTED_CAPS = {
    "SQUEEZE_STATE": 2808,
    "CATALYST": 2,
    "MARKET_CONTEXT": 1,
    "ORDER_FLOW_CVD": 0,
}


class SsFamilyExampleBuildingTests(unittest.TestCase):
    def test_fixture_matches_builder_byte_for_byte(self) -> None:
        self.assertEqual(
            FIXTURE.read_bytes(),
            canonical_bytes(build_ss_family_examples()),
        )

    def test_root_hash_is_fixed(self) -> None:
        self.assertEqual(examples_root_hash(build_ss_family_examples()), EXPECTED_ROOT_HASH)

    def test_builder_is_deterministic_no_rng(self) -> None:
        first = canonical_bytes(build_ss_family_examples())
        second = canonical_bytes(build_ss_family_examples())
        self.assertEqual(first, second)

    def test_all_examples_are_pit_valid(self) -> None:
        examples = build_ss_family_examples()
        self.assertEqual(validate_examples(examples), [])
        for example in examples:
            ok, _reasons = validate_temporal_example(example)
            self.assertTrue(ok, example["example_id"])

    def test_family_caps_match_measured_slice(self) -> None:
        from collections import Counter

        occurrences = Counter(
            f["evidence_family"] for e in build_ss_family_examples() for f in e["features"]
        )
        for family, expected in EXPECTED_CAPS.items():
            self.assertEqual(occurrences[family], expected, family)

    def test_no_declared_only_family_is_ever_attached(self) -> None:
        attached = {
            f["evidence_family"]
            for e in build_ss_family_examples()
            for f in e["features"]
        }
        self.assertTrue(attached.isdisjoint(DECLARED_ONLY_FAMILIES))

    def test_declared_only_family_cannot_be_loaded(self) -> None:
        for family in DECLARED_ONLY_FAMILIES:
            with self.assertRaises(ValueError):
                load_donor_rows(family)


class AdversarialRejectionTests(unittest.TestCase):
    def test_feature_after_decision_is_rejected(self) -> None:
        example = {
            "example_id": "adv-1",
            "instrument_id": "BIYA",
            "decision_time_ns": 1000,
            "features": [
                {
                    "evidence_family": "SQUEEZE_STATE",
                    "feature_source": "X",
                    "available_time_ns": 2000,
                }
            ],
            "outcome_time_ns": 3000,
        }
        self.assertFalse(validate_temporal_example(example)[0])
        violations = validate_examples([example])
        self.assertTrue(any("FEATURE_AFTER_DECISION" in v for v in violations))

    def test_outcome_before_decision_is_rejected(self) -> None:
        example = {
            "example_id": "adv-2",
            "instrument_id": "BIYA",
            "decision_time_ns": 1000,
            "features": [],
            "outcome_time_ns": 500,
        }
        ok, reasons = validate_temporal_example(example)
        self.assertFalse(ok)
        self.assertTrue(any("OUTCOME_BEFORE_DECISION" in r for r in reasons))

    def test_finviz_screen_without_capture_is_rejected(self) -> None:
        ok, reason = reject_historical_finviz_screen_without_capture(
            feature_source="FINVIZ_SCREEN", capture_present=False
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "NO_RETROACTIVE_FINVIZ_SCREEN_RECONSTRUCTION")

    def test_finviz_screen_with_capture_is_allowed(self) -> None:
        ok, reason = reject_historical_finviz_screen_without_capture(
            feature_source="FINVIZ_SCREEN", capture_present=True
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_non_finviz_source_never_trips_finviz_rule(self) -> None:
        ok, reason = reject_historical_finviz_screen_without_capture(
            feature_source="BIYA_MARKET_BARS_INTRADAY_FIXTURE", capture_present=False
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()

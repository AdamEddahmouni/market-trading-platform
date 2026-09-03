"""Tests for PI5 participant walk-forward skill."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import ParticipantQualityFlag  # noqa: E402
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.donor_bridge.participant_adapter import (  # noqa: E402
    build_participant_cross_lane_bundle,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.skill import (  # noqa: E402
    apply_shrinkage,
    build_participant_skill_bundle,
    estimate_participant_skill,
    load_price_outcome_fixture,
)
from market_platform_foundation.participant.bridge import query_participant_actions_from_ledger  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_ledger_from_edgar_fixture  # noqa: E402

SKILL_HISTORY_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "edgar" / "biya_participant_skill_history.json"
)
PRICE_FIXTURE = ROOT / "tests" / "fixtures" / "participant" / "biya_price_outcomes.json"
GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "participant" / "biya_participant_skill_expected.json"


class ParticipantSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        self.cutoff = iso_to_epoch_ns("2026-06-15T23:59:59Z")
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(
                fixture_path=SKILL_HISTORY_FIXTURE,
                as_of_time_ns=self.cutoff,
            )
        )
        self.price_fixture = load_price_outcome_fixture(PRICE_FIXTURE)
        self.daily_closes = {
            str(k): float(v) for k, v in self.price_fixture["daily_closes"].items()
        }
        with GOLDEN_FIXTURE.open(encoding="utf-8") as handle:
            self.golden = json.load(handle)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def _actions(self) -> list[dict]:
        ledger = get_institutional_ledger()
        assert ledger is not None
        return query_participant_actions_from_ledger(
            ledger.events,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
        )

    def test_apply_shrinkage_formula(self) -> None:
        self.assertAlmostEqual(apply_shrinkage(0.10, sample_count=6), 6 / 11 * 0.10, places=6)
        self.assertIsNone(apply_shrinkage(None, sample_count=0))

    def test_insufficient_sample_fail_closed(self) -> None:
        actions = self._actions()
        snapshots = estimate_participant_skill(
            actions,
            prediction_cutoff=self.cutoff,
            daily_closes=self.daily_closes,
        )
        john = next(row for row in snapshots if row.display_name == "John Director")
        sell_estimate = next(row for row in john.estimates if row.dimension.value == "sell_skill")
        self.assertIn(
            ParticipantQualityFlag.SKILL_INSUFFICIENT_SAMPLE.value,
            sell_estimate.quality_flags,
        )

    def test_golden_jane_officer_buy_skill(self) -> None:
        actions = self._actions()
        bundle = build_participant_skill_bundle(
            actions,
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
        )
        self.assertTrue(bundle["available"])
        summary = bundle["summary"]
        jane = summary["participants"]["Jane Officer"]["dimensions"]["buy_skill"]
        expected = self.golden["participants"]["Jane Officer"]["buy_skill"]
        self.assertEqual(jane["sample_count"], expected["sample_count"])
        self.assertAlmostEqual(jane["raw_mean"], expected["raw_mean"], places=3)
        self.assertAlmostEqual(jane["shrunk_estimate"], expected["shrunk_estimate"], places=3)

    def test_weak_buyer_below_baseline_signal(self) -> None:
        actions = self._actions()
        bundle = build_participant_skill_bundle(
            actions,
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
        )
        summary = bundle["summary"]
        self.assertIn(
            EvidenceSignal.PARTICIPANT_SKILL_BELOW_BASELINE.value,
            summary["cross_lane_signals"],
        )
        self.assertEqual(
            summary["below_baseline_participant_count"],
            self.golden["summary"]["below_baseline_participant_count"],
        )

    def test_pit_adversarial_future_action_excluded(self) -> None:
        early_cutoff = iso_to_epoch_ns("2025-12-01T00:00:00Z")
        actions = self._actions()
        early_snapshots = estimate_participant_skill(
            actions,
            prediction_cutoff=early_cutoff,
            daily_closes=self.daily_closes,
        )
        late_snapshots = estimate_participant_skill(
            actions,
            prediction_cutoff=self.cutoff,
            daily_closes=self.daily_closes,
        )
        jane_early = next(row for row in early_snapshots if row.display_name == "Jane Officer")
        jane_late = next(row for row in late_snapshots if row.display_name == "Jane Officer")
        early_buy = next(row for row in jane_early.estimates if row.dimension.value == "buy_skill")
        late_buy = next(row for row in jane_late.estimates if row.dimension.value == "buy_skill")
        self.assertLess(early_buy.sample_count, late_buy.sample_count)

    def test_cross_lane_skill_publish(self) -> None:
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(
                fixture_path=SKILL_HISTORY_FIXTURE,
                as_of_time_ns=self.cutoff,
            )
        )
        snapshot, evidence = build_participant_cross_lane_bundle(
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
        )
        self.assertTrue(snapshot.get("participant_skill_available"))
        signals = {row.get("signal") for row in evidence}
        self.assertIn(EvidenceSignal.PARTICIPANT_SKILL_BELOW_BASELINE.value, signals)


if __name__ == "__main__":
    unittest.main()

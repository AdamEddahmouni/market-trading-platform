"""Vintage/PIT tests on admitted FRED, CFTC, and EIA verticals.

Fixture-only. No Live. No second store. No new analytics engine.
Does not duplicate tests/xa02/test_xa02_vintage_series.py.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.cftc.datasets import CotDataset, dataset_spec
from market_platform_foundation.cftc.mapping import CotProductMapper
from market_platform_foundation.cftc.normalize import normalize_api_rows as normalize_cftc_rows
from market_platform_foundation.eia.contracts import EnergyHistoryClass, EnergyPitConfidence
from market_platform_foundation.eia.normalize import normalize_api_row
from market_platform_foundation.eia.pit import energy_as_of, latest_visible_or_flags
from market_platform_foundation.eia.quality import EiaQualityFlag, quality_blocks_fundamentals, vintage_honesty_flags
from market_platform_foundation.eia.registry import lookup_canonical
from market_platform_foundation.fred.availability import normalize_knowledge_end
from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.admission import admit_macro_observation, eligible_at_decision_time as fred_eligible
from market_platform_foundation.xa02.enums import RevisionClassification
from market_platform_foundation.xa02.fixtures import load_fixture as load_xa02_fixture
from market_platform_foundation.xa02.fixtures import macro_observations_from_fixture
from market_platform_foundation.xa02.registry import reset_registry_for_tests as reset_xa02_registry
from market_platform_foundation.xa02.vintage_series import PitSelectionOutcome, build_vintage_series, select_series_as_of
from market_platform_foundation.xa03.admission import admit_positioning_observation, eligible_at_decision_time as cftc_eligible
from market_platform_foundation.xa03.fixtures import load_fixture as load_xa03_fixture
from market_platform_foundation.xa03.fixtures import positioning_observations_from_revision_fixture
from market_platform_foundation.xa03.registry import reset_registry_for_tests as reset_xa03_registry

ROOT = Path(__file__).resolve().parents[1]
EIA_FIXTURES = ROOT / "fixtures" / "eia"
CFTC_FIXTURES = ROOT / "fixtures" / "cftc"


def _load_eia(name: str) -> dict:
    return json.loads((EIA_FIXTURES / name).read_text(encoding="utf-8"))


class AdmittedFredCftcEiaVintagePitTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_xa03_registry()

    def _admit_fred_revision_sequence(self):
        payload = load_xa02_fixture("rates_revision_sequence.json")
        return [admit_macro_observation(item) for item in macro_observations_from_fixture(payload)]

    def _admit_cftc_week_of_august_18(self):
        payload = json.loads((CFTC_FIXTURES / "tff_futures_only_es.json").read_text(encoding="utf-8"))
        rows = [dict(payload["rows"][0], report_date_as_yyyy_mm_dd="2026-08-18")]
        observations = list(
            normalize_cftc_rows(
                rows,
                spec=dataset_spec(CotDataset.TFF_FUTURES_ONLY),
                mapper=CotProductMapper(),
                observed_time="2026-08-21T20:00:00Z",
                retrieved_time="2026-08-21T20:00:00Z",
            )
        )
        return [
            admit_positioning_observation(item, retrieved_time="2026-08-21T20:00:00Z") for item in observations
        ]

    def test_fred_realtime_end_is_never_first_availability(self) -> None:
        admitted = self._admit_fred_revision_sequence()
        series = build_vintage_series(admitted)[0]
        for vintage in series.vintages:
            self.assertEqual(vintage.knowledge_start, vintage.observation.provenance.realtime_start)
            self.assertNotEqual(vintage.knowledge_start, vintage.observation.provenance.realtime_end)
            self.assertEqual(
                vintage.knowledge_end,
                normalize_knowledge_end(vintage.observation.provenance.realtime_end),
            )
            self.assertNotEqual(vintage.observation.available_time, vintage.observation.provenance.realtime_end)

        still_v1 = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-02-13T00:00:00Z",
        )
        self.assertEqual(still_v1.outcome, PitSelectionOutcome.SELECTED)
        assert still_v1.selected is not None
        self.assertEqual(still_v1.selected.observation.normalized_value, 1.88)
        self.assertEqual(still_v1.provenance.realtime_end, "2020-02-13")

        superseded = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-02-14T00:00:00Z",
        )
        self.assertEqual(superseded.outcome, PitSelectionOutcome.SELECTED)
        assert superseded.selected is not None
        self.assertEqual(superseded.selected.observation.normalized_value, 1.75)

    def test_fred_envelope_eligibility_does_not_close_superseded_vintages(self) -> None:
        admitted = self._admit_fred_revision_sequence()
        after_all = "2020-04-01T00:00:00Z"
        self.assertTrue(all(fred_eligible(item, after_all) for item in admitted))
        pit = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time=after_all,
        )
        self.assertEqual(pit.outcome, PitSelectionOutcome.SELECTED)
        assert pit.selected is not None
        self.assertEqual(pit.selected.observation.normalized_value, 1.80)
        self.assertEqual(len(admitted), 3)

    def test_cftc_has_no_alfred_knowledge_interval_supersession(self) -> None:
        payload = load_xa03_fixture("source_revision.json")
        versioned = positioning_observations_from_revision_fixture(payload)
        admitted = [
            admit_positioning_observation(
                obs,
                retrieved_time=obs.observed_time,
                revision_number=max(0, revision_number - 1),
            )
            for obs, revision_number in versioned
        ]
        originals = [item for item in admitted if item.revision_classification == RevisionClassification.ORIGINAL_OR_AS_REPORTED]
        revisions = [item for item in admitted if item.revision_classification == RevisionClassification.VINTAGE_IDENTIFIED]
        self.assertTrue(originals)
        self.assertTrue(revisions)
        for envelope in admitted:
            self.assertEqual(envelope.provenance.realtime_end, "")
        late = "2026-08-15T20:00:00Z"
        self.assertTrue(all(cftc_eligible(item, late) for item in originals))
        self.assertTrue(any(cftc_eligible(item, late) for item in revisions))

    def test_eia_current_api_history_is_not_original_vintage(self) -> None:
        stocks = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        production = lookup_canonical("CRUDE_OIL_PRODUCTION")
        assert stocks and production
        clocks = _load_eia("cftc_eia_independent_clocks.json")
        stock_obs = normalize_api_row(
            {"period": clocks["period_end"], "series": stocks.series, "value": 438765},
            entry=stocks,
            observed_time=clocks["wpsr_publication"],
            retrieved_time=clocks["wpsr_publication"],
            api_first_observed_time=clocks["wpsr_publication"],
        )
        production_obs = normalize_api_row(
            {"period": clocks["period_end"], "series": production.series, "value": 13456},
            entry=production,
            observed_time=clocks["wpsr_publication"],
            retrieved_time=clocks["wpsr_publication"],
            api_first_observed_time=clocks["wpsr_publication"],
        )
        assert stock_obs and production_obs
        self.assertEqual(stock_obs.history_class, EnergyHistoryClass.CURRENT_API_HISTORY)
        self.assertEqual(stock_obs.pit_confidence, EnergyPitConfidence.CURRENT_HISTORY_ONLY)
        self.assertIn(EiaQualityFlag.HISTORICAL_VINTAGE_UNAVAILABLE.value, stock_obs.quality_flags)
        self.assertNotIn(EiaQualityFlag.PIT_UNCERTAIN.value, stock_obs.quality_flags)
        self.assertFalse(quality_blocks_fundamentals(stock_obs.quality_flags))

        self.assertEqual(production_obs.pit_confidence, EnergyPitConfidence.HISTORICAL_PIT_UNCERTAIN)
        self.assertIn(EiaQualityFlag.HISTORICAL_VINTAGE_UNAVAILABLE.value, production_obs.quality_flags)
        self.assertIn(EiaQualityFlag.PIT_UNCERTAIN.value, production_obs.quality_flags)
        self.assertFalse(quality_blocks_fundamentals(production_obs.quality_flags))

        live_capture = normalize_api_row(
            {"period": clocks["period_end"], "series": stocks.series, "value": 438765},
            entry=stocks,
            observed_time=clocks["wpsr_publication"],
            retrieved_time=clocks["wpsr_publication"],
            api_first_observed_time=clocks["wpsr_publication"],
            history_class=EnergyHistoryClass.LIVE_RELEASE_CAPTURE,
        )
        assert live_capture is not None
        self.assertNotIn(EiaQualityFlag.HISTORICAL_VINTAGE_UNAVAILABLE.value, live_capture.quality_flags)
        self.assertEqual(
            vintage_honesty_flags(
                history_class=EnergyHistoryClass.LIVE_RELEASE_CAPTURE.value,
                pit_confidence=EnergyPitConfidence.PROSPECTIVE_VERSIONED_PIT.value,
            ),
            (),
        )

        visible = energy_as_of(
            [stock_obs],
            decision_time="2026-08-19T15:00:00Z",
            canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS",
        )
        assert visible is not None
        self.assertEqual(visible.history_class, EnergyHistoryClass.CURRENT_API_HISTORY)
        self.assertNotEqual(visible.history_class, EnergyHistoryClass.ARCHIVED_RELEASE_SNAPSHOT)
        self.assertNotEqual(visible.pit_confidence, EnergyPitConfidence.PROSPECTIVE_VERSIONED_PIT)

    def test_admitted_verticals_keep_independent_clocks(self) -> None:
        clocks = _load_eia("cftc_eia_independent_clocks.json")
        cutoff = next(step["decision_time"] for step in clocks["timeline"] if step["label"] == "Wednesday_before_1030_ET")
        self.assertEqual(cutoff, "2026-08-19T14:29:00Z")

        fred = select_series_as_of(
            self._admit_fred_revision_sequence(),
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time=cutoff,
        )
        self.assertEqual(fred.outcome, PitSelectionOutcome.SELECTED)

        cftc = self._admit_cftc_week_of_august_18()
        self.assertTrue(cftc)
        self.assertFalse(any(cftc_eligible(item, cutoff) for item in cftc))
        self.assertTrue(any(cftc_eligible(item, clocks["cot_publication"]) for item in cftc))

        stocks = lookup_canonical("COMMERCIAL_CRUDE_STOCKS")
        assert stocks
        eia_obs = normalize_api_row(
            {"period": clocks["period_end"], "series": stocks.series, "value": 438765},
            entry=stocks,
            observed_time=clocks["wpsr_publication"],
            retrieved_time=clocks["wpsr_publication"],
            api_first_observed_time=clocks["wpsr_publication"],
        )
        assert eia_obs is not None
        before, flags = latest_visible_or_flags(
            [eia_obs],
            decision_time=cutoff,
            canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS",
        )
        self.assertIsNone(energy_as_of([eia_obs], decision_time=cutoff, canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS"))
        self.assertIsNone(before)
        self.assertIn(EiaQualityFlag.REPORT_NOT_YET_RELEASED.value, flags)
        after = energy_as_of(
            [eia_obs],
            decision_time="2026-08-19T15:00:00Z",
            canonical_indicator_id="COMMERCIAL_CRUDE_STOCKS",
        )
        self.assertIsNotNone(after)
        self.assertIn(EiaQualityFlag.HISTORICAL_VINTAGE_UNAVAILABLE.value, after.quality_flags)

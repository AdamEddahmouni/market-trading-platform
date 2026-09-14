"""Vintage-aware series PIT tests — fixture-only, no Live, no second store."""

from __future__ import annotations

import unittest

from market_platform_foundation.fred.availability import AvailabilityPrecision
from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.quality import FredQualityFlag
from market_platform_foundation.fred.registry import lookup_canonical
from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.admission import admit_macro_observation
from market_platform_foundation.xa02.enums import RevisionClassification
from market_platform_foundation.xa02.fixtures import load_fixture, macro_observations_from_fixture
from market_platform_foundation.xa02.identity import vintage_identity_from_admitted
from market_platform_foundation.xa02.registry import reset_registry_for_tests
from market_platform_foundation.xa02.vintage_series import (
    PitSelectionOutcome,
    build_vintage_series,
    select_series_as_of,
    series_as_of,
)


class Xa02VintageSeriesTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_registry_for_tests()

    def _admit_revision_sequence(self):
        payload = load_fixture("rates_revision_sequence.json")
        return [admit_macro_observation(item) for item in macro_observations_from_fixture(payload)]

    def test_groups_revisions_into_one_series(self) -> None:
        admitted = self._admit_revision_sequence()
        series_list = build_vintage_series(admitted)
        self.assertEqual(len(series_list), 1)
        series = series_list[0]
        self.assertEqual(series.identity.canonical_indicator_id, "US_10Y_TREASURY_YIELD")
        self.assertEqual(series.identity.observation_date, "2020-01-01")
        self.assertEqual(len(series.vintages), 3)
        identities = [item.vintage_identity for item in series.vintages]
        self.assertEqual(len(set(identities)), 3)
        self.assertEqual(
            [item.observation.normalized_value for item in series.vintages],
            [1.88, 1.75, 1.80],
        )

    def test_as_of_before_first_vintage_is_unavailable(self) -> None:
        admitted = self._admit_revision_sequence()
        result = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-01-10T00:00:00Z",
        )
        self.assertEqual(result.outcome, PitSelectionOutcome.PIT_UNAVAILABLE)
        self.assertIsNone(result.selected)
        self.assertIn(FredQualityFlag.PIT_UNAVAILABLE.value, result.quality_flags)

    def test_knowledge_interval_selects_then_supersedes(self) -> None:
        admitted = self._admit_revision_sequence()
        v1 = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-02-01T00:00:00Z",
        )
        self.assertEqual(v1.outcome, PitSelectionOutcome.SELECTED)
        assert v1.selected is not None
        self.assertEqual(v1.selected.observation.normalized_value, 1.88)
        self.assertEqual(v1.provenance.realtime_start, "2020-01-15")
        self.assertEqual(v1.provenance.realtime_end, "2020-02-13")
        self.assertEqual(v1.provenance.revision_number, 0)

        v2 = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-02-20T00:00:00Z",
        )
        self.assertEqual(v2.outcome, PitSelectionOutcome.SELECTED)
        assert v2.selected is not None
        self.assertEqual(v2.selected.observation.normalized_value, 1.75)
        self.assertEqual(v2.provenance.revision_number, 1)

        v3 = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-04-01T00:00:00Z",
        )
        self.assertEqual(v3.outcome, PitSelectionOutcome.SELECTED)
        assert v3.selected is not None
        self.assertEqual(v3.selected.observation.normalized_value, 1.80)
        self.assertEqual(v3.provenance.revision_number, 2)

    def test_date_only_same_day_intraday_fails_closed(self) -> None:
        admitted = self._admit_revision_sequence()
        result = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-01-15T13:30:00Z",
        )
        self.assertEqual(result.outcome, PitSelectionOutcome.DATE_ONLY_INTRADAY)
        self.assertIsNone(result.selected)
        self.assertIn(FredQualityFlag.PIT_UNCERTAIN.value, result.quality_flags)

        next_day = select_series_as_of(
            admitted,
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-01-16T00:00:00Z",
        )
        self.assertEqual(next_day.outcome, PitSelectionOutcome.SELECTED)
        assert next_day.selected is not None
        self.assertEqual(next_day.selected.observation.normalized_value, 1.88)

    def test_snapshot_rows_excluded_from_historical_pit(self) -> None:
        entry = lookup_canonical("US_10Y_TREASURY_YIELD")
        assert entry is not None
        obs = MacroObservation(
            canonical_indicator_id=entry.canonical_indicator_id,
            series_id=entry.fred_series_id,
            observation_date="2026-02-12",
            raw_value="4.25",
            normalized_value=4.25,
            frequency=entry.frequency,
            units=entry.units,
            seasonal_adjustment=entry.seasonal_adjustment,
            source_agency=entry.original_source,
            fred_release_id=entry.fred_release_id,
            realtime_start="",
            realtime_end="",
            vintage_date="",
            series_last_updated="2026-02-12T22:00:00Z",
            available_time="2026-02-12T22:00:00Z",
            availability_precision=AvailabilityPrecision.SNAPSHOT.value,
            observed_time="2026-02-12T22:00:00Z",
            retrieved_time="2026-02-13T16:00:00Z",
            api_version="v2",
        )
        admitted = admit_macro_observation(obs)
        self.assertEqual(admitted.revision_classification, RevisionClassification.LATEST_ONLY)
        series_list = build_vintage_series([admitted])
        result = series_as_of(series_list[0], "2026-02-13T00:00:00Z")
        self.assertEqual(result.outcome, PitSelectionOutcome.SNAPSHOT_EXCLUDED)
        self.assertIsNone(result.selected)
        self.assertIn(FredQualityFlag.PIT_UNAVAILABLE.value, result.quality_flags)

    def test_unknown_series_is_unavailable(self) -> None:
        result = select_series_as_of(
            [],
            canonical_indicator_id="US_10Y_TREASURY_YIELD",
            observation_date="2020-01-01",
            decision_time="2020-02-01T00:00:00Z",
        )
        self.assertEqual(result.outcome, PitSelectionOutcome.PIT_UNAVAILABLE)

    def test_vintage_identity_stable_on_admitted_row(self) -> None:
        admitted = self._admit_revision_sequence()[0]
        self.assertEqual(
            vintage_identity_from_admitted(admitted),
            f"{admitted.provenance.realtime_start}:{admitted.provenance.revision_number}",
        )

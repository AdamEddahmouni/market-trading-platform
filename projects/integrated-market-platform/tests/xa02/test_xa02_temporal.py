"""XA-02 temporal and revision semantics tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.fred.availability import AvailabilityPrecision
from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.registry import lookup_canonical
from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.admission import admit_macro_observation, eligible_at_decision_time
from market_platform_foundation.xa02.enums import RevisionClassification
from market_platform_foundation.xa02.fixtures import admit_fixture, macro_observations_from_fixture, load_fixture
from market_platform_foundation.xa02.registry import get_registry, reset_registry_for_tests


class Xa02TemporalTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_registry_for_tests()

    def test_observation_period_not_equal_available_time(self) -> None:
        admitted = admit_fixture(fixture_name="rates_reference_vertical.json")
        registry = get_registry()
        obs = registry.list_observations_for_indicator("US_10Y_TREASURY_YIELD")[0]
        self.assertEqual(obs.event_time, "2026-02-12")
        self.assertEqual(obs.available_time, "2026-02-12T22:00:00Z")
        self.assertNotEqual(obs.event_time, obs.available_time)
        self.assertNotEqual(obs.retrieval_time, obs.event_time)

    def test_late_revision_excluded_from_earlier_cutoff(self) -> None:
        payload = load_fixture("rates_revision_sequence.json")
        macro_observations = macro_observations_from_fixture(payload)
        registry = get_registry()
        registry.bootstrap_catalog()
        admitted = [admit_macro_observation(item) for item in macro_observations]
        for item in admitted:
            registry.admit_observation(item)
        early = [item for item in admitted if eligible_at_decision_time(item, "2020-02-01T00:00:00Z")]
        late = [item for item in admitted if eligible_at_decision_time(item, "2020-03-20T00:00:00Z")]
        self.assertEqual(len(early), 1)
        self.assertEqual(early[0].normalized_value, 1.88)
        self.assertEqual(len(late), 3)
        latest = max(late, key=lambda item: item.available_time)
        self.assertEqual(latest.normalized_value, 1.80)

    def test_revision_vintages_are_distinct_observations(self) -> None:
        payload = load_fixture("rates_revision_sequence.json")
        macro_observations = macro_observations_from_fixture(payload)
        self.assertEqual(len(macro_observations), 3)
        ids = {admit_macro_observation(item).observation_id for item in macro_observations}
        self.assertEqual(len(ids), 3)

    def test_latest_only_classification_for_v2_snapshot(self) -> None:
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

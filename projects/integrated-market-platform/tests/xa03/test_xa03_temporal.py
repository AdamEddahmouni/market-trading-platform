"""XA-03 temporal and revision semantics tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.cftc.release_schedule import publication_time_utc, release_for_position_date
from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.enums import RevisionClassification
from market_platform_foundation.xa02.registry import reset_registry_for_tests as reset_xa02_registry
from market_platform_foundation.xa03.admission import admit_positioning_observation, eligible_at_decision_time
from market_platform_foundation.xa03.fixtures import admit_fixture, load_fixture, positioning_observations_from_fixture
from market_platform_foundation.xa03.fixtures import positioning_observations_from_revision_fixture
from market_platform_foundation.xa03.registry import get_registry, reset_registry_for_tests


class Xa03TemporalTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_registry_for_tests()

    def test_position_date_not_equal_publication_time(self) -> None:
        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        registry = get_registry()
        envelope = registry.get_observation(result["observation_ids"][0])
        self.assertNotEqual(envelope.event_time[:10], envelope.available_time)
        self.assertNotEqual(envelope.event_time, envelope.retrieval_time)

    def test_late_publication_excluded_from_earlier_cutoff(self) -> None:
        from dataclasses import replace

        from market_platform_foundation.cftc.datasets import CotDataset, dataset_spec
        from market_platform_foundation.cftc.mapping import CotProductMapper
        from market_platform_foundation.cftc.normalize import normalize_api_rows

        payload = load_fixture("holiday_delayed_release.json")
        spec = dataset_spec(CotDataset.TFF_FUTURES_ONLY)
        observations = list(
            normalize_api_rows(
                payload["rows"],
                spec=spec,
                mapper=CotProductMapper(),
                observed_time="2026-11-30T20:00:00Z",
                retrieved_time="2026-11-30T20:00:00Z",
            )
        )
        registry = get_registry()
        registry.bootstrap_catalog()
        admitted = [
            admit_positioning_observation(item, retrieved_time="2026-11-30T20:00:00Z") for item in observations
        ]
        for item in admitted:
            registry.admit_observation(item)
        early = [item for item in admitted if eligible_at_decision_time(item, "2026-11-28T00:00:00Z")]
        late = [item for item in admitted if eligible_at_decision_time(item, "2026-12-01T00:00:00Z")]
        self.assertEqual(len(early), 0)
        self.assertGreater(len(late), 0)

    def test_revision_versions_are_distinct_observations(self) -> None:
        payload = load_fixture("source_revision.json")
        versioned = positioning_observations_from_revision_fixture(payload)
        self.assertEqual(len(versioned), 10)
        registry = get_registry()
        registry.bootstrap_catalog()
        ids = set()
        for obs, revision_number in versioned:
            envelope = admit_positioning_observation(
                obs,
                retrieved_time=obs.observed_time,
                revision_number=max(0, revision_number - 1),
            )
            ids.add(registry.admit_observation(envelope))
        self.assertEqual(len(ids), 10)

    def test_later_revision_excluded_from_earlier_cutoff(self) -> None:
        payload = load_fixture("source_revision.json")
        versioned = positioning_observations_from_revision_fixture(payload)
        registry = get_registry()
        registry.bootstrap_catalog()
        admitted = []
        for obs, revision_number in versioned:
            envelope = admit_positioning_observation(
                obs,
                retrieved_time=obs.observed_time,
                revision_number=max(0, revision_number - 1),
            )
            admitted.append(registry.admit_observation(envelope))
        envelopes = [registry.get_observation(item) for item in admitted]
        v1 = [item for item in envelopes if item.revision_classification == RevisionClassification.ORIGINAL_OR_AS_REPORTED]
        v2 = [item for item in envelopes if item.revision_classification == RevisionClassification.VINTAGE_IDENTIFIED]
        self.assertTrue(v1)
        self.assertTrue(v2)
        early_cutoff = "2026-08-14T20:00:00Z"
        late_cutoff = "2026-08-15T20:00:00Z"
        self.assertTrue(all(eligible_at_decision_time(item, early_cutoff) for item in v1))
        self.assertFalse(any(eligible_at_decision_time(item, early_cutoff) for item in v2))
        self.assertTrue(any(eligible_at_decision_time(item, late_cutoff) for item in v2))

    def test_retrieval_later_than_publication_does_not_rewrite_publication(self) -> None:
        payload = load_fixture("positioning_reference_vertical.json")
        observations = positioning_observations_from_fixture(payload)
        obs = observations[0]
        envelope = admit_positioning_observation(obs, retrieved_time="2026-08-20T12:00:00Z")
        self.assertEqual(envelope.available_time, obs.publication_time)
        self.assertEqual(envelope.retrieval_time, "2026-08-20T12:00:00Z")
        release = release_for_position_date(__import__("datetime").date.fromisoformat("2026-08-11"))
        assert release is not None
        self.assertEqual(envelope.available_time, publication_time_utc(release.publication_date))

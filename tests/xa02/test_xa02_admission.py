"""XA-02 admission, identity, and unit tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.fred.contracts import MacroObservation
from market_platform_foundation.fred.normalize import normalize_v1_observation_row, parse_fred_value
from market_platform_foundation.fred.quality import FredQualityFlag
from market_platform_foundation.fred.registry import lookup_canonical
from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.admission import (
    admit_macro_observation,
    classify_revision,
    eligible_at_decision_time,
)
from market_platform_foundation.xa02.enums import RevisionClassification
from market_platform_foundation.xa02.errors import Xa02Error, Xa02ErrorCode
from market_platform_foundation.xa02.fixtures import admit_fixture
from market_platform_foundation.xa02.identity import derive_observation_id_from_macro
from market_platform_foundation.xa02.registry import AdmissionRegistry, get_registry, reset_registry_for_tests


class Xa02AdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_registry_for_tests()

    def _macro_obs(self, *, value: str = "4.25") -> MacroObservation:
        entry = lookup_canonical("US_10Y_TREASURY_YIELD")
        assert entry is not None
        return normalize_v1_observation_row(
            {
                "realtime_start": "2026-02-12",
                "realtime_end": "9999-12-31",
                "date": "2026-02-12",
                "value": value,
            },
            entry=entry,
            retrieved_time="2026-02-13T16:00:00Z",
            observed_time="2026-02-12T22:00:00Z",
        )

    def test_series_id_not_canonical_indicator_id(self) -> None:
        obs = self._macro_obs()
        self.assertEqual(obs.series_id, "DGS10")
        self.assertEqual(obs.canonical_indicator_id, "US_10Y_TREASURY_YIELD")
        self.assertNotEqual(obs.series_id, obs.canonical_indicator_id)

    def test_observation_id_distinct_from_indicator_id(self) -> None:
        obs = self._macro_obs()
        observation_id = derive_observation_id_from_macro(obs)
        self.assertTrue(observation_id.startswith("XA02:OBS:"))
        self.assertNotEqual(observation_id, obs.canonical_indicator_id)

    def test_idempotent_admission(self) -> None:
        registry = AdmissionRegistry()
        registry.bootstrap_catalog()
        admitted = admit_macro_observation(self._macro_obs())
        first = registry.admit_observation(admitted)
        second = registry.admit_observation(admitted)
        self.assertEqual(first, second)

    def test_conflict_on_same_identity_changed_value(self) -> None:
        registry = AdmissionRegistry()
        registry.bootstrap_catalog()
        first = admit_macro_observation(self._macro_obs(value="4.25"))
        second = admit_macro_observation(self._macro_obs(value="4.30"))
        registry.admit_observation(first)
        with self.assertRaises(Xa02Error) as ctx:
            registry.admit_observation(second)
        self.assertEqual(ctx.exception.code, Xa02ErrorCode.OBSERVATION_CONFLICT)

    def test_missing_value_not_zero(self) -> None:
        raw, normalized, flags = parse_fred_value(".")
        self.assertIsNone(normalized)
        self.assertIn(FredQualityFlag.MISSING_VALUE.value, flags)
        obs = self._macro_obs(value=".")
        admitted = admit_macro_observation(obs)
        self.assertIsNone(admitted.normalized_value)
        self.assertIsNone(admitted.raw_value)

    def test_zero_value_preserved(self) -> None:
        obs = self._macro_obs(value="0")
        admitted = admit_macro_observation(obs)
        self.assertEqual(admitted.normalized_value, 0.0)
        self.assertEqual(admitted.raw_value, "0")

    def test_fixture_vertical_round_trip(self) -> None:
        result = admit_fixture(fixture_name="rates_reference_vertical.json")
        self.assertEqual(result["observation_count"], 5)
        registry = get_registry()
        summary = registry.indicator_summary("US_10Y_TREASURY_YIELD")
        self.assertEqual(summary.provider_series_id, "DGS10")
        self.assertEqual(summary.units, "Percent")
        self.assertEqual(summary.observation_count, 1)
        self.assertEqual(summary.relationship_count, 1)

    def test_not_admitted_series_rejected(self) -> None:
        entry = lookup_canonical("US_HEADLINE_CPI")
        assert entry is not None
        obs = normalize_v1_observation_row(
            {"realtime_start": "2026-02-12", "realtime_end": "9999-12-31", "date": "2026-01-01", "value": "300"},
            entry=entry,
            retrieved_time="2026-02-13T16:00:00Z",
            observed_time="2026-02-13T16:00:00Z",
        )
        with self.assertRaises(Xa02Error) as ctx:
            admit_macro_observation(obs)
        self.assertEqual(ctx.exception.code, Xa02ErrorCode.NOT_ADMITTED_SERIES)

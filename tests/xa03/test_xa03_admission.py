"""XA-03 admission, identity, and unit tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.cftc.contracts import CotParticipantCategory
from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.enums import ObservationPayloadKind, SourceProvider
from market_platform_foundation.xa02.envelope import admitted_observation_to_envelope
from market_platform_foundation.xa02.fixtures import admit_fixture as admit_fred_fixture
from market_platform_foundation.xa02.registry import reset_registry_for_tests as reset_xa02_registry
from market_platform_foundation.xa03.admission import admit_positioning_observation
from market_platform_foundation.xa03.errors import Xa03Error, Xa03ErrorCode
from market_platform_foundation.xa03.fixtures import admit_fixture, load_fixture, positioning_observations_from_fixture
from market_platform_foundation.xa03.identity import market_report_id
from market_platform_foundation.xa03.registry import PositioningAdmissionRegistry, get_registry, reset_registry_for_tests


class Xa03AdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_registry_for_tests()

    def test_market_code_not_market_report_id(self) -> None:
        payload = load_fixture("positioning_reference_vertical.json")
        observations = positioning_observations_from_fixture(payload)
        es = next(item for item in observations if item.cftc_contract_market_code == "13874+")
        report_id = market_report_id(
            cftc_contract_market_code=es.cftc_contract_market_code,
            report_family=es.report_family.value,
            position_scope=es.position_scope.value,
        )
        self.assertEqual(es.cftc_contract_market_code, "13874+")
        self.assertTrue(report_id.startswith("CFTC_MARKET:"))
        self.assertNotEqual(es.cftc_contract_market_code, report_id)

    def test_observation_id_distinct_from_market_report_id(self) -> None:
        payload = load_fixture("positioning_reference_vertical.json")
        observations = positioning_observations_from_fixture(payload)
        obs = observations[0]
        admitted = admit_positioning_observation(obs, retrieved_time="2026-08-14T19:35:00Z")
        self.assertTrue(admitted.observation_id.startswith("XA03:OBS:"))
        self.assertNotEqual(admitted.observation_id, admitted.source_subject_id)

    def test_idempotent_admission(self) -> None:
        registry = get_registry()
        registry.bootstrap_catalog()
        payload = load_fixture("positioning_reference_vertical.json")
        obs = positioning_observations_from_fixture(payload)[0]
        envelope = admit_positioning_observation(obs, retrieved_time="2026-08-14T19:35:00Z")
        first = registry.admit_observation(envelope)
        second = registry.admit_observation(envelope)
        self.assertEqual(first, second)

    def test_conflict_on_same_identity_changed_value(self) -> None:
        from dataclasses import replace

        registry = get_registry()
        registry.bootstrap_catalog()
        payload = load_fixture("positioning_reference_vertical.json")
        obs = positioning_observations_from_fixture(payload)[0]
        first = admit_positioning_observation(obs, retrieved_time="2026-08-14T19:35:00Z")
        registry.admit_observation(first)
        assert first.positioning_payload is not None
        tampered_payload = replace(first.positioning_payload, long_positions=(first.positioning_payload.long_positions or 0) + 1)
        second = replace(first, positioning_payload=tampered_payload)
        with self.assertRaises(Xa03Error) as ctx:
            registry.admit_observation(second)
        self.assertEqual(ctx.exception.code, Xa03ErrorCode.OBSERVATION_CONFLICT)

    def test_missing_position_not_zero(self) -> None:
        from dataclasses import replace

        payload = load_fixture("positioning_reference_vertical.json")
        observations = positioning_observations_from_fixture(payload)
        obs = next(item for item in observations if item.participant_category == CotParticipantCategory.LEVERAGED_FUNDS)
        admitted = admit_positioning_observation(obs, retrieved_time="2026-08-14T19:35:00Z")
        assert admitted.positioning_payload is not None
        self.assertIsNotNone(admitted.positioning_payload.long_positions)
        missing_obs = replace(obs, long_positions=None)
        missing_admitted = admit_positioning_observation(missing_obs, retrieved_time="2026-08-14T19:35:00Z")
        assert missing_admitted.positioning_payload is not None
        self.assertIsNone(missing_admitted.positioning_payload.long_positions)

    def test_position_unit_retained(self) -> None:
        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        registry = get_registry()
        envelope = registry.get_observation(result["observation_ids"][0])
        assert envelope.positioning_payload is not None
        self.assertEqual(envelope.positioning_payload.position_unit, "contracts")
        self.assertEqual(envelope.positioning_payload.open_interest_unit, "contracts")

    def test_fixture_vertical_round_trip(self) -> None:
        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        self.assertEqual(len(result["market_report_ids"]), 5)
        self.assertGreater(result["observation_count"], 5)
        registry = get_registry()
        es_market = "CFTC_MARKET:13874+:TFF:FUTURES_ONLY"
        observations = registry.list_observations_for_market(es_market)
        relationships = registry.list_relationships_for_market(es_market)
        self.assertGreater(len(observations), 0)
        self.assertEqual(len(relationships), 1)

    def test_not_admitted_market_rejected(self) -> None:
        from dataclasses import replace

        payload = load_fixture("tff_futures_only_es.json")
        observations = positioning_observations_from_fixture(payload)
        obs = observations[0]
        tampered = replace(obs, cftc_contract_market_code="999999")
        with self.assertRaises(Xa03Error) as ctx:
            admit_positioning_observation(tampered, retrieved_time="2026-08-14T19:35:00Z")
        self.assertEqual(ctx.exception.code, Xa03ErrorCode.NOT_ADMITTED_MARKET)


class Xa03SourceNeutralTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_registry_for_tests()

    def test_fred_admission_still_works(self) -> None:
        fred_result = admit_fred_fixture(fixture_name="rates_reference_vertical.json")
        self.assertEqual(fred_result["observation_count"], 5)

    def test_cftc_uses_common_envelope(self) -> None:
        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        envelope = get_registry().get_observation(result["observation_ids"][0])
        self.assertEqual(envelope.payload_kind, ObservationPayloadKind.POSITIONING_STRUCTURED)
        self.assertEqual(envelope.source_provider, SourceProvider.CFTC)
        self.assertIsNone(envelope.scalar_payload)
        self.assertIsNotNone(envelope.positioning_payload)

    def test_fred_envelope_conversion(self) -> None:
        admit_fred_fixture(fixture_name="rates_reference_vertical.json")
        from market_platform_foundation.xa02.registry import get_registry as get_xa02

        fred_obs = get_xa02().list_observations_for_indicator("US_10Y_TREASURY_YIELD")[0]
        envelope = admitted_observation_to_envelope(fred_obs)
        self.assertEqual(envelope.payload_kind, ObservationPayloadKind.SCALAR_MACRO)
        self.assertEqual(envelope.source_provider, SourceProvider.FRED)

    def test_payloads_remain_typed_not_blob(self) -> None:
        from dataclasses import fields

        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        envelope = get_registry().get_observation(result["observation_ids"][0])
        assert envelope.positioning_payload is not None
        self.assertIsInstance(envelope.positioning_payload.participant_category, str)
        self.assertFalse(any(field.name == "payload_json" for field in fields(envelope)))

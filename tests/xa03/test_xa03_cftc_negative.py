"""XA-03 CFTC-specific negative tests — no analytics or motive inference."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.registry import reset_registry_for_tests as reset_xa02_registry
from market_platform_foundation.xa03.fixtures import admit_fixture, load_fixture, positioning_observations_from_fixture
from market_platform_foundation.xa03.registry import get_registry, reset_registry_for_tests


class Xa03CftcNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_registry_for_tests()

    def test_trader_category_not_instrument(self) -> None:
        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        registry = get_registry()
        envelope = registry.get_observation(result["observation_ids"][0])
        assert envelope.positioning_payload is not None
        category = envelope.positioning_payload.participant_category
        self.assertNotEqual(category, envelope.source_subject_id)
        self.assertFalse(category.startswith("XA:"))

    def test_market_report_not_futures_contract(self) -> None:
        registry = get_registry()
        registry.bootstrap_catalog()
        rel = registry.list_relationships_for_market("CFTC_MARKET:13874+:TFF:FUTURES_ONLY")[0]
        from market_platform_foundation.xa01.registry import get_registry as get_xa01

        record = get_xa01().get(rel.target_xa_canonical_id)
        self.assertNotEqual(rel.subject_id, rel.target_xa_canonical_id)
        self.assertEqual(record.descriptor.identity.instrument_kind.value, "FUTURE_FAMILY")

    def test_long_short_are_reported_quantities_not_signals(self) -> None:
        from dataclasses import fields

        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        registry = get_registry()
        envelope = registry.get_observation(result["observation_ids"][0])
        field_names = {field.name for field in fields(envelope)}
        self.assertNotIn("net_position", field_names)
        self.assertNotIn("squeeze_signal", field_names)
        self.assertNotIn("crowding_score", field_names)
        assert envelope.positioning_payload is not None
        self.assertIn("long_positions", envelope.positioning_payload.__dataclass_fields__)

    def test_no_silent_net_derivation_in_admission(self) -> None:
        from market_platform_foundation.xa02.contracts import envelope_to_dict

        result = admit_fixture(fixture_name="positioning_reference_vertical.json")
        registry = get_registry()
        envelope = registry.get_observation(result["observation_ids"][0])
        serialized = envelope_to_dict(envelope)
        payload = serialized["payload"]
        self.assertNotIn("net_position", payload)
        self.assertNotIn("net_speculative", payload)

    def test_participant_category_preserved_not_motive(self) -> None:
        payload = load_fixture("positioning_reference_vertical.json")
        observations = positioning_observations_from_fixture(payload)
        categories = {item.participant_category.value for item in observations}
        self.assertIn("LEVERAGED_FUNDS", categories)
        for category in categories:
            self.assertNotIn("BULLISH", category)
            self.assertNotIn("CONVICTION", category)

"""XA-04 codec round-trip tests."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa04.codec import (  # noqa: E402
    admission_envelope_from_dict,
    admitted_observation_from_dict,
    cross_asset_relationship_from_dict,
    encode_document,
    instrument_record_from_dict,
)
from tests.xa04.test_xa04_fixtures import populate_vertical_slice_repository  # noqa: E402


class Xa04CodecTests(unittest.TestCase):
    def test_instrument_round_trip(self) -> None:
        repo, state = populate_vertical_slice_repository()
        gc_id = str(state["gc_canonical_id"])
        record = repo.get_instrument(gc_id)
        assert record is not None
        document = encode_document(record)
        restored = instrument_record_from_dict({k: v for k, v in document.items() if k != "_id"})
        self.assertEqual(restored, record)

    def test_scalar_observation_round_trip(self) -> None:
        repo, state = populate_vertical_slice_repository()
        obs_id = state["fred"]["observation_ids"][0]  # type: ignore[index]
        observation = repo.get_scalar_observation(obs_id)
        assert observation is not None
        document = encode_document(observation)
        restored = admitted_observation_from_dict({k: v for k, v in document.items() if k != "_id"})
        self.assertEqual(restored, observation)

    def test_envelope_round_trip(self) -> None:
        repo, state = populate_vertical_slice_repository()
        obs_id = state["cftc"]["observation_ids"][0]  # type: ignore[index]
        envelope = repo.get_admission_envelope(obs_id)
        assert envelope is not None
        document = encode_document(envelope)
        restored = admission_envelope_from_dict({k: v for k, v in document.items() if k != "_id"})
        self.assertEqual(restored, envelope)

    def test_relationship_round_trip(self) -> None:
        repo, _state = populate_vertical_slice_repository()
        relationships = repo.list_cross_asset_relationships_for_target(str(_state["gc_canonical_id"]))
        self.assertTrue(relationships)
        relationship = relationships[0]
        document = encode_document(relationship)
        restored = cross_asset_relationship_from_dict({k: v for k, v in document.items() if k != "_id"})
        self.assertEqual(restored, relationship)

    def test_identity_stable_after_encode(self) -> None:
        repo, state = populate_vertical_slice_repository()
        gc_id = str(state["gc_canonical_id"])
        record = repo.get_instrument(gc_id)
        assert record is not None
        mutated = replace(record, descriptor=replace(record.descriptor, display_name="changed"))
        self.assertEqual(record.descriptor.identity.canonical_id, mutated.descriptor.identity.canonical_id)


if __name__ == "__main__":
    unittest.main()

"""Task 3 — fixed-hash SS-family card fixture determinism tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import canonical_bytes, write_canonical_json
from market_platform_foundation.research.decision_research.ss_cards import build_ss_family_cards

FIXTURE = ROOT / "tests" / "fixtures" / "research" / "experiment_cards.json"

# Fixed hashes recorded at 2026-08-22 (Task 3). A change to any preregistered
# field must change these — and that is a NEW card, never a mutation.
EXPECTED_HASHES: dict[str, str] = {
    "SS-BASE": "69D2C12AD3BF31BA2ED52FA774F82F06F831AA1800243C42A6955032FB87F40D",
    "SS-CAT": "F02459CD1AD038CE94B559997A2746445067402C86E40D287F6051E142736FDF",
    "SS-FV-DISC": "D080C33EB8E2F8B9D7F5789E023B690ADD28BEC2C6A46B9F918911A07EE014EC",
    "SS-MKT": "71F7E466CC816D9F319D6E81A6CB4D6663F59571AE82935158E99211D16E605A",
    "SS-OF": "3D68CBEFB74E78B7AD36B8C444101CAF021D033FE948E88F4CDFB6229BB1C521",
    "SS-OF-CAT": "08E48D1B5474BED39275158C7CC49E76909CF5A83B775A9DD63E72790503E518",
}


class ExperimentCardFixtureTests(unittest.TestCase):
    def test_fixture_matches_builder_byte_for_byte(self) -> None:
        cards = build_ss_family_cards()
        payload = [cards[eid].to_dict() for eid in sorted(cards)]
        self.assertEqual(FIXTURE.read_bytes(), canonical_bytes(payload))

    def test_committed_hashes_are_fixed(self) -> None:
        cards = build_ss_family_cards()
        for experiment_id, expected in EXPECTED_HASHES.items():
            self.assertEqual(cards[experiment_id].card_hash, expected, experiment_id)

    def test_settled_field_values_present(self) -> None:
        cards = build_ss_family_cards()
        self.assertEqual(cards["SS-BASE"].min_sample_oos, 150)
        self.assertEqual(cards["SS-BASE"].primary_metric, "oos_positive_base_rate")
        for eid in ("SS-OF", "SS-CAT", "SS-MKT", "SS-OF-CAT", "SS-FV-DISC"):
            self.assertEqual(cards[eid].primary_metric, "oos_precision_delta_vs_baseline")
            self.assertEqual(cards[eid].primary_metric_threshold, 0.05)
        self.assertEqual(cards["SS-OF-CAT"].hypothesis_label, "EXPLORATORY")
        self.assertEqual(cards["SS-MKT"].min_sample_oos, 45)

    def test_fixture_registers_and_loads_through_registry(self) -> None:
        import tempfile

        from market_platform_foundation.research.decision_research.registry import ExperimentCardRegistry

        cards = build_ss_family_cards()
        with tempfile.TemporaryDirectory() as tmp:
            registry = ExperimentCardRegistry(Path(tmp))
            for card in cards.values():
                registry.register(card)
            self.assertEqual(len(registry.list_cards()), 6)
            loaded = registry.load(cards["SS-BASE"].card_hash)
            self.assertEqual(loaded.card_id, cards["SS-BASE"].card_id)


if __name__ == "__main__":
    unittest.main()

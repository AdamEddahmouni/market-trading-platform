"""Task 1+2 — ExperimentCard hashing/identity + hash-bound registry tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.research.decision_research.cards import ExperimentCard
from market_platform_foundation.research.decision_research.registry import (
    ExperimentCardRegistry,
    verify_experiment_card_registration,
)

PREREG = 1_784_678_400_000_000_000  # fixed, preregistered timestamp constant


def build_card(
    *,
    experiment_id: str = "SS-BASE",
    family: str = "SHORT_SQUEEZE",
    hypothesis_label: str = "CONFIRMATORY",
    baseline_id: str = "SS-BASE",
    added_evidence: tuple[str, ...] = (),
    primary_metric: str = "oos_positive_base_rate",
    min_sample_oos: int = 150,
    primary_metric_threshold: float = 0.05,
    feature_spec: dict | None = None,
) -> ExperimentCard:
    return ExperimentCard(
        experiment_id=experiment_id,
        family=family,
        hypothesis_label=hypothesis_label,
        baseline_id=baseline_id,
        added_evidence=added_evidence,
        feature_spec=feature_spec
        or {"required": ["SQUEEZE_STATE"], "min_quality": {}, "min_freshness_ms": {}},
        outcome_spec={
            "horizon_ns": 1_800_000_000_000,
            "return_basis": "MARK_TO_MARK",
            "cost_model_version": "execution_book_aware_v1",
        },
        inclusion_criteria=("admitted_fixture",),
        exclusion_criteria=("no_retroactive_finviz",),
        primary_metric=primary_metric,
        min_sample_oos=min_sample_oos,
        primary_metric_threshold=primary_metric_threshold,
        preregistered_at_ns=PREREG,
    )


class ExperimentCardCodingTests(unittest.TestCase):
    def test_card_id_and_hash_are_deterministic(self) -> None:
        a = build_card()
        b = build_card()
        self.assertEqual(a.card_id, b.card_id)
        self.assertEqual(a.card_hash, b.card_hash)
        self.assertTrue(a.card_id.startswith("CARD-"))

    def test_card_id_is_uuid5_of_canonical_body(self) -> None:
        from market_platform_foundation.research.decision_research.cards import CARD_NAMESPACE

        import uuid

        card = build_card()
        expected = "CARD-" + str(uuid.uuid5(CARD_NAMESPACE, canonical_bytes(card._body()).decode("latin-1")))
        self.assertEqual(card.card_id, expected)

    def test_hash_covers_canonical_body_not_card_meta(self) -> None:
        card = build_card()
        expected = sha256_bytes(canonical_bytes(card._body()))
        self.assertEqual(card.card_hash, expected)

    def test_added_evidence_order_is_canonicalized(self) -> None:
        a = build_card(experiment_id="SS-OF", added_evidence=("ORDER_FLOW_CVD", "CATALYST"))
        b = build_card(experiment_id="SS-OF", added_evidence=("CATALYST", "ORDER_FLOW_CVD"))
        self.assertEqual(a.card_hash, b.card_hash)
        self.assertEqual(a.card_id, b.card_id)

    def test_any_metric_field_change_creates_new_card_identity(self) -> None:
        a = build_card()
        b = build_card(min_sample_oos=151)
        c = build_card(primary_metric_threshold=0.10)
        self.assertNotEqual(a.card_hash, b.card_hash)
        self.assertNotEqual(a.card_hash, c.card_hash)

    def test_from_dict_round_trip_preserves_identity(self) -> None:
        card = build_card()
        restored = ExperimentCard.from_dict(card.to_dict())
        self.assertEqual(restored.card_hash, card.card_hash)
        self.assertEqual(restored.card_id, card.card_id)
        self.assertEqual(restored.to_dict(), card.to_dict())

    def test_from_dict_rejects_body_hash_mismatch(self) -> None:
        payload = build_card(experiment_id="SS-CAT", added_evidence=("CATALYST",)).to_dict()
        # Tamper with the body but keep the stale card_hash from the original.
        payload["min_sample_oos"] = 999
        with self.assertRaises(ValueError) as ctx:
            ExperimentCard.from_dict(payload)
        self.assertIn("CARD_HASH_MISMATCH", str(ctx.exception))

    def test_construct_rejects_invalid_identity(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentCard(
                experiment_id="",
                family="SHORT_SQUEEZE",
                hypothesis_label="CONFIRMATORY",
                baseline_id="SS-BASE",
                added_evidence=(),
                feature_spec={},
                outcome_spec={},
                inclusion_criteria=(),
                exclusion_criteria=(),
                primary_metric="x",
                min_sample_oos=1,
            )
        with self.assertRaises(ValueError):
            build_card(hypothesis_label="NOT_A_LABEL")
        with self.assertRaises(ValueError):
            build_card(min_sample_oos=0)

    def test_card_json_is_canonical_lf(self) -> None:
        card = build_card()
        path = Path(tempfile.mkdtemp()) / "card.json"
        from market_platform_foundation.canonical import write_canonical_json

        write_canonical_json(path, card.to_dict())
        raw = path.read_bytes()
        self.assertNotIn(b"\r\n", raw)
        self.assertEqual(json.loads(raw), card.to_dict())


class ExperimentCardRegistryTests(unittest.TestCase):
    def _registry(self) -> ExperimentCardRegistry:
        return ExperimentCardRegistry(Path(tempfile.mkdtemp()))

    def test_register_load_round_trip(self) -> None:
        reg = self._registry()
        card = build_card()
        reg.register(card)
        loaded = reg.load(card.card_hash)
        self.assertEqual(loaded.card_hash, card.card_hash)
        self.assertEqual(loaded.to_dict(), card.to_dict())

    def test_register_is_idempotent_and_byte_stable(self) -> None:
        reg = self._registry()
        card = build_card()
        reg.register(card)
        first = reg.path_for(card.card_hash).read_bytes()
        reg.register(card)  # no-op
        self.assertEqual(reg.path_for(card.card_hash).read_bytes(), first)

    def test_get_by_experiment_id_and_list(self) -> None:
        reg = self._registry()
        for eid in ("SS-BASE", "SS-OF", "SS-CAT"):
            reg.register(build_card(experiment_id=eid))
        self.assertEqual(sorted(c.experiment_id for c in reg.list_cards()), ["SS-BASE", "SS-CAT", "SS-OF"])
        self.assertEqual(reg.get("SS-OF").experiment_id, "SS-OF")
        self.assertIsNone(reg.get("SS-UNKNOWN"))

    def test_verify_fails_closed_on_absent_hash(self) -> None:
        card = build_card()
        reg = self._registry()
        with self.assertRaises(ValueError) as ctx:
            verify_experiment_card_registration(card, {"bound_card_hashes": [card.card_hash]}, registry=reg)
        self.assertIn("EXPERIMENT_CARD_NOT_REGISTERED", str(ctx.exception))

    def test_verify_fails_closed_on_unbound_run(self) -> None:
        card = build_card()
        reg = self._registry()
        reg.register(card)
        with self.assertRaises(ValueError) as ctx:
            verify_experiment_card_registration(card, {}, registry=reg)
        self.assertIn("EXPERIMENT_CARD_HASH_UNBOUND", str(ctx.exception))
        with self.assertRaises(ValueError):
            verify_experiment_card_registration(card, {"bound_card_hashes": []}, registry=reg)

    def test_verify_passes_when_registered_and_bound(self) -> None:
        card = build_card()
        reg = self._registry()
        reg.register(card)
        self.assertTrue(
            verify_experiment_card_registration(card, {"bound_card_hashes": [card.card_hash]}, registry=reg)
        )


if __name__ == "__main__":
    unittest.main()

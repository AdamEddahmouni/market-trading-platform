"""Full-universe coverage planning: classification, fair order, batch and round bounds, reconciliation."""

from __future__ import annotations

import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.candidate_reduction import MAX_INTAKE, MAX_SELECTED, build_candidate  # noqa: E402
from market_platform_foundation.intelligence.inference.coverage_plan import (  # noqa: E402
    AI_EVALUATED, AWAITING_EVIDENCE, ELIGIBLE, EVIDENCE_STALE, EVIDENCE_UNAVAILABLE, INELIGIBLE, PROVIDER_UNAVAILABLE,
    UNPROCESSED, UNSUPPORTED, budget_requirement, chunks, classify, fair_order, reconciles, reduction_rounds, tally,
)
from market_platform_foundation.market_data.freshness_contract import evaluate  # noqa: E402

NOW = "2026-10-02T15:00:00Z"
INSTRUMENT = {"instrument_id": "EQ:A", "symbol": "A", "universe": "US_EQUITIES", "asset_class": "EQUITY"}


def status(*, as_of: str | None = NOW, state: str = "AVAILABLE") -> dict:
    return evaluate(capability="market_snapshot", source="IMP_TEST", delivery_mode="SNAPSHOT", now=NOW, as_of=as_of,
                    stale_after_ms=60000, policy="L1_EVENT_V1", basis="PROVIDER_AS_OF", state=state)


def candidate(*observations: tuple) -> dict:
    return build_candidate(INSTRUMENT, list(observations), now=NOW)


class ClassificationTests(unittest.TestCase):
    def test_a_row_is_eligible_exactly_when_the_existing_rule_calls_it_sufficient(self):
        both = candidate(("QUOTE", status(), {"price": 10.0}, []), ("TECHNICALS", status(), {"volume": 5.0}, []))
        self.assertTrue(both["sufficient"])
        self.assertEqual(classify(both), (ELIGIBLE, []))

    def test_a_current_price_alone_is_ineligible_by_the_existing_rule_not_a_new_threshold(self):
        alone = candidate(("QUOTE", status(), {"price": 10.0}, []))
        self.assertEqual(classify(alone), (INELIGIBLE, ["NO_SECOND_STRONG_EVIDENCE"]))

    def test_missing_stale_and_unavailable_evidence_are_never_an_economic_rejection(self):
        stale = candidate(("QUOTE", status(as_of="2026-10-02T14:00:00Z"), {"price": 10.0}, []))
        self.assertEqual(classify(stale)[0], EVIDENCE_STALE)
        no_clock = candidate(("QUOTE", status(as_of=None), {"price": 10.0}, []))
        self.assertEqual(classify(no_clock), (EVIDENCE_UNAVAILABLE, ["NO_OBSERVATION_TIME"]))
        nothing = candidate()
        self.assertEqual(classify(nothing), (EVIDENCE_UNAVAILABLE, ["NO_QUOTE_OBSERVATION"]))
        future = candidate(("QUOTE", status(as_of="2026-10-02T16:00:00Z"), {"price": 10.0}, []))
        self.assertEqual(classify(future), (EVIDENCE_UNAVAILABLE, ["FUTURE_OBSERVATION_TIME"]))
        for found in (stale, no_clock, nothing, future):
            self.assertNotIn(classify(found)[0], (INELIGIBLE, ELIGIBLE, AI_EVALUATED))

    def test_provider_and_entitlement_states_keep_their_own_class(self):
        self.assertEqual(classify(candidate(), provider_reason="MARKET_SNAPSHOT_UNAVAILABLE"),
                         (PROVIDER_UNAVAILABLE, ["MARKET_SNAPSHOT_UNAVAILABLE"]))
        self.assertEqual(classify(candidate(), refused=True), (UNSUPPORTED, ["MOOMOO_QUOTE_NOT_ENTITLED"]))
        self.assertEqual(classify(candidate(("QUOTE", status(state="NOT_ENTITLED"), {}, [])))[0], UNSUPPORTED)
        self.assertEqual(classify(candidate(("QUOTE", status(state="AWAITING_DATA"), {}, [])))[0], AWAITING_EVIDENCE)
        self.assertEqual(classify(candidate(("QUOTE", status(state="PROVIDER_UNAVAILABLE"), {}, [])))[0], PROVIDER_UNAVAILABLE)


class OrderAndBatchTests(unittest.TestCase):
    def test_order_depends_on_identity_only(self):
        ids = [f"EQ:S{index:05d}" for index in range(500)]
        shuffled = list(ids)
        random.Random(7).shuffle(shuffled)
        self.assertEqual(fair_order("set-1", ids), fair_order("set-1", shuffled))
        self.assertEqual(fair_order("set-1", ids), fair_order("set-1", list(reversed(ids))))
        self.assertNotEqual(fair_order("set-1", ids), ids)
        self.assertNotEqual(fair_order("set-1", ids), fair_order("set-2", ids))

    def test_the_head_of_the_sorted_result_is_not_concentrated_in_the_first_batch(self):
        ids = [f"EQ:S{index:05d}" for index in range(4600)]
        first = set(chunks(fair_order("set-1", ids))[0])
        self.assertLess(len(first & set(ids[:MAX_INTAKE])), 10)
        # Neither a short nor a long identifier is favoured.
        mixed = ["EQ:A", "EQ:" + "L" * 40, *ids[:98]]
        position = {value: index for index, value in enumerate(fair_order("set-1", mixed))}
        self.assertNotEqual({position["EQ:A"], position["EQ:" + "L" * 40]}, {0, 1})

    def test_every_row_is_in_exactly_one_batch_at_every_size(self):
        for size in (0, 1, 49, 50, 51, 100, 500, 4600, 20000):
            ids = [f"EQ:S{index:05d}" for index in range(size)]
            batches = chunks(fair_order("set-1", ids))
            self.assertEqual(len(batches), math.ceil(size / MAX_INTAKE))
            self.assertTrue(all(0 < len(batch) <= MAX_INTAKE for batch in batches))
            self.assertEqual(sorted(value for batch in batches for value in batch), ids)

    def test_reduction_rounds_end_in_one_request_and_never_grow(self):
        self.assertEqual(reduction_rounds(0), [])
        self.assertEqual(reduction_rounds(1), [])
        self.assertEqual(reduction_rounds(2), [1])
        self.assertEqual(reduction_rounds(10), [1])
        self.assertEqual(reduction_rounds(11), [2, 1])
        self.assertEqual(reduction_rounds(92), [10, 1])
        self.assertEqual(reduction_rounds(400), [40, 4, 1])
        for batches in range(2, 2000, 37):
            rounds = reduction_rounds(batches)
            self.assertEqual(rounds[-1], 1)
            self.assertEqual(rounds, sorted(rounds, reverse=True))
            self.assertLessEqual(rounds[0], math.ceil(batches * MAX_SELECTED / MAX_INTAKE))

    def test_the_budget_requirement_includes_the_global_comparison(self):
        self.assertEqual(budget_requirement([], []), {"requests": 0, "tokens": 0, "batch_tokens": 0, "reduction_tokens": 0, "reduction_calls": 0})
        one = budget_requirement([40_000], reduction_rounds(1))
        self.assertEqual((one["requests"], one["tokens"]), (1, 40_000))
        many = budget_requirement([40_000, 42_000, 30_000], reduction_rounds(3))
        self.assertEqual(many["requests"], 4)
        self.assertEqual(many["tokens"], 112_000 + 42_000)
        self.assertEqual(many["reduction_tokens"], 42_000)


class ReconciliationTests(unittest.TestCase):
    def test_every_class_lands_in_exactly_one_bucket(self):
        classes = {"a": (AI_EVALUATED, []), "b": (INELIGIBLE, ["NO_SECOND_STRONG_EVIDENCE"]), "c": (UNSUPPORTED, ["NOT_ENTITLED"]),
                   "d": (EVIDENCE_STALE, ["STALE"]), "e": (EVIDENCE_UNAVAILABLE, ["NO_OBSERVATION_TIME"]),
                   "f": (PROVIDER_UNAVAILABLE, ["MARKET_SNAPSHOT_UNAVAILABLE"]), "g": (AWAITING_EVIDENCE, ["PENDING"]),
                   "h": (UNPROCESSED, ["BUDGET_INSUFFICIENT"]), "i": (ELIGIBLE, [])}
        counts = tally(classes)
        self.assertEqual({key: counts[key] for key in ("evaluated", "ineligible", "evidence_blocked", "unprocessed")},
                         {"evaluated": 1, "ineligible": 2, "evidence_blocked": 4, "unprocessed": 2})
        self.assertTrue(reconciles(counts, len(classes)))
        self.assertFalse(reconciles(counts, len(classes) + 1))
        self.assertEqual(counts["reasons"]["UNPROCESSED:BUDGET_INSUFFICIENT"], 1)
        self.assertEqual(counts["reasons"]["ELIGIBLE:ELIGIBLE"], 1)
        self.assertNotIn("AI_EVALUATED:AI_EVALUATED", counts["reasons"])


if __name__ == "__main__":
    unittest.main()

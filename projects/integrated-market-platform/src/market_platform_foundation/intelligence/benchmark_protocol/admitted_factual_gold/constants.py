"""Evaluator-only vs SUT-visible field partitions for admitted factual gold."""

from __future__ import annotations

FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS = frozenset(
    {
        "EXPECTED_FACTS",
        "GOLD_HASH",
        "evaluator_notes",
        "evaluator_gold_ref",
        "ACCEPTABLE_EQUIVALENTS",
        "expected_facts",
        "gold_hash",
        "acceptable_equivalents",
    }
)

FACTUAL_GOLD_SUT_VISIBLE_CASE_KEYS = frozenset(
    {
        "CASE_ID",
        "MODE",
        "QUESTION",
        "EVIDENCE_SET",
        "EVIDENCE_FINGERPRINT",
        "TEMPORAL_CUTOFF",
        "ANSWER_NORMALIZATION",
        "UNKNOWN_POLICY",
        "PROVENANCE_REQUIREMENTS",
        "ROUTING_EXPECTATION",
        "SCORING_GATE",
        "EVIDENCE_ACCESS_MODE",
        "case_id",
        "mode",
        "question",
        "evidence_set",
        "evidence_fingerprint",
        "temporal_cutoff",
        "answer_normalization",
        "unknown_policy",
        "provenance_requirements",
        "routing_expectation",
        "scoring_gate",
        "evidence_access_mode",
    }
)

REQUIRED_CASE_FIELDS_UPPER = frozenset(
    {
        "CASE_ID",
        "MODE",
        "QUESTION",
        "EVIDENCE_SET",
        "EVIDENCE_FINGERPRINT",
        "TEMPORAL_CUTOFF",
        "EXPECTED_FACTS",
        "ANSWER_NORMALIZATION",
        "ACCEPTABLE_EQUIVALENTS",
        "UNKNOWN_POLICY",
        "PROVENANCE_REQUIREMENTS",
        "ROUTING_EXPECTATION",
        "GOLD_HASH",
        "SCORING_GATE",
        "EVIDENCE_ACCESS_MODE",
    }
)

PROVENANCE_CHAIN_KEYS = ("expected_fact", "source_artifact", "source_record", "source_hash")

__all__ = [
    "FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS",
    "FACTUAL_GOLD_SUT_VISIBLE_CASE_KEYS",
    "PROVENANCE_CHAIN_KEYS",
    "REQUIRED_CASE_FIELDS_UPPER",
]

"""Deterministic hashes for admitted factual gold protocol (cases may be empty in M1)."""

from __future__ import annotations

from typing import Any

from ....canonical import canonical_bytes, sha256_bytes
from .types import IBP_FACTUAL_GOLD_HASH_ALGORITHM


def factual_gold_hash_algorithm() -> str:
    return IBP_FACTUAL_GOLD_HASH_ALGORITHM


def compute_caseset_hash(cases: list[dict[str, Any]]) -> str:
    """Content hash over ordered case ids + evidence fingerprints (empty list allowed)."""
    body = {
        "hash_algorithm": IBP_FACTUAL_GOLD_HASH_ALGORITHM,
        "cases": [
            {
                "case_id": row.get("CASE_ID") or row.get("case_id"),
                "evidence_fingerprint": row.get("EVIDENCE_FINGERPRINT") or row.get("evidence_fingerprint"),
            }
            for row in cases
        ],
    }
    return sha256_bytes(canonical_bytes(body))


def compute_goldset_hash(evaluator_gold_refs: list[str]) -> str:
    """Hash over evaluator-only gold artifact refs (empty until M2 populates gold files)."""
    body = {
        "hash_algorithm": IBP_FACTUAL_GOLD_HASH_ALGORITHM,
        "evaluator_gold_refs": sorted(evaluator_gold_refs),
    }
    return sha256_bytes(canonical_bytes(body))


def compute_case_gold_hash(
    *,
    case_id: str,
    expected_facts: list[dict[str, Any]],
    unknown_policy: dict[str, Any],
) -> str:
    """Per-case GOLD_HASH payload (evaluator-only; independent of SUT answers)."""
    body = {
        "hash_algorithm": IBP_FACTUAL_GOLD_HASH_ALGORITHM,
        "case_id": case_id,
        "expected_facts": expected_facts,
        "unknown_policy": unknown_policy,
    }
    return sha256_bytes(canonical_bytes(body))


__all__ = [
    "compute_case_gold_hash",
    "compute_caseset_hash",
    "compute_goldset_hash",
    "factual_gold_hash_algorithm",
]

"""Phase 7 postreview acceptance index algorithms."""

from __future__ import annotations

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    record_identity,
    verify_index_hashes,
)

PHASE7_POSTREVIEW_INDEX_IDS = frozenset(
    {
        "phase7.ai_review_coverage",
        "phase7.ai_review_runs",
        "phase7.approval_records",
        "phase7.candidate_evidence_root",
    }
)


def expected_index_logical_ids(candidate_ids: list[str]) -> tuple[str, ...]:
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("INDEX-DUPLICATE-LOGICAL-ID")
    return tuple(sorted(set(candidate_ids) | PHASE7_POSTREVIEW_INDEX_IDS))

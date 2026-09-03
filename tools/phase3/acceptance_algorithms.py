"""Phase 3 postreview acceptance index algorithms."""

from __future__ import annotations

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    record_identity,
    verify_index_hashes,
)

PHASE3_POSTREVIEW_INDEX_IDS = frozenset(
    {
        "phase3.ai_review_coverage",
        "phase3.ai_review_runs",
        "phase3.approval_records",
        "phase3.candidate_evidence_root",
    }
)


def expected_index_logical_ids(candidate_ids: list[str]) -> tuple[str, ...]:
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("INDEX-DUPLICATE-LOGICAL-ID")
    return tuple(sorted(set(candidate_ids) | PHASE3_POSTREVIEW_INDEX_IDS))

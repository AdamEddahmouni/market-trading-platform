"""Phase 0A postreview acceptance index algorithms (lighter review, no contract suite)."""

from __future__ import annotations

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    record_identity,
    verify_index_hashes,
)

PHASE0A_POSTREVIEW_INDEX_IDS = frozenset(
    {
        "phase0a.ai_review_coverage",
        "phase0a.ai_review_runs",
        "phase0a.approval_records",
        "phase0a.candidate_evidence_root",
    }
)


def expected_index_logical_ids(candidate_ids: list[str]) -> tuple[str, ...]:
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("INDEX-DUPLICATE-LOGICAL-ID")
    return tuple(sorted(set(candidate_ids) | PHASE0A_POSTREVIEW_INDEX_IDS))

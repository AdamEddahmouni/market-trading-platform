"""Dedup operator review rows without rewriting clustering."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from .read_model import OpportunitySummary

DUPLICATE_THESIS_SUPPRESSED = "DUPLICATE_THESIS_SUPPRESSED"


def _group_key(row: OpportunitySummary) -> tuple[str, ...]:
    if row.opportunity_id:
        return ("opp", row.opportunity_id)
    return (
        "attn",
        row.instrument_id,
        row.side or "",
        str(row.valid_until_ns or ""),
        ",".join(sorted(row.catalyst_ids)),
    )


def review_thesis_key(row: OpportunitySummary) -> str:
    """Group key for already-sorted review rows. Does not allocate or rank."""

    if row.identity_kind == "OPPORTUNITY_V1":
        thesis = (row.metadata or {}).get("thesis_identity")
        if isinstance(thesis, str) and thesis.strip():
            return thesis.strip()
        if row.opportunity_id:
            return f"opp:{row.opportunity_id}"
    return f"row:{row.summary_id}"


def keep_ranked_thesis_winners(ordered: tuple[OpportunitySummary, ...]) -> tuple[OpportunitySummary, ...]:
    """Keep the first (already ranked) OpportunityV1 per thesis; extras in duplicates[]."""

    winners: list[OpportunitySummary] = []
    index_by_key: dict[str, int] = {}
    for row in ordered:
        key = review_thesis_key(row)
        existing = index_by_key.get(key)
        if existing is None:
            index_by_key[key] = len(winners)
            winners.append(row)
            continue
        winner = winners[existing]
        metadata = dict(winner.metadata)
        metadata["duplicate_reason"] = DUPLICATE_THESIS_SUPPRESSED
        winners[existing] = replace(
            winner,
            duplicates=winner.duplicates + (row.summary_id,),
            metadata=metadata,
        )
    return tuple(winners)


def dedup_review_rows(rows: tuple[OpportunitySummary, ...]) -> tuple[OpportunitySummary, ...]:
    grouped: dict[tuple[str, ...], list[OpportunitySummary]] = defaultdict(list)
    for row in rows:
        grouped[_group_key(row)].append(row)
    winners: list[OpportunitySummary] = []
    for members in grouped.values():
        ordered = sorted(members, key=lambda item: (item.summary_id, item.opportunity_id or ""))
        winner = ordered[0]
        extras = tuple(item.summary_id for item in ordered[1:])
        if extras:
            winner = replace(winner, duplicates=extras)
        winners.append(winner)
    return tuple(winners)

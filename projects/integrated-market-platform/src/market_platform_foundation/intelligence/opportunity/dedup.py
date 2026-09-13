"""Dedup operator review rows without rewriting clustering."""

from __future__ import annotations

from collections import defaultdict

from .read_model import OpportunitySummary


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
            from dataclasses import replace

            winner = replace(winner, duplicates=extras)
        winners.append(winner)
    return tuple(winners)

"""Temporal supersession for operator review rows sharing a thesis identity.

Dedup removes exact duplicates in one refresh. Rank-order collapse marks co-ranked
losers as ``DUPLICATE_THESIS_SUPPRESSED``. Supersession applies only when every row
in a thesis group carries an explicit decision timestamp; the newest timestamp wins.
If any member lacks a timestamp, fail closed to rank-order (first input row wins).
"""

from __future__ import annotations

from dataclasses import replace

from .dedup import DUPLICATE_THESIS_SUPPRESSED, review_thesis_key
from .read_model import OpportunitySummary

SUPERSEDED_BY_NEWER_THESIS = "SUPERSEDED_BY_NEWER_THESIS"

_DECISION_TIME_FIELDS = (
    "decision_time_ns",
    "created_at_ns",
    "opportunity_decision_time_ns",
)


class SupersessionPolicyError(ValueError):
    """Invalid supersession inputs."""


def decision_time_ns_from_row(row: OpportunitySummary) -> int | None:
    """Extract a PIT decision time from review-row metadata only."""

    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    for key in _DECISION_TIME_FIELDS:
        raw = metadata.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise SupersessionPolicyError("DECISION_TIME_NS_INVALID")
        if value <= 0:
            raise SupersessionPolicyError("DECISION_TIME_NS_INVALID")
        return value
    return None


def _merge_loser_into_winner(
    winner: OpportunitySummary,
    loser: OpportunitySummary,
    *,
    reason: str,
) -> OpportunitySummary:
    metadata = dict(winner.metadata or {})
    metadata["supersession_reason"] = reason
    if reason == DUPLICATE_THESIS_SUPPRESSED:
        metadata["duplicate_reason"] = DUPLICATE_THESIS_SUPPRESSED
    return replace(
        winner,
        duplicates=winner.duplicates + (loser.summary_id,),
        metadata=metadata,
    )


def select_thesis_group_winner(members: tuple[OpportunitySummary, ...]) -> OpportunitySummary:
    """Pick one visible row for a shared thesis. Input order is rank order (best first)."""

    if not members:
        raise SupersessionPolicyError("THESIS_GROUP_EMPTY")
    if len(members) == 1:
        return members[0]

    times: list[tuple[int, int, OpportunitySummary]] = []
    for index, row in enumerate(members):
        stamp = decision_time_ns_from_row(row)
        if stamp is None:
            winner = members[0]
            for loser in members[1:]:
                winner = _merge_loser_into_winner(
                    winner,
                    loser,
                    reason=DUPLICATE_THESIS_SUPPRESSED,
                )
            return winner
        times.append((stamp, index, row))

    max_stamp = max(item[0] for item in times)
    winners_at_max = [item for item in times if item[0] == max_stamp]
    if len(winners_at_max) > 1:
        winner = winners_at_max[0][2]
        for _, _, loser in winners_at_max[1:]:
            winner = _merge_loser_into_winner(
                winner,
                loser,
                reason=DUPLICATE_THESIS_SUPPRESSED,
            )
        older = [item for item in times if item[0] < max_stamp]
        for _, _, loser in older:
            winner = _merge_loser_into_winner(
                winner,
                loser,
                reason=SUPERSEDED_BY_NEWER_THESIS,
            )
        return winner

    winner = winners_at_max[0][2]
    for _, _, loser in times:
        if loser.summary_id == winner.summary_id:
            continue
        reason = SUPERSEDED_BY_NEWER_THESIS if decision_time_ns_from_row(loser) != max_stamp else DUPLICATE_THESIS_SUPPRESSED
        winner = _merge_loser_into_winner(winner, loser, reason=reason)
    return winner


def apply_thesis_supersession(ordered: tuple[OpportunitySummary, ...]) -> tuple[OpportunitySummary, ...]:
    """Collapse shared-thesis rows using temporal supersession when timestamps are complete."""

    if not ordered:
        return ()
    grouped: dict[str, list[OpportunitySummary]] = {}
    order_keys: list[str] = []
    for row in ordered:
        key = review_thesis_key(row)
        if key not in grouped:
            grouped[key] = []
            order_keys.append(key)
        grouped[key].append(row)

    winners: list[OpportunitySummary] = []
    for key in order_keys:
        winners.append(select_thesis_group_winner(tuple(grouped[key])))
    return tuple(winners)

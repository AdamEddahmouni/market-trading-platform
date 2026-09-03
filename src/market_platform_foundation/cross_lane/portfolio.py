"""SHARED P5 cross-lane portfolio intelligence — combine lanes without collapsing them.

Doctrine (extends ``DEC-SYN-001`` — no composite score):

1. **No opaque composite.** Every aggregate is decomposed: raw evidence ids ->
   per-lane fused opportunities -> stances -> uncertainty -> expected value are
   all preserved verbatim in the output alongside any grouping.
2. **Explicit overlap handling.** Positions that cite intersecting evidence-id
   sets (or declare the same ``underlying_event_key``) form an OVERLAP group.
   Group membership is *reported*, never silently summed; each overlap group
   exposes ``net_unique_evidence_fraction`` =
   ``|unique evidence ids| / |evidence citations|`` so double counting is
   measurable instead of hidden.
3. **Conservative correlation handling.** Correlation groups come from explicit
   caller-supplied keys, with one documented default: positions on the same
   normalized symbol share a group (e.g. Short Squeeze + Order Flow on NVDA).
   Within a group the platform does **not** invent correlation coefficients;
   the combined exposure is reported under a documented worst-case policy
   (``combined_fused_net_ev = min(member evs)``) purely as an informational
   bound. It never feeds ranking.
4. **Contradictions stay visible.** Two lanes with opposing directional stances
   inside one correlation group produce a :class:`PortfolioContradiction`.
   Contradictions NEVER average out: they remain listed and demote every
   affected position's rank tier.
5. **Deterministic demote-not-hide ranking.** Ordering is a lexicographic
   policy over fully exposed inputs:

   ``(rank_tier ASC, uncertainty ASC, fused_net_ev DESC, position_id ASC)``

   where ``rank_tier`` is::

       3  status UNAVAILABLE / fused_net_ev missing (fail-closed rows last)
       2  position is a member of a contradicted correlation group
       1  position is a member of an overlap group or concentrated
          correlation group
       0  clean

   Uncertainty ties round to 6 decimals before comparison; ``position_id`` is
   the final tiebreak so equal inputs always produce byte-identical output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .opportunity import FusedOpportunity

PORTFOLIO_VIEW_VERSION = "shared_portfolio_v1"
PORTFOLIO_METHOD = "CROSS_LANE_PORTFOLIO_V1"

# Direction-bearing templates reuse existing repo vocabulary only:
# options CANDIDATE_TEMPLATES + futures FUTURES_REGIME_TEMPLATES.
_BULLISH_TEMPLATES = frozenset({"long_call_atm", "bull_call_spread", "long_otm_call", "outright_trend_long"})
_BEARISH_TEMPLATES = frozenset({"long_put_atm", "bear_put_spread", "outright_trend_short"})


class PortfolioStance(StrEnum):
    """Conservative directional stance derived from the fused payoff template."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NON_DIRECTIONAL = "NON_DIRECTIONAL"
    UNKNOWN = "UNKNOWN"


class PortfolioQualityFlag(StrEnum):
    EVIDENCE_OVERLAP = "PORTFOLIO_EVIDENCE_OVERLAP"
    LANE_CONTRADICTION = "PORTFOLIO_LANE_CONTRADICTION"
    CORRELATION_GROUP_CONCENTRATION = "PORTFOLIO_CORRELATION_GROUP_CONCENTRATION"
    POSITION_INPUTS_INCOMPLETE = "PORTFOLIO_POSITION_INPUTS_INCOMPLETE"


def stance_from_template(template: str | None) -> PortfolioStance:
    """Derive stance from an existing payoff/futures template name.

    Unknown or missing templates never become directional.
    """
    if template is None:
        return PortfolioStance.UNKNOWN
    if template in _BULLISH_TEMPLATES:
        return PortfolioStance.BULLISH
    if template in _BEARISH_TEMPLATES:
        return PortfolioStance.BEARISH
    return PortfolioStance.NON_DIRECTIONAL


def _coerce_fusion(fusion: Any) -> FusedOpportunity:
    """Accept a FusedOpportunity or its fused_opportunity_to_dict payload."""
    if isinstance(fusion, FusedOpportunity):
        return fusion
    if isinstance(fusion, dict):
        inner = fusion.get("fusion") if isinstance(fusion.get("fusion"), dict) else fusion
        return FusedOpportunity(
            fused_net_ev=float(inner["fused_net_ev"]),
            occurrence_weight=float(inner["occurrence_weight"]),
            liquidity_factor=float(inner["liquidity_factor"]),
            gross_ev_before_weights=float(inner["gross_ev_before_weights"]),
            template=inner.get("template"),
            squeeze_aligned=bool(inner.get("squeeze_aligned", False)),
        )
    raise TypeError(f"unsupported fusion payload type: {type(fusion)!r}")


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    """One lane's fused opportunity entering the portfolio view.

    ``fusion`` references the lane's SHARED P4 output (dataclass or dict);
    ``evidence_ids`` lists exactly which evidence-DAG items this position
    consumed so overlapping consumption is explicit and auditable.
    """

    position_id: str
    symbol: str
    lane: str
    fusion: Any
    evidence_ids: tuple[str, ...] = ()
    correlation_group: str | None = None
    underlying_event_key: str | None = None
    uncertainty: float | None = None
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        coerced = _coerce_fusion(self.fusion)
        object.__setattr__(self, "fusion", coerced)


@dataclass(frozen=True, slots=True)
class OverlapGroup:
    """Two or more positions citing intersecting evidence or the same event."""

    group_id: str
    member_position_ids: tuple[str, ...]
    shared_evidence_ids: tuple[str, ...]
    shared_event_keys: tuple[str, ...]
    net_unique_evidence_fraction: float


@dataclass(frozen=True, slots=True)
class PortfolioContradiction:
    """Opposing directional stances inside one correlation group."""

    group_key: str
    members: tuple[tuple[str, str], ...]  # (position_id, stance)
    detail: str


@dataclass(frozen=True, slots=True)
class CorrelationGroupSummary:
    """Informational worst-case aggregation for one correlation group."""

    group_key: str
    member_position_ids: tuple[str, ...]
    combined_ev_policy: str  # WORST_CASE_MIN — documented, never invented coefficients
    combined_fused_net_ev: float
    concentration_flagged: bool


@dataclass(frozen=True, slots=True)
class PortfolioViewSnapshot:
    """SHARED P5 output — aggregates sit beside, never replace, per-lane rows."""

    version: str
    method: str
    as_of_time: str
    ranked_positions: tuple[dict[str, Any], ...]
    overlap_groups: tuple[OverlapGroup, ...]
    contradictions: tuple[PortfolioContradiction, ...]
    correlation_groups: tuple[CorrelationGroupSummary, ...]
    net_unique_evidence_fraction: float
    disclaimer: str = (
        "Cross-lane portfolio decomposition — research view, not a trade recommendation."
    )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": self.version,
            "method": self.method,
            "as_of_time": self.as_of_time,
            "ranked_positions": [dict(row) for row in self.ranked_positions],
            "overlap_groups": [
                {
                    "group_id": g.group_id,
                    "member_position_ids": list(g.member_position_ids),
                    "shared_evidence_ids": list(g.shared_evidence_ids),
                    "shared_event_keys": list(g.shared_event_keys),
                    "net_unique_evidence_fraction": g.net_unique_evidence_fraction,
                }
                for g in self.overlap_groups
            ],
            "contradictions": [
                {
                    "group_key": c.group_key,
                    "members": [[pid, stance] for pid, stance in c.members],
                    "detail": c.detail,
                }
                for c in self.contradictions
            ],
            "correlation_groups": [
                {
                    "group_key": g.group_key,
                    "member_position_ids": list(g.member_position_ids),
                    "combined_ev_policy": g.combined_ev_policy,
                    "combined_fused_net_ev": g.combined_fused_net_ev,
                    "concentration_flagged": g.concentration_flagged,
                }
                for g in self.correlation_groups
            ],
            "net_unique_evidence_fraction": self.net_unique_evidence_fraction,
            "disclaimer": self.disclaimer,
        }
        payload["replay_hash"] = _replay_hash(payload)
        return payload


def _replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def resolve_correlation_group(position: PortfolioPosition) -> str:
    """Explicit caller key wins; otherwise same normalized symbol shares a group."""
    if position.correlation_group:
        return position.correlation_group
    return f"SYMBOL:{position.symbol.strip().upper()}"


def detect_overlap_groups(
    positions: list[PortfolioPosition],
) -> list[OverlapGroup]:
    """Positions sharing any evidence id or underlying event key form one group.

    Union-find keeps transitively linked positions together; groups smaller than
    two members produce nothing. Output is deterministically ordered by group id.
    """
    parent = {p.position_id: p.position_id for p in positions}
    by_id = {p.position_id: p for p in positions}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = sorted((ra, rb))
            parent[hi] = lo

    links: dict[str, set[str]] = {}
    for position in positions:
        for evidence_id in position.evidence_ids:
            links.setdefault(("EVIDENCE", evidence_id), set()).add(position.position_id)
        if position.underlying_event_key:
            links.setdefault(("EVENT", position.underlying_event_key), set()).add(position.position_id)

    for members in links.values():
        ordered = sorted(members)
        for other in ordered[1:]:
            union(ordered[0], other)

    clusters: dict[str, list[str]] = {}
    for position in positions:
        clusters.setdefault(find(position.position_id), []).append(position.position_id)

    groups: list[OverlapGroup] = []
    for member_ids in clusters.values():
        if len(member_ids) < 2:
            continue
        members = [by_id[mid] for mid in sorted(member_ids)]
        citations_total = sum(len(p.evidence_ids) for p in members)
        unique_ids: set[str] = set()
        counts: dict[str, int] = {}
        for p in members:
            for evidence_id in p.evidence_ids:
                unique_ids.add(evidence_id)
                counts[evidence_id] = counts.get(evidence_id, 0) + 1
        shared = tuple(sorted(eid for eid, n in counts.items() if n >= 2))
        fraction = round(len(unique_ids) / citations_total, 6) if citations_total else 1.0
        groups.append(
            OverlapGroup(
                group_id="OVERLAP:" + "|".join(sorted(member_ids)),
                member_position_ids=tuple(sorted(member_ids)),
                shared_evidence_ids=shared,
                shared_event_keys=tuple(
                    sorted(
                        {
                            key[1]
                            for key, linked in links.items()
                            if key[0] == "EVENT"
                            and len(linked) >= 2
                            and linked <= set(member_ids)
                        }
                    )
                ),
                net_unique_evidence_fraction=fraction,
            )
        )
    return sorted(groups, key=lambda g: g.group_id)


def detect_contradictions(
    positions: list[PortfolioPosition],
) -> list[PortfolioContradiction]:
    """Both BULLISH and BEARISH stances inside one correlation group contradict.

    Stances derive only from existing fused templates; non-directional and
    unknown stances never vote. Contradictions are returned, never resolved.
    """
    grouped: dict[str, list[tuple[str, PortfolioStance]]] = {}
    for position in positions:
        fusion: FusedOpportunity = position.fusion  # type: ignore[assignment]
        stance = stance_from_template(fusion.template)
        if stance not in (PortfolioStance.BULLISH, PortfolioStance.BEARISH):
            continue
        grouped.setdefault(resolve_correlation_group(position), []).append(
            (position.position_id, stance)
        )

    contradictions: list[PortfolioContradiction] = []
    for group_key in sorted(grouped):
        entries = sorted(grouped[group_key], key=lambda e: e[0])
        stances = {stance for _, stance in entries}
        if stances == {PortfolioStance.BULLISH, PortfolioStance.BEARISH}:
            contradictions.append(
                PortfolioContradiction(
                    group_key=group_key,
                    members=tuple(entries),
                    detail=(
                        "Opposing directional stances across lanes on the same "
                        "correlation group — preserved visibly, ranks demoted, "
                        "never averaged."
                    ),
                )
            )
    return contradictions


_RANK_TIER_UNAVAILABLE = 3
_RANK_TIER_CONTRADICTED = 2
_RANK_TIER_DEMOTED = 1
_RANK_TIER_CLEAN = 0


def build_portfolio_view(
    positions: list[PortfolioPosition],
    *,
    as_of_time: str,
) -> PortfolioViewSnapshot:
    """Deterministic SHARED P5 portfolio view over per-lane fused opportunities."""
    overlap_groups = detect_overlap_groups(positions)
    contradictions = detect_contradictions(positions)

    overlap_memberships: dict[str, list[str]] = {}
    for group in overlap_groups:
        for pid in group.member_position_ids:
            overlap_memberships.setdefault(pid, []).append(group.group_id)

    contradicted_pids: set[str] = {
        pid for c in contradictions for pid, _ in c.members
    }

    # Correlation-group summaries: informational worst-case bound only.
    corr_members: dict[str, list[PortfolioPosition]] = {}
    for position in positions:
        corr_members.setdefault(resolve_correlation_group(position), []).append(position)
    correlation_summaries: list[CorrelationGroupSummary] = []
    for group_key in sorted(corr_members):
        members = sorted(corr_members[group_key], key=lambda p: p.position_id)
        available = [m for m in members if m.fusion.fused_net_ev is not None]
        combined = min(float(m.fusion.fused_net_ev) for m in available) if available else 0.0
        concentrated = len({m.symbol.strip().upper() for m in members}) == 1 and len(members) > 1
        correlation_summaries.append(
            CorrelationGroupSummary(
                group_key=group_key,
                member_position_ids=tuple(m.position_id for m in members),
                combined_ev_policy="WORST_CASE_MIN",
                combined_fused_net_ev=round(combined, 6),
                concentration_flagged=concentrated,
            )
        )

    summaries_by_position = {
        pid: s for s in correlation_summaries for pid in s.member_position_ids
    }
    rows: list[dict[str, Any]] = []
    for position in positions:
        fusion: FusedOpportunity = position.fusion  # type: ignore[assignment]
        stance = stance_from_template(fusion.template)
        flags: list[str] = list(dict.fromkeys(position.quality_flags))
        net_ev_missing = fusion.fused_net_ev is None
        if position.uncertainty is None:
            flags.append(PortfolioQualityFlag.POSITION_INPUTS_INCOMPLETE.value)
        if position.position_id in overlap_memberships:
            flags.append(PortfolioQualityFlag.EVIDENCE_OVERLAP.value)
        if position.position_id in contradicted_pids:
            flags.append(PortfolioQualityFlag.LANE_CONTRADICTION.value)
        summary = summaries_by_position[position.position_id]
        if summary.concentration_flagged:
            flags.append(PortfolioQualityFlag.CORRELATION_GROUP_CONCENTRATION.value)

        # Fail-closed tiering: only missing EV makes a row UNAVAILABLE.
        # Missing uncertainty stays ranked but flagged and treated as 1.0
        # (worst case) for ordering.
        if net_ev_missing:
            tier = _RANK_TIER_UNAVAILABLE
        elif position.position_id in contradicted_pids:
            tier = _RANK_TIER_CONTRADICTED
        elif position.position_id in overlap_memberships or summary.concentration_flagged:
            tier = _RANK_TIER_DEMOTED
        else:
            tier = _RANK_TIER_CLEAN

        uncertainty = 1.0 if position.uncertainty is None else round(float(position.uncertainty), 6)
        net_ev = None if fusion.fused_net_ev is None else round(float(fusion.fused_net_ev), 6)

        rows.append(
            {
                "position_id": position.position_id,
                "symbol": position.symbol,
                "lane": position.lane,
                "status": "UNAVAILABLE" if net_ev_missing else "RANKED",
                "fused_net_ev": net_ev,
                "occurrence_weight": fusion.occurrence_weight,
                "liquidity_factor": fusion.liquidity_factor,
                "gross_ev_before_weights": fusion.gross_ev_before_weights,
                "template": fusion.template,
                "squeeze_aligned": fusion.squeeze_aligned,
                "stance": stance.value,
                "uncertainty": uncertainty,
                "evidence_ids": sorted(position.evidence_ids),
                "correlation_group": summary.group_key,
                "quality_flags": list(dict.fromkeys(flags)),
                "rank_tier": tier,
                "overlap_group_ids": sorted(overlap_memberships.get(position.position_id, [])),
                "contradicted": position.position_id in contradicted_pids,
            }
        )

    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row["rank_tier"],
            row["uncertainty"],
            -(row["fused_net_ev"] if row["fused_net_ev"] is not None else 0.0),
            row["position_id"],
        )

    ranked = tuple(sorted(rows, key=sort_key))

    total_citations = sum(len(p.evidence_ids) for p in positions)
    unique_citations = len({eid for p in positions for eid in p.evidence_ids})
    book_fraction = round(unique_citations / total_citations, 6) if total_citations else 1.0

    return PortfolioViewSnapshot(
        version=PORTFOLIO_VIEW_VERSION,
        method=PORTFOLIO_METHOD,
        as_of_time=as_of_time,
        ranked_positions=ranked,
        overlap_groups=tuple(overlap_groups),
        contradictions=tuple(contradictions),
        correlation_groups=tuple(correlation_summaries),
        net_unique_evidence_fraction=book_fraction,
    )


__all__ = [
    "PORTFOLIO_METHOD",
    "PORTFOLIO_VIEW_VERSION",
    "CorrelationGroupSummary",
    "OverlapGroup",
    "PortfolioContradiction",
    "PortfolioPosition",
    "PortfolioQualityFlag",
    "PortfolioStance",
    "PortfolioViewSnapshot",
    "build_portfolio_view",
    "detect_contradictions",
    "detect_overlap_groups",
    "resolve_correlation_group",
    "stance_from_template",
]

"""Decision candidate synthesis (DECISION-RESEARCH-001 §8).

``build_decision_candidate`` consumes P3.2 ``WorkspaceEvidence`` lane envelopes
(``ui_api/workspace_evidence.py::_lane_base`` rows: relevance / direction /
quality / freshness) plus optional MC16 ``MultiDocumentSynthesisSummary`` rows
and produces one deterministic :class:`DecisionCandidate`. It never recomputes
lane scores and exposes **no composite score** (``DEC-SYN-001``).

Direction doctrine (extends MC16 — preserve contradictions, no majority vote,
no % bullish):

- ``POSITIVE -> LONG``, ``NEGATIVE -> SHORT``, ``NEUTRAL -> NEUTRAL`` across
  lanes whose quality is usable (``UNAVAILABLE`` / ``NOT_CONFIGURED`` /
  ``NOT_APPLICABLE`` / ``UNKNOWN`` lanes are never directional).
- Any contradiction — lanes on both LONG and SHORT, any ``MIXED`` lane
  direction, or a contradictory MC16 cluster — yields
  ``evidence_mix = MIXED`` with ``direction_hypothesis = NO_HYPOTHESIS``.
- No usable directional evidence -> ``INSUFFICIENT`` /
  ``NO_HYPOTHESIS`` (missing lanes never coerced).
- MC16 quality flags (e.g. ``MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL``) propagate
  verbatim into the piece ``quality_flags``; ``synthesis_confidence`` /
  ``theme_agreement_score`` are declared-features-only (never a direction
  source). MC16 ``contradiction_detected`` enriches the candidate mix but never
  rewrites a lane's own direction.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...normalization.equity_bars import iso_to_epoch_ns

SYNTHESIS_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

HYPOTHESIS_FROM_DIRECTION: dict[str, str] = {
    "POSITIVE": "LONG",
    "NEGATIVE": "SHORT",
    "NEUTRAL": "NEUTRAL",
}
NON_DIRECTIONAL_QUALITY = frozenset(
    {"UNAVAILABLE", "NOT_CONFIGURED", "NOT_APPLICABLE", "UNKNOWN"}
)
# MC16 summaries attach to these lanes (deterministic: the most recent row).
MC16_APPLICABLE_LANES = ("MARKET_CONTEXT", "CATALYST")


@dataclass(slots=True)
class DecisionCandidate:
    candidate_id: str
    instrument_id: str
    generated_at_ns: int
    direction_hypothesis: str
    thesis: str
    evidence_mix: str
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence: list[dict[str, Any]]
    research_only: bool = True
    execution_authority: str = "NONE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "instrument_id": self.instrument_id,
            "generated_at_ns": self.generated_at_ns,
            "direction_hypothesis": self.direction_hypothesis,
            "thesis": self.thesis,
            "evidence_mix": self.evidence_mix,
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "research_only": self.research_only,
            "execution_authority": self.execution_authority,
        }


def _lane_piece(row: dict[str, Any], mc16: dict[str, Any] | None) -> dict[str, Any]:
    """Deterministic per-lane evidence piece for a candidate."""
    flags: list[str] = []
    confidence: Any = None
    agreement: Any = None
    if isinstance(mc16, dict):
        flags = [str(f) for f in (mc16.get("quality_flags") or [])]
        confidence = mc16.get("synthesis_confidence")
        agreement = mc16.get("theme_agreement_score")
    return {
        "lane": str(row.get("lane")),
        "evidence_type": str(row.get("evidence_type")),
        "direction": str(row.get("direction")),
        "quality": str(row.get("quality")),
        "freshness_label": str(row.get("freshness_label")),
        "available_time": row.get("available_time"),
        "summary": str(row.get("summary")),
        "sources": [str(s) for s in (row.get("sources") or [])],
        "reason_codes": [str(r) for r in (row.get("reason_codes") or [])],
        "quality_flags": flags,
        "synthesis_confidence": confidence,
        "theme_agreement_score": agreement,
    }


def build_decision_candidate(
    instrument: str,
    prediction_cutoff: int,
    lane_evidence: list[dict[str, Any]],
    *,
    mc16_summaries: list[dict[str, Any]] | None = None,
) -> DecisionCandidate:
    """Build one deterministic candidate from P3.2 lanes at a prediction cutoff."""
    instrument = str(instrument).strip().upper()
    prediction_cutoff = int(prediction_cutoff)

    # Deterministic MC16 attachment: each summary lands on the matching lane's
    # most recent (last) piece.
    mc16_by_lane: dict[str, dict[str, Any]] = {}
    for summary in mc16_summaries or []:
        if not isinstance(summary, dict):
            continue
        entity = str(summary.get("entity_id") or summary.get("cluster_id") or "")
        lane = "MARKET_CONTEXT"
        if entity and entity.upper() != instrument and "CATALYST" in str(summary.get("consolidated_channels") or ""):
            lane = "CATALYST"
        lanes_matching = [r for r in lane_evidence if str(r.get("lane")) == lane]
        if lanes_matching:
            mc16_by_lane[lane] = summary

    directional: list[tuple[str, dict[str, Any]]] = []  # (hypothesis, piece)
    lanebyname: dict[str, dict[str, Any]] = {}
    contradiction_flags: list[str] = []

    for row in lane_evidence:
        name = str(row.get("lane") or "")
        lanebyname[name] = row
        mc16 = mc16_by_lane.get(name)
        direction = str(row.get("direction") or "UNKNOWN").upper()
        quality = str(row.get("quality") or "UNKNOWN").upper()
        if quality in NON_DIRECTIONAL_QUALITY:
            continue
        if mc16 and mc16.get("contradiction_detected"):
            contradiction_flags.append(f"{name}:MC16_CONTRADICTION")
        if direction in HYPOTHESIS_FROM_DIRECTION:
            directional.append((HYPOTHESIS_FROM_DIRECTION[direction], row, mc16))
        elif direction == "MIXED":
            contradiction_flags.append(f"{name}:LANE_MIXED")

    # PIT guard: a piece whose availability is later than the cutoff is not
    # directional (and is recorded in the thesis narrative only).
    usable: list[tuple[str, dict[str, Any]]] = []
    for hypothesis, row, mc16 in directional:
        available_ns = None
        if row.get("available_time"):
            try:
                available_ns = iso_to_epoch_ns(str(row["available_time"]))
            except ValueError:
                available_ns = None
        if available_ns is not None and available_ns > prediction_cutoff:
            continue
        usable.append((hypothesis, _lane_piece(row, mc16)))

    longs = [p for h, p in usable if h == "LONG"]
    shorts = [p for h, p in usable if h == "SHORT"]
    neutrals = [p for h, p in usable if h == "NEUTRAL"]

    if contradiction_flags or (longs and shorts):
        mix, hypothesis = "MIXED", "NO_HYPOTHESIS"
        supporting = list(longs)
        contradicting = list(shorts)
    elif usable and not longs and not shorts and neutrals:
        mix, hypothesis = "ALIGNED", "NEUTRAL"
        supporting = list(neutrals)
        contradicting = []
    elif longs:
        mix, hypothesis = "ALIGNED", "LONG"
        supporting = list(longs)
        contradicting = list(shorts)
    elif shorts:
        mix, hypothesis = "ALIGNED", "SHORT"
        supporting = list(shorts)
        contradicting = list(longs)
    else:
        mix, hypothesis = "INSUFFICIENT", "NO_HYPOTHESIS"
        supporting = []
        contradicting = []

    # Deterministic display-only thesis with evidence citations (no score).
    lanes_used = [p["lane"] for p in supporting + contradicting]
    order = ("ORDER_FLOW", "SHORT_INTELLIGENCE", "SHORT_SQUEEZE", "MARKET_CONTEXT",
             "CATALYST", "WHALE_INSIDER", "OPTIONS", "FUTURES")
    lanes_used.sort(key=lambda lane: (order.index(lane) if lane in order else 99, lane))
    thesis_bits = [
        f"{lane}: {lanebyname[lane].get('summary') or 'no summary'}" for lane in lanes_used
    ]
    thesis = (
        f"{hypothesis} thesis for {instrument} at cutoff "
        f"{prediction_cutoff} ({len(usable)} usable lane(s)). "
        f"Evidence: {'; '.join(thesis_bits) if thesis_bits else 'none directional.'}"
    )

    body = {
        "instrument": instrument,
        "prediction_cutoff": prediction_cutoff,
        "evidence_mix": mix,
        "direction_hypothesis": hypothesis,
        "contradicting_evidence": contradicting,
        "supporting_evidence": supporting,
        "mc16_flags": sorted(
            f for m in (mc16_summaries or []) if isinstance(m, dict)
            for f in (m.get("quality_flags") or [])
        ),
        "notation_hash": sha256_bytes(canonical_bytes([p for p in usable])),
    }
    canonical = canonical_bytes(body)
    candidate_id = "CAND-" + str(uuid.uuid5(SYNTHESIS_NAMESPACE, canonical.decode("latin-1")))

    return DecisionCandidate(
        candidate_id=candidate_id,
        instrument_id=instrument,
        generated_at_ns=prediction_cutoff,
        direction_hypothesis=hypothesis,
        thesis=thesis,
        evidence_mix=mix,
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
    )


__all__ = [
    "DecisionCandidate",
    "HYPOTHESIS_FROM_DIRECTION",
    "MC16_APPLICABLE_LANES",
    "SYNTHESIS_NAMESPACE",
    "build_decision_candidate",
]

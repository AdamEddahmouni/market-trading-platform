"""MC15 cross-entity propagation — separate donor fields, PIT-safe, fail-closed ambiguity."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..contracts.market_context import ContextQualityFlag, PublicationState
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "market_context_cross_entity_propagation_v1"
SCORING_METHOD = "cross_entity_propagation_v1"
NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

PROPAGATED_CATALYST_ELEVATED_THRESHOLD = 0.50
PROPAGATED_ATTENTION_ELEVATED_THRESHOLD = 0.40

DEFAULT_PROPAGATION_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_nvda_propagation_slice.json"
)
DEFAULT_PROPAGATION_EXPECTED = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_nvda_propagation_expected.json"
)
GATE_PREDICTION_CUTOFF = "2026-07-23T00:00:00.000000000Z"
GATE_EARLY_CUTOFF = "2026-07-22T12:00:00.000000000Z"


class EntityLinkType(StrEnum):
    ETF_CONSTITUENT = "ETF_CONSTITUENT"
    SECTOR_PEER = "SECTOR_PEER"
    SUPPLY_CHAIN = "SUPPLY_CHAIN"


@dataclass(frozen=True, slots=True)
class EntityLink:
    link_id: str
    source_entity_id: str
    target_entity_id: str
    link_type: str
    link_weight: float | None
    event_time: str
    available_time: str
    expires_time: str | None = None
    ambiguous: bool = False
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DonorSignalRow:
    entity_id: str
    event_id: str
    canonical_event_type: str
    catalyst_strength: float | None
    attention_level: float | None
    information_value: float | None
    diffusion_score: float | None
    event_time: str
    available_time: str


@dataclass(frozen=True, slots=True)
class PropagationSummary:
    propagation_id: str
    link_id: str
    link_type: str
    source_entity_id: str
    target_entity_id: str
    source_event_id: str
    canonical_event_type: str
    link_weight: float
    propagated_catalyst_strength: float | None
    propagated_attention_level: float | None
    propagated_information_value: float | None
    propagated_diffusion_score: float | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def propagation_id_from_parts(
    *,
    link_id: str,
    source_event_id: str,
    target_entity_id: str,
) -> str:
    normalized = "|".join(
        ("propagation", link_id, source_event_id, target_entity_id.strip().upper())
    )
    return str(uuid.uuid5(NAMESPACE, normalized))


def load_entity_link_fixture(path: Path) -> tuple[list[EntityLink], list[DonorSignalRow], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    target_symbol = str(payload.get("target_symbol", "BOXL")).upper()
    links_payload = payload.get("entity_links", [])
    signals_payload = payload.get("donor_signals", [])
    links: list[EntityLink] = []
    if isinstance(links_payload, list):
        for row in links_payload:
            if not isinstance(row, dict):
                continue
            source = str(row.get("source_entity_id", "")).upper()
            target = str(row.get("target_entity_id", "")).upper()
            if not source or not target:
                continue
            flags = row.get("quality_flags") or []
            if not isinstance(flags, list):
                flags = []
            links.append(
                EntityLink(
                    link_id=str(row.get("link_id", f"{source}->{target}")),
                    source_entity_id=source,
                    target_entity_id=target,
                    link_type=str(row.get("link_type", EntityLinkType.SECTOR_PEER.value)),
                    link_weight=_optional_float(row.get("link_weight")),
                    event_time=str(row.get("event_time", "")),
                    available_time=str(row.get("available_time", "")),
                    expires_time=(
                        str(row["expires_time"]) if row.get("expires_time") else None
                    ),
                    ambiguous=bool(row.get("ambiguous", False)),
                    quality_flags=tuple(str(item) for item in flags),
                )
            )
    signals: list[DonorSignalRow] = []
    if isinstance(signals_payload, list):
        for row in signals_payload:
            if not isinstance(row, dict):
                continue
            entity_id = str(row.get("entity_id", "")).upper()
            event_id = str(row.get("event_id", ""))
            if not entity_id or not event_id:
                continue
            signals.append(
                DonorSignalRow(
                    entity_id=entity_id,
                    event_id=event_id,
                    canonical_event_type=str(row.get("canonical_event_type", "")),
                    catalyst_strength=_optional_float(row.get("catalyst_strength")),
                    attention_level=_optional_float(row.get("attention_level")),
                    information_value=_optional_float(row.get("information_value")),
                    diffusion_score=_optional_float(row.get("diffusion_score")),
                    event_time=str(row.get("event_time", "")),
                    available_time=str(row.get("available_time", "")),
                )
            )
    return links, signals, target_symbol


def _link_pit_eligible(link: EntityLink, *, prediction_cutoff: int) -> tuple[bool, str | None]:
    if not link.available_time:
        return False, ContextQualityFlag.PROPAGATION_LINK_STALE.value
    if iso_to_epoch_ns(link.available_time) > prediction_cutoff:
        return False, None
    if link.expires_time and iso_to_epoch_ns(link.expires_time) <= prediction_cutoff:
        return False, ContextQualityFlag.PROPAGATION_LINK_STALE.value
    return True, None


def _signal_pit_eligible(signal: DonorSignalRow, *, prediction_cutoff: int) -> bool:
    if not signal.available_time:
        return False
    return iso_to_epoch_ns(signal.available_time) <= prediction_cutoff


def _attenuate(value: float | None, link_weight: float) -> float | None:
    if value is None:
        return None
    return round(max(0.0, min(1.0, value * link_weight)), 6)


def propagate_donor_signal(
    link: EntityLink,
    signal: DonorSignalRow,
    *,
    prediction_cutoff: int,
    target_entity_id: str,
) -> PropagationSummary | None:
    if link.target_entity_id.upper() != target_entity_id.upper():
        return None
    if link.source_entity_id.upper() != signal.entity_id.upper():
        return None
    if link.ambiguous:
        return None
    if link.link_weight is None:
        return None

    link_ok, _ = _link_pit_eligible(link, prediction_cutoff=prediction_cutoff)
    if not link_ok:
        return None
    if not _signal_pit_eligible(signal, prediction_cutoff=prediction_cutoff):
        return None

    if (
        signal.catalyst_strength is None
        and signal.attention_level is None
        and signal.information_value is None
        and signal.diffusion_score is None
    ):
        return None

    available_ns = max(
        iso_to_epoch_ns(link.available_time),
        iso_to_epoch_ns(signal.available_time),
    )
    quality_flags = [
        ContextQualityFlag.CROSS_ENTITY_PROPAGATION_EXPERIMENTAL.value,
        ContextQualityFlag.NO_UNIVERSAL_NEWS_SCORE.value,
    ]
    if (
        signal.catalyst_strength is None
        or signal.attention_level is None
        or signal.information_value is None
        or signal.diffusion_score is None
    ):
        quality_flags.append(ContextQualityFlag.PROPAGATION_SOURCE_UNAVAILABLE.value)

    return PropagationSummary(
        propagation_id=propagation_id_from_parts(
            link_id=link.link_id,
            source_event_id=signal.event_id,
            target_entity_id=target_entity_id,
        ),
        link_id=link.link_id,
        link_type=link.link_type,
        source_entity_id=link.source_entity_id,
        target_entity_id=link.target_entity_id,
        source_event_id=signal.event_id,
        canonical_event_type=signal.canonical_event_type,
        link_weight=round(link.link_weight, 6),
        propagated_catalyst_strength=_attenuate(signal.catalyst_strength, link.link_weight),
        propagated_attention_level=_attenuate(signal.attention_level, link.link_weight),
        propagated_information_value=_attenuate(signal.information_value, link.link_weight),
        propagated_diffusion_score=_attenuate(signal.diffusion_score, link.link_weight),
        event_time=signal.event_time,
        available_time=_epoch_ns_to_iso(available_ns),
        publication_state=PublicationState.PUBLISHED.value,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def _epoch_ns_to_iso(epoch_ns: int) -> str:
    seconds, nanos = divmod(epoch_ns, 1_000_000_000)
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{dt:%Y-%m-%dT%H:%M:%S}.{nanos:09d}Z"


def build_fixture_propagation_pipeline(
    links: list[EntityLink],
    donor_signals: list[DonorSignalRow],
    *,
    prediction_cutoff: int,
    entity_id: str,
) -> tuple[list[PropagationSummary], list[EntityLink], list[dict[str, Any]]]:
    summaries: list[PropagationSummary] = []
    admitted_links: list[EntityLink] = []
    target = entity_id.upper()
    for link in links:
        if link.target_entity_id.upper() != target:
            continue
        link_ok, _ = _link_pit_eligible(link, prediction_cutoff=prediction_cutoff)
        if not link_ok:
            continue
        admitted_links.append(link)
        if link.ambiguous or link.link_weight is None:
            continue
        for signal in donor_signals:
            summary = propagate_donor_signal(
                link,
                signal,
                prediction_cutoff=prediction_cutoff,
                target_entity_id=target,
            )
            if summary is not None:
                summaries.append(summary)

    summaries.sort(
        key=lambda item: (item.available_time, item.link_id, item.source_event_id)
    )
    adapter_rows = [propagation_summary_to_adapter_row(item) for item in summaries]
    return summaries, admitted_links, adapter_rows


def propagation_summary_to_dict(item: PropagationSummary) -> dict[str, Any]:
    return {
        "propagation_id": item.propagation_id,
        "link_id": item.link_id,
        "link_type": item.link_type,
        "source_entity_id": item.source_entity_id,
        "target_entity_id": item.target_entity_id,
        "source_event_id": item.source_event_id,
        "canonical_event_type": item.canonical_event_type,
        "link_weight": item.link_weight,
        "propagated_catalyst_strength": item.propagated_catalyst_strength,
        "propagated_attention_level": item.propagated_attention_level,
        "propagated_information_value": item.propagated_information_value,
        "propagated_diffusion_score": item.propagated_diffusion_score,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "scoring_method": SCORING_METHOD,
    }


def propagation_summary_to_adapter_row(item: PropagationSummary) -> dict[str, Any]:
    return {
        "propagation_id": item.propagation_id,
        "source_entity_id": item.source_entity_id,
        "target_entity_id": item.target_entity_id,
        "source_event_id": item.source_event_id,
        "link_type": item.link_type,
        "propagated_catalyst_strength": item.propagated_catalyst_strength,
        "propagated_attention_level": item.propagated_attention_level,
        "available_time": item.available_time,
        "scoring_method": SCORING_METHOD,
    }


def entity_link_to_dict(item: EntityLink) -> dict[str, Any]:
    return {
        "link_id": item.link_id,
        "source_entity_id": item.source_entity_id,
        "target_entity_id": item.target_entity_id,
        "link_type": item.link_type,
        "link_weight": item.link_weight,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "expires_time": item.expires_time,
        "ambiguous": item.ambiguous,
        "quality_flags": list(item.quality_flags),
    }


def build_propagation_cross_lane_evidence(
    summaries: list[PropagationSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if (
            item.propagated_catalyst_strength is not None
            and item.propagated_catalyst_strength >= PROPAGATED_CATALYST_ELEVATED_THRESHOLD
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.PROPAGATED_CATALYST_ELEVATED,
                    strength=(
                        "HIGH"
                        if item.propagated_catalyst_strength >= 0.65
                        else "MODERATE"
                    ),
                    available=True,
                    source_ref=item.source_event_id,
                    detail=(
                        f"MC15 propagated catalyst {item.propagated_catalyst_strength:.4f} "
                        f"from {item.source_entity_id} via {item.link_type} — not fused score"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "source_entity_id": item.source_entity_id,
                "target_entity_id": item.target_entity_id,
                "link_type": item.link_type,
                "propagated_catalyst_strength": item.propagated_catalyst_strength,
                "propagated_attention_level": item.propagated_attention_level,
                "scoring_method": SCORING_METHOD,
                "research_only": True,
            }
            evidence.append(row)
        if (
            item.propagated_attention_level is not None
            and item.propagated_attention_level >= PROPAGATED_ATTENTION_ELEVATED_THRESHOLD
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.PROPAGATED_ATTENTION_ELEVATED,
                    strength=(
                        "HIGH"
                        if item.propagated_attention_level >= 0.55
                        else "MODERATE"
                    ),
                    available=True,
                    source_ref=item.source_event_id,
                    detail=(
                        f"MC15 propagated attention {item.propagated_attention_level:.4f} "
                        f"from {item.source_entity_id} via {item.link_type}"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "source_entity_id": item.source_entity_id,
                "target_entity_id": item.target_entity_id,
                "link_type": item.link_type,
                "propagated_attention_level": item.propagated_attention_level,
                "propagated_information_value": item.propagated_information_value,
                "scoring_method": SCORING_METHOD,
                "research_only": True,
            }
            evidence.append(row)
    return evidence


def _aggregate_gate_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "FAIL"
    if any(row.get("gate_status") == "FAIL" for row in rows):
        return "FAIL"
    return "PASS"


def run_mc15_gate_validation(
    *,
    fixture_path: Path | None = None,
    expected_path: Path | None = None,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Run MC15 golden, PIT, ambiguity, and doctrine gates on admitted fixtures."""
    fixture = fixture_path or DEFAULT_PROPAGATION_FIXTURE
    expected_file = expected_path or DEFAULT_PROPAGATION_EXPECTED
    cutoff_ns = (
        prediction_cutoff
        if prediction_cutoff is not None
        else iso_to_epoch_ns(GATE_PREDICTION_CUTOFF)
    )
    early_cutoff_ns = iso_to_epoch_ns(GATE_EARLY_CUTOFF)

    payload = json.loads(fixture.read_text(encoding="utf-8"))
    links, donor_signals, target_symbol = load_entity_link_fixture(fixture)
    summaries, admitted_links, _ = build_fixture_propagation_pipeline(
        links,
        donor_signals,
        prediction_cutoff=cutoff_ns,
        entity_id=target_symbol,
    )
    early_summaries, _, _ = build_fixture_propagation_pipeline(
        links,
        donor_signals,
        prediction_cutoff=early_cutoff_ns,
        entity_id=target_symbol,
    )

    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    actual_rows = [propagation_summary_to_dict(item) for item in summaries]
    golden_match = actual_rows == expected.get("propagation_summaries", [])

    ambiguous_links = [link for link in links if link.ambiguous]
    ambiguous_produced = any(
        item.link_id in {link.link_id for link in ambiguous_links} for item in summaries
    )
    ambiguity_gate = not ambiguous_produced

    forbidden_fields = ("news_score", "universal_score", "combined_score", "fused_score")
    doctrine_gate = all(
        not any(field in row for field in forbidden_fields) for row in actual_rows
    ) and all(
        any(key.startswith("propagated_") for key in row)
        for row in actual_rows
        if row
    )

    early_event_ids = {item.source_event_id for item in early_summaries}
    pit_gate = "nvda-guidance-cut" not in early_event_ids or len(early_summaries) < len(
        summaries
    )

    cross_lane = build_propagation_cross_lane_evidence(
        summaries,
        symbol=target_symbol,
        prediction_cutoff=cutoff_ns,
    )
    cross_lane_gate = bool(cross_lane) and all(
        (row.get("metadata") or {}).get("research_only") for row in cross_lane
    )

    gate_summary = [
        {
            "gate_milestone": "MC15-GOLDEN",
            "gate_status": "PASS" if golden_match else "FAIL",
        },
        {
            "gate_milestone": "MC15-PIT",
            "gate_status": "PASS" if pit_gate else "FAIL",
        },
        {
            "gate_milestone": "MC15-AMBIGUITY",
            "gate_status": "PASS" if ambiguity_gate else "FAIL",
        },
        {
            "gate_milestone": "MC15-DOCTRINE",
            "gate_status": "PASS" if doctrine_gate else "FAIL",
        },
        {
            "gate_milestone": "MC15-CROSS-LANE",
            "gate_status": "PASS" if cross_lane_gate else "FAIL",
        },
    ]

    return {
        "artifact_type": "MC15_CROSS_ENTITY_PROPAGATION_GATE_VALIDATION_REPORT",
        "scope": "fixture",
        "research_only": True,
        "not_trade_signal": True,
        "aggregate_status": _aggregate_gate_status(gate_summary),
        "fixture_refs": [
            {
                "role": "entity_link_graph",
                "repository_relative_path": fixture.relative_to(
                    Path(__file__).resolve().parents[4]
                ).as_posix(),
                "admission_id": payload.get("admission_id"),
                "target_symbol": target_symbol,
            },
            {
                "role": "golden_expected",
                "repository_relative_path": expected_file.relative_to(
                    Path(__file__).resolve().parents[4]
                ).as_posix(),
            },
        ],
        "gate_summary": gate_summary,
        "propagation_count": len(summaries),
        "entity_link_count": len(admitted_links),
        "ambiguous_link_count": len(ambiguous_links),
        "propagation_summaries": actual_rows,
    }


__all__ = [
    "DEFAULT_PROPAGATION_EXPECTED",
    "DEFAULT_PROPAGATION_FIXTURE",
    "DonorSignalRow",
    "EntityLink",
    "EntityLinkType",
    "GATE_EARLY_CUTOFF",
    "GATE_PREDICTION_CUTOFF",
    "PRODUCER_VERSION",
    "PROPAGATED_ATTENTION_ELEVATED_THRESHOLD",
    "PROPAGATED_CATALYST_ELEVATED_THRESHOLD",
    "PropagationSummary",
    "SCORING_METHOD",
    "build_fixture_propagation_pipeline",
    "build_propagation_cross_lane_evidence",
    "entity_link_to_dict",
    "load_entity_link_fixture",
    "propagate_donor_signal",
    "propagation_id_from_parts",
    "propagation_summary_to_adapter_row",
    "propagation_summary_to_dict",
    "run_mc15_gate_validation",
]

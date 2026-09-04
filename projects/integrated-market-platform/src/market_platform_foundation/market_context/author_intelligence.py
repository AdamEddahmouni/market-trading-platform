"""MC14 social / author intelligence — influence vs accuracy (experimental)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    AccuracyEvidence,
    AuthorEvidence,
    AuthorIdentity,
    ContextQualityFlag,
    InfluenceEvidence,
    PublicationState,
    accuracy_evidence_to_dict,
    author_evidence_to_dict,
    author_id_from_handle,
    influence_evidence_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "market_context_author_intelligence_v1"
SCORING_METHOD = "author_intelligence_v1"
FOLLOWER_SCALE = 100_000.0
REPOST_SCALE = 5_000.0
INFLUENCE_ELEVATED_THRESHOLD = 0.60
ACCURACY_LOW_THRESHOLD = 0.50


@dataclass(frozen=True, slots=True)
class SocialAuthorFixtureRow:
    document_id: str
    handle: str
    platform: str
    display_name: str | None
    entity_id: str
    follower_count: int | None
    repost_count: int | None
    labeled_correct: float | None
    event_time: str
    available_time: str
    outcome_available_time: str | None


@dataclass(frozen=True, slots=True)
class AuthorIntelligenceSummary:
    author_id: str
    handle: str
    platform: str
    display_name: str | None
    document_id: str
    entity_id: str
    influence_score: float | None
    accuracy_score: float | None
    follower_count: int | None
    repost_count: int | None
    labeled_correct: float | None
    outcome_available_time: str | None
    event_time: str
    available_time: str
    publication_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_social_author_fixture(path: Path) -> list[SocialAuthorFixtureRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("posts") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    result: list[SocialAuthorFixtureRow] = []
    symbol = str(payload.get("symbol", "BOXL")).upper() if isinstance(payload, dict) else "BOXL"
    for row in rows:
        if not isinstance(row, dict):
            continue
        handle = str(row.get("handle", "")).strip()
        if not handle:
            continue
        symbols = row.get("associated_symbols") or [symbol]
        entity_id = str(symbols[0]).upper() if symbols else symbol
        result.append(
            SocialAuthorFixtureRow(
                document_id=str(row.get("document_id", handle)),
                handle=handle,
                platform=str(row.get("platform", "fixture_social")),
                display_name=row.get("display_name"),
                entity_id=entity_id,
                follower_count=_optional_int(row.get("follower_count")),
                repost_count=_optional_int(row.get("repost_count")),
                labeled_correct=_optional_float(row.get("labeled_correct")),
                event_time=str(row.get("event_time", "")),
                available_time=str(row.get("available_time", "")),
                outcome_available_time=(
                    str(row["outcome_available_time"])
                    if row.get("outcome_available_time")
                    else None
                ),
            )
        )
    return result


def compute_influence_score(
    follower_count: int | None,
    repost_count: int | None,
) -> tuple[float | None, bool]:
    components: list[float] = []
    if follower_count is not None:
        components.append(min(1.0, follower_count / FOLLOWER_SCALE))
    if repost_count is not None:
        components.append(min(1.0, repost_count / REPOST_SCALE))
    if not components:
        return None, True
    return round(sum(components) / len(components), 6), False


def compute_accuracy_score(
    labeled_correct: float | None,
    *,
    outcome_available_time: str | None,
    post_available_time: str,
    prediction_cutoff: int,
) -> tuple[float | None, bool]:
    if outcome_available_time is None or labeled_correct is None:
        return None, True
    outcome_ns = iso_to_epoch_ns(outcome_available_time)
    post_ns = iso_to_epoch_ns(post_available_time)
    if outcome_ns > prediction_cutoff or outcome_ns <= post_ns:
        return None, True
    return round(max(0.0, min(1.0, labeled_correct)), 6), False


def score_social_author_row(
    row: SocialAuthorFixtureRow,
    *,
    prediction_cutoff: int,
) -> AuthorIntelligenceSummary | None:
    if not row.available_time:
        return None
    if iso_to_epoch_ns(row.available_time) > prediction_cutoff:
        return None

    quality_flags = [
        ContextQualityFlag.INFLUENCE_NOT_ACCURACY.value,
        ContextQualityFlag.SOCIAL_AUTHOR_EXPERIMENTAL.value,
    ]
    influence, influence_missing = compute_influence_score(
        row.follower_count,
        row.repost_count,
    )
    if influence_missing:
        quality_flags.append(ContextQualityFlag.SOCIAL_INFLUENCE_UNAVAILABLE.value)

    accuracy, accuracy_unvalidated = compute_accuracy_score(
        row.labeled_correct,
        outcome_available_time=row.outcome_available_time,
        post_available_time=row.available_time,
        prediction_cutoff=prediction_cutoff,
    )
    if accuracy_unvalidated:
        quality_flags.append(ContextQualityFlag.AUTHOR_ACCURACY_UNVALIDATED.value)

    author_id = author_id_from_handle(row.handle, platform=row.platform)
    return AuthorIntelligenceSummary(
        author_id=author_id,
        handle=row.handle,
        platform=row.platform,
        display_name=row.display_name,
        document_id=row.document_id,
        entity_id=row.entity_id,
        influence_score=influence,
        accuracy_score=accuracy,
        follower_count=row.follower_count,
        repost_count=row.repost_count,
        labeled_correct=row.labeled_correct if accuracy is not None else None,
        outcome_available_time=row.outcome_available_time,
        event_time=row.event_time,
        available_time=row.available_time,
        publication_state=PublicationState.PUBLISHED.value,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
    )


def build_author_evidence(summary: AuthorIntelligenceSummary) -> AuthorEvidence:
    identity = AuthorIdentity(
        author_id=summary.author_id,
        handle=summary.handle,
        platform=summary.platform,
        display_name=summary.display_name,
        event_time=summary.event_time,
        available_time=summary.available_time,
        provenance_ref=summary.document_id,
        quality_flags=summary.quality_flags,
    )
    influence = InfluenceEvidence(
        author_id=summary.author_id,
        entity_id=summary.entity_id,
        influence_score=summary.influence_score,
        follower_count=summary.follower_count,
        repost_count=summary.repost_count,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=summary.document_id,
        quality_flags=summary.quality_flags,
    )
    accuracy = AccuracyEvidence(
        author_id=summary.author_id,
        entity_id=summary.entity_id,
        accuracy_score=summary.accuracy_score,
        labeled_correct=summary.labeled_correct,
        outcome_available_time=summary.outcome_available_time,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=summary.document_id,
        quality_flags=summary.quality_flags,
    )
    return AuthorEvidence(
        author=identity,
        influence=influence,
        accuracy=accuracy,
        document_id=summary.document_id,
        event_time=summary.event_time,
        available_time=summary.available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=summary.document_id,
        quality_flags=summary.quality_flags,
    )


def build_fixture_author_intelligence_pipeline(
    rows: list[SocialAuthorFixtureRow],
    *,
    prediction_cutoff: int,
    entity_id: str,
) -> tuple[list[AuthorEvidence], list[AuthorIntelligenceSummary], list[dict[str, Any]]]:
    summaries: list[AuthorIntelligenceSummary] = []
    evidence_rows: list[AuthorEvidence] = []
    adapter_rows: list[dict[str, Any]] = []
    for row in rows:
        if row.entity_id != entity_id.upper():
            continue
        summary = score_social_author_row(row, prediction_cutoff=prediction_cutoff)
        if summary is None:
            continue
        summaries.append(summary)
        evidence_rows.append(build_author_evidence(summary))
        adapter_rows.append(author_intelligence_summary_to_adapter_row(summary))
    summaries.sort(key=lambda item: (item.available_time, item.handle))
    evidence_rows.sort(key=lambda item: (item.available_time, item.author.handle))
    adapter_rows.sort(key=lambda item: (item["available_time"], item["handle"]))
    return evidence_rows, summaries, adapter_rows


def author_intelligence_summary_to_dict(item: AuthorIntelligenceSummary) -> dict[str, Any]:
    return {
        "author_id": item.author_id,
        "handle": item.handle,
        "platform": item.platform,
        "display_name": item.display_name,
        "document_id": item.document_id,
        "entity_id": item.entity_id,
        "influence_score": item.influence_score,
        "accuracy_score": item.accuracy_score,
        "follower_count": item.follower_count,
        "repost_count": item.repost_count,
        "labeled_correct": item.labeled_correct,
        "outcome_available_time": item.outcome_available_time,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "quality_flags": list(item.quality_flags),
        "scoring_method": SCORING_METHOD,
    }


def author_intelligence_summary_to_adapter_row(item: AuthorIntelligenceSummary) -> dict[str, Any]:
    return {
        "author_id": item.author_id,
        "handle": item.handle,
        "document_id": item.document_id,
        "entity_id": item.entity_id,
        "influence_score": item.influence_score,
        "accuracy_score": item.accuracy_score,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "scoring_method": SCORING_METHOD,
    }


def build_author_intelligence_cross_lane_evidence(
    summaries: list[AuthorIntelligenceSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if (
            item.influence_score is not None
            and item.influence_score >= INFLUENCE_ELEVATED_THRESHOLD
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.SOCIAL_INFLUENCE_ELEVATED,
                    strength="HIGH" if item.influence_score >= 0.85 else "MODERATE",
                    available=True,
                    source_ref=item.document_id,
                    detail=(
                        f"MC14 social influence {item.influence_score:.4f} "
                        f"for @{item.handle} — not accuracy"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "author_id": item.author_id,
                "handle": item.handle,
                "influence_score": item.influence_score,
                "accuracy_score": item.accuracy_score,
                "scoring_method": SCORING_METHOD,
                "research_only": True,
            }
            evidence.append(row)
        if (
            item.accuracy_score is not None
            and item.accuracy_score < ACCURACY_LOW_THRESHOLD
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.AUTHOR_ACCURACY_LOW,
                    strength="HIGH",
                    available=True,
                    source_ref=item.document_id,
                    detail=(
                        f"MC14 author accuracy {item.accuracy_score:.4f} "
                        f"for @{item.handle} — influence is not truth"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "author_id": item.author_id,
                "handle": item.handle,
                "influence_score": item.influence_score,
                "accuracy_score": item.accuracy_score,
                "scoring_method": SCORING_METHOD,
                "research_only": True,
            }
            evidence.append(row)
    return evidence


def author_contracts_to_dict(evidence: AuthorEvidence) -> dict[str, Any]:
    return {
        "author_evidence": author_evidence_to_dict(evidence),
        "influence_evidence": influence_evidence_to_dict(evidence.influence),
        "accuracy_evidence": accuracy_evidence_to_dict(evidence.accuracy),
    }


__all__ = [
    "ACCURACY_LOW_THRESHOLD",
    "AuthorIntelligenceSummary",
    "INFLUENCE_ELEVATED_THRESHOLD",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "SocialAuthorFixtureRow",
    "author_intelligence_summary_to_adapter_row",
    "author_intelligence_summary_to_dict",
    "build_author_evidence",
    "build_author_intelligence_cross_lane_evidence",
    "build_fixture_author_intelligence_pipeline",
    "compute_accuracy_score",
    "compute_influence_score",
    "load_social_author_fixture",
    "score_social_author_row",
]

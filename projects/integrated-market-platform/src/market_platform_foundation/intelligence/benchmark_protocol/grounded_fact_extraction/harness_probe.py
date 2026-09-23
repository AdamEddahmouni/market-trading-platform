"""Harness-fixture factual probes for legacy Smoke10 (no evaluator gold, no LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..admitted_factual_gold.fact_normalization import normalize_scalar
from .answerability import (
    AnswerabilityClass,
    abstention_reason_for,
    available_capabilities_from_payload,
    classify_answerability,
)
from .claim_linkage import (
    facts_include_negative,
    facts_preserve_provenance,
    link_claim_to_evidence,
)
from .evidence_projection import ProjectedArtifact, artifact_support_hash
from .pipeline import GroundedFactualOutcome, _detect_conflicts
from .question_handlers import (
    handle_market_instrument,
    handle_row_count,
    handle_session_identity,
)
from .types import (
    FACT_ANSWER_NORMALIZATION_POLICY_VERSION,
    FACTUAL_UNKNOWN_DISPOSITION_VERSION,
    FactualAnswerDisposition,
    GROUNDED_FACT_EXTRACTION_VERSION,
)


def _load_harness_artifact(
    repository_root: Path,
    fixture_rel: str | None,
) -> ProjectedArtifact | None:
    if not fixture_rel:
        return None
    path = repository_root / fixture_rel
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return ProjectedArtifact(
        artifact_ref=fixture_rel,
        source_type="HISTORICAL_HARNESS_FIXTURE",
        payload=payload,
        support_hash=artifact_support_hash(repository_root, fixture_rel),
    )


def _format_answer(facts: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in facts:
        field = str(row["field"])
        value = row["value"]
        if isinstance(value, list):
            rendered = ", ".join(normalize_scalar(v, normalization={}) for v in value)
            parts.append(f"{field}: [{rendered}]")
        else:
            parts.append(f"{field}: {normalize_scalar(value, normalization={})}")
    return "; ".join(parts)


def _enrich_with_claim_links(
    facts: list[dict[str, Any]],
    artifact: ProjectedArtifact,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in facts:
        if row.get("claim_link"):
            enriched.append(dict(row))
            continue
        enriched.append(
            link_claim_to_evidence(
                field=str(row["field"]),
                value=row.get("value"),
                artifact=artifact,
                source_path=str(row.get("source_path") or "unknown"),
                confidence=str(row.get("confidence") or "ADMITTED_ARTIFACT"),
            )
        )
    return enriched


def answer_harness_factual_probe(
    *,
    repository_root: Path,
    fixture_rel: str | None,
    blind_mode: str | None,
    case_id: str,
) -> GroundedFactualOutcome:
    """
    Answer a legacy IBP facts probe from a historical harness fixture.

    Does not consult evaluator gold. When evidence is absent or capability-
    mismatched, returns UNKNOWN with an explicit abstention reason (never a
    quality-narrative dump).
    """
    del case_id  # identity only; never branch on case_id
    artifact = _load_harness_artifact(repository_root, fixture_rel)
    evidence_present = artifact is not None
    available = (
        available_capabilities_from_payload(artifact.payload) if artifact is not None else frozenset()
    )
    answerability = classify_answerability(
        blind_mode=blind_mode,
        evidence_present=evidence_present,
        available_capabilities=available,
    )
    if answerability in {
        AnswerabilityClass.ABSENT_EVIDENCE,
        AnswerabilityClass.CAPABILITY_ABSENT,
    }:
        disposition = (
            FactualAnswerDisposition.ABSENT_EVIDENCE
            if answerability == AnswerabilityClass.ABSENT_EVIDENCE
            else FactualAnswerDisposition.CAPABILITY_ABSENT
        )
        return GroundedFactualOutcome(
            disposition=disposition,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason=abstention_reason_for(answerability),
        )

    assert artifact is not None
    # Bar-backed modes: extract instrument/session/row structural facts only.
    candidates: list[dict[str, Any]] = []
    candidates.extend(handle_market_instrument(artifact, "primary instrument"))
    candidates.extend(handle_session_identity(artifact, "session keys"))
    candidates.extend(handle_row_count(artifact, "raw row count"))
    facts = _enrich_with_claim_links(candidates, artifact)

    if _detect_conflicts(facts):
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.CONFLICTING_EVIDENCE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason=abstention_reason_for(AnswerabilityClass.CONTRADICTING_EVIDENCE),
        )

    if not facts:
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.EVIDENCE_NOT_PROJECTABLE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="NO_SUPPORTED_FACT_CANDIDATES",
        )

    if not facts_preserve_provenance(facts):
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.INSUFFICIENT_PROVENANCE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="INSUFFICIENT_PROVENANCE",
        )

    disposition = (
        FactualAnswerDisposition.NEGATIVE_EVIDENCE
        if facts_include_negative(facts)
        else FactualAnswerDisposition.SUPPORTED_ANSWER
    )
    return GroundedFactualOutcome(
        disposition=disposition,
        answer=_format_answer(facts),
        structured_facts=tuple(facts),
        abstention_reason=None,
        extraction_version=GROUNDED_FACT_EXTRACTION_VERSION,
        normalization_policy_version=FACT_ANSWER_NORMALIZATION_POLICY_VERSION,
        unknown_disposition_version=FACTUAL_UNKNOWN_DISPOSITION_VERSION,
    )


__all__ = ["answer_harness_factual_probe"]

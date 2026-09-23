"""Question + admitted evidence → grounded structured answer or UNKNOWN."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..admitted_factual_gold.fact_normalization import normalize_scalar
from .answerability import AnswerabilityClass, classify_answerability
from .claim_linkage import facts_include_negative, facts_preserve_provenance
from .evidence_projection import load_projected_artifacts, primary_artifact
from .question_handlers import QUESTION_CLASS_HANDLERS
from .temporal_cutoff import historical_payload_violates_cutoff
from .types import (
    FACT_ANSWER_NORMALIZATION_POLICY_VERSION,
    FACTUAL_UNKNOWN_DISPOSITION_VERSION,
    FactualAnswerDisposition,
    GROUNDED_FACT_EXTRACTION_VERSION,
)


@dataclass(frozen=True, slots=True)
class GroundedFactualOutcome:
    disposition: FactualAnswerDisposition
    answer: str
    structured_facts: tuple[dict[str, Any], ...]
    abstention_reason: str | None
    extraction_version: str = GROUNDED_FACT_EXTRACTION_VERSION
    normalization_policy_version: str = FACT_ANSWER_NORMALIZATION_POLICY_VERSION
    unknown_disposition_version: str = FACTUAL_UNKNOWN_DISPOSITION_VERSION


def _format_answer(
    facts: list[dict[str, Any]],
    *,
    normalization: dict[str, Any],
) -> str:
    parts: list[str] = []
    for row in facts:
        field = str(row["field"])
        value = row["value"]
        if isinstance(value, list):
            rendered = ", ".join(normalize_scalar(v, normalization=normalization) for v in value)
            parts.append(f"{field}: [{rendered}]")
        else:
            parts.append(f"{field}: {normalize_scalar(value, normalization=normalization)}")
    return "; ".join(parts)


def _facts_have_provenance(facts: list[dict[str, Any]]) -> bool:
    return facts_preserve_provenance(facts)


def _detect_conflicts(facts: list[dict[str, Any]]) -> bool:
    by_field: dict[str, set[str]] = {}
    for row in facts:
        field = str(row["field"])
        token = repr(row.get("value"))
        by_field.setdefault(field, set()).add(token)
    return any(len(values) > 1 for values in by_field.values())


def answer_admitted_factual_question(
    *,
    question: dict[str, Any],
    temporal_cutoff: dict[str, Any] | None,
    evidence_set: dict[str, Any],
    repository_root: Any,
    answer_normalization: dict[str, Any] | None = None,
) -> GroundedFactualOutcome:
    """Generic admitted-evidence factual answer path (no evaluator gold)."""
    normalization = answer_normalization or {}
    question_class = str(question.get("question_class") or "")
    question_text = str(question.get("text") or "")
    handler = QUESTION_CLASS_HANDLERS.get(question_class)
    projected = load_projected_artifacts(repository_root, evidence_set)
    artifact = primary_artifact(projected)
    if handler is None or artifact is None:
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.EVIDENCE_NOT_PROJECTABLE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="QUESTION_CLASS_OR_EVIDENCE_UNAVAILABLE",
        )

    if historical_payload_violates_cutoff(artifact.payload, temporal_cutoff):
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.TEMPORAL_CUTOFF_REFUSED,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="TEMPORAL_CUTOFF_VIOLATION",
        )

    facts = handler(artifact, question_text)
    answerability = classify_answerability(
        blind_mode=None,
        evidence_present=True,
        conflicting=_detect_conflicts(facts) if facts else False,
        negative_fact_present=facts_include_negative(facts) if facts else False,
        question_class=question_class,
    )

    if not facts:
        if question_class == "ABSTENTION":
            return GroundedFactualOutcome(
                disposition=FactualAnswerDisposition.CORRECT_UNKNOWN,
                answer="UNKNOWN",
                structured_facts=(),
                abstention_reason="NOT_IN_ADMITTED_EVIDENCE",
            )
        if question_class == "UNANSWERABLE_METRIC":
            return GroundedFactualOutcome(
                disposition=FactualAnswerDisposition.CORRECT_UNKNOWN,
                answer="UNKNOWN",
                structured_facts=(),
                abstention_reason="METRIC_NOT_IN_ADMITTED_ARTIFACT",
            )
        # Absent field in otherwise loadable artifact ≠ negative observation.
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.ABSENT_EVIDENCE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="ABSENT_FIELD_IN_ADMITTED_EVIDENCE",
        )

    if answerability == AnswerabilityClass.CONTRADICTING_EVIDENCE or _detect_conflicts(facts):
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.CONFLICTING_EVIDENCE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="CONFLICTING_EVIDENCE",
        )

    if not _facts_have_provenance(facts):
        return GroundedFactualOutcome(
            disposition=FactualAnswerDisposition.INSUFFICIENT_PROVENANCE,
            answer="UNKNOWN",
            structured_facts=(),
            abstention_reason="INSUFFICIENT_PROVENANCE",
        )

    disposition = (
        FactualAnswerDisposition.NEGATIVE_EVIDENCE
        if answerability == AnswerabilityClass.NEGATIVE_EVIDENCE
        else FactualAnswerDisposition.SUPPORTED_ANSWER
    )
    return GroundedFactualOutcome(
        disposition=disposition,
        answer=_format_answer(facts, normalization=normalization),
        structured_facts=tuple(facts),
        abstention_reason=None,
    )


__all__ = [
    "GroundedFactualOutcome",
    "answer_admitted_factual_question",
]

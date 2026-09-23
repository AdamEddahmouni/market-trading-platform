"""Versioned types for grounded factual extraction (no evaluator gold)."""

from __future__ import annotations

from enum import StrEnum

GROUNDED_FACT_EXTRACTION_VERSION = "imp.grounded-fact-extraction/1.1.0"
FACT_ANSWER_NORMALIZATION_POLICY_VERSION = "imp.factual-answer-normalization/1.0.0"
FACTUAL_UNKNOWN_DISPOSITION_VERSION = "imp.factual-unknown-disposition/1.1.0"


class FactualAnswerDisposition(StrEnum):
    """Why the pipeline produced an answer or UNKNOWN (orthogonal to evaluator verdicts)."""

    SUPPORTED_ANSWER = "SUPPORTED_ANSWER"
    CORRECT_UNKNOWN = "CORRECT_UNKNOWN"
    UNNECESSARY_UNKNOWN = "UNNECESSARY_UNKNOWN"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
    TEMPORAL_CUTOFF_REFUSED = "TEMPORAL_CUTOFF_REFUSED"
    EVIDENCE_NOT_PROJECTABLE = "EVIDENCE_NOT_PROJECTABLE"
    ABSENT_EVIDENCE = "ABSENT_EVIDENCE"
    CAPABILITY_ABSENT = "CAPABILITY_ABSENT"
    NEGATIVE_EVIDENCE = "NEGATIVE_EVIDENCE"


__all__ = [
    "FACT_ANSWER_NORMALIZATION_POLICY_VERSION",
    "FACTUAL_UNKNOWN_DISPOSITION_VERSION",
    "FactualAnswerDisposition",
    "GROUNDED_FACT_EXTRACTION_VERSION",
]

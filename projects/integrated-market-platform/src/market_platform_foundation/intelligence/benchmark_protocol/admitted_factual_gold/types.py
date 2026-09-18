"""IBP admitted factual gold — contract identifiers (Lane M1; no cases)."""

from __future__ import annotations

from enum import StrEnum

IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION = "imp.ibp-admitted-factual-gold/1.0.0"
IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND = "ibp_admitted_factual_gold_protocol_v1"
IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID = "LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1"
IBP_FACTUAL_SMOKE_PROTOCOL_VERSION = "IBP_FACTUAL_SMOKE_V1"
IBP_FACTUAL_GOLD_HASH_ALGORITHM = "sha256-canonical-json-v1"
IBP_FACTUAL_GOLD_EVALUATOR_STORAGE_PREFIX = "evaluator_only/admitted_factual_gold/"

FORBIDDEN_SYNTHETIC_GOLD_PREFIX = "synthetic-gold-"


class AdmittedFactualSourceType(StrEnum):
    """Evidence sources admissible for factual gold construction."""

    HISTORICAL_DEVELOPMENT_ARTIFACT = "HISTORICAL_DEVELOPMENT_ARTIFACT"
    ADMITTED_FIXTURE_RECORD = "ADMITTED_FIXTURE_RECORD"
    CORPUS_SNAPSHOT_REF = "CORPUS_SNAPSHOT_REF"
    GOVERNED_RESEARCH_MANIFEST = "GOVERNED_RESEARCH_MANIFEST"


class AdmittedFactualEvidenceAccessMode(StrEnum):
    """Mutually exclusive evidence access modes (no implicit mixing)."""

    ADMITTED_EVIDENCE_FIXED = "ADMITTED_EVIDENCE_FIXED"
    CURRENT_WEB_LOOKUP = "CURRENT_WEB_LOOKUP"


class FactualUnknownVerdict(StrEnum):
    """Evaluator-encoded UNKNOWN semantics (not post-hoc relabeling)."""

    CORRECT_UNKNOWN = "CORRECT_UNKNOWN"
    UNNECESSARY_UNKNOWN = "UNNECESSARY_UNKNOWN"
    UNSUPPORTED_ASSERTION = "UNSUPPORTED_ASSERTION"


class FactualCaseScoringGate(StrEnum):
    """Subset gate for scored factual cases."""

    ANSWERABLE_FROM_ADMITTED_EVIDENCE = "ANSWERABLE_FROM_ADMITTED_EVIDENCE"
    EXCLUDED_UNANSWERABLE = "EXCLUDED_UNANSWERABLE"


__all__ = [
    "AdmittedFactualEvidenceAccessMode",
    "AdmittedFactualSourceType",
    "FactualCaseScoringGate",
    "FactualUnknownVerdict",
    "FORBIDDEN_SYNTHETIC_GOLD_PREFIX",
    "IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND",
    "IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID",
    "IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION",
    "IBP_FACTUAL_GOLD_EVALUATOR_STORAGE_PREFIX",
    "IBP_FACTUAL_GOLD_HASH_ALGORITHM",
    "IBP_FACTUAL_SMOKE_PROTOCOL_VERSION",
]

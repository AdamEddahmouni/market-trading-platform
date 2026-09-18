"""IBP admitted factual gold methodology contract (Lane M1 — schema only)."""

from .constants import FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS
from .hashing import (
    compute_case_gold_hash,
    compute_caseset_hash,
    compute_goldset_hash,
    factual_gold_hash_algorithm,
)
from .protocol import (
    candidate_factual_gold_protocol_path,
    default_factual_gold_protocol_path,
    empty_protocol_template,
    load_candidate_factual_gold_protocol,
    load_factual_gold_protocol,
)
from .admitted_evidence_context import (
    admitted_artifacts_accessible,
    build_admitted_evidence_context,
    required_artifact_refs,
)
from .factual_blind_input import build_factual_blind_case_input
from .factual_contamination_audit import audit_factual_smoke_run_contamination
from .factual_evaluator import (
    FACTUAL_CASE_DIMENSIONS,
    load_factual_evaluator_gold,
    score_factual_case_dimensions,
)
from .factual_smoke_execution import (
    IBP_FACTUAL_SMOKE_CONTRACT_ID,
    execute_factual_smoke_baseline,
    execute_factual_smoke_case,
    freeze_factual_smoke_run_configuration,
    scored_factual_case_ids,
)
from .sut_projection import (
    assert_factual_case_safe_for_sut,
    project_factual_case_for_sut,
    strip_factual_gold_evaluator_fields,
)
from .types import (
    AdmittedFactualEvidenceAccessMode,
    AdmittedFactualSourceType,
    FactualCaseScoringGate,
    FactualFactVerdict,
    FactualUnknownVerdict,
    IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND,
    IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID,
    IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION,
    IBP_FACTUAL_GOLD_EVALUATOR_STORAGE_PREFIX,
    IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
)
from .validation import (
    AdmittedFactualGoldContractError,
    validate_factual_gold_case,
    validate_factual_gold_protocol,
)

__all__ = [
    "AdmittedFactualEvidenceAccessMode",
    "AdmittedFactualGoldContractError",
    "AdmittedFactualSourceType",
    "FACTUAL_CASE_DIMENSIONS",
    "FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS",
    "FactualCaseScoringGate",
    "FactualFactVerdict",
    "FactualUnknownVerdict",
    "IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND",
    "IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID",
    "IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION",
    "IBP_FACTUAL_GOLD_EVALUATOR_STORAGE_PREFIX",
    "IBP_FACTUAL_SMOKE_CONTRACT_ID",
    "IBP_FACTUAL_SMOKE_PROTOCOL_VERSION",
    "admitted_artifacts_accessible",
    "assert_factual_case_safe_for_sut",
    "audit_factual_smoke_run_contamination",
    "build_admitted_evidence_context",
    "build_factual_blind_case_input",
    "compute_case_gold_hash",
    "compute_caseset_hash",
    "compute_goldset_hash",
    "candidate_factual_gold_protocol_path",
    "default_factual_gold_protocol_path",
    "empty_protocol_template",
    "execute_factual_smoke_baseline",
    "execute_factual_smoke_case",
    "factual_gold_hash_algorithm",
    "freeze_factual_smoke_run_configuration",
    "load_candidate_factual_gold_protocol",
    "load_factual_evaluator_gold",
    "load_factual_gold_protocol",
    "project_factual_case_for_sut",
    "required_artifact_refs",
    "score_factual_case_dimensions",
    "scored_factual_case_ids",
    "strip_factual_gold_evaluator_fields",
    "validate_factual_gold_case",
    "validate_factual_gold_protocol",
]

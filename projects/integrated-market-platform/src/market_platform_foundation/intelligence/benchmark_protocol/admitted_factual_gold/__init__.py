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
from .sut_projection import (
    assert_factual_case_safe_for_sut,
    project_factual_case_for_sut,
    strip_factual_gold_evaluator_fields,
)
from .types import (
    AdmittedFactualEvidenceAccessMode,
    AdmittedFactualSourceType,
    FactualCaseScoringGate,
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
    "FACTUAL_GOLD_EVALUATOR_ONLY_CASE_KEYS",
    "FactualCaseScoringGate",
    "FactualUnknownVerdict",
    "IBP_ADMITTED_FACTUAL_GOLD_ARTIFACT_KIND",
    "IBP_ADMITTED_FACTUAL_GOLD_HYPOTHESIS_ID",
    "IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION",
    "IBP_FACTUAL_GOLD_EVALUATOR_STORAGE_PREFIX",
    "IBP_FACTUAL_SMOKE_PROTOCOL_VERSION",
    "assert_factual_case_safe_for_sut",
    "compute_case_gold_hash",
    "compute_caseset_hash",
    "compute_goldset_hash",
    "candidate_factual_gold_protocol_path",
    "default_factual_gold_protocol_path",
    "empty_protocol_template",
    "factual_gold_hash_algorithm",
    "load_candidate_factual_gold_protocol",
    "load_factual_gold_protocol",
    "project_factual_case_for_sut",
    "strip_factual_gold_evaluator_fields",
    "validate_factual_gold_case",
    "validate_factual_gold_protocol",
]

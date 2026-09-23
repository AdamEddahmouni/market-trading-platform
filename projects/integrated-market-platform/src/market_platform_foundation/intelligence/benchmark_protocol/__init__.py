"""Intelligence Benchmark Protocol (IBP) — minimal v1 integration layer."""

from .contamination import (
    BenchmarkContaminationError,
    assert_historical_manifest_admissible,
    assert_no_evaluator_gold_in_system_bundle,
    strip_evaluator_only_fields,
)
from .historical_harness_adapter import adapt_historical_research_run_manifest_v1
from .protocol_controls import (
    CONTAMINATED_CASE_POLICY,
    CONTEXT_RESET_POLICY,
    EVIDENCE_CLASS,
    LOOKAHEAD_POLICY,
    VANITY_AGGREGATE_SCORE_POLICY,
    apply_contamination_invalidation,
    assert_no_lookahead_in_blind_input,
    assert_no_vanity_aggregate_score,
    build_protocol_v1_freeze_certificate,
)
from .readiness import assess_benchmark_smoke10_readiness
from .smoke10 import build_smoke10_invocation_contract
from .smoke10_contamination_audit import audit_smoke10_run_contamination
from .smoke10_execution import execute_smoke10_baseline, freeze_smoke10_run_configuration
from .suite_catalog import load_suite_catalog, smoke10_case_ids, suite_catalog_fingerprint
from .admitted_factual_gold import (
    IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION,
    IBP_FACTUAL_SMOKE_PROTOCOL_VERSION,
    load_factual_gold_protocol,
)
from .types import (
    IBP_FULL_SUITE_CASE_COUNT,
    IBP_PROTOCOL_ID,
    IBP_SMOKE10_CASE_COUNT,
    IBP_SMOKE10_CONTRACT_ID,
)

__all__ = [
    "IBP_ADMITTED_FACTUAL_GOLD_SCHEMA_VERSION",
    "IBP_FACTUAL_SMOKE_PROTOCOL_VERSION",
    "BenchmarkContaminationError",
    "CONTAMINATED_CASE_POLICY",
    "CONTEXT_RESET_POLICY",
    "EVIDENCE_CLASS",
    "IBP_FULL_SUITE_CASE_COUNT",
    "IBP_PROTOCOL_ID",
    "IBP_SMOKE10_CASE_COUNT",
    "IBP_SMOKE10_CONTRACT_ID",
    "LOOKAHEAD_POLICY",
    "VANITY_AGGREGATE_SCORE_POLICY",
    "adapt_historical_research_run_manifest_v1",
    "apply_contamination_invalidation",
    "assert_historical_manifest_admissible",
    "assert_no_evaluator_gold_in_system_bundle",
    "assert_no_lookahead_in_blind_input",
    "assert_no_vanity_aggregate_score",
    "assess_benchmark_smoke10_readiness",
    "audit_smoke10_run_contamination",
    "build_protocol_v1_freeze_certificate",
    "build_smoke10_invocation_contract",
    "execute_smoke10_baseline",
    "freeze_smoke10_run_configuration",
    "load_factual_gold_protocol",
    "load_suite_catalog",
    "smoke10_case_ids",
    "strip_evaluator_only_fields",
    "suite_catalog_fingerprint",
]

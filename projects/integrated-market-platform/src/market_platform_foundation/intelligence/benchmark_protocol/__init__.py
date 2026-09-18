"""Intelligence Benchmark Protocol (IBP) — minimal v1 integration layer."""

from .contamination import (
    BenchmarkContaminationError,
    assert_historical_manifest_admissible,
    assert_no_evaluator_gold_in_system_bundle,
    strip_evaluator_only_fields,
)
from .historical_harness_adapter import adapt_historical_research_run_manifest_v1
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
    "IBP_FULL_SUITE_CASE_COUNT",
    "IBP_PROTOCOL_ID",
    "IBP_SMOKE10_CASE_COUNT",
    "IBP_SMOKE10_CONTRACT_ID",
    "adapt_historical_research_run_manifest_v1",
    "assert_historical_manifest_admissible",
    "assert_no_evaluator_gold_in_system_bundle",
    "assess_benchmark_smoke10_readiness",
    "audit_smoke10_run_contamination",
    "build_smoke10_invocation_contract",
    "execute_smoke10_baseline",
    "freeze_smoke10_run_configuration",
    "load_factual_gold_protocol",
    "load_suite_catalog",
    "smoke10_case_ids",
    "strip_evaluator_only_fields",
    "suite_catalog_fingerprint",
]

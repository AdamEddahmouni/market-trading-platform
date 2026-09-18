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
from .suite_catalog import load_suite_catalog, smoke10_case_ids, suite_catalog_fingerprint
from .types import (
    IBP_FULL_SUITE_CASE_COUNT,
    IBP_PROTOCOL_ID,
    IBP_SMOKE10_CASE_COUNT,
    IBP_SMOKE10_CONTRACT_ID,
)

__all__ = [
    "BenchmarkContaminationError",
    "IBP_FULL_SUITE_CASE_COUNT",
    "IBP_PROTOCOL_ID",
    "IBP_SMOKE10_CASE_COUNT",
    "IBP_SMOKE10_CONTRACT_ID",
    "adapt_historical_research_run_manifest_v1",
    "assert_historical_manifest_admissible",
    "assert_no_evaluator_gold_in_system_bundle",
    "assess_benchmark_smoke10_readiness",
    "build_smoke10_invocation_contract",
    "load_suite_catalog",
    "smoke10_case_ids",
    "strip_evaluator_only_fields",
    "suite_catalog_fingerprint",
]

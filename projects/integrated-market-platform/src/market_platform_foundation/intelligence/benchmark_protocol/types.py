"""Intelligence Benchmark Protocol (IBP) minimal types — greenfield v1."""

from __future__ import annotations

from enum import StrEnum

IBP_PROTOCOL_ID = "imp-intelligence-benchmark-protocol-v1"
IBP_PROTOCOL_SCHEMA_VERSION = "imp.intelligence-benchmark-protocol/1.0.0"
IBP_SUITE_CATALOG_SCHEMA_VERSION = "imp.intelligence-benchmark-suite/1.0.0"
IBP_RUN_RECORD_KIND = "intelligence_benchmark_run_record_v1"
IBP_RUN_RECORD_SCHEMA_VERSION = "imp.intelligence-benchmark-run-record/1.0.0"
IBP_SMOKE10_CONTRACT_ID = "ibp-smoke10-invocation-v1"
IBP_FULL_SUITE_CASE_COUNT = 30
IBP_SMOKE10_CASE_COUNT = 10

SIMULATOR_RESEARCH_RESULT_KIND = "SIMULATOR_RESEARCH_RESULT"
ITEM9_CALIBRATION_RESULT_KIND = "ITEM9_CALIBRATION_RESULT"


class IntelligenceBenchmarkBlindMode(StrEnum):
    """Blind evaluation Modes A–E (capability-surface routing; see protocol_controls)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


__all__ = [
    "IBP_FULL_SUITE_CASE_COUNT",
    "IBP_PROTOCOL_ID",
    "IBP_PROTOCOL_SCHEMA_VERSION",
    "IBP_RUN_RECORD_KIND",
    "IBP_RUN_RECORD_SCHEMA_VERSION",
    "IBP_SMOKE10_CASE_COUNT",
    "IBP_SMOKE10_CONTRACT_ID",
    "IBP_SUITE_CATALOG_SCHEMA_VERSION",
    "ITEM9_CALIBRATION_RESULT_KIND",
    "IntelligenceBenchmarkBlindMode",
    "SIMULATOR_RESEARCH_RESULT_KIND",
]

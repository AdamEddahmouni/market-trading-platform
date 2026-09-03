"""System acceptance package (BUILD 25)."""

from .golden_lifecycle import run_golden_lifecycle
from .identity import (
    derive_acceptance_report_id,
    derive_acceptance_spec_id,
    derive_contract_inventory_hash,
    derive_fixture_inventory_hash,
    derive_policy_inventory_hash,
)
from .inventory import (
    AUTHORITY_GRAPH,
    BUILD_INVENTORY,
    CONTRACT_INVENTORY,
    FORBIDDEN_AUTHORITY_PATHS,
    LINEAGE_EDGES,
    build_inventory_summary,
    contract_inventory_hash,
)
from .invariants import REQUIRED_INVARIANT_IDS, invariant_failures, run_invariant_checks
from .runner import run_acceptance
from .scenarios import REQUIRED_SCENARIOS, SCENARIO_REGISTRY, run_scenarios
from .serialization import (
    invariant_result_v1_to_dict,
    scenario_result_v1_to_dict,
    system_acceptance_report_v1_to_dict,
    system_acceptance_spec_v1_to_dict,
)
from .spec import KNOWN_LIMITATION_IDS, REQUIRED_SUITES, build_acceptance_spec
from .types import (
    SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION,
    SYSTEM_ACCEPTANCE_SCHEMA_VERSION,
    AcceptanceDisposition,
    FailureClass,
    GoldenLifecycleArtifacts,
    InvariantResultV1,
    InvariantStatus,
    ScenarioResultV1,
    ScenarioStatus,
    SystemAcceptanceReportV1,
    SystemAcceptanceSpecV1,
)

__all__ = [
    "AUTHORITY_GRAPH",
    "BUILD_INVENTORY",
    "CONTRACT_INVENTORY",
    "FORBIDDEN_AUTHORITY_PATHS",
    "LINEAGE_EDGES",
    "KNOWN_LIMITATION_IDS",
    "REQUIRED_INVARIANT_IDS",
    "REQUIRED_SCENARIOS",
    "REQUIRED_SUITES",
    "SCENARIO_REGISTRY",
    "SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION",
    "SYSTEM_ACCEPTANCE_SCHEMA_VERSION",
    "AcceptanceDisposition",
    "FailureClass",
    "GoldenLifecycleArtifacts",
    "InvariantResultV1",
    "InvariantStatus",
    "ScenarioResultV1",
    "ScenarioStatus",
    "SystemAcceptanceReportV1",
    "SystemAcceptanceSpecV1",
    "build_acceptance_spec",
    "build_inventory_summary",
    "contract_inventory_hash",
    "derive_acceptance_report_id",
    "derive_acceptance_spec_id",
    "derive_contract_inventory_hash",
    "derive_fixture_inventory_hash",
    "derive_policy_inventory_hash",
    "invariant_failures",
    "invariant_result_v1_to_dict",
    "run_acceptance",
    "run_golden_lifecycle",
    "run_invariant_checks",
    "run_scenarios",
    "scenario_result_v1_to_dict",
    "system_acceptance_report_v1_to_dict",
    "system_acceptance_spec_v1_to_dict",
]

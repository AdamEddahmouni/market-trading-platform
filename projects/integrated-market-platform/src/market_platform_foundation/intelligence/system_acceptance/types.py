"""System acceptance contracts (BUILD 25)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


SYSTEM_ACCEPTANCE_SCHEMA_VERSION = "1"
SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION = "build25-v1"


class InvariantStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNVERIFIABLE = "UNVERIFIABLE"


class ScenarioStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class AcceptanceDisposition(StrEnum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_LIMITATIONS = "ACCEPTED_WITH_LIMITATIONS"
    REJECTED = "REJECTED"


class FailureClass(StrEnum):
    TEMPORAL_LEAKAGE = "TEMPORAL_LEAKAGE"
    NON_DETERMINISTIC_IDENTITY = "NON_DETERMINISTIC_IDENTITY"
    SILENT_PERSISTENCE_OVERWRITE = "SILENT_PERSISTENCE_OVERWRITE"
    HOLDOUT_BYPASS = "HOLDOUT_BYPASS"
    CONTAMINATED_PROMOTION = "CONTAMINATED_PROMOTION"
    NON_CHAMPION_OPPORTUNITY = "NON_CHAMPION_OPPORTUNITY"
    RISK_BYPASS = "RISK_BYPASS"
    LIVE_EXECUTION_REACHABLE = "LIVE_EXECUTION_REACHABLE"
    MONITORING_TRAINS = "MONITORING_TRAINS"
    ADAPTATION_PROMOTES = "ADAPTATION_PROMOTES"
    UNPROMOTED_ACTIVATION = "UNPROMOTED_ACTIVATION"
    ARTIFACT_HASH_MISMATCH_IGNORED = "ARTIFACT_HASH_MISMATCH_IGNORED"
    AUTHORITY_BYPASS = "AUTHORITY_BYPASS"
    LINEAGE_AMBIGUITY = "LINEAGE_AMBIGUITY"
    CANONICAL_TTL = "CANONICAL_TTL"
    OTHER = "OTHER"


@dataclass(frozen=True)
class InvariantResultV1:
    invariant_id: str
    status: InvariantStatus
    evidence: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioResultV1:
    scenario_id: str
    status: ScenarioStatus
    expected: str
    observed: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SystemAcceptanceSpecV1:
    acceptance_spec_id: str
    schema_version: str
    source_build_head: str
    required_build_range: tuple[int, int]
    required_suites: tuple[str, ...]
    required_lifecycle_scenarios: tuple[str, ...]
    required_adversarial_scenarios: tuple[str, ...]
    required_invariants: tuple[str, ...]
    required_persistence_checks: tuple[str, ...]
    required_replay_checks: tuple[str, ...]
    required_determinism_checks: tuple[str, ...]
    required_security_checks: tuple[str, ...]
    allowed_known_limitations: tuple[str, ...]
    blocking_failure_classes: tuple[FailureClass, ...]
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SystemAcceptanceReportV1:
    acceptance_report_id: str
    schema_version: str
    acceptance_spec_ref: str
    source_head: str
    candidate_head: str
    scenario_results: tuple[ScenarioResultV1, ...]
    invariant_results: tuple[InvariantResultV1, ...]
    test_suite_results: dict[str, str]
    determinism_results: dict[str, str]
    replay_parity_results: dict[str, str]
    persistence_results: dict[str, str]
    security_results: dict[str, str]
    blocking_failures: tuple[str, ...]
    nonblocking_limitations: tuple[str, ...]
    overall_disposition: AcceptanceDisposition
    implementation_version: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GoldenLifecycleArtifacts:
    """Scientific artifact IDs produced by the golden lifecycle."""

    champion_assignment_id: str | None = None
    runtime_activation_id: str | None = None
    forecast_id: str | None = None
    opportunity_id: str | None = None
    trade_proposal_id: str | None = None
    risk_decision_id: str | None = None
    research_trigger_id: str | None = None
    research_finding_id: str | None = None
    candidate_id: str | None = None
    validation_report_id: str | None = None
    promotion_decision_id: str | None = None

    def scientific_id_map(self) -> dict[str, str | None]:
        return {
            "champion_assignment_id": self.champion_assignment_id,
            "runtime_activation_id": self.runtime_activation_id,
            "forecast_id": self.forecast_id,
            "opportunity_id": self.opportunity_id,
            "trade_proposal_id": self.trade_proposal_id,
            "risk_decision_id": self.risk_decision_id,
            "research_trigger_id": self.research_trigger_id,
            "research_finding_id": self.research_finding_id,
            "candidate_id": self.candidate_id,
            "validation_report_id": self.validation_report_id,
            "promotion_decision_id": self.promotion_decision_id,
        }

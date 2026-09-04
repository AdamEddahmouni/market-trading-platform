"""Native adapters for existing subsystems. Domain engines remain authoritative."""

from __future__ import annotations

import json
from typing import Any, Mapping

from market_platform_foundation.of01.cas import LocalCAS
from market_platform_foundation.of01.records import (
    ActionCategory,
    ConsequenceProfile,
    OutcomeValidity,
    ProvenanceQualifier,
    TerminalResult,
)

from ..config import load_adapter_config
from ..contracts import ArtifactCapture, AttemptSpec, AttributionRequest, AttributionResult, DomainIdentity
from ..gateway import LedgerWriter
from ..identity import IdentityPlan
from ..lifecycle import attribute


def _attempt(result: TerminalResult = TerminalResult.COMPLETED, *, reason: str = "ATTEMPT_COMPLETED") -> tuple[AttemptSpec, ...]:
    return (
        AttemptSpec(sequence=1, terminal_result=result, reason_code=reason),
    )


def _run(
    request: AttributionRequest,
    *,
    writer: LedgerWriter | None,
    cas: LocalCAS | None,
    identities: IdentityPlan | None,
    enabled: bool | None,
    adapter_id: str,
) -> AttributionResult:
    if enabled is None:
        enabled = load_adapter_config(adapter_id).is_enabled()
    return attribute(request, writer=writer, identities=identities, cas=cas, enabled=enabled)


def attribute_benchmark(
    report: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
    material_output: bool = True,
) -> AttributionResult:
    payload = json.dumps(report, sort_keys=True).encode("utf-8") if material_output else None
    request = AttributionRequest(
        adapter_id="benchmark",
        operation_class="BENCHMARK",
        objective="informational benchmark",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="benchmark", id_type="report", value=str(report.get("name", "benchmark"))),
        ),
        attempts=_attempt(),
        outcome_type="BENCHMARK_MEASUREMENT",
        validity=OutcomeValidity.VALID,
        disposition_action=ActionCategory.NO_ACTION,
        disposition_domain_code="INFORMATIONAL",
        outcome_limitations="informational; not a release gate",
        artifact=ArtifactCapture(logical_role="BENCHMARK_REPORT", logical_name="benchmark.json", payload=payload)
        if payload
        else None,
        extra={
            "benchmark_version": report.get("schema_version"),
            "sample_count": report.get("sample_count"),
            "comparability": report.get("comparability", "UNDECLARED"),
            "release_gate": False,
        },
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="benchmark")


def attribute_provider_smoke(
    report: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
    real_provider_executed: bool = False,
) -> AttributionResult:
    executed = bool(report.get("real_provider_executed", real_provider_executed))
    status = str(report.get("status", "NOT_EXECUTED"))
    if executed is False:
        terminal = TerminalResult.NOT_STARTED
        validity = OutcomeValidity.NOT_EVALUATED
        action = ActionCategory.DEFER
        code = "NOT_EXECUTED"
    else:
        terminal = TerminalResult.COMPLETED
        validity = OutcomeValidity.VALID
        action = ActionCategory.ACCEPT if status.upper() in {"PASS", "PASSED", "OK"} else ActionCategory.REJECT
        code = "OBSERVATIONAL_ONLY"
    request = AttributionRequest(
        adapter_id="provider_smoke",
        operation_class="PROVIDER_SMOKE",
        objective=f"observational smoke {report.get('provider', 'unknown')}",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="provider_smoke", id_type="provider", value=str(report.get("provider", "unknown"))),
        ),
        attempts=_attempt(terminal, reason="ATTEMPT_COMPLETED" if executed else "NOT_STARTED"),
        outcome_type="PROVIDER_HEALTH",
        validity=validity,
        disposition_action=action,
        disposition_domain_code=code,
        outcome_limitations="REAL OBSERVATIONAL DATA != LIVE EXECUTION TRANSPORT",
        extra={
            "provider": report.get("provider"),
            "endpoint": report.get("endpoint"),
            "capability": report.get("capability"),
            "market_state": report.get("market_state"),
            "live_execution_authorized": False,
            "production_broker_transport_accepted": False,
            "live_session_authorized": False,
            "order_execution_authorized": False,
            "real_provider_executed": executed,
        },
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="provider_smoke")


def attribute_research(
    report: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
) -> AttributionResult:
    request = AttributionRequest(
        adapter_id="research",
        operation_class="RESEARCH",
        objective=str(report.get("objective", "research")),
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="research", id_type="experiment_id", value=str(report.get("experiment_id", "unknown"))),
        ),
        attempts=_attempt(),
        outcome_type="RESEARCH_RESULT",
        validity=OutcomeValidity.VALID,
        disposition_action=ActionCategory.NO_ACTION,
        disposition_domain_code="RECORDED",
        outcome_limitations="private chain-of-thought is not persisted",
        extra={
            "source_set": report.get("source_set"),
            "model_provider": report.get("model_provider"),
            "prompt_template_id": report.get("prompt_template_id"),
            "chain_of_thought": None,
        },
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="research")


def attribute_training(
    manifest: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
) -> AttributionResult:
    request = AttributionRequest(
        adapter_id="training",
        operation_class="TRAINING",
        objective="training run",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="training", id_type="training_run_id", value=str(manifest.get("training_run_id", "unknown"))),
            DomainIdentity(system="training", id_type="dataset_id", value=str(manifest.get("dataset_id", "unknown"))),
            DomainIdentity(system="training", id_type="candidate_id", value=str(manifest.get("candidate_id", "unknown"))),
        ),
        attempts=_attempt(),
        outcome_type="TRAINING_METRICS",
        validity=OutcomeValidity.VALID,
        disposition_action=ActionCategory.NO_ACTION,
        disposition_domain_code="RECORDED",
        extra={
            "trainer_id": manifest.get("trainer_id"),
            "feature_config_id": manifest.get("feature_config_id"),
            "seed": manifest.get("seed"),
            "source_revision": manifest.get("source_revision"),
        },
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="training")


def attribute_evaluation(
    report: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
) -> AttributionResult:
    underperformed = bool(report.get("underperformed_baseline"))
    request = AttributionRequest(
        adapter_id="evaluation",
        operation_class="EVALUATION",
        objective="model evaluation",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="evaluation", id_type="evaluation_id", value=str(report.get("evaluation_id", "unknown"))),
        ),
        attempts=_attempt(TerminalResult.COMPLETED),
        outcome_type="EVALUATION_RESULT",
        validity=OutcomeValidity.VALID,
        disposition_action=ActionCategory.REJECT if underperformed else ActionCategory.ACCEPT,
        disposition_domain_code="UNDERPERFORMED_BASELINE" if underperformed else "MET_BASELINE",
        extra={"analytical_result": report.get("analytical_result"), "technical_result": "COMPLETED"},
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="evaluation")


def attribute_promotion(
    decision: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
) -> AttributionResult:
    accepted = str(decision.get("decision", "REJECT")).upper() in {"ACCEPT", "PROMOTE", "PASS"}
    request = AttributionRequest(
        adapter_id="promotion",
        operation_class="PROMOTION",
        objective="record existing promotion authority decision",
        consequence_profile=ConsequenceProfile.C3_EVIDENCE_CRITICAL,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="promotion", id_type="decision_id", value=str(decision.get("decision_id", "unknown"))),
        ),
        attempts=_attempt(),
        outcome_type="PROMOTION_DECISION",
        validity=OutcomeValidity.VALID,
        disposition_action=ActionCategory.ACCEPT if accepted else ActionCategory.REJECT,
        disposition_domain_code="EXISTING_AUTHORITY_DECISION",
        outcome_limitations="OF-02 does not promote models",
        extra={
            "candidate_id": decision.get("candidate_id"),
            "policy_id": decision.get("policy_id"),
            "of02_promotes": False,
        },
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="promotion")


def attribute_drift(
    assessment: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
) -> AttributionResult:
    request = AttributionRequest(
        adapter_id="drift",
        operation_class="DRIFT_EVALUATION",
        objective="controlled adaptation evidence",
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="adaptation", id_type="assessment_id", value=str(assessment.get("assessment_id", "unknown"))),
        ),
        attempts=_attempt(),
        outcome_type="DRIFT_ASSESSMENT",
        validity=OutcomeValidity.VALID,
        disposition_action=ActionCategory.NO_ACTION,
        disposition_domain_code="RESEARCH_TRIGGER_ONLY",
        outcome_limitations="drift does not authorize production strategy rewrite",
        extra={
            "trigger": assessment.get("trigger"),
            "autonomous_adaptation": False,
            "adapt_specific_records": False,
        },
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="drift")


def attribute_operational_drill(
    report: Mapping[str, Any],
    *,
    writer: LedgerWriter | None = None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
) -> AttributionResult:
    passed = str(report.get("status", "passed")).lower() in {"passed", "pass", "ok", "verified"}
    request = AttributionRequest(
        adapter_id="operational_drill",
        operation_class="OPERATIONAL_DRILL",
        objective=str(report.get("drill_type", "drill")),
        consequence_profile=ConsequenceProfile.C2_GOVERNED,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="ops", id_type="drill_id", value=str(report.get("drill_id", "unknown"))),
        ),
        attempts=_attempt(),
        outcome_type="DRILL_VERIFICATION",
        validity=OutcomeValidity.VALID if passed else OutcomeValidity.INVALID,
        disposition_action=ActionCategory.ACCEPT if passed else ActionCategory.REJECT,
        disposition_domain_code="VERIFIED" if passed else "FAILED_VERIFICATION",
        extra={"drill_type": report.get("drill_type")},
    )
    return _run(request, writer=writer, cas=cas, identities=identities, enabled=enabled, adapter_id="operational_drill")

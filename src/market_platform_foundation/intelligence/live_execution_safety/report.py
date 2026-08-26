"""Live execution safety report builders (BUILD 28)."""

from __future__ import annotations

from .identity import derive_safety_report_id, _sha256_prefix
from .broker_inventory import BROKER_INVENTORY, BrokerCapabilityStatus
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    BrokerCapabilityCertificationV1,
    BrokerCertificationDisposition,
    BrokerDryRunCertificationReportV1,
    LiveExecutionSafetyReportV1,
    LiveSafetyDisposition,
)


def build_broker_dry_run_report(
    cert: BrokerCapabilityCertificationV1,
    *,
    translation_tests: int,
    pre_submit_tests: int,
    idempotency_tests: int,
    transport_tests: int,
    reconciliation_tests: int,
    kill_switch_tests: int,
    restart_tests: int,
) -> BrokerDryRunCertificationReportV1:
    report_id = _sha256_prefix(
        "BDRYRUN",
        {"broker": cert.broker, "certification_id": cert.certification_id},
    )
    return BrokerDryRunCertificationReportV1(
        report_id=report_id,
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        broker_certification_ref=cert.certification_id,
        execution_gate_policy_ref="BUILD28_LIVE_EXECUTION_GATE_V1",
        adapter_version=cert.adapter_version,
        supported_instruments=("AAPL", "MSFT", "SPY"),
        supported_order_types=("MARKET", "LIMIT"),
        translation_tests_passed=translation_tests,
        pre_submit_validation_tests_passed=pre_submit_tests,
        idempotency_tests_passed=idempotency_tests,
        transport_failure_tests_passed=transport_tests,
        reconciliation_tests_passed=reconciliation_tests,
        kill_switch_tests_passed=kill_switch_tests,
        restart_tests_passed=restart_tests,
        real_submit_count=0,
        real_cancel_count=0,
        real_replace_count=0,
        disposition=cert.disposition,
        limitations=cert.limitations,
        lineage={"broker": cert.broker},
    )


def build_live_execution_safety_report(
    *,
    spec_id: str,
    source_build27_ref: str,
    source_build26_ref: str,
    source_release_candidate_ref: str,
    source_head: str,
    broker_certifications: tuple[BrokerCapabilityCertificationV1, ...],
    dry_run_reports: tuple[BrokerDryRunCertificationReportV1, ...],
    evaluation_as_of_ns: int,
    limitations: tuple[str, ...],
) -> LiveExecutionSafetyReportV1:
    cert_ids = tuple(c.certification_id for c in broker_certifications)
    dry_ids = tuple(r.report_id for r in dry_run_reports)

    in_scope_brokers = {
        e.broker
        for e in BROKER_INVENTORY
        if e.current_status != BrokerCapabilityStatus.UNSUPPORTED
    }
    scoped_certs = [c for c in broker_certifications if c.broker in in_scope_brokers]

    invalid = any(
        c.disposition == BrokerCertificationDisposition.INVALID_EXECUTION_GATE
        for c in scoped_certs
    )
    insufficient = any(
        c.disposition == BrokerCertificationDisposition.INSUFFICIENT_BROKER_CAPABILITY
        for c in scoped_certs
        if c.supports_paper or c.supports_live_transport
    )
    if invalid:
        disposition = LiveSafetyDisposition.INVALID
    elif insufficient:
        disposition = LiveSafetyDisposition.NOT_READY_FOR_LIVE_AUTHORIZATION
    elif limitations:
        disposition = LiveSafetyDisposition.PRELIVE_SAFETY_GATE_COMPLETE_WITH_LIMITATIONS
    else:
        disposition = LiveSafetyDisposition.PRELIVE_SAFETY_GATE_COMPLETE_WITH_LIMITATIONS

    report_id = derive_safety_report_id(
        spec_id=spec_id,
        broker_certification_ids=cert_ids,
        evaluation_as_of_ns=evaluation_as_of_ns,
    )
    return LiveExecutionSafetyReportV1(
        report_id=report_id,
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        source_build27_ref=source_build27_ref,
        source_build26_ref=source_build26_ref,
        source_release_candidate_ref=source_release_candidate_ref,
        source_head=source_head,
        broker_certification_refs=cert_ids,
        dry_run_report_refs=dry_ids,
        evaluation_as_of_ns=evaluation_as_of_ns,
        system_disposition=disposition,
        real_submit_count=0,
        real_cancel_count=0,
        real_replace_count=0,
        limitations=limitations,
        lineage={"spec_id": spec_id},
        metadata={"live_authorization": "NOT_AUTHORIZED"},
    )

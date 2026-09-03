"""BUILD 28 live execution safety certification runner."""

from __future__ import annotations

from dataclasses import dataclass

from .build27_integrity import verify_build27_integrity
from .certification import certify_all_brokers
from .dry_run import GLOBAL_ZERO_SUBMIT_GUARD
from .report import build_broker_dry_run_report, build_live_execution_safety_report
from .scenarios import REQUIRED_SCENARIOS, ScenarioStatus, run_all_scenarios
from .spec import build_live_execution_safety_spec
from .types import LiveSafetyDisposition


BUILD28_KNOWN_LIMITATIONS: tuple[str, ...] = (
    "KL-028-001: IBKR execution adapter not present — observational market data only",
    "KL-028-002: tastytrade unsupported — no adapter",
    "KL-028-003: Broker preview/what-if endpoints not safely callable — local dry-run only",
    "KL-028-004: Replace/order-modification not certified",
    "KL-028-005: Options/futures/crypto not certified — US cash equities only",
    "KL-028-006: Live portfolio reconciliation unavailable — fixture-based only",
    "KL-028-007: No live authorization issued by design",
    "KL-028-008: Production kill switch ACTIVE_BLOCK mandatory",
    "KL-028-009: Real broker wire transport fixture-only for Tradier/Moomoo",
)


@dataclass(frozen=True)
class LiveExecutionSafetyRunResult:
    disposition: LiveSafetyDisposition
    scenario_failures: tuple[str, ...]
    build27_integrity_status: str
    real_submit_count: int
    real_cancel_count: int
    real_replace_count: int
    metadata: dict


def run_live_execution_safety_certification(
    *,
    source_build27_ref: str,
    source_build26_ref: str,
    source_release_candidate_ref: str,
    source_head: str,
    evaluation_as_of_ns: int = 1_700_000_000_000_000_000,
) -> LiveExecutionSafetyRunResult:
    build27 = verify_build27_integrity(expected_head=source_build27_ref)
    if build27.status == "FAIL":
        return LiveExecutionSafetyRunResult(
            disposition=LiveSafetyDisposition.INVALID,
            scenario_failures=build27.reason_codes,
            build27_integrity_status=build27.status,
            real_submit_count=0,
            real_cancel_count=0,
            real_replace_count=0,
            metadata={"build27_disposition": build27.disposition},
        )

    spec = build_live_execution_safety_spec(
        source_build27_ref=source_build27_ref,
        source_build26_ref=source_build26_ref,
        source_release_candidate_ref=source_release_candidate_ref,
        source_head=source_head,
    )
    certifications = certify_all_brokers()
    scenario_results = run_all_scenarios()
    failures = tuple(r.scenario_id for r in scenario_results if r.status != ScenarioStatus.PASS)

    dry_reports = tuple(
        build_broker_dry_run_report(
            cert,
            translation_tests=1,
            pre_submit_tests=len(REQUIRED_SCENARIOS),
            idempotency_tests=1,
            transport_tests=1,
            reconciliation_tests=1,
            kill_switch_tests=1,
            restart_tests=1,
        )
        for cert in certifications
        if cert.supports_paper or cert.supports_market_data
    )

    report = build_live_execution_safety_report(
        spec_id=spec.spec_id,
        source_build27_ref=source_build27_ref,
        source_build26_ref=source_build26_ref,
        source_release_candidate_ref=source_release_candidate_ref,
        source_head=source_head,
        broker_certifications=certifications,
        dry_run_reports=dry_reports,
        evaluation_as_of_ns=evaluation_as_of_ns,
        limitations=BUILD28_KNOWN_LIMITATIONS,
    )

    if failures:
        disposition = LiveSafetyDisposition.INVALID
    else:
        disposition = report.system_disposition

    GLOBAL_ZERO_SUBMIT_GUARD.assert_zero()

    return LiveExecutionSafetyRunResult(
        disposition=disposition,
        scenario_failures=failures,
        build27_integrity_status=build27.status,
        real_submit_count=GLOBAL_ZERO_SUBMIT_GUARD.real_submit_count,
        real_cancel_count=GLOBAL_ZERO_SUBMIT_GUARD.real_cancel_count,
        real_replace_count=GLOBAL_ZERO_SUBMIT_GUARD.real_replace_count,
        metadata={
            "spec_id": spec.spec_id,
            "report_id": report.report_id,
            "build27_disposition": build27.disposition,
            "scenario_count": len(scenario_results),
            "live_authorization": "NOT_AUTHORIZED",
        },
    )

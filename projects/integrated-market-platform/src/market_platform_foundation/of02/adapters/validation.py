"""Validation native adapter. Does not change selection or manifest semantics."""

from __future__ import annotations

import json
from typing import Any, Mapping

from market_platform_foundation.of01.cas import LocalCAS
from market_platform_foundation.of01.records import (
    ActionCategory,
    ConsequenceProfile,
    FailureReasonFamily,
    OutcomeValidity,
    ProvenanceQualifier,
    TerminalResult,
)

from ..config import load_adapter_config
from ..contracts import ArtifactCapture, AttemptSpec, AttributionRequest, AttributionResult, DomainIdentity
from ..gateway import LedgerWriter
from ..identity import IdentityPlan
from ..lifecycle import attribute

ADAPTER_ID = "validation"


def _technical_result(result: Mapping[str, Any]) -> tuple[TerminalResult, FailureReasonFamily | None, str]:
    status = str(result.get("status", "error"))
    if result.get("interrupted"):
        return TerminalResult.INTERRUPTED, FailureReasonFamily.INTERRUPTION, "ATTEMPT_INTERRUPTED"
    if status == "error":
        return TerminalResult.FAILED, FailureReasonFamily.ENVIRONMENT_FAILURE, "ENVIRONMENT_FAILURE"
    if status == "failed":
        return TerminalResult.COMPLETED, None, "ATTEMPT_COMPLETED"
    if status == "passed":
        return TerminalResult.COMPLETED, None, "ATTEMPT_COMPLETED"
    return TerminalResult.FAILED, FailureReasonFamily.UNCLASSIFIED_FAILURE, "UNCLASSIFIED_FAILURE"


def _validity_and_disposition(
    result: Mapping[str, Any],
    *,
    retry_then_pass: bool,
) -> tuple[OutcomeValidity, ActionCategory, str]:
    status = str(result.get("status", "error"))
    errors = int(result.get("errors", 0) or 0)
    failures = int(result.get("failures", 0) or 0)
    if result.get("interrupted"):
        return OutcomeValidity.INDETERMINATE, ActionCategory.CANCEL, "CANCELLED"
    if status == "error" or errors:
        return OutcomeValidity.INDETERMINATE, ActionCategory.DEFER, "ENVIRONMENT_ERROR"
    if status == "failed" or failures:
        return OutcomeValidity.VALID, ActionCategory.REJECT, "TESTS_FAILED"
    if retry_then_pass:
        return OutcomeValidity.VALID, ActionCategory.ACCEPT, "PASS_WITH_RETRY"
    if int(result.get("skips", 0) or 0) > 0:
        return OutcomeValidity.VALID, ActionCategory.ACCEPT, "PASS_WITH_SKIPS"
    return OutcomeValidity.VALID, ActionCategory.ACCEPT, "PASS"


def request_from_validation_result(
    result: Mapping[str, Any],
    *,
    selection: Mapping[str, Any] | None = None,
    attempts: tuple[AttemptSpec, ...] | None = None,
    consequence: ConsequenceProfile = ConsequenceProfile.C1_OPERATIONAL,
    git_revision: str | None = None,
    retry_then_pass: bool = False,
    capture_report: bool = True,
) -> AttributionRequest:
    selection = selection or {}
    terminal, family, reason = _technical_result(result)
    if attempts is None:
        started = None
        ended = None
        attempts = (
            AttemptSpec(
                sequence=1,
                terminal_result=terminal,
                reason_code=reason,
                reason_family=family,
                invocation_ref=f"validation://{result.get('mode', 'unknown')}",
                environment_ref="validation-worker",
                started_at_ns=started,
                ended_at_ns=ended,
            ),
        )
    validity, action, domain_code = _validity_and_disposition(result, retry_then_pass=retry_then_pass)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    report_id = str(result.get("started_at") or result.get("mode") or "validation-report")
    known_missing: tuple[str, ...] = ()
    if git_revision is None:
        known_missing = ("source_revision",)
    return AttributionRequest(
        adapter_id=ADAPTER_ID,
        operation_class="VALIDATION",
        objective=f"validate {result.get('mode', 'unknown')}",
        consequence_profile=consequence,
        provenance_qualifier=ProvenanceQualifier.NATIVE,
        domain_identities=(
            DomainIdentity(system="validation", id_type="report", value=report_id),
        ),
        attempts=attempts,
        outcome_type="VALIDATION_RESULT",
        result_ref="validation-report",
        validity=validity,
        disposition_action=action,
        disposition_domain_code=domain_code,
        known_missing=known_missing,
        repository_identity="integrated-market-platform",
        root_identity="repository-root",
        base_revision=git_revision,
        artifact=ArtifactCapture(
            logical_role="VALIDATION_REPORT",
            logical_name="validation-report.json",
            payload=payload,
        )
        if capture_report
        else None,
        extra={
            "selection_mode": result.get("mode"),
            "full_suite_required": bool(result.get("full_suite_required") or selection.get("full_suite_required")),
            "selected_suites": list(result.get("selected_suites") or selection.get("selected_suite_ids") or ()),
            "tests_run": result.get("tests_run"),
            "passes": result.get("passes"),
            "skips": result.get("skips"),
            "failures": result.get("failures"),
            "errors": result.get("errors"),
        },
    )


def attribute_validation(
    result: Mapping[str, Any],
    *,
    writer: LedgerWriter | None,
    cas: LocalCAS | None = None,
    identities: IdentityPlan | None = None,
    enabled: bool | None = None,
    **kwargs: Any,
) -> AttributionResult:
    if enabled is None:
        enabled = load_adapter_config(ADAPTER_ID).is_enabled()
    request = request_from_validation_result(result, **kwargs)
    return attribute(request, writer=writer, identities=identities, cas=cas, enabled=enabled)

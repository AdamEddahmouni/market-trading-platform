"""Consequence-class attribution failure policy."""

from __future__ import annotations

from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.records import ConsequenceProfile

from .contracts import AttributionRequest, AttributionResult, AttributionStatus, CompletenessState
from .errors import OF02Error, OF02ErrorCode


def apply_failure(request: AttributionRequest, error: BaseException) -> AttributionResult:
    code = getattr(error, "code", None)
    code_value = code.value if hasattr(code, "value") else str(code or OF02ErrorCode.ATTRIBUTION_FAILED)
    message = str(error)
    profile = request.consequence_profile
    completeness = (
        CompletenessState.PARTIAL if request.known_missing else CompletenessState.UNKNOWN
    )
    if isinstance(error, OF01Error) and error.code == OF01ErrorCode.COMMAND_ID_CONFLICT:
        return AttributionResult(
            adapter_id=request.adapter_id,
            status=AttributionStatus.CONFLICTED,
            provenance_qualifier=request.provenance_qualifier,
            attribution_completeness=completeness,
            known_missing=request.known_missing,
            error_code=OF01ErrorCode.COMMAND_ID_CONFLICT.value,
            error_message=message,
        )
    if profile in {ConsequenceProfile.C0_EPHEMERAL, ConsequenceProfile.C1_OPERATIONAL}:
        return AttributionResult(
            adapter_id=request.adapter_id,
            status=AttributionStatus.BEST_EFFORT_FAILED,
            provenance_qualifier=request.provenance_qualifier,
            attribution_completeness=completeness,
            known_missing=request.known_missing,
            error_code=code_value,
            error_message=message,
        )
    if profile == ConsequenceProfile.C3_EVIDENCE_CRITICAL:
        return AttributionResult(
            adapter_id=request.adapter_id,
            status=AttributionStatus.WITHHELD,
            provenance_qualifier=request.provenance_qualifier,
            attribution_completeness=completeness,
            known_missing=request.known_missing,
            withheld_acceptance=True,
            error_code=OF02ErrorCode.ACCEPTANCE_WITHHELD.value,
            error_message=message,
        )
    if profile == ConsequenceProfile.C4_AUTHORITY_CRITICAL:
        raise OF02Error(
            OF02ErrorCode.AUTHORITY_FAIL_CLOSED,
            "C4 attribution failure fails closed",
            {"adapter_id": request.adapter_id, "cause": message},
        )
    return AttributionResult(
        adapter_id=request.adapter_id,
        status=AttributionStatus.FAILED_CLOSED,
        provenance_qualifier=request.provenance_qualifier,
        attribution_completeness=completeness,
        known_missing=request.known_missing,
        error_code=code_value,
        error_message=message,
    )

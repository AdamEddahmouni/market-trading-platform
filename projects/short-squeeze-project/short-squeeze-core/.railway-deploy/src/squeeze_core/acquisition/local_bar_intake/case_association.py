"""Non-executing case-association boundary.

Validates that a declared mapping from a validated bar bundle to an existing case
is structurally sound and references known case/boundary IDs. It performs no
outcome work: it never opens the outcome window, computes a return, creates a
Phase 3A request/result or a Phase 3B label, alters case records, or promotes a
candidate. A validated mapping is preparation for future authorized work, not
evidence that the requested window is complete.
"""

from __future__ import annotations

from .models import (
    CaseAssociationMapping,
    CaseAssociationValidationResult,
    IntakeManifest,
)
from .semantics import BarSession, IntakeReasonCode


def validate_case_association(
    mapping: CaseAssociationMapping,
    *,
    known_case_ids: frozenset[str],
    known_boundary_ids: frozenset[str],
    manifest: IntakeManifest | None = None,
) -> CaseAssociationValidationResult:
    """Validate a case-association mapping against known references.

    ``known_case_ids`` / ``known_boundary_ids`` are supplied by the caller (e.g.
    an existing case registry), so validation never reaches into or mutates case
    records. When a ``manifest`` for ``mapping.bundle_id`` is supplied, symbol,
    interval, and coverage compatibility are checked against it.
    """
    reasons: list[IntakeReasonCode] = []

    case_ok = mapping.case_id in known_case_ids
    if not case_ok:
        reasons.append(IntakeReasonCode.UNKNOWN_CASE_ID)
    boundary_ok = mapping.frozen_detection_boundary_id in known_boundary_ids
    if not boundary_ok:
        reasons.append(IntakeReasonCode.UNKNOWN_BOUNDARY_ID)

    symbol_ok = True
    coverage_ok = True
    interval_ok = True
    if manifest is not None:
        if mapping.bundle_id != manifest.bundle_id:
            symbol_ok = False
            reasons.append(IntakeReasonCode.CASE_SYMBOL_INCOMPATIBLE)
        else:
            if mapping.canonical_symbol != manifest.canonical_symbol:
                symbol_ok = False
                reasons.append(IntakeReasonCode.CASE_SYMBOL_INCOMPATIBLE)
            if mapping.required_interval is not manifest.bar_interval:
                interval_ok = False
                reasons.append(IntakeReasonCode.CASE_INTERVAL_INCOMPATIBLE)
            if not _coverage_compatible(
                mapping.required_session_coverage, manifest.session_coverage
            ):
                coverage_ok = False
                reasons.append(IntakeReasonCode.CASE_COVERAGE_INCOMPATIBLE)

    valid = case_ok and boundary_ok and symbol_ok and coverage_ok and interval_ok
    return CaseAssociationValidationResult(
        mapping_id=str(mapping.deterministic_id),
        case_id=mapping.case_id,
        bundle_id=mapping.bundle_id,
        valid=valid,
        case_id_exists=case_ok,
        boundary_id_exists=boundary_ok,
        symbol_compatible=symbol_ok,
        coverage_compatible=coverage_ok,
        interval_compatible=interval_ok,
        outcome_computed=False,
        phase_3a_or_3b_record_created=False,
        reason_codes=tuple(reasons),
    )


def _coverage_compatible(required: BarSession, provided: BarSession) -> bool:
    if required is provided:
        return True
    # A bundle covering the full extended session satisfies any single-session need.
    return provided is BarSession.EXTENDED


__all__ = ["validate_case_association"]

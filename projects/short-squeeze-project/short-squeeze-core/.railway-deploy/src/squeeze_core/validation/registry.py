"""Reusable comparison-case registry.

BIYA is one case. The registry exists so additional cases can be added without
reworking the framework, and so candidates that *cannot* yet be cased are recorded as
explicit gaps rather than quietly omitted. A registered symbol with no recoverable
output stays ARTIFACT_DISCOVERY_ONLY -- completion is never inferred from a ticker
merely appearing in a log.
"""

from collections.abc import Sequence

from squeeze_core.adapters.diagnostics import DiagnosticSeverity

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .models import CaseStatus, ComparisonCaseEntry, DetectionTimeState

# Symbols observed alongside BIYA in the platform's own corroboration calls on
# 2026-07-17 (docs/phase-2v-biya-artifact-inventory.md, ART-001). They are recorded
# because they are genuine evidence of the screening universe, and left uncased
# because the log preserves no value, label, or score for any of them.
_OBSERVED_UNIVERSE = ("KLRS", "LBGJ", "SG", "TRVI", "SLS")


def observed_universe_entries(
    *,
    artifact_ids: Sequence[str] = ("ART-001",),
) -> tuple[ComparisonCaseEntry, ...]:
    return tuple(
        ComparisonCaseEntry(
            case_id=f"case-{symbol.lower()}",
            symbol=symbol,
            case_status=CaseStatus.ARTIFACT_DISCOVERY_ONLY,
            detection_time_state=DetectionTimeState.BOUNDED_TIME_WINDOW,
            artifact_ids=tuple(artifact_ids),
            limitations=(
                "present in the screening universe but no field value, label, or score was recorded",
                "no market data exists locally for this symbol",
            ),
            acquisition_needs=(
                "a saved candidate row, snapshot, or screenshot showing this symbol's displayed values",
                "historical market bars covering 2026-07-17 and the following session",
            ),
        )
        for symbol in _OBSERVED_UNIVERSE
    )


def build_case_registry(
    entries: Sequence[ComparisonCaseEntry],
) -> tuple[ComparisonCaseEntry, ...]:
    return tuple(sorted(entries, key=lambda item: item.case_id))


def registry_diagnostics(
    entries: Sequence[ComparisonCaseEntry],
) -> tuple[ValidationDiagnostic, ...]:
    blocked = [
        entry
        for entry in entries
        if entry.case_status
        in {
            CaseStatus.ARTIFACT_DISCOVERY_ONLY,
            CaseStatus.BLOCKED_MISSING_DETECTION_TIME,
            CaseStatus.BLOCKED_MISSING_ORIGINAL_OUTPUT,
            CaseStatus.BLOCKED_MISSING_MARKET_DATA,
        }
    ]
    if not blocked:
        return ()
    return sort_diagnostics(
        ValidationDiagnostic(
            code=ValidationDiagnosticCode.VALIDATION_COMPARISON_CASES_UNAVAILABLE,
            severity=DiagnosticSeverity.INFO,
            message=(
                f"{entry.symbol} is registered but not cased ({entry.case_status.value}); "
                "acquisition is required before it can be validated"
            ),
        )
        for entry in blocked
    )


def acquisition_manifest(
    entries: Sequence[ComparisonCaseEntry],
) -> tuple[dict[str, str], ...]:
    """Flat, sorted list of what must be acquired before broader validation is possible."""

    rows: list[dict[str, str]] = []
    for entry in sorted(entries, key=lambda item: item.case_id):
        for need in entry.acquisition_needs:
            rows.append(
                {"case_id": entry.case_id, "symbol": entry.symbol, "acquisition_need": need}
            )
    return tuple(rows)


__all__ = [
    "acquisition_manifest",
    "build_case_registry",
    "observed_universe_entries",
    "registry_diagnostics",
]

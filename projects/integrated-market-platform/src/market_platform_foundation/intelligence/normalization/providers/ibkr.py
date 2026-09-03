"""IBKR normalization interface (BUILD 03 — interface ready, no fabricated runtime)."""

from __future__ import annotations

from typing import Any

from ..errors import NormalizationDiagnostic, NormalizationErrorCode
from ..models import NormalizationContext, NormalizationResult

ADAPTER_ID = "ibkr.observational"
ADAPTER_VERSION = "1"
SUPPORTED_RECORD_TYPES = frozenset({"ibkr_snapshot", "ibkr_history"})


def normalize_ibkr_record(
    record: dict[str, Any],
    *,
    context: NormalizationContext,
) -> NormalizationResult:
    """Interface hook for future IBKR records — does not fabricate live behavior."""
    _ = context
    record_type = str(record.get("record_type") or record.get("capability") or "unknown")
    return NormalizationResult(
        event=None,
        diagnostics=(
            NormalizationDiagnostic(
                code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                message=f"IBKR normalization not yet implemented for record_type={record_type}",
                details={"adapter_id": ADAPTER_ID, "adapter_version": ADAPTER_VERSION},
            ),
        ),
    )


__all__ = ["SUPPORTED_RECORD_TYPES", "normalize_ibkr_record"]

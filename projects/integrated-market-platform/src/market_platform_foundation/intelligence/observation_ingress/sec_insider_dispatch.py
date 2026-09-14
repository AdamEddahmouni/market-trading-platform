"""Market Trackers SEC insider row → normalize → ObservationIngressRouter."""

from __future__ import annotations

from typing import Any, Mapping

from ..normalization.models import NormalizationContext, NormalizationResult
from ..normalization.registry import get_normalizer
from .normalization_bridge import dispatch_normalization_result
from .router import ObservationIngressRouter
from .types import IngressDispatchContext, IngressDispatchReceiptV1


def normalize_sec_insider_row_for_ingress(
    row: Mapping[str, Any],
    *,
    context: NormalizationContext,
    edgar_primary: Mapping[str, Any] | None = None,
) -> NormalizationResult:
    normalizer = get_normalizer("market_trackers.sec_insider")
    if normalizer is None:
        from ..normalization.errors import NormalizationDiagnostic, NormalizationErrorCode

        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    message="market_trackers.sec_insider normalizer not registered",
                ),
            ),
        )
    return normalizer(dict(row), context=context, edgar_primary=edgar_primary)


def dispatch_sec_insider_row(
    router: ObservationIngressRouter,
    row: Mapping[str, Any],
    *,
    normalization_context: NormalizationContext,
    dispatch_context: IngressDispatchContext,
    edgar_primary: Mapping[str, Any] | None = None,
) -> IngressDispatchReceiptV1 | None:
    """Canonical ingress: registry normalizer → dispatch_normalization_result."""
    result = normalize_sec_insider_row_for_ingress(
        row,
        context=normalization_context,
        edgar_primary=edgar_primary,
    )
    return dispatch_normalization_result(router, result, context=dispatch_context)


__all__ = [
    "dispatch_sec_insider_row",
    "normalize_sec_insider_row_for_ingress",
]

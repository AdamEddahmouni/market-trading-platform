"""Bridge BUILD 03 normalization output into observation ingress dispatch."""

from __future__ import annotations

from ..normalization.models import NormalizationResult
from .errors import IngressDispatchError
from .router import ObservationIngressRouter
from .types import IngressDispatchContext, IngressDispatchReceiptV1

try:
    from ...hot_path_telemetry.collector import HotPathClockCollector
except ImportError:  # pragma: no cover
    HotPathClockCollector = None  # type: ignore[misc, assignment]


def dispatch_normalization_result(
    router: ObservationIngressRouter,
    result: NormalizationResult,
    *,
    context: IngressDispatchContext,
    clock_collector: HotPathClockCollector | None = None,
) -> IngressDispatchReceiptV1 | None:
    """Dispatch when normalization produced an EventV1; otherwise no-op."""
    if result.event is None:
        return None
    if clock_collector is not None:
        clock_collector.note_normalized_event(result.event)
    if result.diagnostics:
        raise IngressDispatchError(
            code="INGRESS_NORMALIZATION_DIAGNOSTICS",
            message="normalization carried diagnostics",
            event_id=result.event.event_id,
        )
    return router.dispatch(result.event, context=context)


__all__ = ["dispatch_normalization_result"]

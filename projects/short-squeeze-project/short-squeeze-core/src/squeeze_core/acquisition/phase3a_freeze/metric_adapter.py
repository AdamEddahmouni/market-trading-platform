"""Build the one admissible Phase 2 metric this batch is authorised to construct.

The percentage-change arithmetic is **not** implemented here. This module only chooses
the reference and comparison bar boundaries and delegates to the canonical Phase 2 path
``squeeze_core.metrics.returns.build_return_result`` with
``MetricName.PERCENTAGE_RETURN``. A committed test asserts this package contains no
percentage arithmetic of its own.

Batch 07 authorised exactly this operation as ``ADMISSIBLE_WITH_CONSTRAINTS``:

* both boundary bars must be definitely completed under timestamp uncertainty — enforced
  by selecting only from ``BarLabels.included``;
* prices are not dividend-adjusted, so no ex-dividend instant is assumed inside the
  window — the window is recorded so the assumption stays inspectable.

No absolute price level is used for any blocked operation, and no volume is touched.
"""

from __future__ import annotations

from datetime import datetime

from squeeze_core.contracts import AssetClass
from squeeze_core.metrics import MetricName
from squeeze_core.metrics.models import MetricResult, PriceField, ProviderScopeMode
from squeeze_core.metrics.returns import ReturnRequest, build_return_result

from .evidence_adapter import (
    BAR_INTERVAL,
    PROVIDER,
    BarLabels,
    DetectionContextBars,
    boundaries_for,
)
from .models import TimestampInterpretation

#: Frozen: the reference and comparison observations for the percentage metric.
REFERENCE_SELECTION = "EARLIEST_DEFINITELY_COMPLETED_DETECTION_CONTEXT_BAR"
COMPARISON_SELECTION = "LATEST_DEFINITELY_COMPLETED_DETECTION_CONTEXT_BAR"
PRICE_FIELD = PriceField.CLOSE


class InsufficientAdmissibleBarsError(RuntimeError):
    """Raised when fewer than two definitely-completed bars exist.

    The caller preserves the request and lets the rule resolve through canonical
    missingness rather than fabricating a metric.
    """


def metric_window(labels: BarLabels) -> tuple[datetime, datetime]:
    """The reference and comparison labels, chosen by ordinal position only."""
    if len(labels.included) < 2:
        raise InsufficientAdmissibleBarsError(
            "at least two definitely-completed bars are required for a close-to-close return"
        )
    return labels.included[0], labels.included[-1]


def build_percentage_return(
    bars: DetectionContextBars,
    *,
    as_of: datetime,
    interpretation: TimestampInterpretation | None = None,
) -> MetricResult:
    """Compute the canonical ``PERCENTAGE_RETURN`` for one case's admissible window."""
    reference, comparison = metric_window(bars.labels)
    reading = interpretation or bars.interpretation
    reference_start, reference_end = boundaries_for(reference, reading)
    comparison_start, comparison_end = boundaries_for(comparison, reading)
    return build_return_result(
        bars.observations,
        ReturnRequest(
            symbol=bars.symbol,
            asset_class=AssetClass.EQUITY,
            as_of=as_of,
            source_interval=BAR_INTERVAL,
            start_bar_start=reference_start,
            start_bar_end=reference_end,
            end_bar_start=comparison_start,
            end_bar_end=comparison_end,
            provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
            provider=PROVIDER,
            price_field=PRICE_FIELD,
        ),
        MetricName.PERCENTAGE_RETURN,
    )


__all__ = [
    "COMPARISON_SELECTION",
    "PRICE_FIELD",
    "REFERENCE_SELECTION",
    "InsufficientAdmissibleBarsError",
    "build_percentage_return",
    "metric_window",
]

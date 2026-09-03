"""Current-snapshot Phase 3A evaluation.

This module builds *evidence*. It contains no rule, no threshold, no metric formula and no
detection predicate: every one of those comes from the existing canonical packages.

Pipeline, all canonical:

1. provider bars (``reqHistoricalData``, trailing current window);
2. keep only bars **definitely completed** under both timestamp interpretations —
   ``label + interval <= as_of`` — reusing ``classify_labels`` from the Batch 08 evidence
   adapter, so the Batch 07 bidirectional envelope is the same code, not a copy;
3. normalise through ``squeeze_core.adapters.market_bars.normalize_market_bar_records``,
   with **volume omitted** (Batch 06 left the provider volume unit and its corporate-action
   treatment UNRESOLVED, so no volume-derived value is admissible);
4. ``PERCENTAGE_RETURN`` through ``squeeze_core.metrics.returns.build_return_result``;
5. readiness through the existing Phase 2D builders, reused via the Batch 08
   ``readiness_adapter``;
6. an ordinary ``RuleEvaluationRequest``;
7. ``squeeze_core.evaluation.evaluator.evaluate_candidate``.

## The one deliberate difference from the frozen Batch 08 request

``provider_scope = ("IBKR",)`` here; the frozen request uses ``()``.

Batch 07 blocked absolute price levels because Batch 06 resolved the provider price series
as SPLIT_ADJUSTED: a level recorded at a *past* boundary may have been restated by a
corporate action occurring between that boundary and retrieval. For a bar completed inside
the **current** session, evaluated with ``as_of`` at that same instant, that interval does
not exist, so the adjusted level and the contemporaneous traded level coincide. The
absolute level of the latest definitely-completed current bar is therefore admissible as a
**current price level only**.

This does not touch the historical determination. Frozen mode is unchanged and its request
still carries an empty provider scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

#: Why current absolute price is admissible while historical absolute price is not.
CURRENT_ABSOLUTE_PRICE_STATUS = "CURRENT_ABSOLUTE_PRICE_ADMISSIBLE_WITH_CONSTRAINTS"
CURRENT_ABSOLUTE_PRICE_RATIONALE = (
    "The provider price series is split-adjusted, which makes an absolute level at a past "
    "boundary inadmissible because a later corporate action may have restated it. The "
    "latest definitely-completed current-session bar remains admissible only inside the "
    "short recency window below. The request as-of is the current snapshot receipt time; "
    "the exact bar completion remains preserved on the observation. Admissible as a "
    "current price level only; the historical determination is unchanged."
)
CURRENT_ABSOLUTE_PRICE_CONSTRAINTS = (
    "Only the latest definitely-completed current-session bar may supply an absolute level.",
    "The bar must be within the explicit current-price recency window at snapshot time.",
    "This admissibility is not transferable to any frozen or historical boundary.",
)

#: Why current volume remains inadmissible.
CURRENT_VOLUME_STATUS = "CURRENT_VOLUME_UNIT_UNRESOLVED"
CURRENT_VOLUME_RATIONALE = (
    "Batch 06 found the official documentation silent on the provider's historical volume "
    "unit and on how volume is treated across corporate actions. Nothing about a current "
    "request resolves that, so no volume-derived value is admissible and RELATIVE_VOLUME "
    "remains UNKNOWN. Raw provider volume may be displayed, labelled with an unresolved "
    "unit, but it never enters evidence."
)

#: Exactly the provider scope declared for a current request, when the evidence really is
#: current. See :data:`CURRENT_PRICE_MAX_AGE_S`.
CURRENT_PROVIDER_SCOPE: tuple[str, ...] = ("IBKR",)

#: How recent the as-of instant must be for the absolute-price admissibility argument to
#: hold.
#:
#: That argument (see the module docstring) turns on there being no interval during which
#: a corporate action could restate the price between the bar's completion and the present.
#: That is true seconds after the bar closes. It is *not* true of a bar from a previous
#: session — outside market hours the latest completed bar can be many hours old, and a
#: split can be announced and take effect before trading resumes.
#:
#: When the as-of instant is older than this, the request declares **no provider scope**,
#: exactly as the frozen Batch 08 request does. ``PRICE_RANGE`` and the other scope-gated
#: rules then resolve UNKNOWN through the canonical provider-scope gate rather than
#: asserting an admissibility that no longer holds. Ratio-based rules such as
#: ``PERCENTAGE_CHANGE_MINIMUM`` are unaffected: Batch 07 admitted price ratios regardless
#: of split adjustment, so they keep evaluating.
#:
#: No rule logic lives here. This chooses what evidence is asserted; the canonical
#: evaluator decides every outcome.
CURRENT_PRICE_MAX_AGE_S = 900

STALE_PRICE_SCOPE_REASON = (
    "The latest completed provider bar is older than the current-price admissibility "
    "window, so this snapshot does not assert a provider scope. Absolute price levels are "
    "not admissible from a bar that may predate an unobserved corporate action, and the "
    "scope-gated rules therefore resolve UNKNOWN. Price ratios remain admissible and the "
    "percentage-change rule still evaluates. This is the same posture the frozen research "
    "request takes."
)

PROVIDER = "IBKR"
ADAPTER_VERSION = "phase-3d-batch-11-current-screener.v1"
NORMALIZATION_VERSION = "market-bar-v1"
CURRENT_REQUEST_NAME = "CURRENT_CONTEXT_TRAILING_1D"
SOURCE_ENDPOINT = f"ibkr:reqHistoricalData:{CURRENT_REQUEST_NAME}"

#: The percentage-return window selection, stated in full so it is never mistaken for a
#: previous-close comparison.
PERCENTAGE_RETURN_WINDOW_LABEL = (
    "Close-to-close PERCENTAGE_RETURN from the earliest to the latest definitely-completed "
    "1-minute bar in the current trailing window. This is not a change versus the previous "
    "session close; the canonical metric is a bar-boundary return and is used unaltered."
)

#: Maximum chart points sent to the browser; downsampled by stride, never smoothed.
MAX_CHART_POINTS = 400

#: Which definitely-completed bars are supplied to the evaluator as evidence.
#:
#: The canonical evaluator rebuilds its point-in-time evidence bundle once per rule, and
#: conflict detection inside that bundle is quadratic in the number of observations. Batch
#: 08 pays that cost once, offline. A live screener refreshing many symbols every 30 s
#: cannot.
#:
#: The bars that any enabled rule actually consumes are exactly the two window boundaries:
#: ``PRICE_RANGE`` reads the latest completed bar, ``PERCENTAGE_RETURN`` reads the two
#: window-boundary closes, and the availability rules need at least one bar. No enabled
#: rule declares ``required_history_samples``. Supplying the boundary bars therefore
#: produces **identical outcomes** to supplying the whole window, at a fraction of the cost.
#:
#: This bounds the evidence set, not the observation. The full retrieved series is still
#: charted, and the included / straddling / post-boundary counts of the *whole* window are
#: reported alongside every snapshot, so nothing is hidden.
EVIDENCE_BAR_SELECTION = "WINDOW_BOUNDARY_BARS_ONLY.v1"
EVIDENCE_BAR_SELECTION_RATIONALE = (
    "Rule evidence is the earliest and latest definitely-completed bar of the current "
    "trailing window. Those are the only bars any enabled rule reads, so the outcomes are "
    "identical to supplying the entire window. The complete retrieved series is charted "
    "and its bar counts are reported; only the evaluator's input set is bounded."
)


class CurrentEvidenceUnavailable(RuntimeError):
    """Not enough admissible current evidence exists to construct a request."""


@dataclass(frozen=True, slots=True)
class CurrentEvaluation:
    """A current Phase 3A request/result pair plus the facts describing its evidence."""

    symbol: str
    as_of: datetime
    request: Any
    evaluation: Any
    rule_results: tuple[Any, ...]
    counts: dict[str, int]
    metric: Any | None
    included_bar_count: int
    straddling_bar_count: int
    post_boundary_bar_count: int
    evidence_bar_count: int
    metric_unavailable_reason: str | None
    provider_scope: tuple[str, ...]
    price_scope_reason: str | None


def _bar_interval_seconds() -> int:
    from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import BAR_INTERVAL_SECONDS

    return BAR_INTERVAL_SECONDS


def load_policy():
    """The committed 25-rule policy. No alternate policy is ever constructed."""
    from squeeze_core.evaluation.policies import DEFAULT_POLICY_PATH, load_policy as _load

    return _load(DEFAULT_POLICY_PATH)


def _parse_label(value: str) -> datetime:
    return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00")).astimezone(UTC)


def choose_as_of(labels: list[datetime], now: datetime) -> datetime:
    """The as-of instant: the completion of the most recent bar that is already complete.

    Using the provider's own bar clock rather than the wall clock keeps the as-of instant
    on an observed evidence boundary, so no bar is ever treated as complete before it is.
    """
    interval = timedelta(seconds=_bar_interval_seconds())
    completed = [label + interval for label in labels if label + interval <= now]
    if not completed:
        return now
    return max(completed)


def build_observations(
    symbol: str,
    bars: list[Any],
    *,
    as_of: datetime,
    retrieved_at: datetime,
):
    """Canonical observations for the definitely-completed current bars.

    Volume is omitted, never zeroed. The straddling and post-boundary counts are returned
    so the interface can say exactly how many bars were excluded and why.
    """
    from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import (
        BAR_INTERVAL,
        classify_labels,
        receipt_instant,
    )
    from squeeze_core.acquisition.phase3a_freeze.models import (
        ReceiptModelingPolicy,
        TimestampInterpretation,
    )
    from squeeze_core.adapters.base import AdapterContext
    from squeeze_core.adapters.market_bars import (
        BarCompletionStatus,
        BarSession,
        BarTimestampMeaning,
        BarVolumeUnit,
        MarketBarRecord,
        normalize_market_bar_records,
    )
    from squeeze_core.contracts import AssetClass, EntitlementState, IngestionMethod

    interval = timedelta(seconds=_bar_interval_seconds())
    rows: dict[datetime, Any] = {}
    for bar in bars:
        rows[_parse_label(bar.timestamp_utc)] = bar
    labels = classify_labels(tuple(rows), as_of)
    evidence_labels = select_evidence_labels(labels.included)

    interpretation = TimestampInterpretation.LABEL_IS_INTERVAL_START
    records = []
    for index, label in enumerate(evidence_labels, start=1):
        bar = rows[label]
        start, end = label, label + interval
        records.append(
            MarketBarRecord(
                source_record_id=f"{symbol}::{CURRENT_REQUEST_NAME}::row-{index}",
                provider_schema="MARKET_BAR_V1",
                record_type="MARKET_BAR",
                fixture_origin="SANITIZED_RECORDED_SAMPLE",
                provider=PROVIDER,
                provider_record_id=(
                    f"{symbol}::{CURRENT_REQUEST_NAME}::{int(label.timestamp())}"
                ),
                symbol=symbol,
                asset_class=AssetClass.EQUITY,
                interval=BAR_INTERVAL,
                bar_start=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                bar_end=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                provider_timestamp=label.strftime("%Y-%m-%dT%H:%M:%SZ"),
                timestamp_meaning=BarTimestampMeaning.START,
                open=str(bar.open),
                high=str(bar.high),
                low=str(bar.low),
                close=str(bar.close),
                # Omitted, never zeroed: see CURRENT_VOLUME_RATIONALE.
                volume=None,
                trade_count=None,
                vwap=None,
                volume_unit=BarVolumeUnit.UNKNOWN,
                session=BarSession.UNKNOWN,
                timezone="UTC",
                status=BarCompletionStatus.COMPLETED,
                publication_timestamp=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                revision_number=0,
            )
        )
    # Receipt is modelled as the conservative provider-availability instant of the last
    # included bar, exactly as Batch 08 models it (PROVIDER_AVAILABILITY_AS_RECEIPT). The
    # point-in-time engine gates on receipt; the real local retrieval clock is a few
    # seconds after the bar closed, so using it would make every bar point-in-time
    # ineligible against its own as-of instant. The real retrieval time is retained on the
    # snapshot and displayed as "received" — it is disclosed, not discarded.
    receipt = receipt_instant(
        ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        evidence_labels,
        retrieved_at,
    )
    context = AdapterContext(
        ingested_at=receipt,
        source_timezone="UTC",
        provider=PROVIDER,
        adapter_version=ADAPTER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        entitlement_status=EntitlementState.KNOWN,
        collection_method=IngestionMethod.DOWNLOADED,
        source_endpoint_name=SOURCE_ENDPOINT,
    )
    normalized = normalize_market_bar_records(tuple(records), context)
    if normalized.rejection is not None:
        raise CurrentEvidenceUnavailable(
            f"canonical bar normalization rejected {symbol}: {normalized.rejection.code.value}"
        )
    return normalized.observations, labels, evidence_labels


def select_evidence_labels(included: tuple[datetime, ...]) -> tuple[datetime, ...]:
    """The bars supplied to the evaluator. See :data:`EVIDENCE_BAR_SELECTION`."""
    if len(included) <= 2:
        return tuple(included)
    return (included[0], included[-1])


def build_percentage_return(symbol: str, observations, evidence_labels, as_of: datetime):
    """The canonical ``PERCENTAGE_RETURN``. The arithmetic lives in Phase 2, not here."""
    from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import BAR_INTERVAL
    from squeeze_core.contracts import AssetClass
    from squeeze_core.metrics import MetricName
    from squeeze_core.metrics.models import PriceField, ProviderScopeMode
    from squeeze_core.metrics.returns import ReturnRequest, build_return_result

    if len(evidence_labels) < 2:
        raise CurrentEvidenceUnavailable(
            "At least two definitely-completed bars are required for a close-to-close "
            "return. Fewer were available, so no percentage metric was constructed and "
            "PERCENTAGE_CHANGE_MINIMUM resolves through canonical missingness."
        )
    interval = timedelta(seconds=_bar_interval_seconds())
    reference, comparison = evidence_labels[0], evidence_labels[-1]
    return build_return_result(
        observations,
        ReturnRequest(
            symbol=symbol,
            asset_class=AssetClass.EQUITY,
            as_of=as_of,
            source_interval=BAR_INTERVAL,
            start_bar_start=reference,
            start_bar_end=reference + interval,
            end_bar_start=comparison,
            end_bar_end=comparison + interval,
            provider_scope=ProviderScopeMode.SINGLE_PROVIDER,
            provider=PROVIDER,
            price_field=PriceField.CLOSE,
        ),
        MetricName.PERCENTAGE_RETURN,
    )


def build_finviz_float_observation(
    symbol: str, float_shares: float, *, retrieved_at: datetime,
):
    """Canonical current-snapshot evidence for Finviz's provider-published ``Float``.

    Finviz's official definition matches the canonical ``float_shares`` concept. The
    retrieval instant is retained as the availability boundary; it is never backdated to
    the latest market bar.
    """
    from squeeze_core.contracts import (
        AssetClass, Completeness, DataFreshness, EntitlementState, EventType,
        IngestionMethod, MarketSession, MarketSnapshotPayload, Observation,
        ObservationKind, PayloadType, Provenance, Quality, QualityState,
    )

    value = int(float_shares)
    payload = MarketSnapshotPayload(float_shares=value)
    return Observation(
        schema_version="1.0.0",
        event_type=EventType.MARKET_SNAPSHOT,
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        source="Finviz Elite",
        source_record_id=(
            f"finviz-export:{symbol}:{retrieved_at.isoformat()}:market_snapshot"
        ),
        source_timestamp=retrieved_at,
        received_timestamp=retrieved_at,
        effective_timestamp=retrieved_at,
        market_session=MarketSession.UNKNOWN,
        data_freshness=DataFreshness.UNKNOWN,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=Quality(
            state=QualityState.ESTIMATED,
            reasons=("provider-published abbreviated float precision",),
            evaluated_at=retrieved_at,
            completeness=Completeness.PARTIAL,
        ),
        payload_type=PayloadType.MARKET_SNAPSHOT,
        payload=payload,
        provenance=Provenance(
            provider="Finviz Elite",
            ingestion_method=IngestionMethod.DOWNLOADED,
            origin_kind=ObservationKind.PROVIDER_PUBLISHED,
            normalized=True,
            normalization_version="finviz-current-float.v1",
            entitlement_state=EntitlementState.KNOWN,
            provider_metadata={
                "provider_field": "Float",
                "availability_basis": "EXPORT_RETRIEVAL_TIME",
                "selection_reason": "ONLY_AVAILABLE",
                "research_admissibility": "RESEARCH_ADMISSIBLE",
            },
        ),
    )


def price_scope_for(as_of: datetime, now: datetime) -> tuple[tuple[str, ...], str | None]:
    """Declare a provider scope only while the absolute-price argument actually holds."""
    age = (now - as_of).total_seconds()
    if age > CURRENT_PRICE_MAX_AGE_S:
        return (), (
            f"{STALE_PRICE_SCOPE_REASON} Latest completed bar is "
            f"{int(age)}s old; the admissibility window is {CURRENT_PRICE_MAX_AGE_S}s."
        )
    return CURRENT_PROVIDER_SCOPE, None


def build_request(
    symbol: str, as_of: datetime, policy, observations, metric, readiness,
    *, provider_scope: tuple[str, ...] = CURRENT_PROVIDER_SCOPE,
):
    """An ordinary ``RuleEvaluationRequest``. No parallel request type exists."""
    from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import BAR_INTERVAL
    from squeeze_core.contracts import AssetClass
    from squeeze_core.evaluation.models import RuleEvaluationRequest

    return RuleEvaluationRequest(
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        as_of=as_of,
        policy_version=policy.policy_version,
        enabled_rule_ids=policy.enabled_rule_ids,
        provider_scope=provider_scope,
        market_interval=BAR_INTERVAL,
        market_session=(),
        # Omitted, not defaulted: no volume window and no short-interest, borrow or news
        # provider, because no such current evidence exists.
        volume_window=None,
        short_interest_provider=None,
        borrow_provider=None,
        news_provider=None,
        input_observations=observations,
        input_metrics=() if metric is None else (metric,),
        input_readiness_results=readiness,
        default_substitution_fields=(),
    )


def evaluate_current(
    symbol: str,
    bars: list[Any],
    *,
    now: datetime,
    retrieved_at: datetime,
    policy=None,
    finviz_float_shares: float | None = None,
    finviz_retrieved_at: datetime | None = None,
) -> CurrentEvaluation:
    """Run the canonical 25-rule evaluation over one symbol's current evidence."""
    from squeeze_core.acquisition.phase3a_freeze.readiness_adapter import (
        build_bundle,
        build_readiness_records,
    )
    from squeeze_core.evaluation.evaluator import evaluate_candidate

    policy = policy or load_policy()
    labels_raw = [_parse_label(bar.timestamp_utc) for bar in bars]
    price_evidence_at = choose_as_of(labels_raw, now)
    # The current request boundary is the actual snapshot time. This lets independently
    # retrieved provider evidence retain its truthful receipt time without backdating.
    as_of = now

    observations, labels, evidence_labels = build_observations(
        symbol, bars, as_of=as_of, retrieved_at=retrieved_at
    )
    if finviz_float_shares is not None and finviz_retrieved_at is not None:
        observations = (
            *observations,
            build_finviz_float_observation(
                symbol, finviz_float_shares, retrieved_at=finviz_retrieved_at,
            ),
        )

    metric = None
    metric_unavailable_reason: str | None = None
    try:
        metric = build_percentage_return(symbol, observations, evidence_labels, as_of)
    except CurrentEvidenceUnavailable as exc:
        metric_unavailable_reason = str(exc)

    bundle = build_bundle(symbol, observations, as_of)
    readiness = build_readiness_records(bundle, policy, metric)
    provider_scope, scope_reason = price_scope_for(price_evidence_at, now)
    if finviz_float_shares is not None and finviz_retrieved_at is not None:
        provider_scope = tuple(sorted((*provider_scope, "Finviz Elite")))
    request = build_request(
        symbol, as_of, policy, observations, metric, readiness,
        provider_scope=provider_scope,
    )
    evaluation = evaluate_candidate(request, policy)

    counts: dict[str, int] = {}
    for item in evaluation.rule_results:
        counts[str(item.outcome)] = counts.get(str(item.outcome), 0) + 1
    for key in ("PASS", "FAIL", "UNKNOWN", "CONFLICTED", "INSUFFICIENT_DATA", "NOT_APPLICABLE"):
        counts.setdefault(key, 0)

    return CurrentEvaluation(
        symbol=symbol,
        # Presentation freshness is based on the latest completed market observation,
        # not on the later multi-provider request receipt boundary.
        as_of=price_evidence_at,
        request=request,
        evaluation=evaluation,
        rule_results=tuple(evaluation.rule_results),
        counts=counts,
        metric=metric,
        included_bar_count=len(labels.included),
        straddling_bar_count=labels.straddling_count,
        post_boundary_bar_count=labels.post_boundary_count,
        evidence_bar_count=len(evidence_labels),
        metric_unavailable_reason=metric_unavailable_reason,
        provider_scope=provider_scope,
        price_scope_reason=scope_reason,
    )


# --------------------------------------------------------------- presentation


def _threshold_display(rule) -> str:
    values = [str(value) for value in (rule.threshold_values or ())]
    if not values:
        return "—"
    operator = str(rule.operator) if rule.operator else ""
    unit = rule.threshold_unit or ""
    return " ".join(part for part in (operator, ", ".join(values), unit) if part)


#: Additional current-mode context appended to a rule's reason where it clarifies why an
#: outcome differs from frozen mode. Presentation only; no outcome is changed here.
CURRENT_RULE_NOTES: dict[str, str] = {
    "PRICE_RANGE": (
        "Evaluated in current mode: the absolute level of the latest definitely-completed "
        "current-session bar is admissible as a current price level. " +
        CURRENT_ABSOLUTE_PRICE_RATIONALE
    ),
    "RELATIVE_VOLUME_MINIMUM": CURRENT_VOLUME_RATIONALE,
    "PERCENTAGE_CHANGE_MINIMUM": PERCENTAGE_RETURN_WINDOW_LABEL,
}


def rule_rows(evaluation: CurrentEvaluation, rule_order: list[str] | None = None) -> list[dict[str, Any]]:
    """All 25 rules with observed value, threshold, outcome and reason."""
    from . import reasons

    by_id = {item.rule_id: item for item in evaluation.rule_results}
    order = rule_order or sorted(by_id)
    rows: list[dict[str, Any]] = []
    for rule_id in order:
        rule = by_id.get(rule_id)
        if rule is None:
            continue
        observed = rule.observed_value
        evidence_ids = (
            list(rule.input_metric_ids or ())
            + list(rule.input_observation_ids or ())
            + list(rule.readiness_snapshot_ids or ())
        )
        reason = reasons.explain_evaluation(rule.explanation_code)
        note = CURRENT_RULE_NOTES.get(rule_id)
        if rule_id == "PRICE_RANGE" and evaluation.price_scope_reason:
            note = evaluation.price_scope_reason
        if note:
            reason = f"{reason} {note}"
        rows.append(
            {
                "rule_id": rule_id,
                "rule_version": rule.rule_version,
                "category": str(rule.category),
                "outcome": str(rule.outcome),
                "observed_value": None if observed is None else str(observed),
                "observed_unit": rule.observed_unit,
                "observed_display": (
                    f"{observed} {rule.observed_unit or ''}".strip()
                    if observed is not None
                    else "—"
                ),
                "threshold": _threshold_display(rule),
                "evidence_ids": [str(item) for item in evidence_ids],
                "evidence_display": (
                    f"{len(evidence_ids)} evidence ID(s)" if evidence_ids else "—"
                ),
                "explanation_code": rule.explanation_code,
                "reason": reason,
                "blocking_reason_codes": [],
                "batch07_admissibility_status": (
                    CURRENT_ABSOLUTE_PRICE_STATUS if rule_id == "PRICE_RANGE"
                    else CURRENT_VOLUME_STATUS if rule_id == "RELATIVE_VOLUME_MINIMUM"
                    else "CURRENT_SNAPSHOT_EVIDENCE"
                ),
                "quality_state": str(rule.quality.state),
            }
        )
    return rows


def chart_points(bars: list[Any], as_of: datetime | None = None) -> dict[str, Any]:
    """Current-mode chart: real provider closes, downsampled by stride only."""
    points = [
        {"t": bar.timestamp_utc, "close": float(bar.close)}
        for bar in bars
    ]
    if not points:
        return {
            "available": False,
            "reason": "The provider returned no completed bars for the current window.",
            "points": [],
        }
    stride = max(1, len(points) // MAX_CHART_POINTS)
    sampled = points[::stride]
    if sampled[-1] is not points[-1]:
        sampled.append(points[-1])
    return {
        "available": True,
        "provider": PROVIDER,
        "series_label": "Current session close (raw provider bars)",
        "request_name": CURRENT_REQUEST_NAME,
        "points": sampled,
        "point_count_total": len(points),
        "point_count_plotted": len(sampled),
        # Current candidates have no frozen detection boundary, so none is drawn.
        "boundary_time": None,
        "boundary_label": None,
        "snapshot_time": None if as_of is None else as_of.isoformat().replace("+00:00", "Z"),
        "snapshot_label": "Snapshot Time",
        "forward_window_shown": False,
        "notes": [
            "Every plotted point is a real provider bar close. Downsampling is by stride, "
            "never by smoothing.",
            "Volume is not plotted: the provider's volume unit and corporate-action "
            "treatment are unresolved.",
            "No detection boundary is drawn. A current candidate has no frozen boundary; "
            "the marked instant is the snapshot time.",
        ],
    }


def evaluable_rule_ids(evaluation: CurrentEvaluation) -> list[str]:
    """Rules that reached PASS or FAIL, i.e. were actually supported by evidence."""
    return sorted(
        item.rule_id for item in evaluation.rule_results
        if str(item.outcome) in ("PASS", "FAIL")
    )


def research_detection(evaluation: CurrentEvaluation) -> dict[str, Any]:
    """Current research detection, using the canonical Batch 09 predicate."""
    from squeeze_core.research.detection import evaluate_research_detection
    from squeeze_core.research.policies import (
        DETECTION_POLICY_VERSION,
        load_detection_policy,
    )

    try:
        policy = load_detection_policy(DETECTION_POLICY_VERSION)
        outcome = evaluate_research_detection(evaluation.evaluation, policy)
        return {
            "status": str(outcome.status),
            "reasons": _detection_reasons(outcome),
            "required_rule_ids": list(policy.required_rule_ids),
            "preview_banner": None,
        }
    except Exception as exc:  # noqa: BLE001 - detection is advisory in current mode
        return {
            "status": "UNEVALUABLE",
            "reasons": [
                "The canonical research-detection predicate could not be applied to this "
                f"current snapshot: {type(exc).__name__}: {exc}"
            ],
            "required_rule_ids": [],
            "preview_banner": None,
        }


#: Canonical detection diagnostic codes mapped to the reason prefixes ``reasons`` explains.
_DETECTION_CODE_PREFIX = {
    "RESEARCH_DETECTION_REQUIRED_RULE_UNKNOWN": "REQUIRED_RULE_UNKNOWN",
    "RESEARCH_DETECTION_REQUIRED_RULE_CONFLICTED": "REQUIRED_RULE_CONFLICTED",
    "RESEARCH_DETECTION_REQUIRED_RULE_INSUFFICIENT": "REQUIRED_RULE_INSUFFICIENT_DATA",
}


def _detection_reasons(outcome) -> list[str]:
    from . import reasons

    raw: list[str] = []
    for diagnostic in getattr(outcome, "diagnostics", ()) or ():
        code = str(getattr(diagnostic, "code", ""))
        rule_id = getattr(diagnostic, "rule_id", None)
        prefix = _DETECTION_CODE_PREFIX.get(code)
        raw.append(f"{prefix}:{rule_id}" if prefix and rule_id else code)
    return reasons.explain_detection(raw)


__all__ = [
    "ADAPTER_VERSION",
    "CURRENT_ABSOLUTE_PRICE_CONSTRAINTS",
    "CURRENT_ABSOLUTE_PRICE_RATIONALE",
    "CURRENT_ABSOLUTE_PRICE_STATUS",
    "CURRENT_PROVIDER_SCOPE",
    "CURRENT_REQUEST_NAME",
    "CURRENT_RULE_NOTES",
    "CURRENT_VOLUME_RATIONALE",
    "CURRENT_VOLUME_STATUS",
    "MAX_CHART_POINTS",
    "PERCENTAGE_RETURN_WINDOW_LABEL",
    "PROVIDER",
    "CurrentEvaluation",
    "CurrentEvidenceUnavailable",
    "build_observations",
    "build_percentage_return",
    "build_request",
    "chart_points",
    "choose_as_of",
    "evaluable_rule_ids",
    "evaluate_current",
    "load_policy",
    "research_detection",
    "rule_rows",
]

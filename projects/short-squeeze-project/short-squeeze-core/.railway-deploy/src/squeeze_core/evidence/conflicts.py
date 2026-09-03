from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from typing import Any

from squeeze_core.contracts import (
    BorrowAvailabilityPayload,
    BorrowFeePayload,
    BarPayload,
    MarketSnapshotPayload,
    NewsItemPayload,
    Observation,
    PublishedShortInterestPayload,
    SecFilingPayload,
    TradingHaltPayload,
    TradePayload,
    QuotePayload,
)
from squeeze_core.serialization import canonical_hash

from .models import ConflictClassification, EvidenceConflict
from .policy import PointInTimeEvidencePolicy


@dataclass(frozen=True, slots=True)
class SemanticValue:
    observation: Observation
    semantic_field: str
    value: Any
    unit: str
    comparison_period: str | None = None


_SNAPSHOT_FIELDS = {
    "last_price": "USD",
    "previous_close": "USD",
    "change_percent": "PERCENT_POINTS",
    "volume": "SHARES",
    "average_volume": "SHARES",
    "relative_volume": "RATIO",
    "float_shares": "SHARES",
    "shares_outstanding": "SHARES",
    "short_float_percent": "PERCENT_POINTS",
    "short_ratio_days": "DAYS",
    "market_cap": "USD",
}


def semantic_values(observation: Observation) -> tuple[SemanticValue, ...]:
    payload = observation.payload
    fields: list[tuple[str, Any, str, str | None]] = []
    if isinstance(payload, MarketSnapshotPayload):
        fields.extend(
            (name, getattr(payload, name), unit, None)
            for name, unit in _SNAPSHOT_FIELDS.items()
        )
    elif isinstance(payload, BorrowFeePayload):
        fields.append(
            (
                "annualized_borrow_fee_percent",
                payload.annualized_fee_percent,
                "PERCENT_POINTS_ANNUALIZED",
                None,
            )
        )
    elif isinstance(payload, BorrowAvailabilityPayload):
        fields.extend(
            [
                ("borrow_available_shares", payload.available_shares, "SHARES", None),
                ("borrow_lender_count", payload.lender_count, "COUNT", None),
                ("borrow_hard_to_borrow", payload.hard_to_borrow, "BOOLEAN", None),
            ]
        )
    elif isinstance(payload, PublishedShortInterestPayload):
        comparison_period = (
            None if payload.settlement_date is None else payload.settlement_date.isoformat()
        )
        fields.extend(
            [
                (
                    "published_short_shares",
                    payload.short_shares,
                    "SHARES",
                    comparison_period,
                ),
                (
                    "published_short_float_percent",
                    payload.short_float_percent,
                    "PERCENT_POINTS",
                    comparison_period,
                ),
                (
                    "published_days_to_cover",
                    payload.days_to_cover,
                    "DAYS",
                    comparison_period,
                ),
            ]
        )
    elif isinstance(payload, SecFilingPayload):
        comparison_period = payload.accession_number
        fields.extend(
            [
                ("sec_form_type", payload.form_type, "FORM_TYPE", comparison_period),
                ("sec_filed_at", payload.filed_at, "UTC_TIMESTAMP", comparison_period),
                (
                    "sec_period_of_report",
                    payload.period_of_report,
                    "CALENDAR_DATE",
                    comparison_period,
                ),
                (
                    "sec_primary_document",
                    payload.primary_document,
                    "DOCUMENT_BASENAME",
                    comparison_period,
                ),
                ("sec_issuer_cik", payload.issuer_cik, "CIK", comparison_period),
            ]
        )
    elif isinstance(payload, TradingHaltPayload):
        metadata = observation.provenance.provider_metadata
        comparison_period = str(
            metadata.get("halt_event_key", f"observation:{observation.observation_id}")
        )
        fields.extend(
            [
                ("halt_code", metadata.get("halt_code"), "PROVIDER_CODE", comparison_period),
                (
                    "halt_quote_resumption_scheduled_at",
                    metadata.get("quote_resumption_scheduled_at"),
                    "UTC_TIMESTAMP",
                    comparison_period,
                ),
                (
                    "halt_quote_resumed_at",
                    metadata.get("quote_resumed_at"),
                    "UTC_TIMESTAMP",
                    comparison_period,
                ),
                (
                    "halt_trade_resumption_scheduled_at",
                    metadata.get("trade_resumption_scheduled_at"),
                    "UTC_TIMESTAMP",
                    comparison_period,
                ),
                (
                    "halt_trading_resumed_at",
                    metadata.get("trading_resumed_at"),
                    "UTC_TIMESTAMP",
                    comparison_period,
                ),
            ]
        )
    elif isinstance(payload, BarPayload):
        metadata = observation.provenance.provider_metadata
        comparison_period = canonical_hash(
            {
                "symbol": observation.symbol,
                "asset_class": observation.asset_class,
                "exchange": observation.exchange,
                "interval": payload.timeframe,
                "bar_start": metadata.get("bar_start"),
                "bar_end": metadata.get("bar_end"),
                "volume_unit": metadata.get("volume_unit"),
            }
        )
        volume_unit = str(metadata.get("volume_unit", "UNKNOWN"))
        fields.extend(
            [
                ("bar_open", payload.open, "PRICE", comparison_period),
                ("bar_high", payload.high, "PRICE", comparison_period),
                ("bar_low", payload.low, "PRICE", comparison_period),
                ("bar_close", payload.close, "PRICE", comparison_period),
                ("bar_volume", payload.volume, volume_unit, comparison_period),
                ("bar_trade_count", payload.trade_count, "COUNT", comparison_period),
                ("bar_vwap", payload.vwap, "PRICE", comparison_period),
            ]
        )
    elif isinstance(payload, (TradePayload, QuotePayload)):
        metadata = observation.provenance.provider_metadata
        comparison_period = canonical_hash(
            {
                "symbol": observation.symbol,
                "asset_class": observation.asset_class,
                "exchange": observation.exchange,
                "venue": metadata.get("venue"),
                "market_scope": metadata.get("market_scope"),
                "event_timestamp": metadata.get("event_timestamp"),
                "sequence_scope": metadata.get("sequence_scope"),
                "sequence_number": observation.sequence_number,
                "size_unit": metadata.get("size_unit"),
                "status": metadata.get("status"),
            }
        )
        size_unit = str(metadata.get("size_unit", "UNKNOWN"))
        if isinstance(payload, TradePayload):
            fields.extend(
                [
                    ("trade_price", payload.price, "PRICE", comparison_period),
                    ("trade_size", payload.size, size_unit, comparison_period),
                    ("trade_conditions", payload.conditions, "PROVIDER_CODES", comparison_period),
                ]
            )
        else:
            fields.extend(
                [
                    ("quote_bid_price", payload.bid_price, "PRICE", comparison_period),
                    ("quote_bid_size", payload.bid_size, size_unit, comparison_period),
                    ("quote_ask_price", payload.ask_price, "PRICE", comparison_period),
                    ("quote_ask_size", payload.ask_size, size_unit, comparison_period),
                    ("quote_condition", metadata.get("quote_condition"), "PROVIDER_CODE", comparison_period),
                    ("quote_market_state", metadata.get("quote_market_state"), "STRUCTURAL_STATE", comparison_period),
                ]
            )
    return tuple(
        SemanticValue(observation, name, value, unit, comparison_period)
        for name, value, unit, comparison_period in fields
        if value is not None
    )


def _numeric_difference(left: Any, right: Any) -> tuple[Decimal | None, Decimal | None]:
    if isinstance(left, bool) or isinstance(right, bool):
        return None, None
    try:
        left_decimal = Decimal(str(left))
        right_decimal = Decimal(str(right))
    except Exception:
        return None, None
    absolute = abs(left_decimal - right_decimal)
    denominator = max(abs(left_decimal), abs(right_decimal))
    relative = None if denominator == 0 else absolute / denominator
    return absolute, relative


def _conflict(
    left: SemanticValue,
    right: SemanticValue,
    classification: ConflictClassification,
) -> EvidenceConflict:
    absolute, relative = _numeric_difference(left.value, right.value)
    periods = sorted(
        {
            period
            for period in (left.comparison_period, right.comparison_period)
            if period is not None
        }
    )
    comparison_period = "|".join(periods) if periods else None
    seed = {
        "symbol": left.observation.symbol,
        "semantic_field": left.semantic_field,
        "observation_ids": (left.observation.observation_id, right.observation.observation_id),
        "classification": classification,
        "comparison_period": comparison_period,
    }
    return EvidenceConflict(
        conflict_id=f"conflict-{canonical_hash(seed)[:24]}",
        symbol=left.observation.symbol or "",
        semantic_field=left.semantic_field,
        observation_ids=(left.observation.observation_id, right.observation.observation_id),
        values=(left.value, right.value),
        units=(left.unit, right.unit),
        sources=(left.observation.source, right.observation.source),
        effective_timestamps=(
            left.observation.effective_timestamp,
            right.observation.effective_timestamp,
        ),
        received_timestamps=(
            left.observation.received_timestamp,
            right.observation.received_timestamp,
        ),
        absolute_difference=absolute,
        relative_difference=relative,
        classification=classification,
        comparison_period=comparison_period,
    )


def _is_revision_pair(left: SemanticValue, right: SemanticValue) -> bool:
    if left.observation.provenance.provider != right.observation.provenance.provider:
        return False
    if left.observation.observation_id in right.observation.parent_observation_ids:
        return True
    if right.observation.observation_id in left.observation.parent_observation_ids:
        return True
    left_supersedes = left.observation.provenance.provider_metadata.get(
        "supersedes_source_record_id"
    )
    right_supersedes = right.observation.provenance.provider_metadata.get(
        "supersedes_source_record_id"
    )
    left_amends = left.observation.provenance.provider_metadata.get(
        "amends_accession_number"
    )
    right_amends = right.observation.provenance.provider_metadata.get(
        "amends_accession_number"
    )
    left_accession = getattr(left.observation.payload, "accession_number", None)
    right_accession = getattr(right.observation.payload, "accession_number", None)
    left_bar_supersedes = left.observation.provenance.provider_metadata.get(
        "supersedes_provider_record_id"
    )
    right_bar_supersedes = right.observation.provenance.provider_metadata.get(
        "supersedes_provider_record_id"
    )
    bar_lifecycle_chain = (
        isinstance(left.observation.payload, BarPayload)
        and isinstance(right.observation.payload, BarPayload)
        and left.observation.provenance.provider
        == right.observation.provenance.provider
        and (left_bar_supersedes is not None or right_bar_supersedes is not None)
    )
    return (
        left_supersedes == right.observation.source_record_id
        or right_supersedes == left.observation.source_record_id
        or (left_amends is not None and left_amends == right_accession)
        or (right_amends is not None and right_amends == left_accession)
        or left_bar_supersedes == right.observation.source_record_id
        or right_bar_supersedes == left.observation.source_record_id
        or bar_lifecycle_chain
    )


def _news_conflict(
    left: Observation,
    right: Observation,
    field: str,
    left_value: Any,
    right_value: Any,
) -> EvidenceConflict:
    ordered = sorted(
        ((left, left_value), (right, right_value)), key=lambda item: item[0].observation_id
    )
    left_observation, left_value = ordered[0]
    right_observation, right_value = ordered[1]
    common_symbols = sorted(
        set(left_observation.payload.associated_symbols)
        & set(right_observation.payload.associated_symbols)
    )
    classification = (
        ConflictClassification.DUPLICATE_CONFLICT
        if left_observation.source_record_id == right_observation.source_record_id
        else ConflictClassification.VALUE_CONFLICT
    )
    comparison_period = (
        left_observation.payload.url
        if left_observation.payload.url == right_observation.payload.url
        else left_observation.source_record_id
    )
    seed = {
        "semantic_field": field,
        "observation_ids": (
            left_observation.observation_id,
            right_observation.observation_id,
        ),
        "classification": classification,
        "comparison_period": comparison_period,
    }
    return EvidenceConflict(
        conflict_id=f"conflict-{canonical_hash(seed)[:24]}",
        symbol=common_symbols[0] if common_symbols else "",
        semantic_field=field,
        observation_ids=(
            left_observation.observation_id,
            right_observation.observation_id,
        ),
        values=(left_value, right_value),
        units=("OBJECTIVE_METADATA", "OBJECTIVE_METADATA"),
        sources=(left_observation.source, right_observation.source),
        effective_timestamps=(
            left_observation.effective_timestamp,
            right_observation.effective_timestamp,
        ),
        received_timestamps=(
            left_observation.received_timestamp,
            right_observation.received_timestamp,
        ),
        classification=classification,
        comparison_period=comparison_period,
    )


def _news_conflicts(observations: Iterable[Observation]) -> list[EvidenceConflict]:
    news = sorted(
        (item for item in observations if isinstance(item.payload, NewsItemPayload)),
        key=lambda item: item.observation_id,
    )
    conflicts: list[EvidenceConflict] = []
    for left, right in combinations(news, 2):
        if (
            left.observation_id in right.parent_observation_ids
            or right.observation_id in left.parent_observation_ids
        ):
            continue
        same_provider_record = left.source_record_id == right.source_record_id
        same_url = left.payload.url is not None and left.payload.url == right.payload.url
        if not same_provider_record and not same_url:
            continue
        comparisons = (
            ("news_headline", left.payload.headline, right.payload.headline),
            (
                "news_publication_timestamp",
                left.payload.published_at,
                right.payload.published_at,
            ),
            (
                "news_associated_symbols",
                left.payload.associated_symbols,
                right.payload.associated_symbols,
            ),
            ("news_canonical_url", left.payload.url, right.payload.url),
        )
        for field, left_value, right_value in comparisons:
            if left_value != right_value:
                conflicts.append(
                    _news_conflict(left, right, field, left_value, right_value)
                )
    return conflicts


def build_conflicts(
    observations: Iterable[Observation],
    policy: PointInTimeEvidencePolicy,
) -> tuple[EvidenceConflict, ...]:
    grouped: dict[str, list[SemanticValue]] = defaultdict(list)
    for observation in observations:
        for value in semantic_values(observation):
            grouped[value.semantic_field].append(value)

    conflicts: list[EvidenceConflict] = []
    for field in sorted(grouped):
        values = sorted(
            grouped[field],
            key=lambda item: (
                item.observation.effective_timestamp,
                item.comparison_period or "",
                item.observation.source,
                item.observation.observation_id,
            ),
        )
        is_published_field = field.startswith("published_")
        is_sec_field = field.startswith("sec_")
        is_halt_field = field.startswith("halt_")
        is_bar_field = field.startswith("bar_")
        is_trade_field = field.startswith("trade_")
        is_quote_field = field.startswith("quote_")
        is_period_keyed = is_published_field or is_sec_field or is_halt_field or is_bar_field or is_trade_field or is_quote_field
        for left, right in combinations(values, 2):
            if is_period_keyed and _is_revision_pair(left, right):
                continue
            if is_period_keyed and left.comparison_period != right.comparison_period:
                if is_trade_field or is_quote_field or is_bar_field:
                    continue
                conflicts.append(
                    _conflict(left, right, ConflictClassification.TEMPORAL_DIFFERENCE)
                )
                continue
            if (
                not is_period_keyed
                and left.observation.effective_timestamp
                != right.observation.effective_timestamp
            ):
                conflicts.append(
                    _conflict(left, right, ConflictClassification.TEMPORAL_DIFFERENCE)
                )
                continue
            if is_halt_field and left.value == right.value:
                continue
            if left.observation.source == right.observation.source:
                conflicts.append(
                    _conflict(left, right, ConflictClassification.DUPLICATE_CONFLICT)
                )
                continue
            if left.value == right.value:
                continue
            absolute, _ = _numeric_difference(left.value, right.value)
            tolerance = policy.conflict_tolerance.get(field, Decimal("0"))
            if absolute is not None and absolute <= tolerance:
                continue
            conflicts.append(_conflict(left, right, ConflictClassification.VALUE_CONFLICT))

    conflicts.extend(_news_conflicts(observations))
    conflicts.sort(
        key=lambda item: (
            item.semantic_field,
            item.classification.value,
            item.effective_timestamps,
            item.observation_ids,
            item.conflict_id,
        )
    )
    return tuple(conflicts)

"""Deterministic, offline normalization of a local bar bundle into canonical bars.

Ambiguous, malformed, tampered, incomplete, or semantically unsafe input is
rejected or quarantined with explicit reason codes. Nothing is inferred or
repaired: missing OHLCV stays missing, ambiguous timezones stay ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from squeeze_core.adapters.market_bars.parsing import BarParseError, parse_bar_timestamp
from squeeze_core.adapters.market_bars.semantics import BarIntervalKind, BarIntervalUnit

from .artifact_validation import read_artifact_bytes, validate_artifact_bytes
from .csv_adapter import ParsedRow, parse_delimited_rows
from .models import (
    CanonicalMarketBar,
    ColumnMappingProfile,
    IntakeManifest,
    NormalizationDiagnostics,
    NormalizedBarSet,
    RowDiagnostic,
)
from .semantics import (
    BarInterval,
    CorporateActionHandling,
    DataTimeBasis,
    DuplicatePolicy,
    IntakeReasonCode,
    IntakeValidationStatus,
    IntendedUse,
    PriceAdjustmentSemantics,
    RowNormalizationStatus,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)


_THOUSANDS = {
    ThousandsSeparatorPolicy.COMMA: ",",
    ThousandsSeparatorPolicy.SPACE: " ",
    ThousandsSeparatorPolicy.UNDERSCORE: "_",
}
_NON_FINITE_TOKENS = {"nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
_DECIMAL_RE = re.compile(r"[+-]?\d+(\.\d+)?$")
_INTEGER_RE = re.compile(r"[+-]?\d+$")
_PARSE_ERROR_CODES = {
    "BAR_MISSING_TIMEZONE": IntakeReasonCode.UNKNOWN_TIMEZONE,
    "BAR_AMBIGUOUS_LOCAL_TIME": IntakeReasonCode.AMBIGUOUS_TIMEZONE,
    "BAR_NONEXISTENT_LOCAL_TIME": IntakeReasonCode.NONEXISTENT_LOCAL_TIME,
    "BAR_INVALID_TIMESTAMP": IntakeReasonCode.INVALID_TIMESTAMP,
    "BAR_MISSING_START": IntakeReasonCode.INVALID_TIMESTAMP,
}


class _RowError(ValueError):
    def __init__(self, code: IntakeReasonCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class NormalizationOutcome:
    bar_set: NormalizedBarSet | None
    diagnostics: NormalizationDiagnostics


@dataclass(slots=True)
class _Candidate:
    row_number: int
    record_id: str
    bar: CanonicalMarketBar


@dataclass(slots=True)
class _Collector:
    normalized: list[_Candidate] = field(default_factory=list)
    rows: list[RowDiagnostic] = field(default_factory=list)
    bundle_codes: set[IntakeReasonCode] = field(default_factory=set)


def _resolve_timezone_ok(name: str) -> bool:
    if name == "UTC":
        return True
    if re.fullmatch(r"[+-]\d{2}:\d{2}", name):
        return int(name[1:3]) <= 23 and int(name[4:6]) <= 59
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def _interval_duration(interval: BarInterval) -> timedelta | None:
    if interval.kind is BarIntervalKind.SESSION_BASED:
        return None
    return {
        BarIntervalUnit.MINUTE: timedelta(minutes=interval.magnitude),
        BarIntervalUnit.HOUR: timedelta(hours=interval.magnitude),
    }[interval.unit]


# Provider-name token identifying Interactive Brokers as the data source.
# IBKR TRADES bars have honestly UNKNOWN volume-adjustment and timestamp semantics
# (see ADR 0066). These UNKNOWN values are accepted with documented provenance.
_IBKR_PROVIDER_TOKEN = "Interactive Brokers"


def _is_ibkr_provider(manifest: IntakeManifest) -> bool:
    """Check whether the manifest declares an Interactive Brokers source."""
    return _IBKR_PROVIDER_TOKEN.lower() in manifest.provider_name.lower()


def _manifest_semantic_codes(manifest: IntakeManifest) -> set[IntakeReasonCode]:
    codes: set[IntakeReasonCode] = set()
    is_ibkr = _is_ibkr_provider(manifest)
    if manifest.timestamp_semantics not in {TimestampSemantics.START, TimestampSemantics.END}:
        if not is_ibkr:
            codes.add(IntakeReasonCode.MISSING_TIMESTAMP_SEMANTICS)
    if manifest.price_adjustment_semantics is PriceAdjustmentSemantics.UNKNOWN:
        codes.add(IntakeReasonCode.MISSING_ADJUSTMENT_SEMANTICS)
    if manifest.volume_adjustment_semantics is VolumeAdjustmentSemantics.UNKNOWN:
        if not is_ibkr:
            codes.add(IntakeReasonCode.MISSING_ADJUSTMENT_SEMANTICS)
    if manifest.corporate_action_handling is CorporateActionHandling.UNKNOWN:
        codes.add(IntakeReasonCode.MISSING_ADJUSTMENT_SEMANTICS)
    else:
        price_is_raw = manifest.price_adjustment_semantics is PriceAdjustmentSemantics.RAW_UNADJUSTED
        handling_is_raw = manifest.corporate_action_handling is CorporateActionHandling.RAW_NO_ADJUSTMENT
        if (
            manifest.price_adjustment_semantics is not PriceAdjustmentSemantics.UNKNOWN
            and price_is_raw != handling_is_raw
        ):
            codes.add(IntakeReasonCode.CONTRADICTORY_ADJUSTMENT_SEMANTICS)
    if manifest.data_time_basis is DataTimeBasis.CURRENT:
        codes.add(IntakeReasonCode.CURRENT_VALUE_AS_HISTORICAL)
    elif manifest.data_time_basis is DataTimeBasis.UNKNOWN:
        codes.add(IntakeReasonCode.DATA_TIME_BASIS_UNKNOWN)
    if (
        manifest.value_authenticity is ValueAuthenticity.SYNTHETIC_FIXTURE
        and manifest.intended_use is IntendedUse.HISTORICAL_EVIDENCE
    ):
        codes.add(IntakeReasonCode.SYNTHETIC_VALUE_AS_HISTORICAL)
    if not _resolve_timezone_ok(manifest.event_timezone):
        codes.add(IntakeReasonCode.UNKNOWN_TIMEZONE)
    if _interval_duration(manifest.bar_interval) is None:
        # Session-based (daily) bars need explicit boundaries this batch does not model.
        codes.add(IntakeReasonCode.UNSUPPORTED_INTERVAL)
    return codes


def _clean_number(raw: str, profile: ColumnMappingProfile) -> str | None:
    value = raw.strip()
    if value == "" or value in profile.null_tokens:
        return None
    if profile.thousands_separator_policy is not ThousandsSeparatorPolicy.DISALLOW:
        value = value.replace(_THOUSANDS[profile.thousands_separator_policy], "")
    if profile.decimal_separator != ".":
        if "." in value:
            raise _RowError(IntakeReasonCode.MALFORMED_DECIMAL, "unexpected '.' in decimal")
        value = value.replace(profile.decimal_separator, ".")
    return value


def _parse_price(raw: str, profile: ColumnMappingProfile) -> Decimal | None:
    cleaned = _clean_number(raw, profile)
    if cleaned is None:
        return None
    if cleaned.lower() in _NON_FINITE_TOKENS:
        raise _RowError(IntakeReasonCode.NAN_OR_INFINITY, "non-finite value")
    if not _DECIMAL_RE.match(cleaned):
        raise _RowError(IntakeReasonCode.MALFORMED_DECIMAL, "malformed decimal")
    try:
        parsed = Decimal(cleaned)
    except InvalidOperation as error:
        raise _RowError(IntakeReasonCode.MALFORMED_DECIMAL, "malformed decimal") from error
    if not parsed.is_finite():
        raise _RowError(IntakeReasonCode.NAN_OR_INFINITY, "non-finite value")
    return parsed


def _parse_int(raw: str, profile: ColumnMappingProfile, negative_code: IntakeReasonCode) -> int | None:
    cleaned = _clean_number(raw, profile)
    if cleaned is None:
        return None
    if cleaned.lower() in _NON_FINITE_TOKENS:
        raise _RowError(IntakeReasonCode.NAN_OR_INFINITY, "non-finite value")
    if not _INTEGER_RE.match(cleaned):
        raise _RowError(IntakeReasonCode.MALFORMED_DECIMAL, "malformed integer")
    parsed = int(cleaned)
    if parsed < 0:
        raise _RowError(negative_code, "negative value")
    return parsed


def _cell(row: ParsedRow, column: str | None) -> str | None:
    if column is None:
        return None
    return row.cells.get(column)


def _event_timestamp(row: ParsedRow, manifest: IntakeManifest, profile: ColumnMappingProfile) -> datetime:
    if profile.timestamp_column is not None:
        raw = _cell(row, profile.timestamp_column)
    else:
        date_part = _cell(row, profile.date_column)
        time_part = _cell(row, profile.time_column)
        raw = None if date_part is None or time_part is None else f"{date_part.strip()} {time_part.strip()}"
    if raw is None or not raw.strip():
        raise _RowError(IntakeReasonCode.INVALID_TIMESTAMP, "missing timestamp")
    try:
        parsed = parse_bar_timestamp(
            raw, session_date=None, timezone_name=manifest.event_timezone, field="event_time"
        )
    except BarParseError as error:
        raise _RowError(
            _PARSE_ERROR_CODES.get(error.code, IntakeReasonCode.INVALID_TIMESTAMP), str(error)
        ) from error
    if parsed is None:
        raise _RowError(IntakeReasonCode.INVALID_TIMESTAMP, "missing timestamp")
    return parsed.timestamp


def _build_bar(
    row: ParsedRow, manifest: IntakeManifest, profile: ColumnMappingProfile
) -> tuple[str, CanonicalMarketBar]:
    symbol_cell = _cell(row, profile.symbol_column)
    if symbol_cell is not None and symbol_cell.strip().upper() != manifest.provider_symbol:
        raise _RowError(IntakeReasonCode.SYMBOL_MISMATCH, "row symbol disagrees with manifest")
    venue_cell = _cell(row, profile.venue_column)
    if venue_cell is not None and venue_cell.strip().upper() != manifest.market_or_venue.upper():
        raise _RowError(IntakeReasonCode.MARKET_VENUE_MISMATCH, "row venue disagrees with manifest")

    labeled = _event_timestamp(row, manifest, profile)
    duration = _interval_duration(manifest.bar_interval)
    assert duration is not None  # session-based intervals are blocked at bundle level
    if manifest.timestamp_semantics is TimestampSemantics.START:
        start, end = labeled, labeled + duration
    else:
        start, end = labeled - duration, labeled

    if start < manifest.expected_start_time or end > manifest.expected_end_time:
        raise _RowError(IntakeReasonCode.EVENT_TIME_OUTSIDE_COVERAGE, "bar outside declared coverage")

    prices: dict[str, Decimal] = {}
    for name, column in (
        ("open", profile.open_column), ("high", profile.high_column),
        ("low", profile.low_column), ("close", profile.close_column),
    ):
        raw = _cell(row, column)
        parsed = None if raw is None else _parse_price(raw, profile)
        if parsed is None:
            raise _RowError(IntakeReasonCode.MISSING_OHLC_VALUE, f"missing {name}")
        prices[name] = parsed
    if (
        prices["high"] < max(prices["open"], prices["close"], prices["low"])
        or prices["low"] > min(prices["open"], prices["close"], prices["high"])
    ):
        raise _RowError(IntakeReasonCode.INVALID_OHLC_RELATIONSHIP, "impossible OHLC relationship")

    volume = None
    raw_volume = _cell(row, profile.volume_column)
    if raw_volume is not None:
        volume = _parse_int(raw_volume, profile, IntakeReasonCode.NEGATIVE_VOLUME)
    trade_count = None
    raw_trade = _cell(row, profile.trade_count_column)
    if raw_trade is not None:
        trade_count = _parse_int(raw_trade, profile, IntakeReasonCode.NEGATIVE_TRADE_COUNT)
    vwap = None
    raw_vwap = _cell(row, profile.vwap_column)
    if raw_vwap is not None:
        vwap = _parse_price(raw_vwap, profile)
    currency = None
    raw_currency = _cell(row, profile.currency_column)
    if raw_currency is not None and raw_currency.strip():
        currency = raw_currency.strip().upper()

    record_id = f"{manifest.bundle_id}::row-{row.source_row_number}"
    bar = CanonicalMarketBar(
        canonical_symbol=manifest.canonical_symbol,
        provider_symbol=manifest.provider_symbol,
        market_or_venue=manifest.market_or_venue,
        interval=manifest.bar_interval,
        event_start_time=start,
        event_end_time=end,
        event_timezone=manifest.event_timezone,
        session=manifest.session_coverage,
        open=prices["open"],
        high=prices["high"],
        low=prices["low"],
        close=prices["close"],
        volume=volume,
        trade_count=trade_count,
        vwap=vwap,
        currency=currency,
        price_adjustment_semantics=manifest.price_adjustment_semantics,
        volume_adjustment_semantics=manifest.volume_adjustment_semantics,
        value_authenticity=manifest.value_authenticity,
        source_artifact_id=f"{manifest.bundle_id}::raw",
        source_row_number=row.source_row_number,
        source_record_id=record_id,
    )
    return record_id, bar


def _dedupe_and_check(collector: _Collector, profile: ColumnMappingProfile) -> list[_Candidate]:
    by_start: dict[datetime, list[_Candidate]] = {}
    for candidate in collector.normalized:
        by_start.setdefault(candidate.bar.event_start_time, []).append(candidate)

    kept: list[_Candidate] = []
    for start, group in by_start.items():
        if len(group) == 1:
            kept.append(group[0])
            continue
        if profile.duplicate_policy is DuplicatePolicy.REJECT_ALL_DUPLICATES:
            collector.bundle_codes.add(IntakeReasonCode.DUPLICATE_TIMESTAMP)
            for candidate in group:
                collector.rows.append(RowDiagnostic(
                    source_row_number=candidate.row_number, source_record_id=candidate.record_id,
                    status=RowNormalizationStatus.REJECTED,
                    reason_codes=(IntakeReasonCode.DUPLICATE_TIMESTAMP,),
                    message="duplicate timestamp rejected by policy",
                ))
            continue
        signatures = {_bar_signature(candidate.bar) for candidate in group}
        ordered = sorted(group, key=lambda item: item.row_number)
        if len(signatures) == 1:
            kept.append(ordered[0])
            for candidate in ordered[1:]:
                collector.rows.append(RowDiagnostic(
                    source_row_number=candidate.row_number, source_record_id=candidate.record_id,
                    status=RowNormalizationStatus.QUARANTINED,
                    reason_codes=(IntakeReasonCode.DUPLICATE_TIMESTAMP,),
                    message="identical duplicate collapsed",
                ))
        else:
            collector.bundle_codes.add(IntakeReasonCode.CONFLICTING_DUPLICATE_BAR)
            for candidate in ordered:
                collector.rows.append(RowDiagnostic(
                    source_row_number=candidate.row_number, source_record_id=candidate.record_id,
                    status=RowNormalizationStatus.REJECTED,
                    reason_codes=(IntakeReasonCode.CONFLICTING_DUPLICATE_BAR,),
                    message="conflicting duplicate bar at the same timestamp",
                ))
    kept.sort(key=lambda item: (item.bar.event_start_time, item.row_number))
    return kept


def _bar_signature(bar: CanonicalMarketBar) -> tuple:
    return (
        bar.event_start_time, bar.event_end_time, bar.open, bar.high, bar.low, bar.close,
        bar.volume, bar.trade_count, bar.vwap, bar.currency,
    )


def _check_ordering_and_continuity(
    collector: _Collector, manifest: IntakeManifest, profile: ColumnMappingProfile,
    kept: list[_Candidate],
) -> None:
    if profile.sort_expectation is SortExpectation.REQUIRE_PRESORTED:
        by_input = sorted(collector.normalized, key=lambda item: item.row_number)
        starts = [item.bar.event_start_time for item in by_input]
        if starts != sorted(starts):
            collector.bundle_codes.add(IntakeReasonCode.NON_MONOTONIC_ORDER)

    duration = _interval_duration(manifest.bar_interval)
    for earlier, later in zip(kept, kept[1:]):
        if later.bar.event_start_time < earlier.bar.event_end_time:
            collector.bundle_codes.add(IntakeReasonCode.OVERLAPPING_BARS)
        elif (
            manifest.session_coverage_policy is SessionCoveragePolicy.REQUIRE_CONTINUOUS
            and duration is not None
            and later.bar.event_start_time != earlier.bar.event_end_time
        ):
            collector.bundle_codes.add(IntakeReasonCode.COVERAGE_GAP)


def normalize_bundle(
    root: Path, manifest: IntakeManifest, profile: ColumnMappingProfile
) -> NormalizationOutcome:
    """Validate and normalize an on-disk bundle."""
    return normalize_from_bytes(manifest, profile, read_artifact_bytes(root, manifest))


def normalize_from_bytes(
    manifest: IntakeManifest, profile: ColumnMappingProfile, content: bytes | None
) -> NormalizationOutcome:
    """Validate and normalize raw artifact bytes (filesystem-free entry point)."""
    collector = _Collector()

    artifact_report = validate_artifact_bytes(manifest, content)
    if artifact_report.status is not IntakeValidationStatus.ACCEPTED:
        collector.bundle_codes.update(artifact_report.reason_codes)
        return _finalize(manifest, collector, total_rows=0, kept=[])

    collector.bundle_codes.update(_manifest_semantic_codes(manifest))
    if collector.bundle_codes:
        # A bundle-level semantic barrier blocks normalization entirely; no bars.
        return _finalize(manifest, collector, total_rows=0, kept=[])

    assert content is not None
    parse_outcome = parse_delimited_rows(content, profile)
    if parse_outcome.reason is not None:
        collector.bundle_codes.add(parse_outcome.reason)
        return _finalize(manifest, collector, total_rows=0, kept=[])

    total_rows = len(parse_outcome.rows)
    for row in parse_outcome.rows:
        try:
            record_id, bar = _build_bar(row, manifest, profile)
        except _RowError as error:
            collector.rows.append(RowDiagnostic(
                source_row_number=row.source_row_number,
                status=RowNormalizationStatus.REJECTED,
                reason_codes=(error.code,), message=str(error),
            ))
            collector.bundle_codes.add(error.code)
            continue
        collector.normalized.append(_Candidate(row.source_row_number, record_id, bar))

    kept = _dedupe_and_check(collector, profile)
    _check_ordering_and_continuity(collector, manifest, profile, kept)
    return _finalize(manifest, collector, total_rows=total_rows, kept=kept)


# Reason codes that force a full bundle rejection (unsafe to accept partially).
_FATAL_CODES = {
    IntakeReasonCode.CONFLICTING_DUPLICATE_BAR,
    IntakeReasonCode.OVERLAPPING_BARS,
    IntakeReasonCode.NON_MONOTONIC_ORDER,
    IntakeReasonCode.COVERAGE_GAP,
    IntakeReasonCode.DUPLICATE_TIMESTAMP,
    IntakeReasonCode.INVALID_OHLC_RELATIONSHIP,
    IntakeReasonCode.MALFORMED_DECIMAL,
    IntakeReasonCode.NAN_OR_INFINITY,
    IntakeReasonCode.NEGATIVE_VOLUME,
    IntakeReasonCode.NEGATIVE_TRADE_COUNT,
    IntakeReasonCode.MISSING_OHLC_VALUE,
    IntakeReasonCode.EVENT_TIME_OUTSIDE_COVERAGE,
    IntakeReasonCode.SYMBOL_MISMATCH,
    IntakeReasonCode.MARKET_VENUE_MISMATCH,
    IntakeReasonCode.INVALID_TIMESTAMP,
    IntakeReasonCode.UNKNOWN_TIMEZONE,
    IntakeReasonCode.AMBIGUOUS_TIMEZONE,
    IntakeReasonCode.NONEXISTENT_LOCAL_TIME,
    IntakeReasonCode.MISSING_TIMESTAMP_SEMANTICS,
    IntakeReasonCode.MISSING_ADJUSTMENT_SEMANTICS,
    IntakeReasonCode.CONTRADICTORY_ADJUSTMENT_SEMANTICS,
    IntakeReasonCode.CURRENT_VALUE_AS_HISTORICAL,
    IntakeReasonCode.SYNTHETIC_VALUE_AS_HISTORICAL,
    IntakeReasonCode.DATA_TIME_BASIS_UNKNOWN,
    IntakeReasonCode.UNSUPPORTED_INTERVAL,
    IntakeReasonCode.UNSUPPORTED_ENCODING,
    IntakeReasonCode.UNSUPPORTED_FORMAT,
    IntakeReasonCode.ARTIFACT_MISSING,
    IntakeReasonCode.ARTIFACT_EMPTY,
    IntakeReasonCode.ARTIFACT_BYTE_LENGTH_MISMATCH,
    IntakeReasonCode.ARTIFACT_SHA256_MISMATCH,
}


def _finalize(
    manifest: IntakeManifest, collector: _Collector, *, total_rows: int, kept: list[_Candidate]
) -> NormalizationOutcome:
    fatal = collector.bundle_codes & _FATAL_CODES
    quarantined = sum(
        1 for row in collector.rows if row.status is RowNormalizationStatus.QUARANTINED
    )
    rejected_rows = sum(
        1 for row in collector.rows if row.status is RowNormalizationStatus.REJECTED
    )

    if fatal:
        status = IntakeValidationStatus.REJECTED
        bar_set = None
        normalized_count = 0
    elif quarantined:
        status = IntakeValidationStatus.QUARANTINED
        bar_set = _bar_set(manifest, kept)
        normalized_count = len(kept)
    else:
        status = IntakeValidationStatus.ACCEPTED
        bar_set = _bar_set(manifest, kept)
        normalized_count = len(kept)

    for candidate in kept:
        collector.rows.append(RowDiagnostic(
            source_row_number=candidate.row_number, source_record_id=candidate.record_id,
            status=RowNormalizationStatus.NORMALIZED,
            reason_codes=(), message="normalized",
        ))

    diagnostics = NormalizationDiagnostics(
        bundle_id=manifest.bundle_id,
        status=status,
        total_rows=total_rows,
        normalized_count=normalized_count if not fatal else 0,
        quarantined_count=quarantined,
        rejected_count=rejected_rows,
        bundle_reason_codes=tuple(collector.bundle_codes),
        row_diagnostics=tuple(collector.rows),
    )
    return NormalizationOutcome(bar_set=None if fatal else bar_set, diagnostics=diagnostics)


def _bar_set(manifest: IntakeManifest, kept: list[_Candidate]) -> NormalizedBarSet:
    return NormalizedBarSet(
        bundle_id=manifest.bundle_id,
        canonical_symbol=manifest.canonical_symbol,
        interval=manifest.bar_interval,
        source_artifact_id=f"{manifest.bundle_id}::raw",
        bars=tuple(candidate.bar for candidate in kept),
    )


__all__ = ["NormalizationOutcome", "normalize_bundle", "normalize_from_bytes"]

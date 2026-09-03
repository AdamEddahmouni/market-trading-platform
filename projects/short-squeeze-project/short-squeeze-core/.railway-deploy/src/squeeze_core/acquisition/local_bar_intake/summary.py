"""Deterministic intake summary and canonical bar serialization (JSONL / CSV)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.serialization import canonical_json_bytes

from .models import (
    ArtifactValidationReport,
    CanonicalMarketBar,
    IntakeManifest,
    IntakeSummary,
    NormalizationDiagnostics,
    NormalizedBarSet,
)
from .semantics import IntakeReasonCode


CSV_COLUMNS = (
    "canonical_symbol", "provider_symbol", "market_or_venue", "interval",
    "event_start_time", "event_end_time", "event_timezone", "session",
    "open", "high", "low", "close", "volume", "trade_count", "vwap", "currency",
    "price_adjustment_semantics", "volume_adjustment_semantics", "value_authenticity",
    "source_artifact_id", "source_row_number", "source_record_id",
)


def _decimal_str(value: Decimal) -> str:
    if value == 0:
        return "0"
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _iso(value: datetime) -> str:
    # Matches the canonical JSON datetime encoder so CSV and JSONL agree byte-for-byte.
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return _decimal_str(value)
    return str(value)


def serialize_bars_jsonl(bar_set: NormalizedBarSet) -> bytes:
    return b"".join(canonical_json_bytes(bar) + b"\n" for bar in bar_set.bars)


def serialize_bars_csv(bar_set: NormalizedBarSet) -> bytes:
    lines = [",".join(CSV_COLUMNS)]
    for bar in bar_set.bars:
        values = []
        for column in CSV_COLUMNS:
            attribute = getattr(bar, column)
            if column in {"event_start_time", "event_end_time"}:
                values.append(_iso(attribute))
            else:
                values.append(_cell(attribute))
        lines.append(",".join(values))
    return ("\n".join(lines) + "\n").encode("utf-8")


def build_intake_summary(
    manifest: IntakeManifest,
    artifact_report: ArtifactValidationReport,
    diagnostics: NormalizationDiagnostics,
    bar_set: NormalizedBarSet | None,
) -> IntakeSummary:
    reasons: set[IntakeReasonCode] = set(artifact_report.reason_codes)
    reasons.update(diagnostics.bundle_reason_codes)

    event_start_min = None
    event_end_max = None
    if bar_set is not None and bar_set.bars:
        event_start_min = min(bar.event_start_time for bar in bar_set.bars)
        event_end_max = max(bar.event_end_time for bar in bar_set.bars)

    return IntakeSummary(
        bundle_id=manifest.bundle_id,
        provider_name=manifest.provider_name,
        canonical_symbol=manifest.canonical_symbol,
        market_or_venue=manifest.market_or_venue,
        interval=manifest.bar_interval,
        artifact_validation_status=artifact_report.status,
        normalization_status=diagnostics.status,
        normalized_bar_count=0 if bar_set is None else len(bar_set.bars),
        quarantined_row_count=diagnostics.quarantined_count,
        rejected_row_count=diagnostics.rejected_count,
        event_start_min=event_start_min,
        event_end_max=event_end_max,
        retrieval_time=manifest.retrieval_time,
        export_time=manifest.export_time,
        price_adjustment_semantics=manifest.price_adjustment_semantics,
        volume_adjustment_semantics=manifest.volume_adjustment_semantics,
        session_coverage=manifest.session_coverage,
        value_authenticity=manifest.value_authenticity,
        reason_codes=tuple(reasons),
    )


__all__ = [
    "CSV_COLUMNS",
    "serialize_bars_jsonl",
    "serialize_bars_csv",
    "build_intake_summary",
]

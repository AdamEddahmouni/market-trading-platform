"""Read detection-context bars and normalize them through the canonical bar adapter.

Hard guards, checked before any file is opened:

* only a path whose filename ends ``-detection-context.csv`` may be opened for values;
* any forward artifact (``FROZEN_FORWARD_24H`` / ``-frozen-forward-24h.*``) raises;
* any path under a Phase 3B outcome root raises.

Every accepted open is appended to an access log, so ``forward_ohlcv_accessed`` and
``outcome_accessed`` in the frozen records are *observed* facts rather than assertions.

No CSV parsing, timestamp parsing, OHLC validation, or observation construction is
reimplemented here: rows are parsed with the Batch 03 delimited adapter and normalized
with ``squeeze_core.adapters.market_bars.normalize_market_bar_records``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from squeeze_core.adapters.base import AdapterContext
from squeeze_core.adapters.market_bars import (
    BarCompletionStatus,
    BarInterval,
    BarSession,
    BarTimestampMeaning,
    BarVolumeUnit,
    MarketBarRecord,
    normalize_market_bar_records,
)
from squeeze_core.contracts import (
    AssetClass,
    EntitlementState,
    IngestionMethod,
    Observation,
)

from ..local_bar_intake.csv_adapter import parse_delimited_rows
from ..local_bar_intake.models import ColumnMappingProfile
from ..local_bar_intake.semantics import TimestampSemantics
from .models import (
    DETECTION_CONTEXT_REQUEST,
    FORWARD_REQUEST,
    ReceiptModelingPolicy,
    TimestampInterpretation,
)

BAR_INTERVAL = BarInterval.ONE_MINUTE
BAR_INTERVAL_SECONDS = 60
ADAPTER_VERSION = "phase-3d-batch-08-phase3a-freeze.v1"
NORMALIZATION_VERSION = "market-bar-v1"
PROVIDER = "IBKR"
SOURCE_ENDPOINT = f"ibkr:reqHistoricalData:{DETECTION_CONTEXT_REQUEST}"

#: The exact Batch 05 raw-CSV column layout (see intake raw header).
DETECTION_CONTEXT_PROFILE = ColumnMappingProfile(
    profile_id="ibkr-batch-05-detection-context.v1",
    has_header=True,
    delimiter=",",
    encoding="utf-8",
    timestamp_column="timestamp_utc",
    open_column="open",
    high_column="high",
    low_column="low",
    close_column="close",
    volume_column="volume",
    trade_count_column="bar_count",
    vwap_column="wap",
    symbol_column="requested_symbol",
)

_DETECTION_SUFFIX = "-detection-context.csv"
_FORWARD_TOKENS = ("frozen-forward", FORWARD_REQUEST.lower())
_OUTCOME_TOKENS = ("outcome", "phase3b", "phase-3b", "forward-outcome")


class ForwardArtifactAccessError(RuntimeError):
    """Raised on any attempt to open a forward-window artifact for values."""


class OutcomeArtifactAccessError(RuntimeError):
    """Raised on any attempt to open a Phase 3B outcome artifact."""


class NonDetectionContextArtifactError(RuntimeError):
    """Raised when a path is not a permitted detection-context bar artifact."""


@dataclass
class EvidenceAccessLog:
    """Observed record of what this package actually opened."""

    opened_paths: list[str] = field(default_factory=list)
    refused_paths: list[str] = field(default_factory=list)

    @property
    def forward_ohlcv_accessed(self) -> bool:
        return any(
            any(token in name.lower() for token in _FORWARD_TOKENS)
            for name in self.opened_paths
        )

    @property
    def outcome_accessed(self) -> bool:
        return any(
            any(token in name.lower() for token in _OUTCOME_TOKENS)
            for name in self.opened_paths
        )


def guard_detection_context_path(path: Path, log: EvidenceAccessLog | None = None) -> Path:
    """Refuse anything that is not a permitted detection-context bar artifact."""
    name = path.name.lower()
    full = str(path).lower().replace("\\", "/")
    if any(token in full for token in _FORWARD_TOKENS):
        if log is not None:
            log.refused_paths.append(str(path))
        raise ForwardArtifactAccessError(
            f"refusing to open a forward-window artifact for values: {path.name}"
        )
    if any(token in full for token in _OUTCOME_TOKENS):
        if log is not None:
            log.refused_paths.append(str(path))
        raise OutcomeArtifactAccessError(
            f"refusing to open a Phase 3B outcome artifact: {path.name}"
        )
    if not name.endswith(_DETECTION_SUFFIX):
        if log is not None:
            log.refused_paths.append(str(path))
        raise NonDetectionContextArtifactError(
            f"not a permitted detection-context bar artifact: {path.name}"
        )
    return path


def read_detection_context_bytes(path: Path, log: EvidenceAccessLog) -> bytes:
    """Read the raw bytes of a permitted detection-context artifact."""
    guard_detection_context_path(path, log)
    content = path.read_bytes()
    log.opened_paths.append(str(path))
    return content


def sha256_and_length(content: bytes) -> tuple[str, int]:
    return hashlib.sha256(content).hexdigest(), len(content)


@dataclass(frozen=True)
class BarLabels:
    """Labels observed in the artifact, split by the boundary envelope."""

    included: tuple[datetime, ...]
    straddling_count: int
    post_boundary_count: int


def _parse_label(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))


def _interval() -> timedelta:
    return timedelta(seconds=BAR_INTERVAL_SECONDS)


def classify_labels(labels: tuple[datetime, ...], boundary: datetime) -> BarLabels:
    """Split labels into definitely-completed / straddling / post-boundary.

    "Definitely completed" means completed under *both* timestamp interpretations, i.e.
    ``label + interval <= boundary``. This is the Batch 07 bidirectional envelope and is
    interpretation-independent, so no START/END choice is made here.
    """
    interval = _interval()
    included: list[datetime] = []
    straddling = 0
    post = 0
    for label in labels:
        if label + interval <= boundary:
            included.append(label)
        elif label < boundary:
            straddling += 1
        else:
            post += 1
    return BarLabels(
        included=tuple(sorted(included)),
        straddling_count=straddling,
        post_boundary_count=post,
    )


def boundaries_for(
    label: datetime, interpretation: TimestampInterpretation
) -> tuple[datetime, datetime]:
    """Bar (start, end) under an explicit interpretation of the label."""
    interval = _interval()
    if interpretation is TimestampInterpretation.LABEL_IS_INTERVAL_START:
        return label, label + interval
    return label - interval, label


def _timestamp_semantics(interpretation: TimestampInterpretation) -> TimestampSemantics:
    return (
        TimestampSemantics.START
        if interpretation is TimestampInterpretation.LABEL_IS_INTERVAL_START
        else TimestampSemantics.END
    )


def _availability_instant(label: datetime) -> datetime:
    """Conservative latest-possible completion of a bar labelled ``label``."""
    return label + _interval()


def receipt_instant(
    policy: ReceiptModelingPolicy,
    included_labels: tuple[datetime, ...],
    retrieval_completed_at: datetime,
) -> datetime:
    """The single ``ingested_at`` for the adapter context, per the declared policy."""
    if policy is ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT:
        return retrieval_completed_at
    if not included_labels:
        return retrieval_completed_at
    return max(_availability_instant(label) for label in included_labels)


@dataclass(frozen=True)
class DetectionContextBars:
    """Canonical observations plus the frozen facts describing their selection."""

    symbol: str
    observations: tuple[Observation, ...]
    labels: BarLabels
    artifact_name: str
    artifact_sha256: str
    artifact_byte_length: int
    receipt_instant: datetime
    interpretation: TimestampInterpretation


def _record(
    symbol: str,
    label: datetime,
    row: dict[str, str],
    interpretation: TimestampInterpretation,
    index: int,
) -> MarketBarRecord:
    start, end = boundaries_for(label, interpretation)
    availability = _availability_instant(label)
    return MarketBarRecord(
        source_record_id=f"{symbol}::{DETECTION_CONTEXT_REQUEST}::row-{index}",
        provider_schema="MARKET_BAR_V1",
        record_type="MARKET_BAR",
        # Provenance label required by the record contract: these are real recorded
        # provider bars, held privately and never committed.
        fixture_origin="SANITIZED_RECORDED_SAMPLE",
        provider=PROVIDER,
        provider_record_id=f"{symbol}::{DETECTION_CONTEXT_REQUEST}::{int(label.timestamp())}",
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        interval=BAR_INTERVAL,
        bar_start=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        bar_end=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        provider_timestamp=label.strftime("%Y-%m-%dT%H:%M:%SZ"),
        timestamp_meaning=(
            BarTimestampMeaning.START
            if interpretation is TimestampInterpretation.LABEL_IS_INTERVAL_START
            else BarTimestampMeaning.END
        ),
        open=row["open"],
        high=row["high"],
        low=row["low"],
        close=row["close"],
        # Volume is deliberately omitted: Batch 07 blocked every volume-dependent
        # operation for unresolved unit / corporate-action / filter semantics. Omitted,
        # never zeroed.
        volume=None,
        trade_count=None,
        vwap=None,
        volume_unit=BarVolumeUnit.UNKNOWN,
        session=BarSession.UNKNOWN,
        timezone="UTC",
        status=BarCompletionStatus.COMPLETED,
        publication_timestamp=availability.strftime("%Y-%m-%dT%H:%M:%SZ"),
        revision_number=0,
    )


def load_detection_context_bars(
    path: Path,
    *,
    symbol: str,
    boundary: datetime,
    retrieval_completed_at: datetime,
    receipt_policy: ReceiptModelingPolicy,
    interpretation: TimestampInterpretation = TimestampInterpretation.LABEL_IS_INTERVAL_START,
    log: EvidenceAccessLog | None = None,
) -> DetectionContextBars:
    """Load, filter, and canonically normalize one symbol's detection-context bars."""
    access_log = log if log is not None else EvidenceAccessLog()
    content = read_detection_context_bytes(path, access_log)
    sha256, byte_length = sha256_and_length(content)

    parsed = parse_delimited_rows(content, DETECTION_CONTEXT_PROFILE)
    if parsed.reason is not None:
        raise ValueError(f"detection-context artifact could not be parsed: {parsed.reason}")

    rows_by_label: dict[datetime, dict[str, str]] = {}
    for row in parsed.rows:
        cells = row.cells
        if cells.get("request_name") != DETECTION_CONTEXT_REQUEST:
            raise ForwardArtifactAccessError(
                "detection-context artifact contains a non-detection-context request name"
            )
        rows_by_label[_parse_label(cells["timestamp_utc"])] = cells

    labels = classify_labels(tuple(rows_by_label), boundary)
    receipt = receipt_instant(receipt_policy, labels.included, retrieval_completed_at)

    records = tuple(
        _record(symbol, label, rows_by_label[label], interpretation, index)
        for index, label in enumerate(labels.included, start=1)
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
    normalized = normalize_market_bar_records(records, context)
    if normalized.rejection is not None:
        raise ValueError(
            f"canonical bar normalization rejected {symbol}: {normalized.rejection.code.value}"
        )
    return DetectionContextBars(
        symbol=symbol,
        observations=normalized.observations,
        labels=labels,
        artifact_name=path.name,
        artifact_sha256=sha256,
        artifact_byte_length=byte_length,
        receipt_instant=receipt,
        interpretation=interpretation,
    )


__all__ = [
    "ADAPTER_VERSION",
    "BAR_INTERVAL",
    "BAR_INTERVAL_SECONDS",
    "DETECTION_CONTEXT_PROFILE",
    "NORMALIZATION_VERSION",
    "PROVIDER",
    "SOURCE_ENDPOINT",
    "BarLabels",
    "DetectionContextBars",
    "EvidenceAccessLog",
    "ForwardArtifactAccessError",
    "NonDetectionContextArtifactError",
    "OutcomeArtifactAccessError",
    "boundaries_for",
    "classify_labels",
    "guard_detection_context_path",
    "load_detection_context_bars",
    "read_detection_context_bytes",
    "receipt_instant",
    "sha256_and_length",
]

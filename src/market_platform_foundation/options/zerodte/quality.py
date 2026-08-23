"""Quality taxonomy and fail-closed gates for intraday chain snapshots.

Every gate fails closed: an absent field produces a blocking flag — never a
silent pass, never a zero-fill (research plan §4.3 "missing flow → zero" is a
forbidden practice).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .contracts import (
    IntradayChainSnapshotRecord,
    expiration_session_close_ns,
)

DEFAULT_MAX_AVAILABLE_LAG_NS = 60 * 1_000_000_000  # 60s available-time lag budget
DEFAULT_MAX_ABSOLUTE_WIDTH = 0.50  # currency units, bid/ask width cap
DEFAULT_MAX_WIDTH_FRACTION_OF_MID = 0.10


class ZeroDTEQualityFlag(StrEnum):
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    MISSING_BID = "MISSING_BID"
    MISSING_ASK = "MISSING_ASK"
    QUOTE_WIDTH_EXCEEDED = "QUOTE_WIDTH_EXCEEDED"
    EXPIRY_PAST_SESSION_CLOSE = "EXPIRY_PAST_SESSION_CLOSE"
    EXPIRATION_BEFORE_EVENT_TIME = "EXPIRATION_BEFORE_EVENT_TIME"
    DUPLICATE_SNAPSHOT_KEY = "DUPLICATE_SNAPSHOT_KEY"
    NEGATIVE_DTE = "NEGATIVE_DTE"


@dataclass(frozen=True, slots=True)
class StalenessPolicy:
    """Available-time lag threshold above which a snapshot is stale."""

    max_available_lag_ns: int = DEFAULT_MAX_AVAILABLE_LAG_NS

    def __post_init__(self) -> None:
        if self.max_available_lag_ns < 0:
            raise ValueError("max_available_lag_ns must be non-negative")


@dataclass(frozen=True, slots=True)
class LiquidityPolicy:
    """Quote-presence and width gates. Absent fields always block."""

    require_bid: bool = True
    require_ask: bool = True
    max_absolute_width: float | None = DEFAULT_MAX_ABSOLUTE_WIDTH
    max_width_fraction_of_mid: float | None = DEFAULT_MAX_WIDTH_FRACTION_OF_MID

    def __post_init__(self) -> None:
        if self.max_absolute_width is not None and self.max_absolute_width <= 0:
            raise ValueError("max_absolute_width must be positive when set")
        if self.max_width_fraction_of_mid is not None and self.max_width_fraction_of_mid <= 0:
            raise ValueError("max_width_fraction_of_mid must be positive when set")


BLOCKING_FLAGS = frozenset(
    {
        ZeroDTEQualityFlag.STALE_SNAPSHOT.value,
        ZeroDTEQualityFlag.MISSING_BID.value,
        ZeroDTEQualityFlag.MISSING_ASK.value,
        ZeroDTEQualityFlag.QUOTE_WIDTH_EXCEEDED.value,
        ZeroDTEQualityFlag.EXPIRY_PAST_SESSION_CLOSE.value,
        ZeroDTEQualityFlag.EXPIRATION_BEFORE_EVENT_TIME.value,
        ZeroDTEQualityFlag.DUPLICATE_SNAPSHOT_KEY.value,
        ZeroDTEQualityFlag.NEGATIVE_DTE.value,
    }
)


def quality_blocks_snapshot(flags: tuple[str, ...] | list[str]) -> bool:
    return any(flag in BLOCKING_FLAGS for flag in flags)


def staleness_flags(
    record: IntradayChainSnapshotRecord,
    *,
    policy: StalenessPolicy | None = None,
) -> tuple[ZeroDTEQualityFlag, ...]:
    active_policy = policy or StalenessPolicy()
    lag = record.available_time_ns - record.event_time_ns
    if lag > active_policy.max_available_lag_ns:
        return (ZeroDTEQualityFlag.STALE_SNAPSHOT,)
    return ()


def liquidity_flags(
    record: IntradayChainSnapshotRecord,
    *,
    policy: LiquidityPolicy | None = None,
) -> tuple[ZeroDTEQualityFlag, ...]:
    """Bid/ask presence + width caps. Missing quote fields FAIL CLOSED.

    ``record`` carries the snapshot-level reference quote (best bid/ask on the
    reference strike or underlying proxy). Snapshot-level absence of either
    side blocks; per-strike sparsity is a post-admission analytics concern.
    """
    active_policy = policy or LiquidityPolicy()
    flags: list[ZeroDTEQualityFlag] = []
    has_bid = record.best_bid is not None
    has_ask = record.best_ask is not None
    if not has_bid:
        if active_policy.require_bid:
            flags.append(ZeroDTEQualityFlag.MISSING_BID)
        else:
            return tuple(flags)
    if not has_ask:
        if active_policy.require_ask:
            flags.append(ZeroDTEQualityFlag.MISSING_ASK)
        else:
            return tuple(flags)
    bid = float(record.best_bid)
    ask = float(record.best_ask)
    width = ask - bid
    mid = (ask + bid) / 2.0
    if active_policy.max_absolute_width is not None and width > active_policy.max_absolute_width:
        flags.append(ZeroDTEQualityFlag.QUOTE_WIDTH_EXCEEDED)
        return tuple(flags)
    if (
        active_policy.max_width_fraction_of_mid is not None
        and mid > 0
        and width / mid > active_policy.max_width_fraction_of_mid
    ):
        flags.append(ZeroDTEQualityFlag.QUOTE_WIDTH_EXCEEDED)
    return tuple(flags)


def expiration_boundary_flags(record: IntradayChainSnapshotRecord) -> tuple[ZeroDTEQualityFlag, ...]:
    """16:00 ET session-close expiry edge checks for the expiry's ET calendar date."""
    flags: list[ZeroDTEQualityFlag] = []
    if record.expiration_timestamp_ns < record.event_time_ns:
        flags.append(ZeroDTEQualityFlag.EXPIRATION_BEFORE_EVENT_TIME)
        flags.append(ZeroDTEQualityFlag.NEGATIVE_DTE)
        return tuple(flags)
    close_ns = expiration_session_close_ns(record.expiration_timestamp_ns)
    if record.event_time_ns > close_ns:
        flags.append(ZeroDTEQualityFlag.EXPIRY_PAST_SESSION_CLOSE)
    return tuple(flags)


DUPLICATE_SNAPSHOT_KEY_REASON = "DUPLICATE_SNAPSHOT_UNDERLYING_EVENT_TIME"


def detect_duplicate_snapshots(
    records: list[IntradayChainSnapshotRecord] | tuple[IntradayChainSnapshotRecord, ...],
) -> dict[tuple[str, int], list[int]]:
    """Indexes (into ``records``) of snapshots sharing (underlying, event_time_ns)."""
    seen: dict[tuple[str, int], list[int]] = {}
    for index, record in enumerate(records):
        seen.setdefault((record.underlying, record.event_time_ns), []).append(index)
    return {key: indexes for key, indexes in seen.items() if len(indexes) > 1}


def evaluate_snapshot_quality(
    record: IntradayChainSnapshotRecord,
    *,
    staleness_policy: StalenessPolicy | None = None,
    liquidity_policy: LiquidityPolicy | None = None,
    duplicate_keys: frozenset[tuple[str, int]] | None = None,
) -> dict[str, object]:
    """Full quality evaluation; ``admissible`` False whenever ANY gate fails."""
    flags: list[ZeroDTEQualityFlag] = []
    flags.extend(staleness_flags(record, policy=staleness_policy))
    flags.extend(liquidity_flags(record, policy=liquidity_policy))
    flags.extend(expiration_boundary_flags(record))
    if duplicate_keys is not None and (record.underlying, record.event_time_ns) in duplicate_keys:
        flags.append(ZeroDTEQualityFlag.DUPLICATE_SNAPSHOT_KEY)
    blocking_reasons = sorted({flag.value for flag in flags})
    return {
        "underlying": record.underlying,
        "event_time_ns": record.event_time_ns,
        "flags": [flag.value for flag in flags],
        "blocking": quality_blocks_snapshot([flag.value for flag in flags]),
        "blocking_reasons": blocking_reasons,
    }


__all__ = [
    "BLOCKING_FLAGS",
    "DEFAULT_MAX_ABSOLUTE_WIDTH",
    "DEFAULT_MAX_AVAILABLE_LAG_NS",
    "DEFAULT_MAX_WIDTH_FRACTION_OF_MID",
    "DUPLICATE_SNAPSHOT_KEY_REASON",
    "LiquidityPolicy",
    "StalenessPolicy",
    "ZeroDTEQualityFlag",
    "detect_duplicate_snapshots",
    "evaluate_snapshot_quality",
    "expiration_boundary_flags",
    "liquidity_flags",
    "quality_blocks_snapshot",
    "staleness_flags",
]

"""Persistent aggressive-flow metaorder detection — Order Flow OF11."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .aggressor import classify_bar_delta
from .contracts import (
    AggressorSide,
    ClassifiedTrade,
    MetaorderFlowState,
    MetaorderPrimitive,
    MboOrderSide,
    QueueSnapshot,
)
from .queue import compute_queue_imbalance_mbo

DETECTION_METHOD = "persistent_aggressive_flow_v1"
DETECTION_VERSION = "1"
DEFAULT_MIN_SIGNED_VOLUME = 500.0
DEFAULT_MIN_TRADE_COUNT = 3
DEFAULT_MIN_DURATION_SECONDS = 2.0


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classified_trades_from_bars(
    bars: list[dict[str, Any]],
    *,
    instrument: str = "",
    venue: str = "US_EQUITY",
) -> list[ClassifiedTrade]:
    """Convert fixture bar dicts to ClassifiedTrade sequence."""
    trades: list[ClassifiedTrade] = []
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            continue
        bar_time = str(bar.get("date", ""))
        if not bar_time:
            continue
        delta = float(bar.get("delta", 0.0))
        volume = float(bar.get("volume", abs(delta)))
        quality = str(bar.get("quality", "bvc"))
        source = str(bar.get("source", ""))
        classified = classify_bar_delta(
            bar_time=bar_time,
            delta=delta,
            volume=volume,
            quality=quality,
            source=source,
            venue=venue,
        )
        trades.append(
            ClassifiedTrade(
                trade_id=f"{bar_time}:{index}",
                price=float(bar.get("close", 0.0)),
                quantity=classified.quantity,
                aggressor_side=classified.aggressor_side,
                signed_volume=classified.signed_volume,
                aggressor_source=classified.aggressor_source,
                classification_method=classified.classification_method,
                classification_confidence=classified.classification_confidence,
                trade_timestamp=bar_time,
                quote_timestamp=bar_time,
                provider=source,
                venue=venue or instrument,
            )
        )
    return trades


def _flow_state_for_cluster(
  trades: list[ClassifiedTrade],
) -> MetaorderFlowState:
    if not trades:
        return MetaorderFlowState.FLOW_STALLED
    last = trades[-1]
    if last.signed_volume == 0 or last.aggressor_side == AggressorSide.UNKNOWN:
        return MetaorderFlowState.FLOW_STALLED
    if len(trades) >= 2:
        prev = trades[-2]
        if abs(last.signed_volume) < abs(prev.signed_volume) * 0.5:
            return MetaorderFlowState.FLOW_WEAKENING
    return MetaorderFlowState.FLOW_ACTIVE


def _mbo_corroborates_buy(snapshot: QueueSnapshot | None) -> bool:
    if snapshot is None:
        return False
    imbalance = compute_queue_imbalance_mbo(snapshot)
    return imbalance < -0.1


def _mbo_corroborates_sell(snapshot: QueueSnapshot | None) -> bool:
    if snapshot is None:
        return False
    imbalance = compute_queue_imbalance_mbo(snapshot)
    return imbalance > 0.1


def detect_metaorder_primitives(
    trades: list[ClassifiedTrade],
    *,
    instrument: str,
    venue: str = "",
    min_signed_volume: float = DEFAULT_MIN_SIGNED_VOLUME,
    min_trade_count: int = DEFAULT_MIN_TRADE_COUNT,
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS,
    mbo_snapshots: list[QueueSnapshot] | None = None,
) -> list[MetaorderPrimitive]:
    """Detect probable parent-order execution from persistent same-side aggressive flow."""
    if not trades:
        return []

    mbo_by_time: dict[str, QueueSnapshot] = {}
    if mbo_snapshots:
        for snapshot in mbo_snapshots:
            mbo_by_time[snapshot.event_time] = snapshot

    primitives: list[MetaorderPrimitive] = []
    cluster: list[ClassifiedTrade] = []
    cluster_side: AggressorSide | None = None

    def flush_cluster() -> None:
        nonlocal cluster, cluster_side
        if not cluster or cluster_side is None:
            cluster = []
            cluster_side = None
            return
        signed_volume = sum(trade.signed_volume for trade in cluster)
        if cluster_side == AggressorSide.SELL:
            signed_volume = abs(signed_volume) * -1
        else:
            signed_volume = abs(signed_volume)
        if len(cluster) < min_trade_count or abs(signed_volume) < min_signed_volume:
            cluster = []
            cluster_side = None
            return
        start_time = cluster[0].trade_timestamp
        end_time = cluster[-1].trade_timestamp
        duration = (_parse_timestamp(end_time) - _parse_timestamp(start_time)).total_seconds()
        if duration < min_duration_seconds and len(cluster) < min_trade_count + 1:
            cluster = []
            cluster_side = None
            return
        flow_state = _flow_state_for_cluster(cluster)
        mbo_snapshot = mbo_by_time.get(end_time)
        mbo_corroborated = (
            _mbo_corroborates_buy(mbo_snapshot)
            if cluster_side == AggressorSide.BUY
            else _mbo_corroborates_sell(mbo_snapshot)
        )
        primitive_id = f"{instrument}:{start_time}:{end_time}:{cluster_side.value}"
        primitives.append(
            MetaorderPrimitive(
                primitive_id=primitive_id,
                instrument=instrument,
                venue=venue or instrument,
                aggressor_side=cluster_side,
                signed_volume=signed_volume,
                trade_count=len(cluster),
                start_time=start_time,
                end_time=end_time,
                available_time=end_time,
                flow_state=flow_state,
                detection_method=DETECTION_METHOD,
                detection_version=DETECTION_VERSION,
                mbo_corroborated=mbo_corroborated,
                quality_flags=() if cluster_side != AggressorSide.UNKNOWN else ("AGGRESSOR_UNKNOWN",),
            )
        )
        cluster = []
        cluster_side = None

    for trade in trades:
        if trade.aggressor_side in {AggressorSide.UNKNOWN} or trade.signed_volume == 0:
            flush_cluster()
            continue
        if cluster_side is None:
            cluster_side = trade.aggressor_side
            cluster = [trade]
            continue
        if trade.aggressor_side == cluster_side:
            cluster.append(trade)
            continue
        flush_cluster()
        cluster_side = trade.aggressor_side
        cluster = [trade]

    flush_cluster()
    return primitives


__all__ = [
    "DEFAULT_MIN_DURATION_SECONDS",
    "DEFAULT_MIN_SIGNED_VOLUME",
    "DEFAULT_MIN_TRADE_COUNT",
    "DETECTION_METHOD",
    "DETECTION_VERSION",
    "classified_trades_from_bars",
    "detect_metaorder_primitives",
]

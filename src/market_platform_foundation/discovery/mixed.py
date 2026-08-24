"""Pure mixed-queue aggregation and inspectable attention ranking."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


LANES_BY_SCREEN: dict[str, tuple[str, ...]] = {
    "SHORT_SQUEEZE_DISCOVERY": ("SQUEEZE",),
    "UNUSUAL_VOLUME_DISCOVERY": ("MOMENTUM",),
    "MOMENTUM_IGNITION_DISCOVERY": ("MOMENTUM",),
    "GAP_CATALYST_DISCOVERY": ("MOMENTUM", "CATALYST"),
    "EARNINGS_MOVER_DISCOVERY": ("CATALYST", "SWING"),
    "ANALYST_EVENT_DISCOVERY": ("CATALYST", "SWING"),
    "INSIDER_ACTIVITY_DISCOVERY": ("CATALYST", "SWING"),
    "TECHNICAL_BREAKOUT_DISCOVERY": ("MOMENTUM", "SWING"),
}

_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _candidate_set_dict(candidate_set: Any) -> dict[str, Any]:
    if isinstance(candidate_set, dict):
        return candidate_set
    converter = getattr(candidate_set, "to_dict", None)
    if callable(converter):
        payload = converter()
        if isinstance(payload, dict):
            return payload
    raise TypeError("candidate_set must be a dictionary or expose to_dict()")


@dataclass(slots=True)
class MixedCandidate:
    instrument_id: str
    lanes: list[str]
    screen_matches: list[str]
    matched_reasons: list[str]
    metrics: dict[str, Any]
    discovery_as_of: str
    available_time_ns: int
    quality: str
    provenance: list[dict[str, Any]]
    attention_score: float = 0.0
    attention_components: dict[str, float] = field(default_factory=dict)
    ranking_reasons: list[str] = field(default_factory=list)
    market: dict[str, Any] | None = None
    queue_rank: int | None = None
    candidate_role: str = "INVESTIGATE"

    def to_dict(self) -> dict[str, Any]:
        market = dict(self.market) if self.market is not None else _snapshot_market_record(self)
        status = str(market.get("status") or "UNAVAILABLE")
        freshness = market.get("freshness_ms")
        if freshness is None:
            freshness_label = status
        elif freshness < 1_000:
            freshness_label = f"{freshness} ms"
        else:
            freshness_label = f"{freshness / 1_000:.1f} s"
        return {
            "instrument_id": self.instrument_id,
            "candidate_role": "INVESTIGATE",
            "lanes": list(self.lanes),
            "screen_matches": list(self.screen_matches),
            "matched_reasons": list(self.matched_reasons),
            "metrics": dict(self.metrics),
            "discovery_as_of": self.discovery_as_of,
            "available_time_ns": self.available_time_ns,
            "quality": self.quality,
            "provenance": [dict(item) for item in self.provenance],
            "attention_score": self.attention_score,
            "attention_components": dict(self.attention_components),
            "ranking_reasons": list(self.ranking_reasons),
            "market": market,
            "data_status": status,
            "freshness_label": freshness_label,
            "queue_rank": self.queue_rank,
        }


def _snapshot_market_record(candidate: MixedCandidate) -> dict[str, Any]:
    price = _finite_number(candidate.metrics.get("price"))
    volume = _finite_number(candidate.metrics.get("volume"))
    return {
        "provider": "FINVIZ_ELITE",
        "status": "SNAPSHOT",
        "as_of_ns": candidate.available_time_ns,
        "freshness_ms": None,
        "last_price": price,
        "bid_price": None,
        "ask_price": None,
        "spread_pct": None,
        "volume": volume,
        "quality": candidate.quality,
        "reason": "FINVIZ_DISCOVERY_SNAPSHOT",
    }


def _eligible(symbol: str, reasons: Sequence[Any], metrics: Mapping[str, Any], quality: str) -> bool:
    if not _SYMBOL_RE.fullmatch(symbol) or not any(str(reason).strip() for reason in reasons):
        return False
    if quality == "UNAVAILABLE":
        return False
    if "price" in metrics and metrics.get("price") is not None:
        price = _finite_number(metrics.get("price"))
        if price is None or price <= 0:
            return False
    return True


def _component_scores(candidate: MixedCandidate, *, now_ns: int) -> tuple[dict[str, float], list[str]]:
    metrics = candidate.metrics
    market = candidate.market or {}
    reasons: list[str] = []

    rel_volume = _finite_number(metrics.get("rel_volume"))
    change_pct = _finite_number(metrics.get("change_pct"))
    short_float = _finite_number(metrics.get("short_float_pct"))
    volume = _finite_number(market.get("volume"))
    if volume is None:
        volume = _finite_number(metrics.get("volume"))

    setup = 0.0
    if rel_volume is not None and rel_volume > 0:
        setup += min(15.0, rel_volume * 3.0)
        reasons.append(f"RVOL_{rel_volume:.2f}")
    if change_pct is not None:
        setup += min(12.0, abs(change_pct) * 1.2)
        reasons.append(f"ABS_CHANGE_{abs(change_pct):.1f}_PCT")
    if short_float is not None and short_float > 0:
        setup += min(10.0, short_float / 5.0)
        reasons.append(f"SHORT_FLOAT_{short_float:.1f}_PCT")
    setup += min(8.0, len(candidate.screen_matches) * 2.0)
    setup = min(45.0, setup)

    discovery_age_s = max(0.0, (now_ns - candidate.available_time_ns) / 1_000_000_000)
    freshness = max(0.0, 20.0 - min(20.0, discovery_age_s / 30.0))
    market_freshness = _finite_number(market.get("freshness_ms"))
    if market.get("status") == "LIVE" and market_freshness is not None:
        freshness = max(freshness, max(0.0, 20.0 - market_freshness / 250.0))
    freshness = min(20.0, freshness)

    liquidity = 0.0
    if volume is not None and volume > 0:
        liquidity += min(15.0, max(0.0, math.log10(volume) - 2.0) * 3.0)
    spread = _finite_number(market.get("spread_pct"))
    if spread is not None and spread >= 0:
        liquidity += max(0.0, 5.0 - min(5.0, spread * 10.0))
    liquidity = min(20.0, liquidity)

    live_confirmation = 0.0
    if market.get("status") == "LIVE" and market.get("quality") == "PASS":
        live_confirmation = 10.0
        if _finite_number(market.get("last_price")) is not None:
            live_confirmation += 5.0
        reasons.append("FRESH_L1_QUOTE")
    live_confirmation = min(15.0, live_confirmation)

    penalty = 0.0
    status = str(market.get("status") or "")
    market_reason = str(market.get("reason") or "")
    if candidate.quality != "PASS":
        penalty -= 3.0
        reasons.append("DEGRADED_DISCOVERY_QUALITY")
    if status == "STALE":
        penalty -= 8.0
        reasons.append("STALE_MARKET_DATA")
    elif status == "DELAYED":
        penalty -= 4.0
        reasons.append("DELAYED_MARKET_DATA")
    elif status == "UNAVAILABLE":
        penalty -= 2.0
        reasons.append("LIVE_PROVIDER_UNAVAILABLE")
    if market_reason == "CROSSED_MARKET":
        penalty -= 5.0
        reasons.append("CROSSED_MARKET")
    if market.get("quality") == "DEGRADED" and status not in {"STALE", "DELAYED"}:
        penalty -= 2.0
        reasons.append("DEGRADED_MARKET_QUALITY")

    return (
        {
            "setup_strength": round(setup, 2),
            "freshness": round(freshness, 2),
            "liquidity_marketability": round(liquidity, 2),
            "live_confirmation": round(live_confirmation, 2),
            "quality_penalty": round(penalty, 2),
        },
        reasons,
    )


def rerank_candidates(candidates: Iterable[MixedCandidate], *, now_ns: int) -> list[MixedCandidate]:
    ranked = list(candidates)
    for candidate in ranked:
        components, reasons = _component_scores(candidate, now_ns=now_ns)
        candidate.attention_components = components
        candidate.attention_score = round(max(0.0, sum(components.values())), 2)
        candidate.ranking_reasons = reasons
    ranked.sort(
        key=lambda item: (
            -item.attention_score,
            -item.available_time_ns,
            -len(item.screen_matches),
            item.instrument_id,
        )
    )
    for index, candidate in enumerate(ranked, start=1):
        candidate.queue_rank = index
    return ranked


def aggregate_candidate_sets(
    candidate_sets: Iterable[Any],
    *,
    now_ns: int,
    market_by_symbol: Mapping[str, dict[str, Any]] | None = None,
) -> list[MixedCandidate]:
    """Merge versioned screen results by canonical symbol and rank for inspection."""

    merged: dict[str, MixedCandidate] = {}
    metric_times: dict[str, dict[str, int]] = {}
    for item in candidate_sets:
        payload = _candidate_set_dict(item)
        screen_id = str(payload.get("screen_id") or "").upper()
        lanes = LANES_BY_SCREEN.get(screen_id)
        if lanes is None:
            continue
        set_available_ns = int(payload.get("available_time_ns") or 0)
        set_received_at = str(payload.get("received_at") or "")
        set_quality = str(payload.get("quality") or "DEGRADED").upper()
        for raw_candidate in payload.get("candidates") or []:
            if not isinstance(raw_candidate, dict):
                continue
            symbol = str(raw_candidate.get("instrument_id") or "").strip().upper()
            reasons = list(raw_candidate.get("matched_reasons") or [])
            metrics = dict(raw_candidate.get("metrics") or {})
            quality = str(raw_candidate.get("quality") or set_quality).upper()
            if not _eligible(symbol, reasons, metrics, quality):
                continue
            available_ns = int(raw_candidate.get("available_time_ns") or set_available_ns)
            discovered_at = str(raw_candidate.get("discovered_at") or set_received_at)
            capture_provenance = {
                "provider": str(payload.get("provider") or "FINVIZ_ELITE"),
                "screen_id": screen_id,
                "screen_version": str(payload.get("screen_version") or raw_candidate.get("screen_version") or ""),
                "run_id": str(payload.get("run_id") or ""),
                "received_at": set_received_at,
                "available_time_ns": available_ns,
                "candidate": dict(raw_candidate.get("provenance") or {}),
            }
            existing = merged.get(symbol)
            if existing is None:
                existing = MixedCandidate(
                    instrument_id=symbol,
                    lanes=sorted(set(lanes)),
                    screen_matches=[screen_id],
                    matched_reasons=sorted({str(reason).strip() for reason in reasons if str(reason).strip()}),
                    metrics=dict(metrics),
                    discovery_as_of=discovered_at,
                    available_time_ns=available_ns,
                    quality=quality,
                    provenance=[capture_provenance],
                )
                merged[symbol] = existing
                metric_times[symbol] = {key: available_ns for key in metrics}
            else:
                existing.lanes = sorted(set(existing.lanes).union(lanes))
                existing.screen_matches = sorted(set(existing.screen_matches).union({screen_id}))
                existing.matched_reasons = sorted(
                    set(existing.matched_reasons).union(str(reason).strip() for reason in reasons if str(reason).strip())
                )
                existing.provenance.append(capture_provenance)
                if quality != "PASS":
                    existing.quality = "DEGRADED"
                if available_ns > existing.available_time_ns:
                    existing.available_time_ns = available_ns
                    existing.discovery_as_of = discovered_at
                for key, value in metrics.items():
                    if available_ns >= metric_times[symbol].get(key, -1):
                        existing.metrics[key] = value
                        metric_times[symbol][key] = available_ns

    market = market_by_symbol or {}
    for symbol, candidate in merged.items():
        candidate.market = dict(market[symbol]) if symbol in market else None
    return rerank_candidates(merged.values(), now_ns=now_ns)

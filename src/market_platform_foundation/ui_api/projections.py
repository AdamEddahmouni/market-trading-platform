"""DTO projection builders for UI-001 read-only API."""

from __future__ import annotations

from typing import Any

from ..features.institutional import FUND_ETF_FAMILY, FUTURES_DEPTH_FAMILY, FUTURES_FAMILY, LARGE_TRANSACTIONS_FAMILY, OPTIONS_FAMILY, ORDER_BOOK_FAMILY, ORDER_FLOW_FAMILY, PUBLIC_CATALYST_FAMILY, REGULATORY_DISCLOSURE_FAMILY, WHALE_FAMILIES
from ..providers.projections import catalyst_available, disclosure_available, fund_etf_available, futures_available, large_transactions_available, options_available, order_book_available, order_flow_available
from .store import ReplayStore

CAPABILITY_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("bars.intraday_1m", "BAR_OHLCV_1M equity intraday"),
    ("depth.L2", "Level 2 order book"),
    ("options.chain", "Options chain"),
    ("whale.disclosure", "Regulatory disclosure feed"),
    ("live.quotes", "Live market quotes"),
    ("paper.execution", "Paper trading execution"),
)


def build_as_of_context(store: ReplayStore) -> dict[str, object]:
    return {
        "as_of_time": store.as_of_time(),
        "mode": store.mode,
        "replay_session_id": store.session_id,
        "timezone": store.timezone,
    }


def build_quality_summary(store: ReplayStore) -> dict[str, object]:
    bar = store.current_bar()
    quality = bar.get("quality_state", "GOOD")
    state = str(quality) if quality else "GOOD"
    if state not in {"GOOD", "PARTIAL", "DEGRADED", "STALE", "UNAVAILABLE"}:
        state = "GOOD"
    return {
        "affected_symbols": [store.instrument_id],
        "detail": "Admitted equity intraday fixture; bar-only capability",
        "state": state,
    }


def build_capabilities(store: ReplayStore) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    disclosure_ready = disclosure_available(
        instrument_id=store.instrument_id,
        prediction_cutoff=store.prediction_cutoff(),
    )
    order_flow_ready = order_flow_available(
        instrument_id="NVDA",
        prediction_cutoff=store.prediction_cutoff(),
    )
    options_ready = options_available(
        instrument_id=store.instrument_id,
        prediction_cutoff=store.prediction_cutoff(),
    )
    large_transactions_ready = large_transactions_available(
        instrument_id="NVDA",
        prediction_cutoff=store.prediction_cutoff(),
    )
    order_book_ready = order_book_available(
        instrument_id="NVDA",
        prediction_cutoff=store.prediction_cutoff(),
    )
    futures_ready = futures_available(
        instrument_id="ES",
        prediction_cutoff=store.prediction_cutoff(),
    )
    catalyst_ready = catalyst_available(
        instrument_id="BOXL",
        prediction_cutoff=store.prediction_cutoff(),
    )
    fund_etf_ready = fund_etf_available(
        instrument_id="NVDA",
        prediction_cutoff=store.prediction_cutoff(),
    )
    for capability_id, label in CAPABILITY_DEFINITIONS:
        if capability_id == "bars.intraday_1m":
            rows.append(
                {
                    "capability_id": capability_id,
                    "explanation_ref": f"cap:{capability_id}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if capability_id == "depth.L2":
            if order_book_ready:
                rows.append(
                    {
                        "capability_id": capability_id,
                        "explanation_ref": f"cap:{capability_id}",
                        "state": "AVAILABLE",
                    }
                )
            else:
                rows.append(
                    {
                        "capability_id": capability_id,
                        "explanation_ref": f"cap:{capability_id}",
                        "reason": "No entitled L2 source on admitted fixture",
                        "state": "UNSUPPORTED",
                    }
                )
            continue
        if capability_id == "whale.disclosure":
            if disclosure_ready:
                rows.append(
                    {
                        "capability_id": capability_id,
                        "explanation_ref": f"cap:{capability_id}",
                        "state": "AVAILABLE",
                    }
                )
            else:
                rows.append(
                    {
                        "capability_id": capability_id,
                        "explanation_ref": f"cap:{capability_id}",
                        "reason": "No entitled institutional source on admitted fixture",
                        "state": "UNSUPPORTED",
                    }
                )
            continue
        if capability_id.startswith("whale."):
            rows.append(
                {
                    "capability_id": capability_id,
                    "explanation_ref": f"cap:{capability_id}",
                    "reason": "No entitled institutional source on admitted fixture",
                    "state": "UNSUPPORTED",
                }
            )
            continue
        rows.append(
            {
                "capability_id": capability_id,
                "explanation_ref": f"cap:{capability_id}",
                "reason": f"{label} not authorized in UI-001 V1",
                "state": "UNSUPPORTED",
            }
        )
    for family in WHALE_FAMILIES:
        if family == REGULATORY_DISCLOSURE_FAMILY and disclosure_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family == ORDER_FLOW_FAMILY and order_flow_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family == OPTIONS_FAMILY and options_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family == LARGE_TRANSACTIONS_FAMILY and large_transactions_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family == ORDER_BOOK_FAMILY and order_book_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family in (FUTURES_FAMILY, FUTURES_DEPTH_FAMILY) and futures_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family == PUBLIC_CATALYST_FAMILY and catalyst_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        if family == FUND_ETF_FAMILY and fund_etf_ready:
            rows.append(
                {
                    "capability_id": f"whale.{family}",
                    "explanation_ref": f"cap:whale.{family}",
                    "state": "AVAILABLE",
                }
            )
            continue
        rows.append(
            {
                "capability_id": f"whale.{family}",
                "explanation_ref": f"cap:whale.{family}",
                "reason": "WHALE_NO_ENTITLED_SOURCE",
                "state": "UNSUPPORTED",
            }
        )
    return sorted(rows, key=lambda row: str(row["capability_id"]))


def build_context_payload(store: ReplayStore) -> dict[str, object]:
    return {
        "as_of_context": build_as_of_context(store),
        "capability_states": build_capabilities(store),
        "quality_summary": build_quality_summary(store),
        "scope_symbols": [store.instrument_id],
    }


def _strategy_signal_items(store: ReplayStore) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    cutoff = store.prediction_cutoff()
    interpretations = store.strategy.get("interpretions", [])
    rank = 1
    for row in interpretations:
        if not isinstance(row, dict):
            continue
        obs_time = int(row.get("observation_time", 0))
        if obs_time > cutoff:
            continue
        outcome = str(row.get("outcome", "abstain"))
        if outcome != "signal":
            continue
        ref = f"explain:strategy:{obs_time}"
        items.append(
            {
                "attention_id": f"att-strategy-{obs_time}",
                "explanation_ref": ref,
                "headline": f"Strategy signal at {store.as_of_time()}",
                "instrument_id": store.instrument_id,
                "priority_rank": rank,
                "reasons": [
                    {
                        "code": "STRATEGY_SIGNAL",
                        "label": str(row.get("alignment", "forecast alignment")),
                    },
                    {
                        "code": "PREREGISTERED",
                        "label": "Preregistered strategy evaluation",
                    },
                ],
                "tier": 2,
            }
        )
        rank += 1
    return items


def _quality_attention_item(store: ReplayStore) -> dict[str, object] | None:
    quality = build_quality_summary(store)
    if quality["state"] == "GOOD":
        return None
    return {
        "attention_id": "att-quality-system",
        "explanation_ref": "explain:quality:system",
        "headline": f"Data quality {quality['state']} for {store.instrument_id}",
        "instrument_id": store.instrument_id,
        "priority_rank": 0,
        "reasons": [
            {"code": "QUALITY_DEGRADED", "label": str(quality.get("detail", "Quality notice"))},
        ],
        "tier": 1,
    }


def _squeeze_attention_items() -> list[dict[str, object]]:
    from ..donor_bridge.projections import (
        build_squeeze_attention_items,
        build_squeeze_scanner_attention_items,
    )

    return build_squeeze_attention_items() + build_squeeze_scanner_attention_items()


def _catalyst_attention_items() -> list[dict[str, object]]:
    from ..donor_bridge.projections import build_catalyst_attention_items

    return build_catalyst_attention_items()


def _futures_attention_items(store: ReplayStore) -> list[dict[str, object]]:
    from ..providers.projections import build_workspace_futures_payload

    futures = build_workspace_futures_payload(
        "ES",
        as_of_context=build_as_of_context(store),
        prediction_cutoff=store.prediction_cutoff(),
    )
    if not futures.get("available"):
        return []
    signal = str(futures.get("latest_imbalance_signal", "neutral"))
    if signal not in {"supports_long", "supports_short"}:
        return []
    ratio = futures.get("latest_imbalance_ratio")
    ratio_label = f" (ratio {ratio})" if ratio is not None else ""
    return [
        {
            "attention_id": "att-futures-es-imbalance",
            "explanation_ref": "explain:futures:ES",
            "headline": f"ES depth imbalance {signal}{ratio_label}",
            "instrument_id": "ES",
            "priority_rank": 2,
            "reasons": [
                {
                    "code": "FUTURES_DEPTH_IMBALANCE",
                    "label": f"Depth-derived signal from {futures.get('provenance', 'fixture')}",
                },
            ],
            "tier": 2,
        }
    ]


def _tier1_attention_items(store: ReplayStore) -> list[dict[str, object]]:
    tier1: list[dict[str, object]] = []
    quality_item = _quality_attention_item(store)
    if quality_item:
        tier1.append(quality_item)
    tier1.append(
        {
            "attention_id": "att-replay-context",
            "explanation_ref": "explain:replay:context",
            "headline": f"Replay cursor at bar {store.cursor_index + 1}/{len(store.bars)}",
            "instrument_id": store.instrument_id,
            "priority_rank": 0,
            "reasons": [
                {"code": "REPLAY_ACTIVE", "label": "Global REPLAY mode"},
                {"code": "BAR_OHLCV", "label": "Admitted equity intraday bars"},
            ],
            "tier": 1,
        }
    )
    return tier1


def _all_attention_items(store: ReplayStore) -> list[dict[str, object]]:
    return (
        _tier1_attention_items(store)
        + _squeeze_attention_items()
        + _catalyst_attention_items()
        + _futures_attention_items(store)
        + _strategy_signal_items(store)
    )


def _count_series(rows: list[dict[str, object]], label_key: str) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(label_key, "UNKNOWN"))
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def build_attention_page(
    store: ReplayStore,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, object]:
    page_size = limit or store.page_size
    tier1 = _tier1_attention_items(store)
    combined = _all_attention_items(store)
    start = 0
    if cursor:
        for idx, item in enumerate(combined):
            if item["attention_id"] == cursor:
                start = idx + 1
                break
    page = combined[start : start + page_size]
    next_cursor = page[-1]["attention_id"] if len(page) == page_size and start + page_size < len(combined) else None
    tier_rows = [{"tier": str(item.get("tier", 2))} for item in combined]
    return {
        "as_of_context": build_as_of_context(store),
        "capability_states": build_capabilities(store),
        "items": page,
        "next_cursor": next_cursor,
        "pinned_tier1_count": len(tier1),
        "tier_summary": _count_series(tier_rows, "tier"),
    }


def build_instrument_overview(store: ReplayStore, instrument_id: str) -> dict[str, object]:
    if instrument_id != store.instrument_id:
        raise ValueError("UI_INSTRUMENT_NOT_FOUND")
    bars_payload = []
    for bar in store.bars_visible():
        payload = bar.get("bar_payload", {})
        if not isinstance(payload, dict):
            continue
        bars_payload.append(
            {
                "available_time": int(bar["available_time"]),
                "close": str(payload.get("close", "0")),
                "epistemic_class": "OBSERVED",
                "high": str(payload.get("high", "0")),
                "low": str(payload.get("low", "0")),
                "open": str(payload.get("open", "0")),
                "quality_state": str(bar.get("quality_state", "GOOD")),
                "time": _bar_time_iso(int(bar["available_time"])),
                "volume": int(payload.get("volume", 0)),
            }
        )
    features = store.bar_features_at_cutoff()
    return {
        "as_of_context": build_as_of_context(store),
        "bars": bars_payload,
        "capability_states": build_capabilities(store),
        "epistemic_class": "OBSERVED",
        "features": [
            {
                "epistemic_class": "DERIVED",
                "feature_id": row["feature_id"],
                "value": row["value"],
            }
            for row in features
        ],
        "instrument_id": instrument_id,
        "quality_summary": build_quality_summary(store),
    }


def _bar_time_iso(epoch_ns: int) -> str:
    seconds = epoch_ns // 1_000_000_000
    nanos = epoch_ns % 1_000_000_000
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def build_explain_payload(store: ReplayStore, ref: str) -> dict[str, object]:
    if ref == "explain:replay:context":
        body = {
            "alignment_summary": "Replay-only research UI on admitted fixture",
            "level": 2,
            "meaning": "Workspace is in REPLAY mode synchronized to a bar cursor",
            "ref": ref,
            "why": "UI-001 exposes deterministic replay over Phase 8 pipeline outputs",
        }
    elif ref == "explain:quality:system":
        quality = build_quality_summary(store)
        body = {
            "alignment_summary": f"Quality state {quality['state']}",
            "level": 2,
            "meaning": "Aggregate data quality for active scope",
            "ref": ref,
            "why": str(quality.get("detail", "")),
        }
    elif ref.startswith("explain:strategy:"):
        obs_time = int(ref.rsplit(":", 1)[-1])
        body = {
            "alignment_summary": "Preregistered strategy produced a signal",
            "level": 2,
            "meaning": f"Strategy evaluation at observation time {obs_time}",
            "ref": ref,
            "why": "Forecast momentum alignment passed preregistration gates",
        }
    elif ref.startswith("cap:"):
        cap_id = ref.removeprefix("cap:")
        caps = {row["capability_id"]: row for row in build_capabilities(store)}
        cap = caps.get(cap_id, {"state": "UNSUPPORTED", "reason": "Unknown capability"})
        body = {
            "alignment_summary": str(cap.get("state", "UNSUPPORTED")),
            "level": 1,
            "meaning": f"Capability {cap_id}",
            "ref": ref,
            "why": str(cap.get("reason", "Available on admitted fixture")),
        }
    elif ref.startswith("explain:squeeze:scanner:"):
        symbol = ref.removeprefix("explain:squeeze:scanner:")
        from ..donor_bridge.projections import build_workspace_squeeze_payload

        squeeze = build_workspace_squeeze_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
            data_mode="current",
        )
        if not squeeze.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": str(squeeze.get("ignition_state", "UNKNOWN")),
            "level": 2,
            "meaning": f"Current scanner squeeze state for {symbol.upper()}",
            "ref": ref,
            "why": (
                f"{squeeze.get('outcome_status', 'UNKNOWN')} · "
                f"{squeeze.get('evidence_coverage', 'coverage unknown')} · "
                f"{squeeze.get('disclaimer', '')}"
            ),
        }
    elif ref.startswith("explain:squeeze:"):
        symbol = ref.removeprefix("explain:squeeze:")
        from ..donor_bridge.projections import build_workspace_squeeze_payload

        squeeze = build_workspace_squeeze_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
            data_mode="frozen",
        )
        if not squeeze.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": str(squeeze.get("ignition_state", "UNKNOWN")),
            "level": 2,
            "meaning": f"Squeeze research state for {symbol.upper()}",
            "ref": ref,
            "why": (
                f"{squeeze.get('outcome_status', 'UNKNOWN')} · "
                f"{squeeze.get('evidence_coverage', 'coverage unknown')} · "
                f"{squeeze.get('disclaimer', '')}"
            ),
        }
    elif ref.startswith("explain:catalyst:"):
        symbol = ref.removeprefix("explain:catalyst:")
        from ..providers.projections import build_workspace_catalyst_payload as build_fixture_catalyst

        catalyst = build_fixture_catalyst(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not catalyst.get("available"):
            from ..donor_bridge.projections import build_workspace_catalyst_payload as build_bridge_catalyst

            catalyst = build_bridge_catalyst(symbol, as_of_context=build_as_of_context(store))
        if not catalyst.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        if catalyst.get("catalysts"):
            latest = catalyst["catalysts"][-1]
            alignment = str(latest.get("lean", "UNKNOWN"))
            why_headline = str(latest.get("headline", ""))
        else:
            trade = catalyst.get("trade_signal") or {}
            alignment = str(trade.get("decision", "UNKNOWN"))
            why_headline = str(trade.get("news_headline") or trade.get("reasoning", ""))
        body = {
            "alignment_summary": alignment,
            "level": 2,
            "meaning": f"Public catalyst evidence for {symbol.upper()}",
            "ref": ref,
            "why": f"{why_headline} · {catalyst.get('disclaimer', '')}",
        }
    elif ref.startswith("explain:attention:"):
        remainder = ref.removeprefix("explain:attention:")
        parts = remainder.split(":", 1)
        symbol = parts[0].upper()
        event_id = parts[1] if len(parts) > 1 else None
        from ..providers.projections import build_workspace_market_context_payload

        mc_payload = build_workspace_market_context_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not mc_payload.get("attention_available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        summaries = mc_payload.get("attention_summaries") or []
        selected = None
        if event_id:
            for row in summaries:
                if isinstance(row, dict) and row.get("event_id") == event_id:
                    selected = row
                    break
        if selected is None and summaries:
            selected = summaries[-1] if isinstance(summaries[-1], dict) else None
        if not isinstance(selected, dict):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        info_value = selected.get("information_value")
        reflexive = selected.get("reflexive_impact")
        body = {
            "alignment_summary": (
                f"attention {selected.get('attention_level')} · "
                f"info {info_value if info_value is not None else 'UNAVAILABLE'}"
            ),
            "level": 2,
            "meaning": f"MC9 attention diffusion for {symbol}",
            "ref": ref,
            "why": (
                f"{selected.get('headline', selected.get('canonical_event_type', 'event'))} · "
                f"reflexive {reflexive if reflexive is not None else 'UNAVAILABLE'} · "
                f"{mc_payload.get('disclaimer', '')}"
            ),
        }
    elif ref.startswith("explain:author:"):
        remainder = ref.removeprefix("explain:author:")
        parts = remainder.split(":", 1)
        symbol = parts[0].upper()
        handle = parts[1] if len(parts) > 1 else None
        from ..providers.projections import build_workspace_market_context_payload

        mc_payload = build_workspace_market_context_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not mc_payload.get("author_intelligence_available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        summaries = mc_payload.get("author_intelligence_summaries") or []
        selected = None
        if handle:
            for row in summaries:
                if isinstance(row, dict) and row.get("handle") == handle:
                    selected = row
                    break
        if selected is None and summaries:
            selected = summaries[-1] if isinstance(summaries[-1], dict) else None
        if not isinstance(selected, dict):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        influence = selected.get("influence_score")
        accuracy = selected.get("accuracy_score")
        body = {
            "alignment_summary": (
                f"influence {influence if influence is not None else 'UNAVAILABLE'} · "
                f"accuracy {accuracy if accuracy is not None else 'UNVALIDATED'}"
            ),
            "level": 2,
            "meaning": f"MC14 social author intelligence for {symbol} — influence is not accuracy",
            "ref": ref,
            "why": (
                f"@{selected.get('handle', 'unknown')} · "
                f"{mc_payload.get('disclaimer', '')}"
            ),
        }
    elif ref.startswith("explain:propagation:"):
        remainder = ref.removeprefix("explain:propagation:")
        parts = remainder.split(":", 1)
        symbol = parts[0].upper()
        source_event_id = parts[1] if len(parts) > 1 else None
        from ..providers.projections import build_workspace_market_context_payload

        mc_payload = build_workspace_market_context_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not mc_payload.get("cross_entity_propagation_available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        summaries = mc_payload.get("cross_entity_propagation_summaries") or []
        selected = None
        if source_event_id:
            for row in summaries:
                if isinstance(row, dict) and row.get("source_event_id") == source_event_id:
                    selected = row
                    break
        if selected is None and summaries:
            selected = summaries[-1] if isinstance(summaries[-1], dict) else None
        if not isinstance(selected, dict):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        catalyst = selected.get("propagated_catalyst_strength")
        attention = selected.get("propagated_attention_level")
        body = {
            "alignment_summary": (
                f"propagated catalyst {catalyst if catalyst is not None else 'UNAVAILABLE'} · "
                f"propagated attention {attention if attention is not None else 'UNAVAILABLE'}"
            ),
            "level": 2,
            "meaning": (
                f"MC15 cross-entity propagation for {symbol} — separate fields, no fused score"
            ),
            "ref": ref,
            "why": (
                f"{selected.get('source_entity_id', 'unknown')} via "
                f"{selected.get('link_type', 'unknown')} · "
                f"{mc_payload.get('disclaimer', '')}"
            ),
        }
    elif ref.startswith("explain:disclosure:"):
        symbol = ref.removeprefix("explain:disclosure:")
        from ..providers.projections import build_workspace_disclosure_payload

        disclosure = build_workspace_disclosure_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not disclosure.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": f"{disclosure.get('event_count', 0)} disclosure event(s)",
            "level": 2,
            "meaning": f"Regulatory disclosure feed for {symbol.upper()}",
            "ref": ref,
            "why": str(disclosure.get("disclaimer", "")),
        }
    elif ref.startswith("explain:order-flow:"):
        symbol = ref.removeprefix("explain:order-flow:")
        from ..providers.projections import build_workspace_order_flow_payload

        order_flow = build_workspace_order_flow_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not order_flow.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": f"{order_flow.get('event_count', 0)} order-flow event(s)",
            "level": 2,
            "meaning": f"Signed order-flow / CVD feed for {symbol.upper()}",
            "ref": ref,
            "why": str(order_flow.get("disclaimer", "")),
        }
    elif ref.startswith("explain:options:"):
        symbol = ref.removeprefix("explain:options:")
        from ..providers.projections import build_workspace_options_payload

        options = build_workspace_options_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not options.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": f"{options.get('activity_count', 0)} options activity event(s)",
            "level": 2,
            "meaning": f"Options unusual-activity feed for {symbol.upper()}",
            "ref": ref,
            "why": str(options.get("disclaimer", "")),
        }
    elif ref.startswith("explain:large-transactions:"):
        symbol = ref.removeprefix("explain:large-transactions:")
        from ..providers.projections import build_workspace_large_transactions_payload

        large_transactions = build_workspace_large_transactions_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not large_transactions.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": f"{large_transactions.get('print_count', 0)} large-print event(s)",
            "level": 2,
            "meaning": f"Large-transaction feed for {symbol.upper()}",
            "ref": ref,
            "why": str(large_transactions.get("disclaimer", "")),
        }
    elif ref.startswith("explain:order-book:"):
        symbol = ref.removeprefix("explain:order-book:")
        from ..providers.projections import build_workspace_order_book_payload

        order_book = build_workspace_order_book_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not order_book.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": f"{order_book.get('snapshot_count', 0)} depth snapshot(s)",
            "level": 2,
            "meaning": f"Order-book depth feed for {symbol.upper()}",
            "ref": ref,
            "why": str(order_book.get("disclaimer", "")),
        }
    elif ref.startswith("explain:fund-etf:"):
        symbol = ref.removeprefix("explain:fund-etf:")
        from ..providers.projections import build_workspace_fund_etf_payload

        fund_etf = build_workspace_fund_etf_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not fund_etf.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        body = {
            "alignment_summary": f"{fund_etf.get('event_count', 0)} fund/ETF context event(s)",
            "level": 2,
            "meaning": f"Fund/ETF cross-asset context for {symbol.upper()}",
            "ref": ref,
            "why": str(fund_etf.get("disclaimer", "")),
        }
    elif ref.startswith("explain:futures:"):
        symbol = ref.removeprefix("explain:futures:")
        from ..providers.projections import build_workspace_futures_payload

        futures = build_workspace_futures_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        if not futures.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        snapshot_count = futures.get("snapshot_count", len(futures.get("snapshots", [])))
        body = {
            "alignment_summary": f"{snapshot_count} ES depth snapshot(s)",
            "level": 2,
            "meaning": f"ES futures depth / imbalance for {symbol.upper()}",
            "ref": ref,
            "why": str(futures.get("disclaimer", "")),
        }
    else:
        raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
    return {
        "as_of_context": build_as_of_context(store),
        "capability_states": build_capabilities(store),
        "explanation": body,
        "inspector_ref": ref.replace("explain:", "inspect:", 1),
    }


def build_inspect_payload(store: ReplayStore, ref: str) -> dict[str, object]:
    default_tab = "SUMMARY"
    explain_ref = ref.replace("inspect:", "explain:", 1)
    if ref.startswith("inspect:squeeze:timeline:"):
        symbol_for_explain = ref.removeprefix("inspect:squeeze:timeline:")
        explain_ref = f"explain:squeeze:{symbol_for_explain}"
        default_tab = "TIMELINE"
    explain = build_explain_payload(store, explain_ref)
    explanation = explain["explanation"]
    if not isinstance(explanation, dict):
        raise ValueError("UI_INSPECT_INVALID")
    tabs = {
        "SUMMARY": {
            "headline": str(explanation.get("meaning", "")),
            "summary": str(explanation.get("why", "")),
            "alignment": str(explanation.get("alignment_summary", "")),
        },
        "EVIDENCE": {
            "items": [
                {
                    "evidence_id": ref,
                    "epistemic_class": "DERIVED" if "strategy" in ref else "OBSERVED",
                    "family": "strategy" if "strategy" in ref else "platform",
                    "as_of": store.as_of_time(),
                    "quality": build_quality_summary(store),
                }
            ],
        },
    }
    if "strategy" in ref:
        tabs["DERIVATION"] = {
            "method": "run_strategy_evaluation + interpret_strategy",
            "inputs": ["bar_derived_features", "naive_forecast"],
            "source": "Phase 6 preregistered strategy pipeline",
        }
    if "squeeze" in ref:
        if ref.startswith("inspect:squeeze:timeline:"):
            symbol = ref.removeprefix("inspect:squeeze:timeline:")
            squeeze_data_mode = "frozen"
        elif ref.startswith("inspect:squeeze:scanner:"):
            symbol = ref.removeprefix("inspect:squeeze:scanner:")
            squeeze_data_mode = "current"
        else:
            symbol = ref.rsplit(":", 1)[-1]
            squeeze_data_mode = "frozen"
        from ..donor_bridge.projections import build_workspace_squeeze_payload

        squeeze = build_workspace_squeeze_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
            data_mode=squeeze_data_mode,
        )
        tabs["EVIDENCE"]["items"] = [
            {
                "evidence_id": ref,
                "epistemic_class": "OBSERVED",
                "family": "squeeze",
                "as_of": store.as_of_time(),
                "quality": {"state": str(squeeze.get("freshness", "FROZEN"))},
            }
        ]
        tabs["DERIVATION"] = {
            "method": (
                "short-squeeze-project current scanner bridge"
                if squeeze_data_mode == "current"
                else "short-squeeze-project FROZEN_DEMO bridge"
            ),
            "inputs": ["donor /api/current/candidate" if squeeze_data_mode == "current" else "donor /api/frozen/candidate"],
            "source": "Read-only donor integration (no canonical admission)",
        }
        if squeeze.get("rules"):
            tabs["RULES"] = {
                "rows": squeeze.get("rules", []),
                "summary": squeeze.get("phase3a_summary", ""),
            }
        if squeeze.get("ignition_evidence"):
            tabs["SUMMARY"]["ignition_evidence"] = squeeze.get("ignition_evidence")
        state_machine = squeeze.get("state_machine", {})
        if isinstance(state_machine, dict):
            tabs["TIMELINE"] = {
                "changed_criteria": state_machine.get("changed_criteria", []),
                "current_state": state_machine.get("current_state"),
                "events": state_machine.get("transitions", []),
                "last_transition_label": state_machine.get("last_transition_label"),
                "unchanged_criteria": state_machine.get("unchanged_criteria", []),
                "unknown_criteria": state_machine.get("unknown_criteria", []),
            }
        readiness = squeeze.get("readiness", {})
        if isinstance(readiness, dict):
            tabs["PROVENANCE"] = {
                "freshness_state": readiness.get("freshness_state"),
                "provenance_admissible": readiness.get("provenance_admissible"),
                "provenance_reason_codes": readiness.get("provenance_reason_codes", []),
                "rule_outcome_totals": readiness.get("rule_outcome_totals", {}),
                "raw": squeeze.get("provenance"),
            }
    if "catalyst" in ref and "fund-etf" not in ref:
        symbol = ref.rsplit(":", 1)[-1]
        from ..providers.projections import build_workspace_catalyst_payload as build_fixture_catalyst

        catalyst = build_fixture_catalyst(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        source = "ADR-WHALE-007 admitted fixture"
        if not catalyst.get("available"):
            from ..donor_bridge.projections import build_workspace_catalyst_payload as build_bridge_catalyst

            catalyst = build_bridge_catalyst(symbol, as_of_context=build_as_of_context(store))
            source = "Read-only donor integration (no canonical admission)"
        tabs["EVIDENCE"]["items"] = [
            {
                "evidence_id": ref,
                "epistemic_class": "INFERRED",
                "family": "public_catalyst",
                "as_of": store.as_of_time(),
                "quality": {"state": "FIXTURE" if catalyst.get("catalysts") else "DEMO"},
            }
        ]
        tabs["DERIVATION"] = {
            "method": "catalyst_lane.confidence_score + gate_catalyst + lean_direction",
            "inputs": ["news_score", "social_score", "volume_score", "liquidity_ok"],
            "source": source,
        }
        if catalyst.get("catalysts"):
            tabs["CATALYST"] = {"events": catalyst.get("catalysts", [])}
        elif catalyst.get("evidence_cards"):
            tabs["SUMMARY"]["evidence_cards"] = catalyst.get("evidence_cards")
        trade = catalyst.get("trade_signal") or {}
        if trade:
            tabs["SIGNAL"] = {
                "decision": trade.get("decision"),
                "lean": trade.get("lean"),
                "options_score": trade.get("options_score"),
                "options_bias": trade.get("options_bias"),
                "instrument_hint": trade.get("instrument_hint"),
                "headline": trade.get("news_headline") or trade.get("reasoning"),
            }
    if "fund-etf" in ref:
        symbol = ref.rsplit(":", 1)[-1]
        from ..providers.projections import build_workspace_fund_etf_payload

        fund_etf = build_workspace_fund_etf_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        tabs["EVIDENCE"]["items"] = [
            {
                "evidence_id": ref,
                "epistemic_class": "DERIVED",
                "family": "fund_etf_cross_asset",
                "as_of": store.as_of_time(),
                "quality": {
                    "state": "FIXTURE",
                    "event_count": fund_etf.get("event_count", len(fund_etf.get("events", []))),
                    "regime_label": fund_etf.get("latest_regime_label"),
                },
            }
        ]
        tabs["DERIVATION"] = {
            "method": "fund_etf_lane.flow_direction_label + correlation_regime",
            "inputs": ["etf_flow_proxy", "cross_asset_correlation", "regime_label"],
            "source": "ADR-WHALE-008 admitted synthetic fixture",
        }
        tabs["FUND_ETF"] = {"events": fund_etf.get("events", [])}
    if "disclosure" in ref:
        symbol = ref.rsplit(":", 1)[-1]
        from ..providers.projections import build_workspace_disclosure_payload

        disclosure = build_workspace_disclosure_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        tabs["EVIDENCE"]["items"] = [
            {
                "evidence_id": ref,
                "epistemic_class": "OBSERVED",
                "family": "regulatory_disclosure",
                "as_of": store.as_of_time(),
                "quality": {"state": "DELAYED_DISCLOSURE"},
            }
        ]
        tabs["DERIVATION"] = {
            "method": "fixture-first SEC EDGAR adapter",
            "inputs": ["tests/fixtures/providers/edgar/biya_disclosures.json"],
            "source": "Phase 9 whale ledger (research-only)",
        }
        tabs["DISCLOSURE"] = {
            "events": disclosure.get("events", []),
            "disclosure_lag_note": disclosure.get("disclosure_lag_note"),
            "research_only": disclosure.get("research_only"),
        }
    if "futures" in ref:
        symbol = ref.rsplit(":", 1)[-1]
        from ..providers.projections import build_workspace_futures_payload

        futures = build_workspace_futures_payload(
            symbol,
            as_of_context=build_as_of_context(store),
            prediction_cutoff=store.prediction_cutoff(),
        )
        provenance = str(futures.get("provenance", "fixture"))
        tabs["EVIDENCE"]["items"] = [
            {
                "evidence_id": ref,
                "epistemic_class": "DERIVED",
                "family": "futures_depth",
                "legacy_family": "futures_positioning",
                "as_of": store.as_of_time(),
                "quality": {
                    "state": provenance,
                    "snapshot_count": futures.get("snapshot_count", len(futures.get("snapshots", []))),
                    "imbalance_signal": futures.get("latest_imbalance_signal"),
                    "imbalance_ratio": futures.get("latest_imbalance_ratio"),
                },
            }
        ]
        tabs["DERIVATION"] = {
            "method": "futures_lane.depth_imbalance_signal + quarterly_contract_month + is_rth",
            "inputs": ["ES depth ladder", "contract roll metadata", "RTH session gate"],
            "source": (
                "ADR-DATA-002 admitted synthetic fixture"
                if provenance == "fixture"
                else "FuturesX donor bridge (not replay-admitted)"
            ),
        }
    return {
        "as_of_context": build_as_of_context(store),
        "capability_states": build_capabilities(store),
        "default_tab": default_tab,
        "explanation_ref": ref.replace("inspect:", "explain:", 1),
        "ref": ref,
        "tabs": tabs,
    }


def build_research_analytics_payload(store: ReplayStore) -> dict[str, object]:
    cutoff = store.prediction_cutoff()
    attention_items = _all_attention_items(store)
    tier_rows = [{"tier": str(item.get("tier", 2))} for item in attention_items]

    strategy = store.strategy
    interpretations = [
        row
        for row in strategy.get("interpretations", [])
        if isinstance(row, dict) and int(row.get("observation_time", 0)) <= cutoff
    ]
    strategy_outcomes = _count_series(interpretations, "outcome")

    signal_timeline: list[dict[str, object]] = []
    cumulative_signals = 0
    for index, row in enumerate(
        sorted(interpretations, key=lambda item: int(item.get("observation_time", 0))),
        start=1,
    ):
        if str(row.get("outcome")) == "signal":
            cumulative_signals += 1
        signal_timeline.append(
            {
                "observation_index": index,
                "cumulative_signals": cumulative_signals,
                "outcome": str(row.get("outcome", "unknown")),
            }
        )

    risk_rows = [
        row
        for row in store.evaluation.get("risk_decisions", [])
        if isinstance(row, dict)
        and int(row.get("signal_prediction_cutoff", cutoff + 1)) <= cutoff
    ]
    risk_outcomes = _count_series(risk_rows, "decision")

    from ..donor_bridge.historical_cohort import build_historical_cohort_summary_panel
    from ..donor_bridge.projections import build_explore_squeeze_payload

    squeeze_payload = build_explore_squeeze_payload(as_of_context=build_as_of_context(store))
    squeeze_rows = squeeze_payload.get("rows", [])
    squeeze_summary = (
        _count_series([row for row in squeeze_rows if isinstance(row, dict)], "outcome_status")
        if squeeze_payload.get("available")
        else []
    )

    return {
        "as_of_context": build_as_of_context(store),
        "authority_boundary": "READ_ONLY_RESEARCH_VISUALIZATION",
        "disclaimer": "Research visualization only. Charts cite replay and donor-bridge sources. No trade authority.",
        "epistemic_class": "RESEARCH_PROJECTION",
        "panels": {
            "attention_tiers": {
                "available": bool(tier_rows),
                "provenance": {
                    "method": "build_attention_page tier aggregation",
                    "source": "replay attention feed",
                },
                "series": _count_series(tier_rows, "tier"),
            },
            "risk_decisions": {
                "available": bool(risk_rows),
                "provenance": {
                    "method": "run_risk_simulation_evaluation decisions at cutoff",
                    "source": "phase 7 risk simulation",
                },
                "series": risk_outcomes,
            },
            "squeeze_outcomes": {
                "available": bool(squeeze_payload.get("available")),
                "reason": squeeze_payload.get("reason"),
                "provenance": {
                    "bridge_mode": squeeze_payload.get("bridge_mode"),
                    "method": "build_explore_squeeze_payload outcome aggregation",
                    "source": str(squeeze_payload.get("source", "short-squeeze-project")),
                },
                "series": squeeze_summary,
            },
            "squeeze_historical_cohort": build_historical_cohort_summary_panel(),
            "strategy_outcomes": {
                "available": bool(interpretations),
                "provenance": {
                    "method": "run_strategy_evaluation interpretations at cutoff",
                    "source": "phase 5R walk-forward + phase 6 strategy",
                    "walk_forward_fold_count": strategy.get("walk_forward_fold_count"),
                },
                "series": strategy_outcomes,
                "signal_timeline": signal_timeline,
            },
        },
    }


INSTITUTIONAL_FLOW_FAMILY_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (REGULATORY_DISCLOSURE_FAMILY, "Disclosure", "disclosure", "explain:disclosure"),
    (LARGE_TRANSACTIONS_FAMILY, "Large Txn", "large-transactions", "explain:large-transactions"),
    (ORDER_FLOW_FAMILY, "Order Flow", "order-flow", "explain:order-flow"),
    (ORDER_BOOK_FAMILY, "Order Book", "order-book", "explain:order-book"),
    (OPTIONS_FAMILY, "Options", "options", "explain:options"),
    (FUTURES_DEPTH_FAMILY, "Futures depth (L2)", "futures", "explain:futures"),
    (FUND_ETF_FAMILY, "Fund / ETF", "fund-etf", "explain:fund-etf"),
    (PUBLIC_CATALYST_FAMILY, "Catalyst", "catalyst", "explain:catalyst"),
)

_INSTITUTIONAL_ENTITLED_SYMBOLS: dict[str, str] = {
    REGULATORY_DISCLOSURE_FAMILY: "BIYA",
    LARGE_TRANSACTIONS_FAMILY: "NVDA",
    ORDER_FLOW_FAMILY: "NVDA",
    ORDER_BOOK_FAMILY: "NVDA",
    OPTIONS_FAMILY: "BIYA",
    FUTURES_DEPTH_FAMILY: "ES",
    FUND_ETF_FAMILY: "NVDA",
    PUBLIC_CATALYST_FAMILY: "BOXL",
}

_INSTITUTIONAL_AVAILABILITY = {
    REGULATORY_DISCLOSURE_FAMILY: disclosure_available,
    LARGE_TRANSACTIONS_FAMILY: large_transactions_available,
    ORDER_FLOW_FAMILY: order_flow_available,
    ORDER_BOOK_FAMILY: order_book_available,
    OPTIONS_FAMILY: options_available,
    FUTURES_DEPTH_FAMILY: futures_available,
    FUND_ETF_FAMILY: fund_etf_available,
    PUBLIC_CATALYST_FAMILY: catalyst_available,
}


def _pit_filter_rows(rows: list[object], cutoff: int, time_key: str) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        obs_time = row.get(time_key, row.get("prediction_cutoff", row.get("signal_prediction_cutoff")))
        if obs_time is None:
            continue
        if int(obs_time) <= cutoff:
            filtered.append(row)
    return filtered


def build_research_models_payload(store: ReplayStore) -> dict[str, object]:
    cutoff = store.prediction_cutoff()
    strategy = store.strategy
    interpretations = _pit_filter_rows(
        list(strategy.get("interpretations", [])),
        cutoff,
        "observation_time",
    )
    spec = strategy.get("strategy_spec", {})
    manifest = strategy.get("dataset_manifest", {})
    prereg = strategy.get("preregistration", {})
    model_summary: dict[str, object] = {
        "alignment_type": spec.get("alignment_type") if isinstance(spec, dict) else None,
        "dataset_fingerprint": manifest.get("dataset_fingerprint") if isinstance(manifest, dict) else None,
        "model_family": "naive_last_value.v1",
        "strategy_identity_hash": spec.get("strategy_identity_hash") if isinstance(spec, dict) else None,
        "target_horizon_ns": manifest.get("horizon_ns") if isinstance(manifest, dict) else None,
    }
    return {
        "as_of_context": build_as_of_context(store),
        "authority_boundary": "READ_ONLY_RESEARCH",
        "capability_states": build_capabilities(store),
        "disclaimer": "Model Lab projection only. Walk-forward on admitted fixture. No trade authority.",
        "epistemic_class": "RESEARCH_PROJECTION",
        "interpretations": interpretations,
        "interpretation_summary": {
            "abstention_count": strategy.get("abstention_count", 0),
            "signal_count": strategy.get("signal_count", 0),
            "total_at_cutoff": len(interpretations),
        },
        "model_summary": model_summary,
        "preregistration": prereg if isinstance(prereg, dict) else {},
        "preregistration_status": strategy.get("preregistration_status"),
        "strategy_spec": spec if isinstance(spec, dict) else {},
        "walk_forward_fold_count": strategy.get("walk_forward_fold_count", 0),
        "dataset_manifest": manifest if isinstance(manifest, dict) else {},
    }


def build_research_simulation_payload(store: ReplayStore) -> dict[str, object]:
    cutoff = store.prediction_cutoff()
    evaluation = store.evaluation
    risk_decisions = _pit_filter_rows(
        list(evaluation.get("risk_decisions", [])),
        cutoff,
        "signal_prediction_cutoff",
    )
    fills = _pit_filter_rows(list(evaluation.get("fills", [])), cutoff, "fill_time")
    orders = _pit_filter_rows(list(evaluation.get("orders", [])), cutoff, "activation_time")
    intents = _pit_filter_rows(list(evaluation.get("intents", [])), cutoff, "observation_time")
    attributions = _pit_filter_rows(list(evaluation.get("attributions", [])), cutoff, "observation_time")
    ledger = evaluation.get("ledger", {})
    reconciliation = evaluation.get("reconciliation", {})
    return {
        "as_of_context": build_as_of_context(store),
        "attributions": attributions,
        "authority_boundary": "READ_ONLY_SIMULATION",
        "capability_states": build_capabilities(store),
        "disclaimer": "Simulation Lab projection only. Deterministic bar-conservative simulator. No execution authority.",
        "epistemic_class": "SIMULATION_PROJECTION",
        "fill_audit": evaluation.get("fill_audit", {}),
        "fills": fills,
        "intents": intents,
        "ledger_summary": {
            "cash_minor": ledger.get("cash_minor") if isinstance(ledger, dict) else None,
            "entry_count": len(ledger.get("entries", [])) if isinstance(ledger, dict) else 0,
            "position_shares": ledger.get("position_shares") if isinstance(ledger, dict) else None,
            "realized_pnl_minor": ledger.get("realized_pnl_minor") if isinstance(ledger, dict) else None,
        },
        "mode_label": "SIMULATION",
        "orders": orders,
        "reconciliation": reconciliation if isinstance(reconciliation, dict) else {},
        "risk_decisions": risk_decisions,
        "risk_policy_id": (
            evaluation.get("risk_policy", {}).get("policy_id")
            if isinstance(evaluation.get("risk_policy"), dict)
            else None
        ),
    }


def build_workspace_institutional_flow_payload(store: ReplayStore, symbol: str) -> dict[str, object]:
    instrument_id = symbol.upper()
    cutoff = store.prediction_cutoff()
    as_of = build_as_of_context(store)
    families: list[dict[str, object]] = []
    for family_id, label, route_segment, explain_prefix in INSTITUTIONAL_FLOW_FAMILY_SPECS:
        entitled_symbol = _INSTITUTIONAL_ENTITLED_SYMBOLS[family_id]
        availability_fn = _INSTITUTIONAL_AVAILABILITY[family_id]
        available = availability_fn(instrument_id=entitled_symbol, prediction_cutoff=cutoff)
        reason = None if available else "WHALE_NO_PIT_ELIGIBLE_OR_UNSUPPORTED"
        families.append(
            {
                "available": available,
                "entitled_symbol": entitled_symbol,
                "explanation_ref": f"{explain_prefix}:{entitled_symbol}",
                "family_id": family_id,
                "label": label,
                "reason": reason,
                "route_path": f"/workspace/{entitled_symbol}/{route_segment}",
            }
        )
    return {
        "as_of_context": as_of,
        "available_family_count": sum(1 for row in families if row.get("available")),
        "capability_states": build_capabilities(store),
        "disclaimer": "Institutional Flow composite. Each family is separately inspectable. No invented identity.",
        "epistemic_class": "INSTITUTIONAL_COMPOSITE",
        "families": families,
        "family_count": len(families),
        "research_only": True,
        "symbol": instrument_id,
    }


def build_replay_session(store: ReplayStore) -> dict[str, object]:
    bar = store.current_bar()
    return {
        "as_of_context": build_as_of_context(store),
        "capability_states": build_capabilities(store),
        "cursor_index": store.cursor_index,
        "event_count": len(store.bars),
        "instrument_id": store.instrument_id,
        "session_id": store.session_id,
        "available_time": int(bar["available_time"]),
        "speed": 1,
    }


def scrub_replay(store: ReplayStore, *, cursor_index: int | None = None, available_time: int | None = None) -> dict[str, object]:
    if cursor_index is not None:
        store.set_cursor_index(cursor_index)
    elif available_time is not None:
        store.set_cursor_by_time(available_time)
    else:
        raise ValueError("UI_REPLAY_SCRUB_MISSING_TARGET")
    return build_replay_session(store)

"""DTO projection builders for UI-001 read-only API."""

from __future__ import annotations

from typing import Any

from ..features.institutional import LARGE_TRANSACTIONS_FAMILY, OPTIONS_FAMILY, WHALE_FAMILIES, ORDER_FLOW_FAMILY, REGULATORY_DISCLOSURE_FAMILY
from ..providers.projections import disclosure_available, large_transactions_available, options_available, order_flow_available
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
    from ..donor_bridge.projections import build_squeeze_attention_items

    return build_squeeze_attention_items()


def _catalyst_attention_items() -> list[dict[str, object]]:
    from ..donor_bridge.projections import build_catalyst_attention_items

    return build_catalyst_attention_items()


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
    elif ref.startswith("explain:squeeze:"):
        symbol = ref.removeprefix("explain:squeeze:")
        from ..donor_bridge.projections import build_workspace_squeeze_payload

        squeeze = build_workspace_squeeze_payload(
            symbol,
            as_of_context=build_as_of_context(store),
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
        from ..donor_bridge.projections import build_workspace_catalyst_payload

        catalyst = build_workspace_catalyst_payload(
            symbol,
            as_of_context=build_as_of_context(store),
        )
        if not catalyst.get("available"):
            raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
        trade = catalyst.get("trade_signal") or {}
        body = {
            "alignment_summary": str(trade.get("decision", "UNKNOWN")),
            "level": 2,
            "meaning": f"Catalyst paper signal for {symbol.upper()}",
            "ref": ref,
            "why": (
                f"{trade.get('news_headline') or trade.get('reasoning', '')} · "
                f"{catalyst.get('disclaimer', '')}"
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
        else:
            symbol = ref.rsplit(":", 1)[-1]
        from ..donor_bridge.projections import build_workspace_squeeze_payload

        squeeze = build_workspace_squeeze_payload(
            symbol,
            as_of_context=build_as_of_context(store),
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
            "method": "short-squeeze-project FROZEN_DEMO bridge",
            "inputs": ["donor /api/frozen/candidate"],
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
    if "catalyst" in ref:
        symbol = ref.rsplit(":", 1)[-1]
        from ..donor_bridge.projections import build_workspace_catalyst_payload

        catalyst = build_workspace_catalyst_payload(
            symbol,
            as_of_context=build_as_of_context(store),
        )
        trade = catalyst.get("trade_signal") or {}
        tabs["EVIDENCE"]["items"] = [
            {
                "evidence_id": ref,
                "epistemic_class": "INFERRED",
                "family": "catalyst",
                "as_of": store.as_of_time(),
                "quality": {"state": "DEMO"},
            }
        ]
        tabs["DERIVATION"] = {
            "method": "internship-project demo state bridge",
            "inputs": ["trade_log.json", "watchlist.json"],
            "source": "Read-only donor integration (no canonical admission)",
        }
        if catalyst.get("evidence_cards"):
            tabs["SUMMARY"]["evidence_cards"] = catalyst.get("evidence_cards")
        if trade:
            tabs["SIGNAL"] = {
                "decision": trade.get("decision"),
                "lean": trade.get("lean"),
                "options_score": trade.get("options_score"),
                "options_bias": trade.get("options_bias"),
                "instrument_hint": trade.get("instrument_hint"),
                "headline": trade.get("news_headline") or trade.get("reasoning"),
            }
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

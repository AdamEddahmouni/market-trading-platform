"""Read-only disclosure and order-flow projections for UI-001."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.market_context import baseline_sentiment_to_dict
from ..features.institutional import get_institutional_ledger
from ..providers.whale_ledger import (
    FUND_ETF_FAMILY,
    FUTURES_FAMILY,
    LARGE_TRANSACTIONS_FAMILY,
    OPTIONS_FAMILY,
    ORDER_BOOK_FAMILY,
    ORDER_FLOW_FAMILY,
    PUBLIC_CATALYST_FAMILY,
)


def disclosure_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family="regulatory_disclosure",
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def order_flow_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=ORDER_FLOW_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def options_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=OPTIONS_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def large_transactions_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=LARGE_TRANSACTIONS_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def order_book_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=ORDER_BOOK_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def futures_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=FUTURES_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def catalyst_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=PUBLIC_CATALYST_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def fund_etf_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    ledger = get_institutional_ledger()
    if ledger is None:
        return False
    events = ledger.query_events(
        family=FUND_ETF_FAMILY,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return bool(events)


def build_workspace_disclosure_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    from ..donor_bridge.participant_adapter import build_participant_actions_bundle

    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Institutional disclosure not entitled. Fail-closed per ADR-WHALE-001.",
            "events": [],
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    events = ledger.query_disclosure_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not events:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible disclosure events for this symbol at replay cutoff.",
            "events": [],
            "reason": "WHALE_NO_PIT_ELIGIBLE_DISCLOSURE",
            "research_only": True,
            "symbol": instrument_id,
        }
    participant_bundle = build_participant_actions_bundle(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "SEC filings are delayed public disclosures, not a live tape. "
            "Participant semantics are research decomposition, not trade signals. "
            "Research-only per ADR-WHALE-001."
        ),
        "disclosure_lag_note": "SEC filings are delayed public disclosures, not a live tape.",
        "events": events,
        "event_count": len(events),
        "ledger_id": ledger.ledger_id,
        "participant_actions": participant_bundle.get("actions", []),
        "participant_summary": participant_bundle.get("summary", {}),
        "participant_evidence": participant_bundle.get("typed_evidence", []),
        "participant_skill_summary": (
            participant_bundle.get("skill", {}).get("summary", {})
            if isinstance(participant_bundle.get("skill"), dict)
            else {}
        ),
        "participant_skill_available": bool(
            isinstance(participant_bundle.get("skill"), dict)
            and participant_bundle.get("skill", {}).get("available")
        ),
        "provider_id": "sec.edgar.fixture",
        "research_only": True,
        "symbol": instrument_id,
    }


def build_workspace_order_flow_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "bars": [],
            "disclaimer": "Order-flow evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    bars = ledger.query_order_flow_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not bars:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "bars": [],
            "disclaimer": "No PIT-eligible order-flow events for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_ORDER_FLOW",
            "research_only": True,
            "symbol": instrument_id,
        }
    from ..order_flow.cvd import compute_cvd_state, provenance_fractions_from_bars

    cvd_state = compute_cvd_state(bars)
    provenance = provenance_fractions_from_bars(bars)
    cvd_summary: dict[str, object] = {
        **provenance,
        "session_cvd": cvd_state.session_cvd if cvd_state else 0.0,
        "cvd_slope": cvd_state.cvd_slope if cvd_state else None,
        "cvd_acceleration": cvd_state.cvd_acceleration if cvd_state else None,
        "aggressive_buy_volume": cvd_state.aggressive_buy_volume if cvd_state else 0.0,
        "aggressive_sell_volume": cvd_state.aggressive_sell_volume if cvd_state else 0.0,
    }
    from ..order_flow.metaorder import classified_trades_from_bars, detect_metaorder_primitives
    from ..order_flow.contracts import metaorder_primitive_to_dict

    trades = classified_trades_from_bars(bars, instrument=instrument_id)
    primitives = detect_metaorder_primitives(trades, instrument=instrument_id)
    metaorder_summary = {
        "primitive_count": len(primitives),
        "metaorder_available": bool(primitives),
        "primitives": [metaorder_primitive_to_dict(item) for item in primitives],
    }
    return {
        "as_of_context": as_of_context,
        "available": True,
        "bars": bars,
        "bar_count": len(bars),
        "cvd_summary": cvd_summary,
        "metaorder_summary": metaorder_summary,
        "disclaimer": (
            "Order-flow metrics are derived from admitted fixture trade classification. "
            "CVD = aggressive buy volume minus aggressive sell volume — not buyer count. "
            "Unknown aggressor remains unknown. Research-only per ADR-WHALE-003."
        ),
        "ledger_id": ledger.ledger_id,
        "provider_id": "cvd.fixture.order_flow",
        "research_only": True,
        "symbol": instrument_id,
    }


def _chain_contracts_to_surface_activities(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt canonical chain contracts to activity shape for O2 surface builder."""
    adapted: list[dict[str, Any]] = []
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        bid_raw = contract.get("bid")
        ask_raw = contract.get("ask")
        adapted.append(
            {
                "strike": float(contract.get("strike", 0)),
                "expiry": contract.get("expiration"),
                "option_type": contract.get("call_put"),
                "bid": float(bid_raw) if bid_raw is not None else 0.0,
                "ask": float(ask_raw) if ask_raw is not None else 0.0,
                "event_time": contract.get("event_time"),
                "open_interest": contract.get("open_interest"),
                "multiplier": contract.get("multiplier"),
                "deliverable": contract.get("deliverable"),
                "quality_flags": contract.get("quality_flags"),
                "underlying_price": contract.get("underlying_price"),
            }
        )
    return adapted


def _options_event_vol_enrichment(
    symbol: str,
    *,
    as_of_time: str,
    chain_rows: list[dict[str, Any]],
    physical_forecast: dict[str, Any] | None,
    squeeze_context: dict[str, Any] | None,
    catalyst_event_times: list[str] | None = None,
) -> dict[str, Any]:
    from ..options.event_vol import build_event_vol_snapshot, load_earnings_event_fixture

    earnings_fixture = load_earnings_event_fixture(symbol)
    return build_event_vol_snapshot(
        symbol,
        as_of_time,
        chain_rows=chain_rows,
        earnings_event=earnings_fixture,
        physical_forecast=physical_forecast,
        squeeze_context=squeeze_context,
        catalyst_event_times=catalyst_event_times or [],
    )


def _options_strategy_enrichment(
    symbol: str,
    *,
    as_of_time: str,
    chain_rows: list[dict[str, Any]],
    physical_forecast: dict[str, Any] | None,
    p_vs_q_executable_edge: dict[str, Any] | None,
    execution_friction: dict[str, Any] | None,
    squeeze_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from ..options.strategy import build_strategy_snapshot

    return build_strategy_snapshot(
        symbol,
        as_of_time,
        executable_edge=p_vs_q_executable_edge,
        physical_forecast=physical_forecast,
        chain_rows=chain_rows,
        friction=execution_friction,
        squeeze_context=squeeze_context,
    )


def _options_execution_enrichment(
    symbol: str,
    *,
    as_of_time: str,
    chain_rows: list[dict[str, Any]],
    strategy_snapshot: dict[str, Any] | None,
    execution_friction: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from ..options.execution import build_execution_snapshot

    return build_execution_snapshot(
        symbol,
        as_of_time,
        strategy_snapshot=strategy_snapshot,
        chain_rows=chain_rows,
        friction=execution_friction,
        squeeze_context=squeeze_context,
    )


def _opportunity_snapshot_enrichment(
    symbol: str,
    as_of_time: str,
    *,
    strategy_snapshot: dict[str, Any] | None = None,
    execution_snapshot: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
    causal_intelligence: dict[str, Any] | None = None,
    order_flow_payload: dict[str, Any] | None = None,
    options_payload: dict[str, Any] | None = None,
    execution_friction: dict[str, Any] | None = None,
    futures_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """SHARED P4 — fuse cross-lane inputs into opportunity snapshot."""
    from ..donor_bridge.opportunity_adapter import build_opportunity_fusion_bundle

    squeeze_detail: dict[str, Any] | None = None
    if causal_intelligence:
        squeeze_detail = {"causal_intelligence": causal_intelligence}
    elif squeeze_context and squeeze_context.get("available"):
        squeeze_detail = {
            "causal_intelligence": {
                "state": squeeze_context.get("squeeze_state"),
                "remaining_fuel": squeeze_context.get("remaining_squeeze_fuel"),
                "exhaustion_risk": squeeze_context.get("exhaustion_risk"),
            }
        }

    bundle, _ = build_opportunity_fusion_bundle(
        symbol,
        as_of_time,
        strategy_snapshot=strategy_snapshot,
        execution_snapshot=execution_snapshot,
        physical_forecast=physical_forecast,
        squeeze_context=squeeze_context,
        squeeze_detail=squeeze_detail,
        order_flow_payload=order_flow_payload,
        options_payload=options_payload,
        execution_friction=execution_friction,
        futures_payload=futures_payload,
    )
    return bundle["opportunity_snapshot"]


def build_workspace_opportunity_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
    squeeze_causal: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Build SHARED P4 opportunity fusion payload for workspace surfaces."""
    instrument_id = symbol.upper()
    causal = squeeze_causal if isinstance(squeeze_causal, dict) else _lightweight_squeeze_causal(
        instrument_id, prediction_cutoff
    )
    order_flow_payload = build_workspace_order_flow_payload(
        instrument_id,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    options_payload = build_workspace_options_payload(
        instrument_id,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
        squeeze_causal=causal if isinstance(causal, dict) else None,
    )
    from ..options.features.squeeze_context import build_squeeze_context_for_options

    squeeze_context = build_squeeze_context_for_options(causal if isinstance(causal, dict) else None)
    distribution = build_workspace_distribution_payload(
        instrument_id,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    physical_forecast = distribution.get("forecast") if distribution.get("available") else None
    strategy_snapshot = options_payload.get("strategy_snapshot")
    execution_snapshot = options_payload.get("execution_snapshot")
    execution_friction = options_payload.get("p_vs_q_executable_edge")
    if not isinstance(execution_friction, dict):
        from ..options.edge import estimate_execution_friction

        activities = options_payload.get("activities", [])
        execution_friction = estimate_execution_friction(activities if isinstance(activities, list) else [])

    futures_payload: dict[str, Any] | None = None
    if instrument_id == "ES":
        futures_payload = build_workspace_futures_payload(
            instrument_id,
            as_of_context=as_of_context,
            prediction_cutoff=prediction_cutoff,
        )

    as_of_time = ""
    if isinstance(strategy_snapshot, dict) and strategy_snapshot.get("as_of_time"):
        as_of_time = str(strategy_snapshot["as_of_time"])
    elif isinstance(options_payload.get("chain_snapshot"), dict):
        as_of_time = str(options_payload["chain_snapshot"].get("as_of_time", ""))

    opportunity_snapshot = _opportunity_snapshot_enrichment(
        instrument_id,
        as_of_time,
        strategy_snapshot=strategy_snapshot if isinstance(strategy_snapshot, dict) else None,
        execution_snapshot=execution_snapshot if isinstance(execution_snapshot, dict) else None,
        physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
        squeeze_context=squeeze_context,
        causal_intelligence=causal if isinstance(causal, dict) else None,
        order_flow_payload=order_flow_payload,
        options_payload=options_payload if isinstance(options_payload, dict) else None,
        execution_friction=execution_friction if isinstance(execution_friction, dict) else None,
        futures_payload=futures_payload if isinstance(futures_payload, dict) else None,
    )

    return {
        "as_of_context": as_of_context,
        "available": bool(opportunity_snapshot.get("available")),
        "disclaimer": (
            "Cross-lane EV fusion decomposes probability, payoff, costs, and liquidity. "
            "Not a trade recommendation."
        ),
        "opportunity_snapshot": opportunity_snapshot,
        "research_only": True,
        "symbol": instrument_id,
    }


def _options_dealer_enrichment(
    *,
    chain_available: bool,
    chain_enrichment: dict[str, Any],
    activities: list[dict[str, Any]],
    as_of_time: str = "",
) -> dict[str, Any]:
    from ..options.dealer import build_dealer_snapshot

    source_rows: list[dict[str, Any]] = []
    if chain_available and chain_enrichment.get("chain_contracts"):
        source_rows = [dict(row) for row in chain_enrichment["chain_contracts"] if isinstance(row, dict)]
    elif activities:
        source_rows = [dict(row) for row in activities if isinstance(row, dict)]
    dealer_snapshot = build_dealer_snapshot(source_rows, as_of_time=as_of_time)
    return {
        "dealer_snapshot": dealer_snapshot,
        "dealer_position_available": bool(dealer_snapshot.get("available")),
    }


def _enrich_options_chain_payload(
    symbol: str,
    *,
    prediction_cutoff: int,
) -> dict[str, Any]:
    """Fetch option chain via composition registry — PIT on event_time (chain provider)."""
    from ..contracts.options import OptionChainSnapshot, option_chain_snapshot_to_dict
    from ..contracts.options_quality import OptionQualityFlag
    from .composition import get_provider_composition

    provider = get_provider_composition().option_chain
    result = provider.fetch_chain(symbol.upper(), as_of_time_ns=prediction_cutoff)
    if result.status != "available" or not result.events:
        snapshot = OptionChainSnapshot(
            underlying_id=symbol.upper(),
            as_of_time="",
            contracts=(),
            chain_quality="UNAVAILABLE",
            provider_id=getattr(provider, "provider_id", ""),
            available=False,
            reason=result.reason_code or "OPTION_CHAIN_UNAVAILABLE",
        )
        return {
            "chain_available": False,
            "chain_snapshot": option_chain_snapshot_to_dict(snapshot),
        }

    contracts = [dict(event) for event in result.events]
    as_of_time = str(contracts[0].get("event_time", "")) if contracts else ""
    blocking = any(
        OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value in (contract.get("quality_flags") or [])
        for contract in contracts
    )
    chain_quality = "DEGRADED" if blocking else "GOOD"
    snapshot = OptionChainSnapshot(
        underlying_id=symbol.upper(),
        as_of_time=as_of_time,
        contracts=tuple(contracts),
        chain_quality=chain_quality,
        provider_id=result.provider_id,
        available=True,
    )
    return {
        "chain_available": True,
        "chain_snapshot": option_chain_snapshot_to_dict(snapshot),
        "chain_contracts": contracts,
    }


def build_workspace_options_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
    squeeze_causal: dict[str, object] | None = None,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    chain_enrichment = _enrich_options_chain_payload(instrument_id, prediction_cutoff=prediction_cutoff)
    chain_snapshot = chain_enrichment.get("chain_snapshot", {})
    chain_available = bool(chain_enrichment.get("chain_available"))
    chain_as_of_time = str(chain_snapshot.get("as_of_time", "")) if isinstance(chain_snapshot, dict) else ""
    dealer_fields = _options_dealer_enrichment(
        chain_available=chain_available,
        chain_enrichment=chain_enrichment,
        activities=[],
        as_of_time=chain_as_of_time,
    )
    event_vol_snapshot = _options_event_vol_enrichment(
        instrument_id,
        as_of_time=chain_as_of_time,
        chain_rows=chain_enrichment.get("chain_contracts", []) if chain_available else [],
        physical_forecast=None,
        squeeze_context=None,
    )
    strategy_snapshot = _options_strategy_enrichment(
        instrument_id,
        as_of_time=chain_as_of_time,
        chain_rows=chain_enrichment.get("chain_contracts", []) if chain_available else [],
        physical_forecast=None,
        p_vs_q_executable_edge=None,
        execution_friction=None,
    )
    execution_snapshot = _options_execution_enrichment(
        instrument_id,
        as_of_time=chain_as_of_time,
        chain_rows=chain_enrichment.get("chain_contracts", []) if chain_available else [],
        strategy_snapshot=strategy_snapshot,
    )
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "activities": [],
            "as_of_context": as_of_context,
            "available": False,
            "chain_available": chain_available,
            "chain_snapshot": chain_snapshot,
            "dealer_position_available": dealer_fields["dealer_position_available"],
            "dealer_snapshot": dealer_fields["dealer_snapshot"],
            "event_vol_snapshot": event_vol_snapshot,
            "strategy_snapshot": strategy_snapshot,
            "execution_snapshot": execution_snapshot,
            "disclaimer": "Options evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    activities = ledger.query_options_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not activities:
        from ..options.features.squeeze_context import build_squeeze_context_for_options

        causal = squeeze_causal if isinstance(squeeze_causal, dict) else _lightweight_squeeze_causal(
            instrument_id, prediction_cutoff
        )
        squeeze_context = build_squeeze_context_for_options(causal if isinstance(causal, dict) else None)
        distribution = build_workspace_distribution_payload(
            instrument_id,
            as_of_context=as_of_context,
            prediction_cutoff=prediction_cutoff,
        )
        physical_forecast = distribution.get("forecast") if distribution.get("available") else None
        chain_rows = (
            _chain_contracts_to_surface_activities(chain_enrichment["chain_contracts"])
            if chain_available and chain_enrichment.get("chain_contracts")
            else []
        )
        catalyst_times: list[str] = []
        if isinstance(physical_forecast, dict):
            for row in physical_forecast.get("catalyst_events", []):
                if isinstance(row, dict) and row.get("event_time"):
                    catalyst_times.append(str(row["event_time"]))
        event_vol_snapshot = _options_event_vol_enrichment(
            instrument_id,
            as_of_time=chain_as_of_time,
            chain_rows=chain_rows,
            physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
            squeeze_context=squeeze_context,
            catalyst_event_times=catalyst_times,
        )
        from ..options.edge import (
            apply_executable_edge,
            compare_physical_vs_risk_neutral,
            estimate_execution_friction,
        )
        from ..options.risk_neutral import infer_risk_neutral_distribution
        from ..options.surface import build_volatility_surface

        surface = build_volatility_surface(chain_rows) if chain_rows else {"available": False}
        risk_neutral_forecast = infer_risk_neutral_distribution(
            surface,
            symbol=instrument_id,
            as_of_time=chain_as_of_time,
        )
        p_vs_q_edge = compare_physical_vs_risk_neutral(
            physical_forecast if isinstance(physical_forecast, dict) else None,
            risk_neutral_forecast,
        )
        execution_friction = estimate_execution_friction(chain_rows)
        p_vs_q_executable_edge = apply_executable_edge(p_vs_q_edge, execution_friction)
        strategy_snapshot = _options_strategy_enrichment(
            instrument_id,
            as_of_time=chain_as_of_time,
            chain_rows=chain_rows,
            physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
            p_vs_q_executable_edge=p_vs_q_executable_edge,
            execution_friction=execution_friction,
            squeeze_context=squeeze_context,
        )
        execution_snapshot = _options_execution_enrichment(
            instrument_id,
            as_of_time=chain_as_of_time,
            chain_rows=chain_rows,
            strategy_snapshot=strategy_snapshot,
            execution_friction=execution_friction,
            squeeze_context=squeeze_context,
        )
        order_flow_payload = build_workspace_order_flow_payload(
            instrument_id,
            as_of_context=as_of_context,
            prediction_cutoff=prediction_cutoff,
        )
        opportunity_snapshot = _opportunity_snapshot_enrichment(
            instrument_id,
            chain_as_of_time,
            strategy_snapshot=strategy_snapshot,
            execution_snapshot=execution_snapshot,
            physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
            squeeze_context=squeeze_context,
            causal_intelligence=causal if isinstance(causal, dict) else None,
            order_flow_payload=order_flow_payload,
            execution_friction=execution_friction,
        )
        return {
            "activities": [],
            "as_of_context": as_of_context,
            "available": False,
            "chain_available": chain_available,
            "chain_snapshot": chain_snapshot,
            "dealer_position_available": dealer_fields["dealer_position_available"],
            "dealer_snapshot": dealer_fields["dealer_snapshot"],
            "event_vol_snapshot": event_vol_snapshot,
            "strategy_snapshot": strategy_snapshot,
            "execution_snapshot": execution_snapshot,
            "opportunity_snapshot": opportunity_snapshot,
            "p_vs_q_edge": p_vs_q_edge,
            "p_vs_q_executable_edge": p_vs_q_executable_edge,
            "disclaimer": "No PIT-eligible options events for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_OPTIONS",
            "research_only": True,
            "symbol": instrument_id,
        }

    from ..options.dealer import build_dealer_snapshot
    from ..options.edge import (
        apply_executable_edge,
        compare_physical_vs_risk_neutral,
        estimate_execution_friction,
    )
    from ..options.features.squeeze_context import build_squeeze_context_for_options
    from ..options.flow import build_flow_snapshot
    from ..options.risk_neutral import infer_risk_neutral_distribution
    from ..options.surface import build_volatility_surface
    from ..options.vrp import vrp_research_snapshot

    causal = squeeze_causal if isinstance(squeeze_causal, dict) else _lightweight_squeeze_causal(
        instrument_id, prediction_cutoff
    )
    squeeze_context = build_squeeze_context_for_options(causal if isinstance(causal, dict) else None)
    distribution = build_workspace_distribution_payload(
        instrument_id,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    physical_forecast = distribution.get("forecast") if distribution.get("available") else None

    surface_source: list[dict[str, Any]] = list(activities)
    canonical_contracts = [
        row.get("canonical_contract")
        for row in activities
        if isinstance(row, dict) and isinstance(row.get("canonical_contract"), dict)
    ]
    if chain_available and chain_enrichment.get("chain_contracts"):
        surface_source = _chain_contracts_to_surface_activities(chain_enrichment["chain_contracts"])
        canonical_contracts = list(chain_enrichment["chain_contracts"])

    surface = build_volatility_surface(surface_source)
    as_of_time = ""
    if surface_source and isinstance(surface_source[0], dict):
        as_of_time = str(surface_source[0].get("event_time", ""))
    risk_neutral_forecast = infer_risk_neutral_distribution(
        surface,
        symbol=instrument_id,
        as_of_time=as_of_time,
    )
    p_vs_q_edge = compare_physical_vs_risk_neutral(
        physical_forecast if isinstance(physical_forecast, dict) else None,
        risk_neutral_forecast,
    )
    execution_friction = estimate_execution_friction(activities)
    p_vs_q_executable_edge = apply_executable_edge(p_vs_q_edge, execution_friction)
    signed_flow_snapshot = build_flow_snapshot(activities, as_of_time=as_of_time)
    dealer_source = surface_source
    if chain_available and chain_enrichment.get("chain_contracts"):
        dealer_source = [dict(row) for row in chain_enrichment["chain_contracts"] if isinstance(row, dict)]
    dealer_snapshot = build_dealer_snapshot(dealer_source, as_of_time=as_of_time)

    catalyst_times: list[str] = []
    if isinstance(physical_forecast, dict):
        for row in physical_forecast.get("catalyst_events", []):
            if isinstance(row, dict) and row.get("event_time"):
                catalyst_times.append(str(row["event_time"]))
    event_vol_snapshot = _options_event_vol_enrichment(
        instrument_id,
        as_of_time=as_of_time or chain_as_of_time,
        chain_rows=surface_source,
        physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
        squeeze_context=squeeze_context,
        catalyst_event_times=catalyst_times,
    )
    vrp_research = vrp_research_snapshot(
        physical_forecast if isinstance(physical_forecast, dict) else None,
        risk_neutral_forecast,
        event_vol_snapshot=event_vol_snapshot,
    )
    strategy_snapshot = _options_strategy_enrichment(
        instrument_id,
        as_of_time=as_of_time or chain_as_of_time,
        chain_rows=surface_source,
        physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
        p_vs_q_executable_edge=p_vs_q_executable_edge,
        execution_friction=execution_friction,
        squeeze_context=squeeze_context,
    )
    execution_snapshot = _options_execution_enrichment(
        instrument_id,
        as_of_time=as_of_time or chain_as_of_time,
        chain_rows=surface_source,
        strategy_snapshot=strategy_snapshot,
        execution_friction=execution_friction,
        squeeze_context=squeeze_context,
    )
    order_flow_payload = build_workspace_order_flow_payload(
        instrument_id,
        as_of_context=as_of_context,
        prediction_cutoff=prediction_cutoff,
    )
    opportunity_snapshot = _opportunity_snapshot_enrichment(
        instrument_id,
        as_of_time or chain_as_of_time,
        strategy_snapshot=strategy_snapshot,
        execution_snapshot=execution_snapshot,
        physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
        squeeze_context=squeeze_context,
        causal_intelligence=causal if isinstance(causal, dict) else None,
        order_flow_payload=order_flow_payload,
        options_payload={
            "symbol": instrument_id,
            "available": True,
            "strategy_snapshot": strategy_snapshot,
            "activities": activities,
        },
        execution_friction=execution_friction,
    )

    return {
        "activities": activities,
        "activity_count": len(activities),
        "as_of_context": as_of_context,
        "available": True,
        "canonical_contracts": canonical_contracts,
        "chain_available": chain_available,
        "chain_snapshot": chain_snapshot,
        "dealer_position_available": bool(dealer_snapshot.get("available")),
        "dealer_snapshot": dealer_snapshot,
        "event_vol_snapshot": event_vol_snapshot,
        "strategy_snapshot": strategy_snapshot,
        "execution_snapshot": execution_snapshot,
        "opportunity_snapshot": opportunity_snapshot,
        "disclaimer": (
            "Unusual options volume is not directional intent. "
            "Direction labels remain ambiguous unless explicitly supported. "
            "Research-only per ADR-WHALE-004."
        ),
        "ledger_id": ledger.ledger_id,
        "p_vs_q_edge": p_vs_q_edge,
        "p_vs_q_executable_edge": p_vs_q_executable_edge,
        "provider_id": "options.fixture.activity",
        "research_only": True,
        "risk_neutral_forecast": risk_neutral_forecast,
        "signed_flow_snapshot": signed_flow_snapshot,
        "squeeze_context": squeeze_context,
        "symbol": instrument_id,
        "volatility_surface": surface,
        "vrp_research": vrp_research,
    }


def _lightweight_squeeze_causal(symbol: str, prediction_cutoff: int) -> dict[str, Any] | None:
    """Fetch squeeze causal state without cross-lane fusion (avoids circular feedback)."""
    del prediction_cutoff
    try:
        from ..donor_bridge.projections import DEFAULT_BASE_URL, fetch_frozen_candidate_detail, is_available

        if not is_available(base_url=DEFAULT_BASE_URL):
            return None
        detail = fetch_frozen_candidate_detail(symbol.upper(), base_url=DEFAULT_BASE_URL)
        causal = detail.get("causal_intelligence")
        return causal if isinstance(causal, dict) else None
    except (ConnectionError, ValueError, ImportError):
        return None


def build_workspace_large_transactions_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Large-transaction evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "prints": [],
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    prints = ledger.query_large_transaction_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not prints:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible large-transaction events for this symbol at replay cutoff.",
            "prints": [],
            "reason": "WHALE_NO_PIT_ELIGIBLE_LARGE_TRANSACTIONS",
            "research_only": True,
            "symbol": instrument_id,
        }
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "Large prints are size anomalies normalized to rolling volume or ADV. "
            "They are not directional intent or participant identity. "
            "Research-only per ADR-WHALE-005."
        ),
        "ledger_id": ledger.ledger_id,
        "print_count": len(prints),
        "prints": prints,
        "provider_id": "large_prints.fixture.activity",
        "research_only": True,
        "symbol": instrument_id,
    }


def _queue_summary_from_event(event_row: dict[str, Any]) -> dict[str, Any] | None:
    """Extract OF10 MBO queue fields from a ledger summary row."""
    if not event_row.get("mbo_capability_available"):
        return None
    return {
        "queue_method": event_row.get("queue_method"),
        "queue_version": event_row.get("queue_version"),
        "queue_imbalance_mbo": event_row.get("queue_imbalance_mbo"),
        "mbo_capability_available": event_row.get("mbo_capability_available"),
    }


def _liquidity_summary_from_event(event_row: dict[str, Any]) -> dict[str, Any] | None:
    """Extract OF6 liquidity dynamics fields from a ledger summary row."""
    if event_row.get("liquidity_method") is None and event_row.get("depth_withdrawal") is None:
        return None
    summary: dict[str, Any] = {
        "liquidity_method": event_row.get("liquidity_method"),
        "liquidity_version": event_row.get("liquidity_version"),
        "net_depth_delta": event_row.get("net_depth_delta"),
        "depth_withdrawal": event_row.get("depth_withdrawal"),
        "depth_replenishment": event_row.get("depth_replenishment"),
        "fragility_score": event_row.get("fragility_score"),
        "total_depth": event_row.get("total_depth"),
        "spread_delta": event_row.get("spread_delta"),
    }
    if event_row.get("resiliency_score") is not None:
        summary["resiliency_score"] = event_row.get("resiliency_score")
    return summary


def _impact_summary_from_event(event_row: dict[str, Any]) -> dict[str, Any] | None:
    """Extract OF7 impact dynamics fields from a ledger summary row."""
    if event_row.get("impact_method") is None and event_row.get("impact_regime") is None:
        return None
    summary: dict[str, Any] = {
        "impact_method": event_row.get("impact_method"),
        "impact_version": event_row.get("impact_version"),
        "mid_delta": event_row.get("mid_delta"),
        "impact_regime": event_row.get("impact_regime"),
        "opposing_replenishment": event_row.get("opposing_replenishment"),
    }
    if event_row.get("aggression_signed_volume") is not None:
        summary["aggression_signed_volume"] = event_row.get("aggression_signed_volume")
    if event_row.get("price_efficiency") is not None:
        summary["price_efficiency"] = event_row.get("price_efficiency")
    if event_row.get("absorption_score") is not None:
        summary["absorption_score"] = event_row.get("absorption_score")
    if event_row.get("exhaustion_score") is not None:
        summary["exhaustion_score"] = event_row.get("exhaustion_score")
    if event_row.get("impact_quality_flags") is not None:
        summary["impact_quality_flags"] = event_row.get("impact_quality_flags")
    return summary


def _microstructure_forecast_from_event(event_row: dict[str, Any]) -> dict[str, Any] | None:
    """Extract OF8 microstructure forecast fields from a ledger summary row."""
    if event_row.get("forecast_method") is None and event_row.get("direction_bias") is None:
        return None
    summary: dict[str, Any] = {
        "forecast_method": event_row.get("forecast_method"),
        "forecast_version": event_row.get("forecast_version"),
        "forecast_horizon_seconds": event_row.get("forecast_horizon_seconds"),
        "expected_mid_delta": event_row.get("expected_mid_delta"),
        "direction_bias": event_row.get("direction_bias"),
        "continuation_probability": event_row.get("continuation_probability"),
        "reversal_probability": event_row.get("reversal_probability"),
        "volatility_proxy": event_row.get("volatility_proxy"),
        "composite_bias": event_row.get("composite_bias"),
        "model_confidence": event_row.get("model_confidence"),
    }
    if event_row.get("forecast_quality_flags") is not None:
        summary["forecast_quality_flags"] = event_row.get("forecast_quality_flags")
    return summary


def _execution_forecast_from_event(event_row: dict[str, Any]) -> dict[str, Any] | None:
    """Extract OF9 execution forecast fields from a ledger summary row."""
    if event_row.get("execution_method") is None and event_row.get("aggressive_fill_probability") is None:
        return None
    summary: dict[str, Any] = {
        "execution_method": event_row.get("execution_method"),
        "execution_version": event_row.get("execution_version"),
        "book_model_version": event_row.get("book_model_version"),
        "queue_model_version": event_row.get("queue_model_version"),
        "aggressive_fill_probability": event_row.get("aggressive_fill_probability"),
        "passive_fill_probability": event_row.get("passive_fill_probability"),
        "expected_slippage_spread_fraction": event_row.get("expected_slippage_spread_fraction"),
        "expected_slippage_absolute": event_row.get("expected_slippage_absolute"),
        "adverse_selection_risk": event_row.get("adverse_selection_risk"),
        "touch_depth_bid": event_row.get("touch_depth_bid"),
        "touch_depth_ask": event_row.get("touch_depth_ask"),
        "displayed_depth_consumed_fraction": event_row.get("displayed_depth_consumed_fraction"),
    }
    if event_row.get("execution_quality_flags") is not None:
        summary["execution_quality_flags"] = event_row.get("execution_quality_flags")
    return summary


def build_workspace_order_book_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Order-book evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "snapshots": [],
            "symbol": instrument_id,
        }
    snapshots = ledger.query_order_book_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not snapshots:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible order-book snapshots for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_ORDER_BOOK",
            "research_only": True,
            "snapshots": [],
            "symbol": instrument_id,
        }
    latest = snapshots[-1]
    from ..order_flow.l1 import compute_l1_state

    l1_features: dict[str, object] | None = None
    best_bid = latest.get("best_bid")
    best_ask = latest.get("best_ask")
    bid_size = latest.get("bid_size")
    ask_size = latest.get("ask_size")
    if all(value is not None for value in (best_bid, best_ask, bid_size, ask_size)):
        l1_state = compute_l1_state(
            best_bid=float(best_bid),
            best_ask=float(best_ask),
            bid_size=float(bid_size),
            ask_size=float(ask_size),
        )
        if l1_state is not None:
            from ..order_flow.contracts import l1_state_to_dict

            l1_features = l1_state_to_dict(l1_state)
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "Visible liquidity and imbalance metrics are derived from admitted fixture snapshots. "
            "Resting bid/ask size is not aggressive flow or participant identity. "
            "Research-only per ADR-WHALE-006."
        ),
        "latest_imbalance_ratio": latest.get("imbalance_ratio"),
        "latest_l1": l1_features,
        "latest_ofi_value": latest.get("ofi_value"),
        "latest_ofi_method": latest.get("ofi_method"),
        "latest_ofi_version": latest.get("ofi_version"),
        "latest_book_state_valid": latest.get("book_state_valid"),
        "latest_liquidity_summary": _liquidity_summary_from_event(latest),
        "latest_impact_summary": _impact_summary_from_event(latest),
        "latest_microstructure_forecast": _microstructure_forecast_from_event(latest),
        "latest_execution_forecast": _execution_forecast_from_event(latest),
        "latest_queue_snapshot": _queue_summary_from_event(latest),
        "mbo_capability_available": latest.get("mbo_capability_available", False),
        "ledger_id": ledger.ledger_id,
        "provider_id": "depth.fixture.order_book",
        "research_only": True,
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "symbol": instrument_id,
    }


def _enrich_es_futures_f3_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F3 curve, basis, and carry for ES fixture chain."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.basis import basis_payload
    from ..futures.carry import carry_payload
    from ..futures.curve import build_curve_snapshot_from_chain, curve_snapshot_payload
    from .adapters.fixture_futures import FixtureFuturesProvider
    from .adapters.fixture_futures_chain import FixtureFuturesChainProvider
    from .composition import get_provider_composition

    chain_result = get_provider_composition().futures_chain.fetch_chain(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if chain_result.status != "available":
        chain_result = FixtureFuturesChainProvider().fetch_chain(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )
    chain = chain_result
    curve = curve_snapshot_payload(chain)
    payload["curve_snapshot"] = curve
    payload["futures_curve_available"] = curve.get("available", False)

    snapshot = build_curve_snapshot_from_chain(chain)
    fixture = FixtureFuturesProvider()._fixture
    spot_ref = fixture.get("spot_reference")
    spot_price = None
    spot_id = ""
    if isinstance(spot_ref, dict):
        spot_price = spot_ref.get("price")
        spot_id = str(spot_ref.get("id", ""))
    if snapshot is not None:
        if spot_price is not None:
            payload["basis_observation"] = basis_payload(
                snapshot,
                spot_price,
                spot_reference_id=spot_id,
            )
        else:
            payload["basis_observation"] = {"available": False, "reason": "BASIS_REFERENCE_MISSING"}
        payload["carry_observation"] = carry_payload(
            snapshot,
            spot_reference=spot_price,
        )
        payload["futures_carry_available"] = payload["carry_observation"].get("available", False)
    else:
        payload["basis_observation"] = {"available": False, "reason": "CURVE_SNAPSHOT_UNAVAILABLE"}
        payload["carry_observation"] = {"available": False, "reason": "CURVE_SNAPSHOT_UNAVAILABLE"}
        payload["futures_carry_available"] = False
    return _enrich_es_futures_f4_payload(payload, prediction_cutoff=prediction_cutoff)


def _enrich_es_futures_f4_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F4 COT positioning and OI velocity hypotheses for ES fixture."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.positioning import positioning_payload
    from .adapters.fixture_futures_positioning import FixtureFuturesPositioningProvider
    from .composition import get_provider_composition

    composition = get_provider_composition()
    positioning_result = composition.futures_positioning.fetch_positioning(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if positioning_result.status != "available":
        positioning_result = FixtureFuturesPositioningProvider().fetch_positioning(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )
    chain_result = composition.futures_chain.fetch_chain(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if chain_result.status != "available":
        from .adapters.fixture_futures_chain import FixtureFuturesChainProvider

        chain_result = FixtureFuturesChainProvider().fetch_chain(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )

    decision_time = prediction_cutoff if prediction_cutoff is not None else 0
    f4_payload = positioning_payload(
        positioning_result,
        chain_result,
        decision_time=decision_time,
    )
    payload["positioning_snapshot"] = f4_payload.get("positioning_snapshot")
    payload["futures_positioning_available"] = bool(f4_payload.get("futures_positioning_available"))
    payload["oi_velocity_hypothesis"] = f4_payload.get("oi_velocity_hypothesis")
    payload["crowding_regime"] = f4_payload.get("crowding_regime")
    if f4_payload.get("quality_flags"):
        payload["positioning_quality_flags"] = f4_payload.get("quality_flags")
    return _enrich_es_futures_f5_payload(payload, prediction_cutoff=prediction_cutoff)


def _enrich_es_futures_f5_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F5 trend/carry baselines for ES fixture."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.baselines import baselines_payload
    from ..futures.curve import build_curve_snapshot_from_chain
    from .adapters.fixture_futures_bars import FixtureFuturesBarsProvider
    from .adapters.fixture_futures_chain import FixtureFuturesChainProvider
    from .composition import get_provider_composition

    composition = get_provider_composition()
    bars_result = composition.futures_bars.fetch_bars(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if bars_result.status != "available":
        bars_result = FixtureFuturesBarsProvider().fetch_bars(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )

    chain_result = composition.futures_chain.fetch_chain(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if chain_result.status != "available":
        chain_result = FixtureFuturesChainProvider().fetch_chain(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )

    curve_snapshot = build_curve_snapshot_from_chain(chain_result)
    carry_observation = payload.get("carry_observation", {})
    if not isinstance(carry_observation, dict):
        carry_observation = {}

    decision_time = prediction_cutoff if prediction_cutoff is not None else 0
    f5_payload = baselines_payload(
        bars_result,
        curve_snapshot,
        carry_observation,
        decision_time=decision_time,
    )

    payload["trend_baseline_snapshot"] = f5_payload.get("trend_baseline_snapshot")
    payload["carry_baseline"] = f5_payload.get("carry_baseline")
    payload["curve_momentum"] = f5_payload.get("curve_momentum")
    payload["futures_baselines_available"] = bool(f5_payload.get("futures_baselines_available"))
    payload["trend_regime"] = f5_payload.get("trend_regime")
    if f5_payload.get("quality_flags"):
        payload["baselines_quality_flags"] = f5_payload.get("quality_flags")

    carry_baseline = f5_payload.get("carry_baseline")
    if isinstance(carry_baseline, dict) and carry_observation.get("available"):
        if carry_baseline.get("carry_percentile") is not None:
            carry_observation["carry_percentile"] = carry_baseline.get("carry_percentile")
        if carry_baseline.get("carry_change") is not None:
            carry_observation["carry_change"] = carry_baseline.get("carry_change")
        if carry_baseline.get("carry_zscore") is not None:
            carry_observation["carry_zscore"] = carry_baseline.get("carry_zscore")
        payload["carry_observation"] = carry_observation

    return _enrich_es_futures_f7_payload(payload, prediction_cutoff=prediction_cutoff)


def _enrich_es_futures_f7_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F7 macro event calendar for ES fixture."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.macro_events import macro_events_payload
    from .adapters.fixture_futures_macro import FixtureFuturesMacroEventsProvider
    from .composition import get_provider_composition

    composition = get_provider_composition()
    macro_result = composition.futures_macro.fetch_macro_events(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if macro_result.status != "available":
        macro_result = FixtureFuturesMacroEventsProvider().fetch_macro_events(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )

    decision_time = prediction_cutoff if prediction_cutoff is not None else 0
    f7_payload = macro_events_payload(
        macro_result,
        instrument_family="ES",
        decision_time=decision_time,
    )
    payload["macro_event_snapshot"] = f7_payload.get("macro_event_snapshot")
    payload["futures_macro_available"] = bool(f7_payload.get("futures_macro_available"))
    payload["macro_risk_regime"] = f7_payload.get("macro_risk_regime")
    payload["event_window_active"] = f7_payload.get("event_window_active")
    if f7_payload.get("quality_flags"):
        payload["macro_quality_flags"] = f7_payload.get("quality_flags")
    return _enrich_es_futures_f8_payload(payload, prediction_cutoff=prediction_cutoff)


def _enrich_es_futures_f8_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F8 leverage / liquidation stress for ES fixture."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.leverage_stress import leverage_stress_payload
    from .adapters.fixture_futures_margin import FixtureFuturesMarginProvider
    from .composition import get_provider_composition

    composition = get_provider_composition()
    margin_result = composition.futures_margin.fetch_margin(
        "ES",
        as_of_time_ns=prediction_cutoff,
    )
    if margin_result.status != "available":
        margin_result = FixtureFuturesMarginProvider().fetch_margin(
            "ES",
            as_of_time_ns=prediction_cutoff,
        )

    lead_price = None
    snapshots = payload.get("snapshots")
    if isinstance(snapshots, list) and snapshots:
        latest = snapshots[-1]
        if isinstance(latest, dict):
            best_bid = latest.get("best_bid")
            best_ask = latest.get("best_ask")
            if best_bid is not None and best_ask is not None:
                lead_price = (float(best_bid) + float(best_ask)) / 2.0
    if lead_price is None:
        curve = payload.get("curve_snapshot")
        if isinstance(curve, dict):
            prices = curve.get("prices")
            if isinstance(prices, list) and prices:
                lead_price = float(prices[0])

    fragility_score = None
    liquidity = payload.get("latest_liquidity_summary")
    if isinstance(liquidity, dict):
        raw_fragility = liquidity.get("fragility_score")
        if raw_fragility is not None:
            fragility_score = float(raw_fragility)

    decision_time = prediction_cutoff if prediction_cutoff is not None else 0
    f8_payload = leverage_stress_payload(
        margin_result,
        instrument_family="ES",
        decision_time=decision_time,
        crowding_regime=str(payload.get("crowding_regime", "")) or None,
        lead_price=lead_price,
        fragility_score=fragility_score,
    )
    payload["leverage_stress_snapshot"] = f8_payload.get("leverage_stress_snapshot")
    payload["futures_leverage_stress_available"] = bool(
        f8_payload.get("futures_leverage_stress_available")
    )
    payload["stress_regime"] = f8_payload.get("stress_regime")
    payload["long_liquidation_risk"] = f8_payload.get("long_liquidation_risk")
    payload["short_liquidation_risk"] = f8_payload.get("short_liquidation_risk")
    if f8_payload.get("quality_flags"):
        payload["leverage_quality_flags"] = f8_payload.get("quality_flags")
    return _enrich_es_futures_f6_payload(payload, prediction_cutoff=prediction_cutoff)


def _enrich_es_futures_f6_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F6 asset-family context for ES fixture."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.families.registry import family_context_payload

    macro_snapshot = payload.get("macro_event_snapshot")
    leverage_snapshot = payload.get("leverage_stress_snapshot")
    f6_payload = family_context_payload(
        "ES",
        payload,
        macro_snapshot=macro_snapshot if isinstance(macro_snapshot, dict) else None,
        leverage_snapshot=leverage_snapshot if isinstance(leverage_snapshot, dict) else None,
    )
    payload["family_context_snapshot"] = f6_payload.get("family_context_snapshot")
    payload["futures_family_available"] = bool(f6_payload.get("futures_family_available"))
    if f6_payload.get("missing_capabilities"):
        payload["family_missing_capabilities"] = f6_payload.get("missing_capabilities")
    return _enrich_es_futures_f9_payload(payload, prediction_cutoff=prediction_cutoff)


def _enrich_es_futures_f9_payload(
    payload: dict[str, Any],
    *,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Attach F9 relative-value spreads and MC6 macro surprise summaries for ES fixture."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.relative_value import relative_value_payload
    from ..futures.curve import build_curve_snapshot_from_chain
    from ..market_context.expectations import (
        build_fixture_surprise_pipeline,
        load_expectations_fixture,
        surprise_summary_to_dict,
    )
    from .adapters.fixture_futures_chain import FixtureFuturesChainProvider

    decision_time = prediction_cutoff if prediction_cutoff is not None else 0
    chain_result = FixtureFuturesChainProvider().fetch_chain(
        "ES",
        as_of_time_ns=decision_time,
    )
    curve_snapshot = build_curve_snapshot_from_chain(chain_result)
    rv_payload = relative_value_payload(
        curve_snapshot,
        chain_result,
        decision_time=decision_time,
    )
    payload["relative_value_snapshot"] = rv_payload.get("relative_value_snapshot")
    payload["futures_relative_value_available"] = bool(
        rv_payload.get("futures_relative_value_available")
    )
    if rv_payload.get("quality_flags"):
        payload["relative_value_quality_flags"] = rv_payload.get("quality_flags")

    if _DEFAULT_ES_MACRO_EXPECTATIONS_FIXTURE.is_file():
        macro_rows = load_expectations_fixture(_DEFAULT_ES_MACRO_EXPECTATIONS_FIXTURE)
        _, _, macro_summaries, _ = build_fixture_surprise_pipeline(
            macro_rows,
            prediction_cutoff=decision_time,
        )
        payload["macro_surprise_summaries"] = [
            surprise_summary_to_dict(item) for item in macro_summaries
        ]
        payload["macro_surprise_available"] = any(
            item.surprise_available for item in macro_summaries
        )
    return payload


def build_workspace_futures_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    from ..donor_bridge.futures_client import fetch_depth_latest, is_available as futures_bridge_available
    from ..errors import OfflineBoundaryViolation

    bridge_available = False
    try:
        bridge_available = futures_bridge_available()
    except (ConnectionError, OfflineBoundaryViolation, OSError):
        bridge_available = False

    if bridge_available:
        try:
            bridge = fetch_depth_latest()
            if bridge.get("available"):
                snap = bridge.get("snapshot", {})
                if isinstance(snap, dict):
                    from datetime import datetime

                    from ..donor_bridge.bridge_depth_state import resolve_bridge_ofi, update as update_bridge_depth
                    from ..donor_patterns.futures_lane import (
                        depth_imbalance_signal,
                        is_rth,
                        project_futures_depth,
                    )

                    bids = snap.get("bids", [])
                    asks = snap.get("asks", [])
                    if not isinstance(bids, list):
                        bids = []
                    if not isinstance(asks, list):
                        asks = []
                    signal, ratio = depth_imbalance_signal(bids, asks)
                    ofi_state = resolve_bridge_ofi(instrument_id, snap)
                    event_time = str(snap.get("event_time", ""))
                    if event_time:
                        try:
                            event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                        except ValueError:
                            event_dt = datetime.now()
                    else:
                        event_dt = datetime.now()
                    rth = is_rth(event_dt)
                    session_state = "RTH" if rth else "EXTENDED"
                    contract_month = str(bridge.get("contract_month", ""))
                    exchange = str(bridge.get("exchange", "CME"))
                    bridge_row = project_futures_depth(
                        symbol=instrument_id,
                        contract_month=contract_month,
                        exchange=exchange,
                        session_state=session_state,
                        snapshot=snap,
                        imbalance_ratio=ratio,
                        imbalance_signal=signal,
                        ofi_value=ofi_state["ofi_value"],
                        rth=rth,
                        ofi_method=ofi_state.get("ofi_method"),
                        ofi_version=ofi_state.get("ofi_version"),
                        book_state_valid=ofi_state.get("book_state_valid"),
                        ofi_degraded=ofi_state.get("ofi_degraded"),
                        ofi_quality_flags=ofi_state.get("ofi_quality_flags"),
                    )
                    bridge_row["event_time"] = event_time or None
                    update_bridge_depth(instrument_id, snap)
                    from ..order_flow.forecast import compute_microstructure_forecast

                    bridge_forecast = compute_microstructure_forecast(
                        snap,
                        ofi_value=float(ofi_state.get("ofi_value") or 0.0),
                        book_state_valid=ofi_state.get("book_state_valid"),
                        bar_delta=None,
                    )
                    bridge_forecast_summary = _microstructure_forecast_from_event(
                        {
                            "forecast_method": bridge_forecast.forecast_method,
                            "forecast_version": bridge_forecast.forecast_version,
                            "forecast_horizon_seconds": bridge_forecast.forecast_horizon_seconds,
                            "expected_mid_delta": bridge_forecast.expected_mid_delta,
                            "direction_bias": bridge_forecast.direction_bias.value,
                            "continuation_probability": bridge_forecast.continuation_probability,
                            "reversal_probability": bridge_forecast.reversal_probability,
                            "volatility_proxy": bridge_forecast.volatility_proxy,
                            "composite_bias": bridge_forecast.composite_bias,
                            "model_confidence": bridge_forecast.model_confidence,
                            "forecast_quality_flags": list(bridge_forecast.quality_flags),
                        }
                    )
                    from ..order_flow.execution_forecast import (
                        compute_execution_forecast,
                        execution_forecast_to_dict,
                    )

                    bridge_execution = compute_execution_forecast(
                        snap,
                        book_state_valid=ofi_state.get("book_state_valid"),
                        continuation_probability=bridge_forecast.continuation_probability,
                        reversal_probability=bridge_forecast.reversal_probability,
                        direction_bias=bridge_forecast.direction_bias,
                    )
                    bridge_execution_summary = _execution_forecast_from_event(
                        execution_forecast_to_dict(bridge_execution)
                    )
                else:
                    bridge_row = {}
                    signal = "neutral"
                    ratio = 0.0
                    ofi_state = {
                        "ofi_value": None,
                        "ofi_method": None,
                        "ofi_version": None,
                        "book_state_valid": False,
                        "ofi_degraded": True,
                        "ofi_quality_flags": ["INVALID_SNAPSHOT"],
                    }
                    session_state = "UNKNOWN"
                    bridge_forecast_summary = None
                    bridge_execution_summary = None
                return _enrich_es_futures_f3_payload(
                    {
                    "as_of_context": as_of_context,
                    "available": True,
                    "canonical_family": "futures_depth",
                    "contract_month": bridge.get("contract_month"),
                    "disclaimer": (
                        "Live donor-bridge ES depth snapshot. Not admitted into canonical replay. "
                        "Research-only."
                    ),
                    "exchange": bridge.get("exchange", "CME"),
                    "latest_book_state_valid": ofi_state.get("book_state_valid"),
                    "latest_imbalance_ratio": bridge_row.get("imbalance_ratio", ratio) if bridge_row else ratio,
                    "latest_imbalance_signal": bridge_row.get("imbalance_signal", signal) if bridge_row else signal,
                    "latest_ofi_degraded": ofi_state.get("ofi_degraded"),
                    "latest_ofi_method": ofi_state.get("ofi_method"),
                    "latest_ofi_quality_flags": ofi_state.get("ofi_quality_flags"),
                    "latest_ofi_value": ofi_state.get("ofi_value"),
                    "latest_ofi_version": ofi_state.get("ofi_version"),
                    "latest_microstructure_forecast": bridge_forecast_summary,
                    "latest_execution_forecast": bridge_execution_summary,
                    "legacy_whale_family": "futures_positioning",
                    "provenance": "donor_bridge",
                    "provider_id": "futuresx.donor_bridge",
                    "research_only": True,
                    "session_state": bridge_row.get("session_state", session_state) if bridge_row else session_state,
                    "snapshot": snap,
                    "snapshot_count": 1 if bridge_row else 0,
                    "snapshots": [bridge_row] if bridge_row else [],
                    "symbol": instrument_id,
                    }
                , prediction_cutoff=prediction_cutoff)
        except (ConnectionError, ValueError, OfflineBoundaryViolation, OSError):
            pass
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Futures depth evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "snapshots": [],
            "symbol": instrument_id,
        }
    snapshots = ledger.query_futures_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not snapshots:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible futures depth snapshots for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_FUTURES",
            "research_only": True,
            "snapshots": [],
            "symbol": instrument_id,
        }
    latest = snapshots[-1]
    payload = {
        "as_of_context": as_of_context,
        "available": True,
        "book_pressure_side": latest.get("book_pressure_side"),
        "canonical_family": "futures_depth",
        "contract_month": latest.get("contract_month"),
        "data_kind": latest.get("data_kind", "depth_derived"),
        "disclaimer": (
            "ES depth and imbalance signals are derived from admitted synthetic fixture snapshots. "
            "Legacy whale family futures_positioning is depth-derived, not CFTC positioning. "
            "Research-only per ADR-DATA-002."
        ),
        "exchange": latest.get("exchange", "CME"),
        "interpretation_policy": latest.get("interpretation_policy"),
        "latest_book_pressure_side": latest.get("book_pressure_side"),
        "latest_imbalance_ratio": latest.get("imbalance_ratio"),
        "latest_imbalance_signal": latest.get("imbalance_signal"),
        "latest_ofi_value": latest.get("ofi_value"),
        "latest_ofi_method": latest.get("ofi_method"),
        "latest_ofi_version": latest.get("ofi_version"),
        "latest_book_state_valid": latest.get("book_state_valid"),
        "latest_liquidity_summary": _liquidity_summary_from_event(latest),
        "latest_impact_summary": _impact_summary_from_event(latest),
        "latest_microstructure_forecast": _microstructure_forecast_from_event(latest),
        "latest_execution_forecast": _execution_forecast_from_event(latest),
        "latest_queue_snapshot": _queue_summary_from_event(latest),
        "mbo_capability_available": latest.get("mbo_capability_available", False),
        "legacy_whale_family": "futures_positioning",
        "ledger_id": ledger.ledger_id,
        "provenance": "fixture",
        "provider_id": "depth.fixture.futures",
        "research_only": True,
        "session_state": latest.get("session_state"),
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "symbol": instrument_id,
        "synthetic": True,
    }
    return _enrich_es_futures_f3_payload(payload, prediction_cutoff=prediction_cutoff)


def build_workspace_catalyst_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    if market_context_available(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    ):
        mc_payload = build_workspace_market_context_payload(
            instrument_id,
            as_of_context=as_of_context,
            prediction_cutoff=prediction_cutoff,
        )
        if mc_payload.get("catalyst_available"):
            adapter_rows = mc_payload.get("catalyst_adapter_rows") or []
            gated = [row for row in adapter_rows if isinstance(row, dict) and row.get("gate_ok")]
            latest = gated[-1] if gated else (adapter_rows[-1] if adapter_rows else None)
            thesis = mc_payload.get("thesis_invalidation_evidence")
            return {
                "as_of_context": as_of_context,
                "available": True,
                "catalyst_count": len(adapter_rows),
                "catalysts": adapter_rows,
                "catalyst_evidence": mc_payload.get("catalyst_evidence") or [],
                "catalyst_summaries": mc_payload.get("catalyst_summaries") or [],
                "thesis_invalidation_evidence": thesis,
                "attention_available": mc_payload.get("attention_available", False),
                "attention_summaries": mc_payload.get("attention_summaries") or [],
                "attention_evidence": mc_payload.get("attention_evidence") or [],
                "attention_adapter_rows": mc_payload.get("attention_adapter_rows") or [],
                "disclaimer": (
                    "MC8 CatalystEvidence fuses MC6–MC7 components with exposed scores. "
                    "MC9 AttentionEvidence separates information value from reflexive impact. "
                    "Not a trade recommendation. Research-only per MC8–MC9 design spec."
                ),
                "latest_confidence": latest.get("confidence") if isinstance(latest, dict) else None,
                "latest_gate_ok": latest.get("gate_ok") if isinstance(latest, dict) else None,
                "provider_id": "market_context.catalyst",
                "research_only": True,
                "symbol": instrument_id,
                "source": "mc9_fixture_pipeline",
            }

    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "catalysts": [],
            "disclaimer": "Public catalyst evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    catalysts = ledger.query_catalyst_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not catalysts:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "catalysts": [],
            "disclaimer": "No PIT-eligible catalyst events for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_CATALYST",
            "research_only": True,
            "symbol": instrument_id,
        }
    latest = catalysts[-1]
    return {
        "as_of_context": as_of_context,
        "available": True,
        "catalyst_count": len(catalysts),
        "catalysts": catalysts,
        "disclaimer": (
            "Catalyst confidence and lean are inferred from admitted fixture signals. "
            "They are not trade recommendations or paper execution state. "
            "Research-only per ADR-WHALE-007."
        ),
        "latest_confidence": latest.get("confidence"),
        "latest_gate_ok": latest.get("gate_ok"),
        "latest_headline": latest.get("headline"),
        "latest_lean": latest.get("lean"),
        "ledger_id": ledger.ledger_id,
        "provider_id": "catalyst.fixture.activity",
        "research_only": True,
        "symbol": instrument_id,
    }


def build_workspace_fund_etf_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "Fund/ETF cross-asset evidence not entitled. Fail-closed per ADR-WHALE-001.",
            "events": [],
            "reason": "WHALE_NO_ENTITLED_SOURCE",
            "research_only": True,
            "symbol": instrument_id,
        }
    events = ledger.query_fund_etf_summaries(
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    if not events:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible fund/ETF events for this symbol at replay cutoff.",
            "events": [],
            "reason": "WHALE_NO_PIT_ELIGIBLE_FUND_ETF",
            "research_only": True,
            "symbol": instrument_id,
        }
    latest = events[-1]
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "ETF flow proxies and cross-asset context are derived from admitted synthetic fixture rows. "
            "They are not live fund-flow feeds or trade recommendations. "
            "Research-only per ADR-WHALE-008."
        ),
        "event_count": len(events),
        "events": events,
        "latest_correlation_20d": latest.get("correlation_20d"),
        "latest_flow_proxy_ratio": latest.get("flow_proxy_ratio"),
        "latest_regime_label": latest.get("regime_label"),
        "ledger_id": ledger.ledger_id,
        "provider_id": "fund_etf.fixture.activity",
        "research_only": True,
        "symbol": instrument_id,
    }


def build_workspace_distribution_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Physical distribution forecast from admitted fixture bars (SHARED P2)."""
    del prediction_cutoff
    instrument_id = symbol.upper()
    from .adapters.fixture_distribution import FixtureDistributionForecastProvider

    provider = FixtureDistributionForecastProvider()
    result = provider.fetch_distribution_forecast(instrument_id)
    if result.status != "available" or not result.events:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": (
                "Physical distribution forecast unavailable for this symbol. "
                "Fail-closed per SHARED P2."
            ),
            "forecast": None,
            "reason": result.reason_code or "DISTRIBUTION_NOT_AVAILABLE",
            "research_only": True,
            "symbol": instrument_id,
        }
    forecast = result.events[0]
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "Physical (P) return distribution forecasts are platform-owned baselines. "
            "Not mixed with risk-neutral (Q) inference. Research-only."
        ),
        "forecast": forecast,
        "provider_id": provider.provider_id,
        "research_only": True,
        "symbol": instrument_id,
    }


_DEFAULT_MC_RAW_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_raw_documents_slice.json"
)
_DEFAULT_MC_FINBERT_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_finbert_labels_slice.json"
)
_DEFAULT_MC_LLM_EXTRACTION_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_llm_extraction_slice.json"
)
_DEFAULT_MC_STRUCTURED_METRICS_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_structured_metrics_slice.json"
)
_DEFAULT_MC_EXPECTATIONS_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_expectations_slice.json"
)
_DEFAULT_ES_MACRO_EXPECTATIONS_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "es_macro_expectations_slice.json"
)
_MC_FIXTURE_SYMBOL = "BOXL"


def market_context_available(*, instrument_id: str, prediction_cutoff: int) -> bool:
    """True when admitted MC4 fixture sentiment is available for the symbol."""
    if instrument_id.upper() != _MC_FIXTURE_SYMBOL:
        return False
    if not _DEFAULT_MC_RAW_FIXTURE.is_file():
        return False
    return prediction_cutoff > 0


def build_workspace_market_context_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
) -> dict[str, Any]:
    """Build MC4–MC12 market context workspace payload (BOXL fixture scope)."""
    from ..market_context.entity_resolution import (
        build_symbol_mapping_registry,
        load_context_document_records,
    )
    from ..market_context.extraction import (
        PRODUCER_VERSION as EXTRACTION_PRODUCER_VERSION,
        build_fixture_extraction_pipeline,
        document_extraction_to_dict,
        event_extraction_summary_to_dict,
        load_llm_extraction_fixture,
        load_structured_metrics_fixture,
    )
    from ..market_context.sentiment import (
        PRODUCER_VERSION,
        build_fixture_sentiment_pipeline,
        build_sentiment_cross_lane_evidence,
        load_finbert_fixture_labels,
    )
    from ..market_context.expectations import (
        PRODUCER_VERSION as EXPECTATIONS_PRODUCER_VERSION,
        build_fixture_surprise_pipeline,
        build_surprise_cross_lane_evidence,
        load_expectations_fixture,
        surprise_summary_to_dict,
    )
    from ..market_context.impact_components import (
        PRODUCER_VERSION as IMPACT_PRODUCER_VERSION,
        build_fixture_impact_pipeline,
        build_impact_cross_lane_evidence,
        impact_component_summary_to_dict,
    )
    from ..market_context.catalyst import (
        PRODUCER_VERSION as CATALYST_PRODUCER_VERSION,
        build_catalyst_cross_lane_evidence,
        build_fixture_catalyst_pipeline,
        catalyst_summary_to_dict,
        short_thesis_invalidation_to_dict,
    )
    from ..market_context.attention import (
        PRODUCER_VERSION as ATTENTION_PRODUCER_VERSION,
        build_attention_cross_lane_evidence,
        build_fixture_attention_pipeline,
        attention_summary_to_dict,
    )
    from ..market_context.narrative import (
        PRODUCER_VERSION as NARRATIVE_PRODUCER_VERSION,
        build_fixture_narrative_pipeline,
        build_narrative_cross_lane_evidence,
        narrative_summary_to_dict,
    )
    from ..market_context.reaction import (
        PRODUCER_VERSION as REACTION_PRODUCER_VERSION,
        build_fixture_reaction_pipeline,
        build_reaction_cross_lane_evidence,
        load_reaction_fixture,
        reaction_summary_to_dict,
    )
    from ..market_context.macro import (
        PRODUCER_VERSION as MACRO_PRODUCER_VERSION,
        build_fixture_macro_pipeline,
        build_macro_cross_lane_evidence,
        load_macro_context_fixture,
        macro_summary_to_dict,
    )
    from ..contracts.market_context import (
        attention_evidence_to_dict,
        catalyst_evidence_to_dict,
        credibility_evidence_to_dict,
        expectation_snapshot_to_dict,
        macro_context_evidence_to_dict,
        market_reaction_evidence_to_dict,
        materiality_evidence_to_dict,
        narrative_evidence_to_dict,
        novelty_evidence_to_dict,
        surprise_evidence_to_dict,
    )

    instrument_id = symbol.upper()
    if instrument_id != _MC_FIXTURE_SYMBOL:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "baseline_sentiment_available": False,
            "disclaimer": (
                "Baseline financial sentiment is admitted on BOXL fixture scope only. "
                "Semantic labels are not trade direction or catalyst strength."
            ),
            "document_extractions": [],
            "document_sentiments": [],
            "event_extraction_summaries": [],
            "event_extraction_available": False,
            "event_sentiment_summaries": [],
            "impact_component_summaries": [],
            "impact_components_available": False,
            "credibility_evidence": [],
            "materiality_evidence": [],
            "novelty_evidence": [],
            "reason": "MARKET_CONTEXT_FIXTURE_SYMBOL_UNSUPPORTED",
            "research_only": True,
            "symbol": instrument_id,
        }

    if not _DEFAULT_MC_RAW_FIXTURE.is_file():
        return {
            "as_of_context": as_of_context,
            "available": False,
            "baseline_sentiment_available": False,
            "disclaimer": "Market context fixture not found. Fail-closed.",
            "document_extractions": [],
            "document_sentiments": [],
            "event_extraction_summaries": [],
            "event_extraction_available": False,
            "event_sentiment_summaries": [],
            "impact_component_summaries": [],
            "impact_components_available": False,
            "credibility_evidence": [],
            "materiality_evidence": [],
            "novelty_evidence": [],
            "reason": "MARKET_CONTEXT_FIXTURE_MISSING",
            "research_only": True,
            "symbol": instrument_id,
        }

    finbert_labels: dict[str, object] = {}
    if _DEFAULT_MC_FINBERT_FIXTURE.is_file():
        finbert_labels = load_finbert_fixture_labels(_DEFAULT_MC_FINBERT_FIXTURE)

    records = load_context_document_records(
        _DEFAULT_MC_RAW_FIXTURE,
        symbol_mappings=build_symbol_mapping_registry(instrument_id),
    )
    llm_labels: dict[str, object] = {}
    if _DEFAULT_MC_LLM_EXTRACTION_FIXTURE.is_file():
        llm_labels = load_llm_extraction_fixture(_DEFAULT_MC_LLM_EXTRACTION_FIXTURE)

    structured_metrics: dict[str, object] = {}
    if _DEFAULT_MC_STRUCTURED_METRICS_FIXTURE.is_file():
        structured_metrics = load_structured_metrics_fixture(
            _DEFAULT_MC_STRUCTURED_METRICS_FIXTURE
        )

    extraction_results, enriched_events, extraction_summaries = build_fixture_extraction_pipeline(
        records,
        prediction_cutoff=prediction_cutoff,
        llm_labels=llm_labels,
        structured_metrics=structured_metrics,
    )

    document_results, events, event_summaries = build_fixture_sentiment_pipeline(
        records,
        prediction_cutoff=prediction_cutoff,
        finbert_labels=finbert_labels,
    )
    if not document_results:
        return {
            "as_of_context": as_of_context,
            "available": False,
            "baseline_sentiment_available": False,
            "disclaimer": "No PIT-eligible documents for baseline sentiment at replay cutoff.",
            "document_extractions": [],
            "document_sentiments": [],
            "event_extraction_summaries": [],
            "event_extraction_available": False,
            "event_sentiment_summaries": [],
            "impact_component_summaries": [],
            "impact_components_available": False,
            "credibility_evidence": [],
            "materiality_evidence": [],
            "novelty_evidence": [],
            "reason": "MARKET_CONTEXT_NO_PIT_ELIGIBLE_DOCUMENTS",
            "research_only": True,
            "symbol": instrument_id,
        }

    document_sentiments = [
        {
            "document_id": item.document_id,
            "keyword": baseline_sentiment_to_dict(item.keyword) if item.keyword else None,
            "finbert": baseline_sentiment_to_dict(item.finbert) if item.finbert else None,
            "targeted": (
                {
                    "entity_id": item.targeted.entity_id,
                    "label": item.targeted.label.value,
                    "confidence": item.targeted.confidence,
                    "uncertainty_score": item.targeted.uncertainty_score,
                }
                if item.targeted
                else None
            ),
        }
        for item in document_results
    ]
    event_sentiment_summaries = [
        {
            "event_id": summary.event_id,
            "canonical_event_type": summary.canonical_event_type,
            "document_count": summary.document_count,
            "keyword": baseline_sentiment_to_dict(summary.keyword) if summary.keyword else None,
            "finbert": baseline_sentiment_to_dict(summary.finbert) if summary.finbert else None,
        }
        for summary in event_summaries
    ]
    event_extraction_summaries = [
        event_extraction_summary_to_dict(summary) for summary in extraction_summaries
    ]
    document_extractions = [
        document_extraction_to_dict(item) for item in extraction_results
    ]
    cross_lane_evidence = build_sentiment_cross_lane_evidence(
        event_summaries,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )

    expectation_rows: list = []
    if _DEFAULT_MC_EXPECTATIONS_FIXTURE.is_file():
        expectation_rows = load_expectations_fixture(_DEFAULT_MC_EXPECTATIONS_FIXTURE)
    expectations, surprises, surprise_summaries, _ = build_fixture_surprise_pipeline(
        expectation_rows,
        prediction_cutoff=prediction_cutoff,
    )
    surprise_cross_lane = build_surprise_cross_lane_evidence(
        surprises,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + surprise_cross_lane

    novelty_rows, materiality_rows, credibility_rows, impact_summaries = (
        build_fixture_impact_pipeline(
            records,
            enriched_events,
            prediction_cutoff=prediction_cutoff,
            surprise_summaries=surprise_summaries,
        )
    )
    impact_cross_lane = build_impact_cross_lane_evidence(
        impact_summaries,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + impact_cross_lane

    catalyst_evidence, catalyst_summaries, thesis_invalidation, catalyst_adapter_rows = (
        build_fixture_catalyst_pipeline(
            impact_summaries,
            prediction_cutoff=prediction_cutoff,
            entity_id=instrument_id,
        )
    )
    catalyst_cross_lane = build_catalyst_cross_lane_evidence(
        catalyst_summaries,
        thesis_invalidation,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + catalyst_cross_lane

    attention_evidence, attention_summaries, attention_adapter_rows = (
        build_fixture_attention_pipeline(
            enriched_events,
            catalyst_summaries,
            prediction_cutoff=prediction_cutoff,
            entity_id=instrument_id,
        )
    )
    attention_cross_lane = build_attention_cross_lane_evidence(
        attention_summaries,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + attention_cross_lane

    narrative_evidence, narrative_summaries, narrative_adapter_rows = (
        build_fixture_narrative_pipeline(
            catalyst_summaries,
            event_summaries,
            prediction_cutoff=prediction_cutoff,
            entity_id=instrument_id,
        )
    )
    narrative_cross_lane = build_narrative_cross_lane_evidence(
        narrative_summaries,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + narrative_cross_lane

    reaction_fixture_path = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "market_context"
        / "boxl_reaction_slice.json"
    )
    reaction_fixture = (
        load_reaction_fixture(reaction_fixture_path)
        if reaction_fixture_path.is_file()
        else {}
    )
    reaction_evidence, reaction_summaries, reaction_adapter_rows = (
        build_fixture_reaction_pipeline(
            catalyst_summaries,
            surprise_summaries,
            reaction_fixture,
            prediction_cutoff=prediction_cutoff,
            entity_id=instrument_id,
        )
    )
    reaction_cross_lane = build_reaction_cross_lane_evidence(
        reaction_summaries,
        symbol=instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + reaction_cross_lane
    reaction_contradictions = [
        reaction_summary_to_dict(item)
        for item in reaction_summaries
        if item.reaction_mismatch
    ]

    macro_fixture_path = (
        Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "market_context"
        / "boxl_macro_context_slice.json"
    )
    macro_events = (
        load_macro_context_fixture(macro_fixture_path)
        if macro_fixture_path.is_file()
        else []
    )
    macro_evidence, macro_summary, macro_adapter_row = build_fixture_macro_pipeline(
        macro_events,
        prediction_cutoff=prediction_cutoff,
    )
    macro_cross_lane = build_macro_cross_lane_evidence(
        macro_summary,
        prediction_cutoff=prediction_cutoff,
    )
    cross_lane_evidence = list(cross_lane_evidence) + macro_cross_lane

    from ..runtime.catalyst_attention import (
        CatalystAttentionRuntime,
        catalyst_attention_snapshot_to_dict,
    )
    from ..runtime.corporate_events import (
        CorporateEventRegistry,
        corporate_event_to_dict,
    )

    corporate_registry = CorporateEventRegistry.from_extraction_summaries(
        [
            {
                "event_id": item.event_id,
                "canonical_event_type": item.canonical_event_type,
                "event_time": item.event_time,
                "available_time": item.available_time,
            }
            for item in catalyst_summaries
        ],
        instrument_id=instrument_id,
    )
    corporate_events = corporate_registry.query_events(
        instrument_id,
        prediction_cutoff=prediction_cutoff,
    )
    catalyst_runtime = CatalystAttentionRuntime().build_snapshot(
        [attention_summary_to_dict(item) for item in attention_summaries],
        instrument_id=instrument_id,
        catalyst_summaries=[catalyst_summary_to_dict(item) for item in catalyst_summaries],
    )

    return {
        "as_of_context": as_of_context,
        "available": True,
        "baseline_sentiment_available": True,
        "cross_lane_evidence": cross_lane_evidence,
        "disclaimer": (
            "BaselineFinancialSentiment is semantic tone only — not economic surprise, "
            "catalyst strength, or trade recommendation. MC5 event extraction provides typed "
            "facts and metrics only — not surprise or trade direction. MC6 SurpriseEvidence "
            "is fail-closed when consensus is missing. MC7 impact components expose novelty, "
            "materiality, and credibility separately. MC8 fuses components into CatalystEvidence "
            "with exposed scores. MC9 separates attention diffusion from information value. "
            "MC10 narrative intelligence is experimental — validate before model decisions. "
            "MC12 classifies market reaction confirmation/contradiction from admitted fixtures "
            "without reimplementing CVD/IV. MC11 publishes shared macro regime context; "
            "Futures F7 owns calendar risk interpretation. "
            "Keyword-v1 runs in stdlib; FinBERT and LLM extractions are fixture-precomputed. "
            "Research-only per MC4–MC12."
        ),
        "document_count": len(document_results),
        "document_extractions": document_extractions,
        "document_sentiments": document_sentiments,
        "event_cluster_count": len(enriched_events),
        "event_extraction_available": bool(extraction_results),
        "event_extraction_summaries": event_extraction_summaries,
        "event_sentiment_summaries": event_sentiment_summaries,
        "expectation_snapshots": [
            expectation_snapshot_to_dict(item) for item in expectations
        ],
        "expectations_available": bool(expectations),
        "expectations_producer_id": "market_context.expectations",
        "expectations_producer_version": EXPECTATIONS_PRODUCER_VERSION,
        "extraction_document_count": len(extraction_results),
        "extraction_producer_id": "market_context.extraction",
        "extraction_producer_version": EXTRACTION_PRODUCER_VERSION,
        "impact_component_summaries": [
            impact_component_summary_to_dict(item) for item in impact_summaries
        ],
        "impact_components_available": bool(impact_summaries),
        "impact_producer_id": "market_context.impact_components",
        "impact_producer_version": IMPACT_PRODUCER_VERSION,
        "catalyst_available": bool(catalyst_summaries),
        "catalyst_count": len(catalyst_summaries),
        "catalyst_evidence": [
            catalyst_evidence_to_dict(item) for item in catalyst_evidence
        ],
        "catalyst_producer_id": "market_context.catalyst",
        "catalyst_producer_version": CATALYST_PRODUCER_VERSION,
        "catalyst_summaries": [
            catalyst_summary_to_dict(item) for item in catalyst_summaries
        ],
        "catalyst_adapter_rows": catalyst_adapter_rows,
        "catalyst_attention_runtime": catalyst_attention_snapshot_to_dict(catalyst_runtime),
        "catalyst_runtime_available": catalyst_runtime.runtime_available,
        "corporate_event_registry": [
            corporate_event_to_dict(item) for item in corporate_events
        ],
        "corporate_event_registry_available": bool(corporate_events),
        "thesis_invalidation_evidence": (
            short_thesis_invalidation_to_dict(thesis_invalidation)
            if thesis_invalidation
            else None
        ),
        "attention_available": bool(attention_summaries),
        "attention_count": len(attention_summaries),
        "attention_evidence": [
            attention_evidence_to_dict(item) for item in attention_evidence
        ],
        "attention_producer_id": "market_context.attention",
        "attention_producer_version": ATTENTION_PRODUCER_VERSION,
        "attention_summaries": [
            attention_summary_to_dict(item) for item in attention_summaries
        ],
        "attention_adapter_rows": attention_adapter_rows,
        "narrative_available": bool(narrative_summaries),
        "narrative_count": len(narrative_summaries),
        "narrative_evidence": [
            narrative_evidence_to_dict(item) for item in narrative_evidence
        ],
        "narrative_producer_id": "market_context.narrative",
        "narrative_producer_version": NARRATIVE_PRODUCER_VERSION,
        "narrative_summaries": [
            narrative_summary_to_dict(item) for item in narrative_summaries
        ],
        "narrative_adapter_rows": narrative_adapter_rows,
        "reaction_available": bool(reaction_summaries),
        "reaction_count": len(reaction_summaries),
        "reaction_evidence": [
            market_reaction_evidence_to_dict(item) for item in reaction_evidence
        ],
        "reaction_producer_id": "market_context.reaction",
        "reaction_producer_version": REACTION_PRODUCER_VERSION,
        "reaction_summaries": [
            reaction_summary_to_dict(item) for item in reaction_summaries
        ],
        "reaction_adapter_rows": reaction_adapter_rows,
        "reaction_contradictions": reaction_contradictions,
        "macro_context_available": macro_summary.macro_context_available,
        "macro_context_evidence": macro_context_evidence_to_dict(macro_evidence),
        "macro_context_summary": macro_summary_to_dict(macro_summary),
        "macro_context_adapter_row": macro_adapter_row,
        "macro_context_producer_id": "market_context.macro",
        "macro_context_producer_version": MACRO_PRODUCER_VERSION,
        "credibility_evidence": [
            credibility_evidence_to_dict(item) for item in credibility_rows
        ],
        "materiality_evidence": [
            materiality_evidence_to_dict(item) for item in materiality_rows
        ],
        "novelty_evidence": [novelty_evidence_to_dict(item) for item in novelty_rows],
        "prediction_cutoff_ns": prediction_cutoff,
        "producer_id": "market_context.sentiment",
        "producer_version": PRODUCER_VERSION,
        "research_only": True,
        "surprise_available": bool(surprises),
        "surprise_count": len(surprises),
        "surprise_evidence": [surprise_evidence_to_dict(item) for item in surprises],
        "surprise_summaries": [
            surprise_summary_to_dict(item) for item in surprise_summaries
        ],
        "symbol": instrument_id,
    }


__all__ = [
    "build_workspace_catalyst_payload",
    "build_workspace_disclosure_payload",
    "build_workspace_distribution_payload",
    "build_workspace_fund_etf_payload",
    "build_workspace_futures_payload",
    "build_workspace_large_transactions_payload",
    "build_workspace_market_context_payload",
    "build_workspace_opportunity_payload",
    "build_workspace_options_payload",
    "build_workspace_order_book_payload",
    "build_workspace_order_flow_payload",
    "catalyst_available",
    "disclosure_available",
    "fund_etf_available",
    "futures_available",
    "large_transactions_available",
    "market_context_available",
    "options_available",
    "order_book_available",
    "order_flow_available",
]

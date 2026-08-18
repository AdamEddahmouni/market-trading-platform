"""Read-only disclosure and order-flow projections for UI-001."""

from __future__ import annotations

from typing import Any

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
    return {
        "as_of_context": as_of_context,
        "available": True,
        "disclaimer": (
            "SEC filings are delayed public disclosures, not a live tape. "
            "Research-only per ADR-WHALE-001."
        ),
        "disclosure_lag_note": "SEC filings are delayed public disclosures, not a live tape.",
        "events": events,
        "event_count": len(events),
        "ledger_id": ledger.ledger_id,
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
    return {
        "as_of_context": as_of_context,
        "available": True,
        "bars": bars,
        "bar_count": len(bars),
        "cvd_summary": cvd_summary,
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


def build_workspace_options_payload(
    symbol: str,
    *,
    as_of_context: dict[str, object],
    prediction_cutoff: int,
    squeeze_causal: dict[str, object] | None = None,
) -> dict[str, Any]:
    instrument_id = symbol.upper()
    ledger = get_institutional_ledger()
    if ledger is None:
        return {
            "activities": [],
            "as_of_context": as_of_context,
            "available": False,
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
        return {
            "activities": [],
            "as_of_context": as_of_context,
            "available": False,
            "disclaimer": "No PIT-eligible options events for this symbol at replay cutoff.",
            "reason": "WHALE_NO_PIT_ELIGIBLE_OPTIONS",
            "research_only": True,
            "symbol": instrument_id,
        }

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
    surface = build_volatility_surface(activities)
    as_of_time = ""
    if activities and isinstance(activities[0], dict):
        as_of_time = str(activities[0].get("event_time", ""))
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
    vrp_research = vrp_research_snapshot(
        physical_forecast if isinstance(physical_forecast, dict) else None,
        risk_neutral_forecast,
    )
    signed_flow_snapshot = build_flow_snapshot(activities, as_of_time=as_of_time)

    return {
        "activities": activities,
        "activity_count": len(activities),
        "as_of_context": as_of_context,
        "available": True,
        "canonical_contracts": [
            row.get("canonical_contract")
            for row in activities
            if isinstance(row, dict) and isinstance(row.get("canonical_contract"), dict)
        ],
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
        "ledger_id": ledger.ledger_id,
        "provider_id": "depth.fixture.order_book",
        "research_only": True,
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "symbol": instrument_id,
    }


def _enrich_es_futures_f3_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach F3 curve, basis, and carry for ES fixture chain."""
    if payload.get("symbol", "").upper() != "ES":
        return payload
    from ..futures.basis import basis_payload
    from ..futures.carry import carry_payload
    from ..futures.curve import build_curve_snapshot_from_chain, curve_snapshot_payload
    from .adapters.fixture_futures import FixtureFuturesProvider
    from .adapters.fixture_futures_chain import FixtureFuturesChainProvider

    chain_provider = FixtureFuturesChainProvider()
    chain = chain_provider.fetch_chain("ES")
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
                    ofi_value = 0.0
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
                        ofi_value=ofi_value,
                        rth=rth,
                    )
                    bridge_row["event_time"] = event_time or None
                else:
                    bridge_row = {}
                    signal = "neutral"
                    ratio = 0.0
                    ofi_value = 0.0
                    session_state = "UNKNOWN"
                return _enrich_es_futures_f3_payload(
                    {
                    "as_of_context": as_of_context,
                    "available": True,
                    "contract_month": bridge.get("contract_month"),
                    "disclaimer": (
                        "Live donor-bridge ES depth snapshot. Not admitted into canonical replay. "
                        "Research-only."
                    ),
                    "exchange": bridge.get("exchange", "CME"),
                    "latest_imbalance_ratio": bridge_row.get("imbalance_ratio", ratio) if bridge_row else ratio,
                    "latest_imbalance_signal": bridge_row.get("imbalance_signal", signal) if bridge_row else signal,
                    "latest_ofi_value": bridge_row.get("ofi_value", ofi_value) if bridge_row else ofi_value,
                    "provenance": "donor_bridge",
                    "provider_id": "futuresx.donor_bridge",
                    "research_only": True,
                    "session_state": bridge_row.get("session_state", session_state) if bridge_row else session_state,
                    "snapshot": snap,
                    "snapshot_count": 1 if bridge_row else 0,
                    "snapshots": [bridge_row] if bridge_row else [],
                    "symbol": instrument_id,
                    }
                )
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
    return _enrich_es_futures_f3_payload(payload)


def build_workspace_catalyst_payload(
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


__all__ = [
    "build_workspace_catalyst_payload",
    "build_workspace_disclosure_payload",
    "build_workspace_distribution_payload",
    "build_workspace_fund_etf_payload",
    "build_workspace_futures_payload",
    "build_workspace_large_transactions_payload",
    "build_workspace_options_payload",
    "build_workspace_order_book_payload",
    "build_workspace_order_flow_payload",
    "catalyst_available",
    "disclosure_available",
    "fund_etf_available",
    "futures_available",
    "large_transactions_available",
    "options_available",
    "order_book_available",
    "order_flow_available",
]

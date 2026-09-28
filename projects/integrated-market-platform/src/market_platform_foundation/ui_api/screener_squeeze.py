"""Selected-instrument Short Squeeze evidence for the Main Screener (S8).

One selected US equity → ``screener-squeeze/1.0.0``: the current evidence the
workstation actually holds for it, grouped as structural pressure, ignition,
live confirmation, and exhaustion, each value with its own source, clock, and
quality; a snapshot state from ``short_intelligence.squeeze_state`` (adapted
from the donor causal evaluator); supporting, conflicting, and missing
evidence; and the exact Screener predicates the row matched (Why Listed).

Everything is read from existing current services: the Finviz Screener
snapshot row, the Moomoo L1 quote, the S4 order-flow/CVD/Level 2 projections
(read only; the Short Squeeze panel's own demand goes through the S4
reference-counted subscription authority), the S7 option-chain cache, Finviz
news, and the publication sources in ``screener_squeeze_sources``. No frozen,
replay, fixture, or historical-cohort data is read, and an unavailable source
is never replaced by one. Nothing here is a score, a probability, a ranking,
or a trade instruction, and nothing feeds Screener filters or sorting.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any, Callable

from ..market_sessions import us_equity_session_label
from ..short_intelligence.squeeze_state import (
    THRESHOLDS,
    OrderFlowInput,
    SqueezeInputs,
    evaluate_snapshot,
)
from .screener_squeeze_sources import (
    NO_RECORD,
    NOT_CONFIGURED,
    PENDING,
    PUBLICATION_CURRENT,
    STALE,
    FinraShortData,
    SecFailsToDeliver,
    ThresholdLists,
    lending_status,
)
from .screener_universes import US_EQUITIES

SCHEMA_VERSION = "screener-squeeze/1.0.0"
VIEWS = ("detail", "summary")
#: A Finviz snapshot row older than this is shown as stale (the export refreshes every 120 s).
FINVIZ_STALE_AFTER_S = 15 * 60
CAPABILITY = {
    "SQUEEZE_STATE": "SNAPSHOT_ASSESSMENT", "TEMPORAL_LIFECYCLE": "NOT_SUPPORTED",
    "SQUEEZE_UNIVERSE_QUERY": "NOT_SUPPORTED", "SQUEEZE_PROBABILITY": "NOT_SUPPORTED",
    "SQUEEZE_SCORE": "NOT_SUPPORTED", "EXECUTION": "NOT_AUTHORIZED",
}
UNAVAILABLE_QUALITIES = frozenset(("MISSING", "NOT_CONFIGURED", "NOT_ENTITLED", "PROVIDER_UNAVAILABLE", "NOT_SUBSCRIBED"))
SOURCE_LABELS = {
    "FINVIZ_ELITE": "Finviz", "MOOMOO": "Moomoo", "MOOMOO_TRADES": "Moomoo trades", "FINRA": "FINRA",
    "REG_SHO": "Reg SHO lists", "SEC_FTD": "SEC FTD", "LENDING": "Securities lending", "FINVIZ_OPTIONS": "Finviz options",
    "FINVIZ_NEWS": "Finviz news", "MOOMOO_DEPTH": "Moomoo depth", "DEALER_POSITIONING": "Dealer positioning",
}
MISSING_LABELS = {
    "SHORT_FLOAT": "Short float %", "OFFICIAL_SHORT_INTEREST": "Official short interest (FINRA)",
    "BORROW": "Borrow fee / availability", "IGNITION_INPUTS": "Change % and relative volume",
    "CATALYST": "Current headlines", "ORDER_FLOW": "Current order flow", "DEALER_POSITIONING": "Dealer gamma positioning",
}


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat().replace("+00:00", "Z")


def _parse(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def metric(metric_id: str, label: str, value: Any, *, unit: str, source: str, quality: str, clock_kind: str,
           as_of: str | None = None, reason: str | None = None, note: str | None = None,
           detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """One value with its own source, clock, and quality. ``value`` is None whenever it is unknown."""

    return {"id": metric_id, "label": label, "value": value, "unit": unit, "source": source,
            "source_label": SOURCE_LABELS.get(source, source), "quality": quality,
            "clock": {"kind": clock_kind, "as_of": as_of}, "reason": reason, "note": note, "detail": detail or {}}


# ----------------------------------------------------------------- defaults
def _default_row(instrument_id: str) -> dict[str, Any] | None:
    from .screener_projections import screener_service

    row, _error = screener_service().row_for(instrument_id)
    return row


def _default_quote(instrument_id: str) -> dict[str, Any]:
    from .screener_projections import screener_service

    try:
        return screener_service().quote_for(instrument_id)
    except Exception:  # noqa: BLE001 — a missing quote is shown as missing
        return {"state": "UNAVAILABLE", "fields": {}}


def _default_specialist(kind: str) -> Callable[[str], dict[str, Any]]:
    def read(instrument_id: str) -> dict[str, Any]:
        from .screener_specialist import specialist_service

        service = specialist_service()
        return {"order_flow": service.order_flow, "cvd": service.cvd, "depth": service.depth}[kind](instrument_id)
    return read


def _default_options(instrument_id: str) -> dict[str, Any] | None:
    from .screener_options import read_options

    return read_options(instrument_id, universe=US_EQUITIES, view="summary")


def _default_news() -> dict[str, Any]:
    from .screener_preview import _default_news as news

    return news()


class ScreenerSqueezeService:
    def __init__(self, *, row_getter: Callable[[str], dict[str, Any] | None] = _default_row,
                 quote_getter: Callable[[str], dict[str, Any]] = _default_quote,
                 order_flow_getter: Callable[[str], dict[str, Any]] | None = None,
                 cvd_getter: Callable[[str], dict[str, Any]] | None = None,
                 depth_getter: Callable[[str], dict[str, Any]] | None = None,
                 options_getter: Callable[[str], dict[str, Any] | None] = _default_options,
                 news_getter: Callable[[], dict[str, Any]] = _default_news,
                 threshold: ThresholdLists | None = None, finra: FinraShortData | None = None,
                 ftd: SecFailsToDeliver | None = None, lending: Callable[[str], dict[str, Any]] = lending_status,
                 clock: Callable[[], float] = time.time, session_label: Callable[[], str] = us_equity_session_label) -> None:
        self._row = row_getter
        self._quote = quote_getter
        self._order_flow = order_flow_getter or _default_specialist("order_flow")
        self._cvd = cvd_getter or _default_specialist("cvd")
        self._depth = depth_getter or _default_specialist("depth")
        self._options = options_getter
        self._news = news_getter
        self._threshold = threshold or ThresholdLists()
        self._finra = finra or FinraShortData()
        self._ftd = ftd or SecFailsToDeliver()
        self._lending = lending
        self._clock = clock
        self._session = session_label

    # ------------------------------------------------------------ sections
    def _finviz(self, row: dict[str, Any], name: str, label: str, unit: str, note: str | None = None) -> dict[str, Any]:
        field = (row.get("fields") or {}).get(name) or {}
        value = field.get("value")
        as_of = field.get("as_of")
        age = None if _parse(as_of) is None else self._clock() - _parse(as_of)
        quality = "MISSING" if value is None else "STALE" if age is not None and age > FINVIZ_STALE_AFTER_S else "SNAPSHOT"
        return metric(name, label, value, unit=unit, source="FINVIZ_ELITE", quality=quality, clock_kind="SNAPSHOT",
                      as_of=as_of, reason="NOT_SUPPLIED_BY_PROVIDER" if value is None else None, note=note)

    def _structural(self, row: dict[str, Any], symbol: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        finra = self._finra.status(symbol)
        threshold = self._threshold.status(symbol)
        ftd = self._ftd.status(symbol)
        lending = self._lending(symbol)
        interest = finra.get("short_interest") or None
        flow = finra.get("short_sale_volume") or None
        finra_quality = finra["state"] if finra["state"] != PUBLICATION_CURRENT or interest else NO_RECORD
        publication = interest["publication_date"] if interest else None
        items = [
            self._finviz(row, "short_float_pct", "Short float", "percent",
                         "Finviz snapshot of reported short interest as % of float; delayed, not a borrow measure"),
            self._finviz(row, "short_ratio", "Short ratio (days to cover)", "days",
                         "Finviz short interest ÷ average daily volume"),
            self._finviz(row, "float_shares", "Float", "shares"),
            self._finviz(row, "shares_outstanding", "Shares outstanding", "shares"),
            metric("official_short_interest", "Official short interest", interest["current"] if interest else None,
                   unit="shares", source="FINRA", quality=finra_quality, clock_kind="PUBLICATION", as_of=publication,
                   reason=finra["reason"], note="Outstanding short position at settlement; published twice monthly",
                   detail={"settlement_date": interest["settlement_date"] if interest else None,
                           "revision_flag": interest["revision_flag"] if interest else None}),
            metric("short_interest_change_pct", "Short interest change", interest["change_pct"] if interest else None,
                   unit="percent", source="FINRA", quality=finra_quality, clock_kind="PUBLICATION", as_of=publication,
                   reason=finra["reason"], note="Versus the prior settlement date",
                   detail={"change_shares": interest["change"] if interest else None}),
            metric("official_days_to_cover", "Days to cover (FINRA)", interest["days_to_cover"] if interest else None,
                   unit="days", source="FINRA", quality=finra_quality, clock_kind="PUBLICATION", as_of=publication,
                   reason=finra["reason"]),
            metric("short_sale_volume", "Short-sale volume (daily flow)", flow["short_sale_volume"] if flow else None,
                   unit="shares", source="FINRA", quality=finra["state"] if flow or finra["state"] != PUBLICATION_CURRENT else NO_RECORD,
                   clock_kind="PUBLICATION", as_of=flow["trade_report_date"] if flow else None, reason=finra["reason"],
                   note="Short-marked trading volume for one day; not short interest",
                   detail={"short_sale_ratio": flow["short_sale_ratio"] if flow else None}),
            metric("borrow_fee", "Borrow fee", lending["fee_pct"], unit="percent", source="LENDING",
                   quality=lending["state"], clock_kind="PROVIDER", as_of=lending["as_of"], reason=lending["reason"]),
            metric("borrow_available", "Borrow availability", lending["available_shares"], unit="shares", source="LENDING",
                   quality=lending["state"], clock_kind="PROVIDER", as_of=lending["as_of"], reason=lending["reason"]),
            metric("threshold_status", "Reg SHO threshold list", threshold["member"], unit="boolean", source="REG_SHO",
                   quality=threshold["state"], clock_kind="DAILY_LIST", as_of=threshold["trade_date"],
                   reason=next((item["reason"] for item in threshold["lists"] if item["reason"]), None),
                   note="List membership (persistent settlement fails); not short interest and not an FTD quantity",
                   detail={"member_of": threshold["member_of"], "lists": threshold["lists"]}),
            metric("ftd_balance", "Fails to deliver (latest settlement)", ftd["balance"], unit="shares", source="SEC_FTD",
                   quality=ftd["state"], clock_kind="PUBLICATION", as_of=ftd["settlement_date"], reason=ftd["reason"],
                   note="SEC aggregate fail balance, published with a delay; not proof of naked shorting",
                   detail={"period": ftd["period_label"], "settlement_days_with_fails": ftd["settlement_days_with_fails"]}),
        ]
        return items, {"finra": finra, "threshold": threshold, "ftd": ftd, "lending": lending}

    def _ignition(self, row: dict[str, Any], symbol: str, quote: dict[str, Any], now: float) -> tuple[list[dict[str, Any]], bool | None, list[dict[str, Any]]]:
        from .screener_preview import current_headlines

        try:
            news = self._news()
        except Exception:  # noqa: BLE001 — shown as an unavailable source
            news = {"success": False, "items": []}
        headlines: list[dict[str, Any]] = []
        if news.get("success") is False and not news.get("items"):
            catalyst: bool | None = None
            catalyst_quality, reason = "PROVIDER_UNAVAILABLE", "NEWS_UNAVAILABLE"
        else:
            headlines = current_headlines(news, symbol, datetime.fromtimestamp(now, tz=UTC))
            catalyst, catalyst_quality, reason = bool(headlines), "SNAPSHOT", None
        price = (quote.get("fields") or {}).get("price") or {}
        live_price = quote.get("state") in ("LIVE", "DELAYED") and price.get("value") is not None
        items = [
            self._finviz(row, "change_pct", "Change", "percent"),
            self._finviz(row, "rel_volume", "Relative volume", "ratio"),
            self._finviz(row, "volume", "Volume", "shares"),
            metric("price", "Price", price.get("value") if live_price else ((row.get("fields") or {}).get("price") or {}).get("value"),
                   unit="USD", source="MOOMOO" if live_price else "FINVIZ_ELITE",
                   quality=("CURRENT" if quote.get("state") == "LIVE" else "DELAYED") if live_price else "SNAPSHOT",
                   clock_kind="STREAMING" if live_price else "SNAPSHOT",
                   as_of=_iso(price["as_of_ns"] / 1e9) if live_price and price.get("as_of_ns") else ((row.get("fields") or {}).get("price") or {}).get("as_of")),
            metric("catalyst", "Current headlines", len(headlines) if catalyst is not None else None, unit="count",
                   source="FINVIZ_NEWS", quality=catalyst_quality, clock_kind="SNAPSHOT",
                   as_of=headlines[0]["published_at"] if headlines else None, reason=reason,
                   note="Headlines in the current move window are context; they are not shown as a cause"),
        ]
        return items, catalyst, headlines

    def _confirmation(self, market_id: str, instrument_id: str, view: str) -> tuple[list[dict[str, Any]], OrderFlowInput | None]:
        flow = self._order_flow(market_id)
        cvd = self._cvd(market_id)
        depth = self._depth(market_id)
        summary = flow.get("summary") or None
        cvd_summary = cvd.get("summary") or None
        state = str(flow.get("state") or "UNAVAILABLE")
        flow_quality = {"CURRENT": "CURRENT", "SESSION_CLOSED": "SESSION_CLOSED", "STALE": "STALE",
                        "NOT_ENTITLED": "NOT_ENTITLED", "CONNECTING": "NOT_SUBSCRIBED",
                        "SUBSCRIPTION_BUSY": "NOT_SUBSCRIBED"}.get(state, "PROVIDER_UNAVAILABLE")
        flow_input = None
        if summary is not None:
            flow_input = OrderFlowInput(state=state, buy_volume=float(summary["buy_volume"]),
                                        sell_volume=float(summary["sell_volume"]),
                                        classified_volume_pct=summary.get("classified_volume_pct"),
                                        recent_delta=cvd_summary.get("recent_delta") if cvd_summary else None,
                                        trade_count=int(summary["trade_count"]))
        latest = flow.get("latest_event_at")
        items = [
            metric("order_flow_net", "Net aggressor volume", summary["net_signed_volume"] if summary else None,
                   unit="shares", source="MOOMOO_TRADES", quality=flow_quality, clock_kind="STREAMING", as_of=latest,
                   reason=flow.get("reason"), note="Buy-aggressor minus sell-aggressor volume since subscription",
                   detail={"buy_volume": summary["buy_volume"] if summary else None,
                           "sell_volume": summary["sell_volume"] if summary else None,
                           "classified_volume_pct": summary["classified_volume_pct"] if summary else None,
                           "trade_count": summary["trade_count"] if summary else None,
                           "window": (flow.get("window") or {}).get("basis")}),
            metric("cvd_recent_delta", "CVD, last 60 s", cvd_summary.get("recent_delta") if cvd_summary else None,
                   unit="shares", source="MOOMOO_TRADES", quality=flow_quality, clock_kind="STREAMING",
                   as_of=cvd.get("latest_event_at"), reason=cvd.get("reason"),
                   note="Derived by IMP from classified trades", detail={"cvd": cvd_summary.get("cvd") if cvd_summary else None}),
        ]
        imbalance = next((item for item in depth.get("imbalance") or [] if item.get("levels") == 10), None)
        depth_state = str(depth.get("state") or "UNAVAILABLE")
        items.append(metric("book_imbalance", "Book imbalance (10 levels)", imbalance["signed"] if imbalance else None,
                            unit="signed_ratio", source="MOOMOO_DEPTH",
                            quality={"CURRENT": "CURRENT", "SESSION_CLOSED": "SESSION_CLOSED", "STALE": "STALE",
                                     "PARTIAL": "CURRENT", "CONNECTING": "NOT_SUBSCRIBED"}.get(depth_state, "PROVIDER_UNAVAILABLE"),
                            clock_kind="STREAMING", as_of=depth.get("latest_event_at"),
                            reason=depth.get("reason") if depth_state != "CURRENT" else None,
                            note="Liquidity context from the Level 2 panel's book; read only when Level 2 is open"))
        if view == "detail":
            options = self._options(instrument_id) or {}
            summary_o = options.get("summary") or None
            has_chain = options.get("state") in ("CURRENT_SNAPSHOT", "MARKET_CLOSED", "STALE") and summary_o
            items.append(metric("options_call_put_volume", "Options call/put volume", summary_o.get("call_put_volume_ratio") if has_chain else None,
                                unit="ratio", source="FINVIZ_OPTIONS",
                                quality=("STALE" if options.get("state") == "STALE" else "SNAPSHOT") if has_chain
                                else "NOT_CONFIGURED" if options.get("state") == "NOT_CONFIGURED" else "PROVIDER_UNAVAILABLE",
                                clock_kind="SNAPSHOT", as_of=(options.get("clock") or {}).get("fetched_at"),
                                reason=None if has_chain else options.get("state") or "OPTIONS_UNAVAILABLE",
                                note="Descriptive call/put activity; volume may be opening or closing trades",
                                detail={"call_volume": summary_o.get("call_volume") if has_chain else None,
                                        "put_volume": summary_o.get("put_volume") if has_chain else None,
                                        "options_state": options.get("state")}))
        else:
            items.append(metric("options_call_put_volume", "Options call/put volume", None, unit="ratio",
                                source="FINVIZ_OPTIONS", quality="NOT_REQUESTED", clock_kind="SNAPSHOT",
                                reason="OPEN_PANEL_FOR_OPTIONS"))
        items.append(metric("dealer_positioning", "Dealer gamma positioning", None, unit="text", source="DEALER_POSITIONING",
                            quality="NOT_CONFIGURED", clock_kind="PROVIDER", reason="NO_DEALER_POSITIONING_SOURCE",
                            note="Required before any gamma or dealer-hedging claim"))
        return items, flow_input

    # ------------------------------------------------------------ envelope
    def read(self, instrument_id: str, *, universe: str = US_EQUITIES, view: str = "detail",
             filters: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
        from .screener_filters import validate_filters
        from .screener_preview import explain_matches

        if universe != US_EQUITIES:
            raise ValueError("SQUEEZE_UNAVAILABLE_FOR_UNIVERSE")
        if view not in VIEWS:
            raise ValueError("INVALID_SQUEEZE_VIEW")
        rules = validate_filters([] if filters is None else filters, universe=universe)
        row = self._row(instrument_id)
        if row is None:
            return None
        now = self._clock()
        symbol = str(row.get("symbol") or instrument_id)
        market_id = str(row.get("market_data_id") or instrument_id)
        quote = self._quote(instrument_id)
        structural, publication = self._structural(row, symbol)
        ignition, catalyst, headlines = self._ignition(row, symbol, quote, now)
        confirmation, flow_input = self._confirmation(market_id, instrument_id, view)
        values = {item["id"]: item for item in structural + ignition + confirmation}
        finra = publication["finra"]
        interest = finra.get("short_interest") or None
        stale = [f"{item['id'].upper()}_STALE" for item in values.values() if item["quality"] == STALE]
        inputs = SqueezeInputs(
            short_float_pct=values["short_float_pct"]["value"], short_ratio_days=values["short_ratio"]["value"],
            float_shares=values["float_shares"]["value"],
            official_short_interest_available=interest is not None and interest.get("current") is not None,
            official_short_interest_change_pct=interest.get("change_pct") if interest else None,
            official_days_to_cover=interest.get("days_to_cover") if interest else None,
            borrow_fee_pct=publication["lending"]["fee_pct"], borrow_available_shares=publication["lending"]["available_shares"],
            change_pct=values["change_pct"]["value"], rel_volume=values["rel_volume"]["value"],
            catalyst_present=catalyst, order_flow=flow_input, dealer_positioning_available=False,
            threshold_list_member=publication["threshold"]["member"], stale_inputs=tuple(stale),
        )
        assessment = evaluate_snapshot(inputs)
        exhaustion = [item for item in assessment.contradicting if item.code in ("EXHAUSTION_SIGNAL", "CVD_DIVERGENCE")]
        every = list(values.values())
        missing = [{"code": code, "label": MISSING_LABELS.get(code, code.replace("_", " ").title()),
                    "reason": _missing_reason(code, values, publication)} for code in assessment.missing]
        unavailable = [item for item in every if item["quality"] in UNAVAILABLE_QUALITIES]
        payload = {
            "schema_version": SCHEMA_VERSION, "generated_at": _iso(now), "instrument_id": instrument_id,
            "universe": universe, "symbol": symbol, "company": row.get("company"), "view": view,
            "market_session": self._session(), "capability": dict(CAPABILITY),
            "assessment": assessment.to_dict(),
            "source_state": "INSUFFICIENT_EVIDENCE" if assessment.state.value == "UNEVALUABLE"
            else "PARTIAL" if unavailable else "COMPLETE",
            "sections": {
                "structural_pressure": structural, "ignition": ignition, "live_confirmation": confirmation,
                "exhaustion": {"evidence": [item.to_dict() for item in exhaustion],
                               "temporal": "NOT_EVALUATED_NO_STATE_HISTORY",
                               "note": "Exhaustion needs fuel and CVD history; a single snapshot can show exhaustion inputs only."},
            },
            "headlines": headlines,
            "evidence": {
                "supporting": [item.to_dict() for item in assessment.supporting],
                "conflicting": [item.to_dict() for item in assessment.contradicting],
                "context": [item.to_dict() for item in assessment.context],
                "missing": missing,
            },
            "coverage": {"supporting": len(assessment.supporting), "conflicting": len(assessment.contradicting),
                         "unavailable": len(unavailable), "stale": sum(1 for item in every if item["quality"] == STALE),
                         "pending": sum(1 for item in every if item["quality"] == PENDING)},
            "sources": _sources(every),
            "why_listed": explain_matches(row, rules, universe=universe),
            "discovery_thresholds": {key: {"value": THRESHOLDS[key].value, "operator": THRESHOLDS[key].operator,
                                           "source": THRESHOLDS[key].source} for key in sorted(THRESHOLDS)},
            "historical_context": None,
            "disclaimer": "Current evidence and a snapshot state only: no squeeze score, probability, ranking, or trade instruction.",
        }
        return payload


def _missing_reason(code: str, values: dict[str, dict[str, Any]], publication: dict[str, Any]) -> str | None:
    if code == "OFFICIAL_SHORT_INTEREST":
        return publication["finra"]["reason"] or publication["finra"]["state"]
    if code == "BORROW":
        return publication["lending"]["reason"]
    if code == "ORDER_FLOW":
        return values["order_flow_net"]["reason"] or values["order_flow_net"]["quality"]
    if code == "DEALER_POSITIONING":
        return "NO_DEALER_POSITIONING_SOURCE"
    if code == "CATALYST":
        return values["catalyst"]["reason"]
    if code == "SHORT_FLOAT":
        return values["short_float_pct"]["reason"]
    if code == "IGNITION_INPUTS":
        return "NOT_SUPPLIED_BY_PROVIDER"
    return None


def _sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per source: its best state and newest clock across the values it supplied."""

    rank = {"CURRENT": 0, "SNAPSHOT": 1, "PUBLICATION_CURRENT": 1, "DELAYED": 2, "SESSION_CLOSED": 2, NO_RECORD: 2,
            STALE: 3, PENDING: 4, "PARTIAL": 4, "NOT_REQUESTED": 5, "NOT_SUBSCRIBED": 6, "MISSING": 6,
            NOT_CONFIGURED: 7, "NOT_ENTITLED": 7, "PROVIDER_UNAVAILABLE": 7}
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        entry = grouped.setdefault(item["source"], {"id": item["source"], "label": item["source_label"], "state": item["quality"],
                                                    "clock_kind": item["clock"]["kind"], "as_of": item["clock"]["as_of"],
                                                    "reason": item["reason"]})
        if rank.get(item["quality"], 8) < rank.get(entry["state"], 8):
            entry.update(state=item["quality"], reason=item["reason"])
        if item["clock"]["as_of"] and (entry["as_of"] is None or item["clock"]["as_of"] > entry["as_of"]):
            entry["as_of"] = item["clock"]["as_of"]
    return list(grouped.values())


_SERVICE: ScreenerSqueezeService | None = None
_SERVICE_LOCK = threading.Lock()


def squeeze_service() -> ScreenerSqueezeService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = ScreenerSqueezeService()
        return _SERVICE


def read_squeeze(instrument_id: str, **kwargs: Any) -> dict[str, Any] | None:
    return squeeze_service().read(instrument_id, **kwargs)


__all__ = ["CAPABILITY", "SCHEMA_VERSION", "ScreenerSqueezeService", "metric", "read_squeeze", "squeeze_service"]

"""Server-owned AI Screener scope, evidence projection, and candidate reduction.

The browser submits only the active Screener query.  This module reconstructs
the bounded result set, projects a small allowlist of facts, re-evaluates the
OCT1-03 freshness policy at the inference cutoff, and delegates to the same
provider instance used by News synthesis.  It has no execution or mutation
authority.
"""
from __future__ import annotations

import copy
import math
import time
from datetime import UTC, datetime
from typing import Any, Callable

from ..intelligence.inference.candidate_reduction import (
    MAX_INTAKE,
    CandidateReducer,
    build_candidate,
)
from .screener_freshness import project_screener_response
from .screener_multi import multi_screener_service
from .screener_universes import universe_spec

SCHEMA_VERSION = "screener-ai-screener/1.0.0"
PREVIEW_SCHEMA_VERSION = "screener-ai-screener-preview/1.0.0"
_CURRENT_FIELDS = (
    "price", "change_pct", "volume", "rel_volume", "rsi_14", "bid", "ask",
    "spread_pct", "open_interest", "base_volume", "quote_volume", "trade_count",
)
_REFERENCE_FIELDS = (
    "reference_rate", "indicative_rate", "auction_yield", "auction_real_yield",
    "auction_discount_margin", "bid_to_cover", "outstanding", "fund_value_pct",
    "observed_price", "observed_yield", "benchmark_spread",
)
_TECHNICAL_FIELDS = (
    "change_pct", "volume", "rel_volume", "rsi_14", "open_interest", "base_volume",
    "quote_volume", "trade_count", "years_to_maturity",
)


def _iso(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), UTC).isoformat().replace("+00:00", "Z")


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def observations_for_row(row: dict[str, Any], *, now: str) -> list[tuple[str, dict[str, Any], dict[str, Any], list[str]]]:
    """Project only bounded row facts; specialist payloads are never serialized wholesale."""
    observations = []
    fields = row.get("fields") or {}
    for capability, allowed in (("QUOTE", ("price",)), ("TECHNICALS", _TECHNICAL_FIELDS), ("RATES", _REFERENCE_FIELDS)):
        for status in row.get("decision_inputs", []):
            names = [name for name in status.get("covered_fields", []) if name in allowed]
            if not names:
                continue
            facts = {name: fields[name]["value"] for name in names if _finite(fields[name].get("value"))}
            # A status applies only to fields sharing its exact source/clock/state.
            observations.append((capability, status, facts, []))
    return observations


def flow_observation(row: dict, universe: str, *, now: str) -> list[tuple]:
    """Read only already-owned specialist state; never request subscriptions."""
    if universe not in ('US_EQUITIES', 'US_ETFS', 'CRYPTO'):
        return []
    if universe == 'CRYPTO':
        from . import screener_crypto as module
        service = getattr(module, '_SPECIALIST', None)
    else:
        from . import screener_specialist as module
        service = module._SERVICE
    if service is None:
        return []
    identifier = row.get('market_data_id') or row['instrument']['instrument_id']
    payload = service.order_flow(identifier)
    projected = project_screener_response('/screener/order-flow', payload, now=now)
    summary, window = payload.get('summary') or {}, payload.get('window') or {}
    count = summary.get('trade_count', 0)
    # Conservative observation: complete exchange-native classification only.
    native = bool(count and summary.get('native_count') == count and not summary.get('unknown_count')
                  and not summary.get('inferred_count') and not window.get('truncated'))
    from ..market_data.freshness_contract import timestamp
    cutoff, start, end = timestamp(now), timestamp(window.get('start')), timestamp(window.get('end'))
    compatible = bool(start and end and cutoff and start <= end <= cutoff and (cutoff-start).total_seconds() <= 4*3600)
    facts = {key: summary.get(key) for key in ('net_signed_volume','native_count','inferred_count','unknown_count','classified_volume_pct')}
    facts['window'] = window
    usable = native and compatible and _finite(summary.get('net_signed_volume'))
    return [('ORDER_FLOW', status, facts if usable else {}, [] if usable else ['FLOW_QUALITY_OR_WINDOW_INSUFFICIENT'])
            for status in projected['decision_inputs']]


class ScreenerAiService:
    """Explicit preview/run boundary for the trader-facing AI Screener."""

    def __init__(self, *, reader: Any | None = None, news: Any | None = None,
                 clock: Callable[[], float] = time.time) -> None:
        self._reader = reader or multi_screener_service()
        self._news = news
        self._clock = clock
        self._reducer: CandidateReducer | None = None
        self._provider_key: tuple[int, str | None] | None = None

    def _news_service(self) -> Any:
        if self._news is not None:
            return self._news
        from .screener_news import news_service

        self._news = news_service()
        return self._news

    def _provider_reducer(self) -> CandidateReducer:
        news = self._news_service()
        provider = news.synthesis_provider()
        key = (id(provider), getattr(provider, "model_id", None))
        if self._reducer is None or self._provider_key != key:
            self._reducer = CandidateReducer(provider=provider, clock=self._clock)
            self._provider_key = key
        return self._reducer

    @staticmethod
    def _query(body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        universe = body.get("universe")
        if not isinstance(universe, str):
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        universe_spec(universe)
        search = body.get("search", "")
        sort = body.get("sort")
        descending = body.get("descending", True)
        filters = body.get("filters", [])
        result_set = body.get("result_set")
        if not isinstance(search, str) or len(search) > 120 or not isinstance(sort, (str, type(None))):
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        if not isinstance(descending, bool) or not isinstance(filters, list) or len(filters) > 64:
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        if result_set is not None and (not isinstance(result_set, str) or len(result_set) > 240):
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        view, screen = body.get("view", "Overview"), body.get("screen", "")
        if not all(isinstance(value, str) and len(value) <= 120 for value in (view, screen)):
            raise ValueError("INVALID_AI_SCREENER_SCOPE")
        return {"universe": universe, "view": view, "screen": screen, "search": search, "sort": sort,
                "descending": descending, "filters": copy.deepcopy(filters), "result_set": result_set}

    def _packet(self, body: dict[str, Any], *, refresh_news: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]], str, dict[str, Any]]:
        query = self._query(body)
        page = self._reader.read(universe=query["universe"], search=query["search"], sort=query["sort"],
                                 descending=query["descending"], offset=0, limit=MAX_INTAKE,
                                 filters=query["filters"], result_set=query["result_set"])
        raw_rows = list(page.get('rows') or [])[:MAX_INTAKE]
        news_reader = getattr(self._news_service(), 'candidate_evidence', None)
        news = news_reader(universe=query['universe'], rows=raw_rows, refresh=refresh_news) if news_reader else {}
        now = _iso(self._clock)
        projected = project_screener_response("/screener", {**page, "rows": list(page.get("rows") or [])[:MAX_INTAKE]}, now=now)
        rows = projected["rows"]
        scope = {key: query[key] for key in ("universe", "search", "sort", "descending", "filters")}
        scope.update(result_set=page.get("result_set_id"), matched_count=int(page.get("result_count") or 0),
                     universe_as_of=page.get("universe_as_of"), screener_as_of=page.get("screener_as_of"),
                     view=query["view"], screen=query["screen"])
        candidates = [build_candidate(row.get("instrument", {}), observations_for_row(row, now=now) +
                      (flow_observation(row, query['universe'], now=now) if refresh_news else []), now=now)
                      for row in rows]
        from .screener_news_evidence import attach_news, fit_news

        for candidate, row in zip(candidates, rows):
            candidate['instrument']['company'] = str(row.get('company') or '')[:120]
            identifier = candidate['instrument']['instrument_id']
            if identifier in news:
                attach_news(candidate, news[identifier], now=now)
        fit_news(scope, candidates, news, now=now)
        return scope, candidates, now, {"matched_count": int(page.get("result_count") or 0),
                                       "result_set": page.get("result_set_id"),
                                       "universe_as_of": page.get("universe_as_of"),
                                       "screener_as_of": page.get("screener_as_of")}

    def _ai_status(self) -> dict[str, Any]:
        return self._news_service().ai_status()

    def preview(self, body: dict[str, Any]) -> dict[str, Any]:
        scope, candidates, now, page_meta = self._packet(body)
        ai = self._ai_status()
        reducer = self._provider_reducer()
        estimate = reducer.estimate(scope, candidates, now) if ai.get("state") == "AVAILABLE" else None
        return {"schema_version": PREVIEW_SCHEMA_VERSION, "ai": ai, "scope": scope,
                "matched_count": page_meta["matched_count"], "intake_count": len(candidates),
                "max_intake": MAX_INTAKE, "estimate": estimate,
                "evidence_summary": {"sufficient": sum(bool(item["sufficient"]) for item in candidates),
                                      "blocked": sum(len(item["blocked"]) for item in candidates),
                                      "missing": sum(len(item["missing"]) for item in candidates),
                                      "weak": sum(len(item["weak"]) for item in candidates)},
                "news_coverage": [{"instrument_id": c['instrument']['instrument_id'], **c.get('news', {})} for c in candidates],
                "decision_cutoff": now, "result_set": page_meta["result_set"]}

    def run(self, body: dict[str, Any]) -> dict[str, Any]:
        scope, candidates, now, page_meta = self._packet(body, refresh_news=True)
        reducer = self._provider_reducer()
        result = reducer.reduce(scope, candidates, now)
        return {**result, "schema_version": SCHEMA_VERSION, "scope": scope,
                "matched_count": page_meta["matched_count"], "intake_count": len(candidates),
                "max_intake": MAX_INTAKE, "result_set": page_meta["result_set"]}


_SERVICE: ScreenerAiService | None = None


def screener_ai_service() -> ScreenerAiService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ScreenerAiService()
    return _SERVICE


def read_ai_screener_preview(body: dict[str, Any]) -> dict[str, Any]:
    return screener_ai_service().preview(body)


def request_ai_screener(body: dict[str, Any]) -> dict[str, Any]:
    return screener_ai_service().run(body)


__all__ = ["MAX_INTAKE", "PREVIEW_SCHEMA_VERSION", "SCHEMA_VERSION", "ScreenerAiService",
           "observations_for_row", "read_ai_screener_preview", "request_ai_screener", "screener_ai_service"]

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
from ..intelligence.inference.run_progress import report_stage
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


def engine_fit(engines: list[dict[str, Any]], *, input_tokens: int | None, output_tokens: int) -> list[dict[str, Any]]:
    """Whether this packet fits each selectable engine. ``fits`` is None when the packet size or the engine's
    context window is not known: nothing is claimed in either direction."""
    required = input_tokens + output_tokens if input_tokens is not None else None
    return [{"engine": engine["id"], "packet_size": required, "context_window": engine.get("context_window"),
             "fits": required <= engine["context_window"] if required is not None and engine.get("context_window") else None}
            for engine in engines]


def observations_for_row(row: dict[str, Any], *, now: str) -> list[tuple[str, dict[str, Any], dict[str, Any], list[str]]]:
    """Project only bounded row facts; specialist payloads are never serialized wholesale."""
    observations = []
    fields = row.get("fields") or {}
    for capability, allowed in (("QUOTE", ("price", "bid", "ask", "spread_pct")), ("TECHNICALS", _TECHNICAL_FIELDS), ("RATES", _REFERENCE_FIELDS)):
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
                 clock: Callable[[], float] = time.time, market_snapshots: Any | None = None) -> None:
        # A dedicated bounded cache never replaces the Screener's universe-wide ordering snapshot.
        self._market_snapshots = market_snapshots
        if reader is None and market_snapshots is None:
            from .screener_snapshot import EtfSnapshotSource
            from .screener_projections import _quote_transport
            self._market_snapshots = EtfSnapshotSource(transport_getter=_quote_transport, prefix='ai-intake', require_complete=False)
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

    def _packet(self, body: dict[str, Any], *, refresh_news: bool = False, include_flow: bool | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], str, dict[str, Any]]:
        # OCT1-07 reads already-owned flow state without refreshing shared News providers.
        include_flow = refresh_news if include_flow is None else include_flow
        query = self._query(body)
        report_stage("SCOPE")
        page = self._reader.read(universe=query["universe"], search=query["search"], sort=query["sort"],
                                 descending=query["descending"], offset=0, limit=MAX_INTAKE,
                                 filters=query["filters"], result_set=query["result_set"])
        raw_rows = list(page.get('rows') or [])[:MAX_INTAKE]
        # Slow shared news must precede acquisition of short-lived market observations.
        report_stage("NEWS")
        news = self._news_for(query['universe'], raw_rows, refresh=refresh_news)
        market, _ = self._market(query['universe'], raw_rows, acquire=refresh_news)
        # Stages are reported in the order the work really happens: news is read before the evidence
        # cutoff is taken, so the cutoff is never older than the news refresh that preceded it.
        report_stage("EVIDENCE")
        now = _iso(self._clock)
        scope = self._scope(query, page)
        candidates, _ = self._candidates(query['universe'], page, raw_rows, market=market, now=now, include_flow=include_flow)
        from .screener_news_evidence import attach_news, fit_news

        report_stage("PACKET", intake_count=len(candidates))
        for candidate in candidates:
            identifier = candidate['instrument']['instrument_id']
            if identifier in news:
                attach_news(candidate, news[identifier], now=now)
        fit_news(scope, candidates, news, now=now)
        return scope, candidates, now, {"matched_count": int(page.get("result_count") or 0),
                                       "result_set": page.get("result_set_id"),
                                       "universe_as_of": page.get("universe_as_of"),
                                       "screener_as_of": page.get("screener_as_of")}

    @staticmethod
    def _scope(query: dict[str, Any], page: dict[str, Any]) -> dict[str, Any]:
        scope = {key: query[key] for key in ("universe", "search", "sort", "descending", "filters")}
        scope.update(result_set=page.get("result_set_id"), matched_count=int(page.get("result_count") or 0),
                     universe_as_of=page.get("universe_as_of"), screener_as_of=page.get("screener_as_of"),
                     view=query["view"], screen=query["screen"])
        return scope

    def _news_for(self, universe: str, raw_rows: list[dict[str, Any]], *, refresh: bool) -> dict[str, Any]:
        news_reader = getattr(self._news_service(), 'candidate_evidence', None)
        return news_reader(universe=universe, rows=raw_rows, refresh=refresh) if news_reader else {}

    def _market(self, universe: str, raw_rows: list[dict[str, Any]], *, acquire: bool) -> tuple[Any | None, str | None]:
        """The bounded vendor snapshot for exactly these rows, or the reason there is none. ``acquire`` takes a
        new one; otherwise only a retained snapshot of the same rows is read."""
        if self._market_snapshots is None or universe not in ('US_EQUITIES', 'US_ETFS'):
            return None, None
        from ..intelligence.inference.hashing import input_hash_from_dict
        from ..market_data.live_runtime import provider_symbol_for
        market_key = input_hash_from_dict({'instruments': sorted(r['instrument']['instrument_id'] for r in raw_rows)})
        if acquire and raw_rows:
            return self._market_snapshots.current(
                [{'instrument': r['instrument'], 'provider_symbol': provider_symbol_for(r['instrument']['instrument_id'])} for r in raw_rows],
                catalog_as_of=market_key, force=True)
        cached = self._market_snapshots.latest()
        return (cached if cached is not None and cached.catalog_as_of == market_key else None), None

    def _candidates(self, universe: str, page: dict[str, Any], raw_rows: list[dict[str, Any]], *, market: Any | None,
                    now: str, include_flow: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Gate these rows' facts at ``now``. News is attached by the caller."""
        projected = project_screener_response("/screener", {**page, "rows": raw_rows}, now=now)
        rows = projected["rows"]
        candidates = []
        for row in rows:
            observations = observations_for_row(row, now=now)
            if market is not None:
                from ..market_data.freshness_contract import evaluate
                identifier = row['instrument']['instrument_id']
                values = market.values.get(identifier) or {}
                status = evaluate(capability='market_snapshot', source='MOOMOO_OPEND_SNAPSHOT', delivery_mode='SNAPSHOT',
                    now=now, as_of=market.row_as_of.get(identifier), stale_after_ms=60000,
                    policy='L1_EVENT_V1', basis='PROVIDER_AS_OF', state='AVAILABLE')
                status['received_at'] = market.as_of
                quote = {name: values[name] for name in ('price', 'bid', 'ask', 'spread_pct') if _finite(values.get(name))}
                technical = {name: values[name] for name in ('volume', 'change_pct') if _finite(values.get(name))}
                if 'change_pct' in technical:
                    technical['change_basis'] = 'PREVIOUS_CLOSE'
                observations.extend([('QUOTE', status, quote, []), ('TECHNICALS', status, technical, [])])
            if include_flow:
                observations.extend(flow_observation(row, universe, now=now))
            candidate = build_candidate(row.get('instrument', {}), observations, now=now)
            candidate['instrument']['company'] = str(row.get('company') or '')[:120]
            candidates.append(candidate)
        return candidates, rows

    def _ai_status(self) -> dict[str, Any]:
        return self._news_service().ai_status()

    def ai_status(self) -> dict[str, Any]:
        """Engine state and shared budget as the News service reports them. Calls no model."""
        return self._ai_status()

    def engine(self) -> dict[str, Any]:
        """The engine the next run would use and its request timeout. Calls no model."""
        reducer = self._provider_reducer()
        provider = reducer.provider
        return {"provider_id": getattr(provider, "provider_id", None), "model_id": getattr(provider, "model_id", None),
                "runtime": (getattr(provider, "runtime", None) or "PAID_API") if provider is not None else None,
                "timeout_seconds": reducer.config.timeout_seconds}

    def validate_scope(self, body: dict[str, Any]) -> dict[str, Any]:
        """The normalized Screener scope, or ValueError. Reads nothing."""
        return self._query(body)

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
                "engine_contract": reducer.contract(),
                "engine_fit": engine_fit(ai.get("engines") or [], input_tokens=estimate["input_tokens"] if estimate else None,
                                         output_tokens=reducer.config.max_tokens),
                "decision_cutoff": now, "result_set": page_meta["result_set"]}

    def run(self, body: dict[str, Any], *, refresh_news: bool = True) -> dict[str, Any]:
        scope, candidates, now, page_meta = self._packet(body, refresh_news=refresh_news, include_flow=True)
        reducer = self._provider_reducer()
        result = reducer.reduce(scope, candidates, now)
        from ..local_state.action_decisions import action_repository
        report_stage("STORED")
        if action_repository().get('candidate_run', result['run_id']) is None:
            action_repository().put('candidate_run', result['run_id'], result)
        return {**result, "schema_version": SCHEMA_VERSION, "scope": scope,
                "matched_count": page_meta["matched_count"], "intake_count": len(candidates),
                "max_intake": MAX_INTAKE, "result_set": page_meta["result_set"]}

    def run_universe(self, body: dict[str, Any], *, run_id: str, account_id: str,
                     should_stop: Callable[[], bool] = lambda: False) -> dict[str, Any]:
        """The operator's Run: every row of the active query accounted for, eligible rows reduced in bounded
        batches, finalists compared globally. ``run`` above remains the single-request method the automatic
        passes use; it reads only the head of the sorted result and never claims coverage."""
        from .screener_ai_coverage import ScreenerAiCoverage

        return ScreenerAiCoverage(self).run(body, run_id=run_id, account_id=account_id, should_stop=should_stop)

    def release_hold(self, run_id: str) -> dict[str, int] | None:
        """Return a dead run's unused budget hold. None for an engine with no budget."""
        budget = getattr(self._provider_reducer().provider, 'budget', None)
        return budget.release(run_id) if budget is not None else None


_SERVICE: ScreenerAiService | None = None


def screener_ai_service() -> ScreenerAiService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ScreenerAiService()
    return _SERVICE


def read_ai_screener_preview(body: dict[str, Any]) -> dict[str, Any]:
    return screener_ai_service().preview(body)


__all__ = ["MAX_INTAKE", "PREVIEW_SCHEMA_VERSION", "SCHEMA_VERSION", "ScreenerAiService", "engine_fit",
           "observations_for_row", "read_ai_screener_preview", "screener_ai_service"]

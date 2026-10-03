"""OCT1-03 Screener evidence projection over already-acquired payloads.

This read-model boundary adds temporal status without fetching any source.
Internal consumers must call eligible_evidence at their own decision cutoff.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..market_data.freshness_contract import evaluate


def _iso(ns: Any) -> str | None:
    if not isinstance(ns, (int, float)) or ns <= 0:
        return None
    try:
        return datetime.fromtimestamp(ns / 1e9, UTC).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError, OSError):
        return None


def project_screener_response(path: str, payload: dict, *, now: str) -> dict:
    """Shallow-copy enriched structures; never mutate source/cache payloads."""
    path = path.split('?')[0]
    supported = {'/screener', '/screener/window', '/screener/preview', '/screener/chart', '/screener/options', '/screener/futures-context', '/screener/order-flow', '/screener/cvd', '/screener/depth', '/screener/order-flow-series', '/screener/connectivity', '/screener/rates-curve', '/screener/squeeze', '/screener/news', '/screener/news/instrument'}
    if path not in supported:
        return payload
    inputs: list[dict] = []
    session = payload.get('market_session')

    def add(capability, source, mode, as_of, *, state=None, ttl=None, policy='UNKNOWN_POLICY',
            basis='PROVIDER_AS_OF', reference=False, **clocks):
        status = evaluate(capability=capability, source=source, delivery_mode=mode, now=now,
                          as_of=as_of, state=state, stale_after_ms=ttl, policy=policy, basis=basis,
                          reference=reference, **clocks)
        inputs.append(status)
        return status

    def field(name, value, *, publication=False):
        state = value.get('state') if value.get('value') is not None else 'UNAVAILABLE'
        mode = 'PUBLICATION_BASED' if publication else 'DELAYED' if state == 'DELAYED' else 'REALTIME' if state == 'LIVE' else 'SNAPSHOT'
        market = name in ('price', 'bid', 'ask', 'spread_pct', 'volume', 'change_pct', 'rel_volume', 'rsi_14')
        # A Finviz export timestamp is retrieval, not provider observation proof.
        source = value.get('source')
        clock = value.get('provider_as_of') or _iso(value.get('event_time_ns')) or value.get('as_of')
        if source == 'FINVIZ_ELITE' and not publication:
            clock = value.get('provider_as_of')
        from .screener_projections import QUOTE_EVENT_STALE_MS
        ttl = QUOTE_EVENT_STALE_MS if mode in ('REALTIME', 'DELAYED') else None
        return {**value, 'decision_evidence': add(name, source, mode, clock, state='SESSION_CLOSED' if session == 'CLOSED' and market else state,
                ttl=ttl, policy='L1_EVENT_V1' if ttl else 'UNKNOWN_POLICY',
                basis='OBSERVATION_DATE' if publication else 'PROVIDER_AS_OF', reference=publication or not market,
                fetched_at=value.get('fetched_at') or (value.get('as_of') if source == 'FINVIZ_ELITE' else None),
                received_at=value.get('received_at') or _iso(value.get('received_ns')))}

    result = dict(payload)
    if path == '/screener':
        rows = []
        for row in payload.get('rows', []):
            start = len(inputs)
            # Evaluate bounded families once per row, not once per table cell.
            groups = {}
            for name, value in row.get('fields', {}).items():
                family = 'market_snapshot' if name in ('price','bid','ask','spread_pct','volume','change_pct','rel_volume','rsi_14') else 'reference_fields'
                if session == 'PUBLICATION_BASED':
                    family = 'publication:' + str(value.get('source')) + ':' + str(value.get('as_of'))
                key = (family, value.get("source"), value.get("state"), value.get("provider_as_of"), value.get("as_of"), value.get("event_time_ns"), value.get("received_ns"), value.get("value") is None)
                groups.setdefault(key, (name, value, []))[2].append(name)
            for key, (name, value, covered_fields) in groups.items():
                family = key[0]
                evidence = field(name, value, publication=session == 'PUBLICATION_BASED')['decision_evidence']
                evidence['capability'] = family
                evidence['covered_fields'] = covered_fields
            rows.append({**row, 'decision_inputs': inputs[start:]})
        result['rows'] = rows
        inputs = []  # retain per-row clocks, never one table-wide status
    if path == '/screener/window':
        result['quotes'] = {identifier: _quote(quote, identifier, now, session=session) for identifier, quote in payload.get('quotes', {}).items()}
    if 'quote' in payload:
        result['quote'] = _quote(payload['quote'], 'quote', now, session=session)
        inputs.extend(result['quote']['decision_inputs'])
    if 'key_data' in payload:
        result['key_data'] = [field(item['field'], item) for item in payload['key_data']]
    if 'bars' in payload and isinstance(payload['bars'], dict):
        bars = payload['bars']
        from ..market_data.current_bars import STALE_TOLERANCE_NS, TIMEFRAMES
        timeframe = bars.get('timeframe')
        inputs.append(evaluate(capability='bars', source=bars.get('provider'), delivery_mode='SNAPSHOT',
                     now=now, as_of=bars.get('latest_complete_bar_end'), received_at=bars.get('received_at'),
                     state=bars.get('state'), stale_after_ms=(TIMEFRAMES[timeframe] * 60_000 + STALE_TOLERANCE_NS // 1_000_000) if timeframe in TIMEFRAMES else None,
                     policy='COMPLETED_BAR_SESSION_V1', basis='LATEST_COMPLETED_BAR_END'))
    if path in ('/screener/order-flow', '/screener/cvd', '/screener/depth', '/screener/order-flow-series'):
        from .screener_specialist import FEED_SILENT_SECONDS
        capability = {'/screener/depth':'level2', '/screener/cvd':'cvd'}.get(path, 'order_flow')
        clock = payload.get('latest') or {}
        previous = payload.get('freshness') or {}
        ttl = previous.get('ttl_ms') if capability == 'level2' else FEED_SILENT_SECONDS * 1000
        add(capability, payload.get('provider'), 'REALTIME',
            payload.get('latest_received_at') or clock.get('received_at') if capability == 'level2' else payload.get('latest_event_at') or clock.get('event_at'),
            state=payload.get('state'), ttl=ttl, policy=previous.get('policy') or 'SYMBOL_FLOW_30S_V1',
            basis='RECEIVE_TIME' if capability == 'level2' else 'EVENT_TIME',
            received_at=payload.get('latest_received_at') or clock.get('received_at'),
            event_at=payload.get('latest_event_at') or clock.get('event_at'))
    if path == '/screener/options':
        clock, provider = payload.get('clock') or {}, payload.get('provider') or {}
        add('options', provider.get('id'), provider.get('delivery', 'SNAPSHOT'), clock.get('fetched_at'),
            state=payload.get('state'), ttl=clock.get('stale_after_s', 0) * 1000 or None,
            policy='OPTIONS_SNAPSHOT_V1', basis='SNAPSHOT_FETCH_TIME', reference=True,
            fetched_at=clock.get('fetched_at'), provider_as_of=clock.get('provider_as_of'),
            latest_trade_at=clock.get('latest_contract_trade_at'), reason=payload.get('reason'))
    if 'futures' in payload:
        from .screener_futures_context import LIVE_MAX_AGE_SECONDS
        for item in (payload.get('futures') or {}).get('items', []):
            quote = item.get('quote') or {}
            add('future:' + item['root'], quote.get('provider'), 'REALTIME', quote.get('as_of'),
                state=quote.get('state', 'UNAVAILABLE') if (item.get('contract') or {}).get('state') == 'CURRENT' else 'UNAVAILABLE', ttl=int(LIVE_MAX_AGE_SECONDS * 1000),
                policy='FUTURES_QUOTE_V1', reference=True, contract_state=(item.get('contract') or {}).get('state'))
    if session == 'PUBLICATION_BASED' or 'bond' in payload.get('schema_version', ''):
        for section in payload.get('sections', []):
            for item in section.get('items', []):
                # Term dates describe identity. They cannot determine currentness.
                if section.get('id') in ('identity', 'terms') or item.get('unit') == 'date':
                    continue
                add('bond:' + item['id'], item.get('source'), 'PUBLICATION_BASED', item.get('as_of'),
                    state='UNAVAILABLE' if item.get('value') is None else 'STALE' if item.get('class') == 'STALE' else None,
                    basis='OBSERVATION_OR_PUBLICATION_DATE', reference=True)
    if path == '/screener/rates-curve':
        for name in ('nominal', 'real'):
            curve = payload.get(name) or {}
            if isinstance(curve, dict):
                add('rates:' + name, curve.get('source') or 'US_TREASURY', 'PUBLICATION_BASED', curve.get('publication_date') or curve.get('date'), state=curve.get('state'), reference=True, basis='PUBLICATION_DATE')
    if path == '/screener/connectivity':
        nodes = []
        for node in payload.get('nodes', []):
            domain = node.get('domain')
            mode = 'PUBLICATION_BASED' if domain == 'BONDS_RATES' else 'SNAPSHOT' if domain == 'OPTIONS' else 'REALTIME' if node.get('state') in ('LIVE','CURRENT','STALE') else 'UNKNOWN'
            ttl = 15000 if domain == 'FUTURES' and mode == 'REALTIME' else 60000 if domain == 'STOCK_ETF' and mode == 'REALTIME' else None
            # Never substitute latest contract trade for an Options snapshot clock.
            evidence = node.get('decision_evidence') or add('node:' + node['node_id'], node.get('source'), mode, node.get('as_of'), state=node.get('state'), ttl=ttl, policy='CROSS_ASSET_SOURCE_V1' if ttl else 'UNKNOWN_POLICY', reference=domain in ('OPTIONS','FUTURES','BONDS_RATES'), received_at=node.get('received_at'))
            if node.get('decision_evidence'):
                inputs.append(evidence)
            nodes.append({**node, 'decision_evidence': evidence})
        result['nodes'] = nodes
        result['selected_instrument'] = next((n for n in nodes if n['node_id'] == (payload.get('selected_instrument') or {}).get('node_id')),payload.get('selected_instrument'))
    moving = (payload.get('why') or {}).get('moving')
    if moving:
        items = []
        for index, item in enumerate(moving.get('items', [])):
            # Derived claims inherit the strictest input state instead of a new clock.
            kind = item.get('kind')
            dependencies = [i for i in inputs if i['capability'] in ('quote', 'bars')] if kind == 'SR_PROXIMITY' else [i for i in inputs if i['capability'] == 'quote'] if kind == 'PRICE_MOVE' else []
            blocked = any(not i['eligible_for_current_decision'] for i in dependencies)
            evidence = add('movement:' + str(index), item.get('source'), 'PUBLICATION_BASED' if kind in ('HEADLINE','CATALYST') else 'SNAPSHOT', item.get('as_of'), state='UNAVAILABLE' if blocked or item.get('class') in ('UNAVAILABLE','INSUFFICIENT_EVIDENCE') else None, reference=True, basis='PUBLICATION_TIME' if kind in ('HEADLINE','CATALYST') else 'DERIVED_INPUT_TIME', reason='DEPENDENCY_INELIGIBLE' if blocked else None)
            items.append({**item, 'decision_evidence': evidence})
        result['why'] = {**payload['why'], 'moving': {**moving, 'items': items}}
    if path == '/screener/squeeze':
        sections = payload.get('sections') or {}
        for section in sections.values():
            if isinstance(section, dict):
                continue  # exhaustion derives other metrics; no new observation clock
            for metric in section:
                clock = metric.get('clock') or {}
                kind = clock.get('kind')
                mode = 'PUBLICATION_BASED' if kind in ('PUBLICATION','DAILY_LIST') else 'REALTIME' if kind == 'STREAMING' else 'SNAPSHOT' if kind in ('SNAPSHOT','PROVIDER') else 'UNKNOWN'
                add('squeeze:' + metric['id'], metric.get('source'), mode, clock.get('as_of'), state=metric.get('quality'), reference=mode != 'REALTIME', basis=kind or 'UNKNOWN', policy='SQUEEZE_SOURCE_POLICY')
    if path in ('/screener/news', '/screener/news/instrument'):
        from .screener_news import WINDOWS
        window = (payload.get('window') or {}).get('id')
        if not payload.get('stories', payload.get('items', [])):
            add('news', None, 'PUBLICATION_BASED', None, state='UNAVAILABLE', reference=True, basis='PUBLICATION_TIME', reason='NO_PUBLISHED_STORIES')
        for story in payload.get('stories', payload.get('items', [])):
            add('news:' + str(story.get('story_id', story.get('id','unknown'))), story.get('provider_id') or ','.join(source.get('provider_id', '') for source in story.get('sources', [])) or None, 'PUBLICATION_BASED', story.get('published_at'), reference=True, basis='PUBLICATION_TIME', fetched_at=story.get('first_retrieved_at'), ttl=WINDOWS[window] * 1000 if window in WINDOWS else None, policy='NEWS_PUBLICATION_RELEVANCE_V1')
    return {**result, 'decision_inputs': inputs}


def _quote(payload: dict, capability: str, now: str, *, session: str | None = None) -> dict:
    from .screener_projections import QUOTE_EVENT_STALE_MS
    price = (payload.get('fields') or {}).get('price') or {}
    state = payload.get('state', 'UNAVAILABLE') if price.get('value') is not None else 'UNAVAILABLE'
    mode = 'DELAYED' if 'DELAY' in str(payload.get('quality',state)) else payload.get('delivery_mode', 'REALTIME' if state in ('LIVE','STALE') else 'UNKNOWN')
    evidence = evaluate(capability=capability,source=price.get('source'),delivery_mode=mode,now=now,
                        as_of=price.get('provider_as_of') or _iso(price.get('event_time_ns')) or price.get('as_of'),
                        received_at=price.get('received_at') or _iso(price.get('received_ns')),
                        stale_after_ms=QUOTE_EVENT_STALE_MS,policy='L1_EVENT_V1',basis='PROVIDER_EVENT_TIME',state='SESSION_CLOSED' if session == 'CLOSED' and state in ('LIVE','DELAYED') else state)
    return {**payload,'decision_inputs':[evidence]}

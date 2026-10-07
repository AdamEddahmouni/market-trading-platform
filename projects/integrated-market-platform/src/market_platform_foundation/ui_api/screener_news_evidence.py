"""OCT1-05 bounded projection of S11 receipts, never a provider pipeline.

Headline language and observed direction are compared, not forecasts or causes.
Shared providers may refresh on explicit Run. Instrument caches are read only.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime

from ..market_data.freshness_contract import evaluate, timestamp
from ..news.finbert_sentiment import BASIS, SENTIMENT_VERSION, summarize
from ..news.instrument_matching import EXACT, CONTEXT, match_profile, profile_for_row, entity_name, CRYPTO_ASSET_NAMES
from ..intelligence.inference.candidate_reduction import build_candidate, MAX_INTAKE, MAX_PACKET_BYTES, packet_candidates
from ..intelligence.inference.hashing import input_hash_from_dict

VERSION = 'screener-news-evidence/1.0.0'
ALIGNMENT_METHOD = 'headline-language-vs-observed-direction/1.0.0'
WINDOW = '4h'
MAX_STORIES = 3
NOTE = 'Headline language sentiment; no forecast, causal proof or trade confirmation. Source counts describe syndication, not credibility.'


def alignment(tone: str | None, direction: str | None) -> str:
    if not tone or not direction:
        return 'UNKNOWN'
    if tone == 'MIXED':
        return 'MIXED'
    if tone == 'NEUTRAL' or direction == 'NEUTRAL':
        return 'CONTEXT_ONLY'
    return 'CONFIRMING' if tone == direction else 'CONFLICTING'


def _coverage(service, provider, query, applicable):
    from .screener_news import provider_status
    if not applicable or not query:
        return [], provider_status(provider, None, scope='INSTRUMENT')
    entry = service._cache.peek((provider, query.upper()))
    if entry is not None:
        result = entry.value if entry.ok else {'success': False, 'error': entry.reason}
        status = provider_status(provider, result, scope='INSTRUMENT')
        status['fetched_at'] = status.get('fetched_at') or entry.fetched_at
        status['snapshot_at'] = entry.fetched_at
        if entry.expires_at <= service._clock() or entry.reason:
            status.update(state='STALE', reason='CACHED_RECEIPT_EXPIRED_OR_REFRESH_FAILED')
        return list(result.get('items') or []), status
    flags = {'newsapi': ('IMP_NEWSAPI_LIVE', 'NEWSAPI_API_KEY'), 'finnhub': ('IMP_FINNHUB_LIVE', 'FINNHUB_API_KEY'),
             'sec_filings': ('IMP_EDGAR_LIVE', 'SEC_USER_AGENT')}
    flag, key = flags[provider]
    state = 'LIVE_DISABLED' if service._env(flag) != '1' else 'NOT_CONFIGURED' if not service._env(key) else 'NOT_CACHED'
    return [], {**provider_status(provider, None, scope='INSTRUMENT'), 'state': state,
                'reason': 'NO_INSTRUMENT_REFRESH_FOR_AI_REDUCTION'}


def project_news(service, *, universe: str, rows: list[dict], refresh: bool = False) -> dict:
    """Bounded candidates and at most MAX_INTAKE * MAX_STORIES unique scores; zero instrument provider calls.

    Candidate profiles reuse canonical matching. S11 cache receipts supply the
    ingestion clock for this projection, so identical receipts preserve identity.
    """
    from .screener_news import WINDOWS, provider_status, aggregate_state, _finviz_published
    if len(rows) > MAX_INTAKE:
        raise ValueError('INTAKE_BOUND_EXCEEDED')
    shared = []
    statuses = []
    for provider, cache_key in [('finviz', ('finviz',)), ('rss', ('rss', universe))]:
        if refresh:
            items, status = service._finviz_items() if provider == 'finviz' else service._rss_items(universe)
        else:
            entry = service._cache.peek(cache_key)
            if entry is None:
                items, status = [], {**provider_status(provider, None, scope='UNIVERSE'), 'state': 'NOT_CACHED', 'reason': 'PREVIEW_CACHE_ONLY'}
            elif provider == 'rss' and entry.ok:
                items = entry.value['items']
                state, reason = aggregate_state(entry.value['feeds'])
                status = {'id': provider, 'state': state, 'reason': reason, 'scope': 'UNIVERSE', 'fetched_at': entry.fetched_at}
            else:
                result = entry.value if entry.ok else {'success': False, 'error': entry.reason}
                items, status = list(result.get('items') or []), provider_status(provider, result, scope='UNIVERSE')
        entry = service._cache.peek(cache_key)
        # Project one detached receipt consistently, even if a refresh completed
        # between the shared-source call and this read. Preview uses S11's exact
        # Eastern-wall-clock conversion too; raw export time is never UTC.
        if entry is not None and entry.ok:
            if provider == 'finviz':
                result = entry.value
                items = [{**item, 'published_time': _finviz_published(item) or item.get('published_time') or '',
                          'quality_flags': ['PUBLISHED_TIME_US_EASTERN_WALL_CLOCK'] if _finviz_published(item) else []}
                         for item in result.get('items') or []]
                status = provider_status(provider, {**result, 'received_at': result.get('received_at') or entry.fetched_at}, scope='UNIVERSE')
            else:
                items = entry.value['items']
                state, reason = aggregate_state(entry.value['feeds'])
                status = {'id': provider, 'state': state, 'reason': reason, 'scope': 'UNIVERSE', 'fetched_at': entry.fetched_at}
        status['snapshot_at'] = entry.fetched_at if entry else None
        if entry and (entry.expires_at <= service._clock() or entry.reason):
            status.update(state='STALE', reason='CACHED_RECEIPT_EXPIRED_OR_REFRESH_FAILED')
        statuses.append(status)
        shared.extend((provider, {**item, 'received_time': item.get('received_time') or item.get('received_at') or status.get('snapshot_at'), '_snapshot_at': status.get('snapshot_at')}) for item in items)
    now = datetime.fromtimestamp(service._clock(), UTC)
    cutoff = now.isoformat().replace('+00:00', 'Z')
    projections, selected = {}, {}
    for row in rows:
        profile = profile_for_row(universe, row)
        identifier = profile.instrument_id
        if identifier in projections:
            continue
        raw, providers = list(shared), list(statuses)
        names = CRYPTO_ASSET_NAMES.get(str(row.get('base_asset') or '').upper()) if universe == 'CRYPTO' else None
        query = (names[0] if names else None) if universe == 'CRYPTO' else entity_name(row.get('company'))
        query = query if query and len(query) >= 4 else profile.symbol
        for provider, query_value, applicable in [('newsapi', query, universe in ('US_EQUITIES','US_ETFS','CRYPTO')),
                ('finnhub', profile.symbol, universe in ('US_EQUITIES','US_ETFS')),
                ('sec_filings', profile.symbol, universe == 'US_EQUITIES')]:
            items, status = _coverage(service, provider, query_value, applicable)
            providers.append(status)
            raw.extend((provider, {**item, 'received_time': item.get('received_time') or item.get('received_at') or status.get('fetched_at'), '_snapshot_at': status.get('snapshot_at')}) for item in items)
        provider_by_id = {p['id']: p for p in providers}
        records = service._records(raw, universe)
        receipts = {(provider, str(item.get('url') or item.get('headline') or '').strip()): item.get('_snapshot_at') for provider, item in raw}
        provider_receipts = {p['id']: p.get('snapshot_at') for p in providers}
        for record in records:
            record.ingested_time = receipts.get((record.provider_id, record.event.url or record.event.headline)) or provider_receipts.get(record.provider_id)
            record.matches = match_profile(profile, headline=record.event.headline, summary=record.event.summary,
                tickers=record.tickers, categories=[cat.id for cat in record.categories], cik=record.cik)
        records = [r for r in records if any(m.confidence in (EXACT, CONTEXT) for m in r.matches)
                   and all(timestamp(clock) is None or timestamp(clock) <= now for clock in (r.available_time, r.event.retrieved_time, r.ingested_time))]
        stories = service._stories(records)
        stories = [s for s in stories if s.moment and 0 <= (now-s.moment).total_seconds() < WINDOWS[WINDOW]]
        stories.sort(key=lambda s: (s.strength, -(s.moment.timestamp()), s.story_id))
        stories = stories[:MAX_STORIES]
        projections[identifier] = {'schema_version': VERSION, 'window': WINDOW, 'snapshot_at': cutoff,
            'providers': [{k: p.get(k) for k in ('id','state','reason','fetched_at','snapshot_at')} for p in providers],
            'stories': [], 'limitations': [NOTE, 'Instrument providers are cache-only; coverage may be partial.']}
        selected[identifier] = (stories, provider_by_id)
    unique = {s.story_id: s for stories, _ in selected.values() for s in stories}
    ordered = [unique[key] for key in sorted(unique)]
    model = service.sentiment_model()
    texts = [s.representative.event.headline for s in ordered]
    scores = model.score(texts) if refresh else model.cached_scores(texts)
    model_status = model.status()
    scores = {story.story_id: {**score, 'model_revision': model_status.get('model_revision'),
              'sentiment_version': SENTIMENT_VERSION, 'basis': BASIS} for story, score in zip(ordered, scores)}
    for identifier, (stories, providers) in selected.items():
        value = projections[identifier]
        for story in stories:
            item = story.to_dict(scores[story.story_id])
            source_states = [providers[r.provider_id]['state'] for r in story.members]
            current = 'CURRENT' in source_states
            delayed = not current and 'DELAYED' in source_states
            state = 'CURRENT' if current else 'DELAYED' if delayed else 'STALE'
            moment = item['published_at'] or item['first_retrieved_at']
            status = evaluate(capability='news:'+story.story_id, source=','.join(sorted({r.provider_id for r in story.members})),
                delivery_mode='DELAYED' if delayed else 'PUBLICATION_BASED', now=cutoff, as_of=moment,
                stale_after_ms=WINDOWS[WINDOW]*1000, reference=True, state=state,
                policy='NEWS_PUBLICATION_RELEVANCE_V1', basis='PUBLICATION_TIME' if item['published_at'] else 'RETRIEVAL_PROXY')
            item.update(status=status, coverage_state=state, window=WINDOW,
                        match_basis=story.matches[0].basis, match_confidence=story.matches[0].confidence)
            item['headline'] = item['headline'][:320]
            item['membership_hash'] = input_hash_from_dict({'members': sorted(r.event.event_id for r in story.members)})
            item.pop('summary', None)
            item['omitted_source_records'] = max(0, len(item['sources'])-3)
            item['sources'] = item['sources'][:3]
            item['matches'] = [m.to_dict() for m in story.matches if m.confidence in (EXACT, CONTEXT)][:3]
            item['categories'] = item['categories'][:3]
            value['stories'].append(item)
        usable = [s for s in value['stories'] if s['status']['eligible_for_reference']]
        value['state'] = 'AVAILABLE' if usable else 'NO_RELEVANT_STORIES' if any(p['state'] in ('CURRENT','DELAYED') for p in value['providers']) else 'PROVIDER_UNAVAILABLE'
        tone = summarize([s['sentiment'] for s in usable], model_status=model_status)
        value['sentiment'] = {**tone, 'model_revision': model_status.get('model_revision'), 'sentiment_version': SENTIMENT_VERSION,
                              'basis': BASIS, 'window': WINDOW}
    return projections


def attach_news(candidate: dict, news: dict, *, now: str) -> None:
    """Join gated reference facts and reproducible pairwise comparisons."""
    observations = []
    for story in news['stories']:
        facts = {key: value for key, value in story.items() if key != 'status'}
        # Source metadata remains bounded but nested probabilities must survive.
        facts['sentiment'] = story['sentiment']
        quality = []
        if story['coverage_state'] != 'CURRENT':
            quality.append('DELAYED_OR_STALE_PROVIDER')
        if not story['published_at']:
            quality.append('PUBLICATION_UNKNOWN_RETRIEVAL_PROXY')
        observations.append(('NEWS', story['status'], facts, quality))
    admitted = [s for s in news['stories'] if s['status']['eligible_for_reference']]
    if admitted and news['sentiment']['scored']:
        status = min((s['status'] for s in admitted), key=lambda s: s['valid_until'] or '')
        quality = ['PARTIAL_SCORING'] if news['sentiment']['unscored'] else []
        if any(s['coverage_state'] != 'CURRENT' or not s['published_at'] for s in admitted):
            quality.append('REFERENCE_QUALITY_LIMITED')
        observations.append(('SENTIMENT', status, news['sentiment'], quality))
    projected = build_candidate(candidate['instrument'], observations, now=now)
    candidate['reference_evidence'].extend(projected['reference_evidence'])
    candidate['blocked'].extend(projected['blocked'])
    candidate['weak'].extend(projected['weak'])
    present = {e['capability'] for e in candidate['reference_evidence']}
    candidate['missing'][:] = [m for m in candidate['missing'] if m['capability'] not in present]
    candidate['news'] = {k:v for k,v in news.items() if k != 'stories'}
    candidate['news']['story_count'] = len([e for e in projected['reference_evidence'] if e['capability']=='NEWS'])
    all_items = [*candidate['current_market_evidence'], *candidate['reference_evidence']]
    candidate['sufficient'] = bool(candidate['instrument'].get('instrument_id')
        and any(e['capability'] == 'QUOTE' and e['facts'].get('price') is not None and not e['weak_reasons']
                for e in candidate['current_market_evidence'])
        and any(e['capability'] != 'QUOTE' and not e['weak_reasons'] for e in all_items))
    tone_items = [e for e in all_items if e['capability'] == 'SENTIMENT']
    sentiment = tone_items[0] if tone_items else None
    candidate['alignments'] = []
    for family, field, label in [('TECHNICALS','change_pct','PRICE'), ('ORDER_FLOW','net_signed_volume','FLOW')]:
        comparators = [e for e in candidate['current_market_evidence'] if e['capability'] == family and field in e['facts'] and not e['weak_reasons']]
        comparator = comparators[0] if len(comparators) == 1 else None
        value = comparator['facts'][field] if comparator else None
        direction = ('POSITIVE' if value > 0 else 'NEGATIVE' if value < 0 else 'NEUTRAL') if isinstance(value,(int,float)) and math.isfinite(value) else None
        tone = news['sentiment']['dominant'] if sentiment and not sentiment['weak_reasons'] else None
        result = alignment(tone, direction)
        comparison = dict(kind='NEWS_SENTIMENT_VS_'+label, method=ALIGNMENT_METHOD, result=result,
            observed_direction=direction, sentiment_refs=[sentiment['evidence_id']] if sentiment else [],
            news_refs=[e['evidence_id'] for e in candidate['reference_evidence'] if e['capability']=='NEWS'],
            comparator_ref=comparator['evidence_id'] if comparator else None, cutoff=now,
            limitations=['LANGUAGE_NOT_FORECAST_OR_TRADE_CONFIRMATION', '4H_REFERENCE_VS_OBSERVATION_WINDOW'])
        comparison['alignment_id'] = 'AL:'+input_hash_from_dict({k:v for k,v in comparison.items() if k!='cutoff'})[:32]
        candidate['alignments'].append(comparison)


def fit_news(scope: dict, candidates: list[dict], projections: dict, *, now: str) -> None:
    """Deterministic global thinning before inference, never raise the 96KB cap.

    Rebuild NEWS/SENTIMENT/alignments after each removal so refs and counts agree.
    Reserve bytes for cutoff and scope serialization; aliases are not copied in packets.
    Thin per-provider status detail on candidates carrying no story before
    removing reference evidence. Repeat after each story removal, since a
    newly empty candidate can release coverage metadata without losing facts.
    """
    def over():
        return len(json.dumps(dict(scope=scope, decision_cutoff=now, candidates=packet_candidates(candidates)), ensure_ascii=False, sort_keys=True).encode('utf-8')) > MAX_PACKET_BYTES

    def thin_empty_coverage():
        for candidate in sorted(candidates, key=lambda c: c['instrument']['instrument_id'], reverse=True):
            status = candidate.get('news')
            if not status or status['story_count'] or not status['providers']:
                continue
            if not over():
                break
            status['providers'] = []
            status['limitations'] = [*status['limitations'], 'GLOBAL_PACKET_STATUS_CAP']

    thin_empty_coverage()
    while over():
        target = max((c for c in candidates if projections.get(c['instrument']['instrument_id'],{}).get('stories')), key=lambda c: (len(projections[c['instrument']['instrument_id']]['stories']), c['instrument']['instrument_id']), default=None)
        if target is None:
            break
        news = projections[target['instrument']['instrument_id']]
        news['stories'].pop()
        news['state'] = 'PACKET_LIMITED'
        # Reaggregate from remaining admitted stories with the canonical count method.
        status = {'state': 'CURRENT' if news['sentiment']['model_id'] else 'NOT_CONFIGURED', 'model_id': news['sentiment']['model_id']}
        metadata = {k:news['sentiment'].get(k) for k in ('model_revision','sentiment_version','basis','window')}
        news['sentiment'] = {**summarize([s['sentiment'] for s in news['stories'] if s['status']['eligible_for_reference']], model_status=status), **metadata}
        news['limitations'] = list(dict.fromkeys([*news['limitations'], 'GLOBAL_PACKET_STORY_CAP']))
        for key in ('reference_evidence','blocked','weak'):
            target[key][:] = [e for e in target[key] if e.get('capability') not in ('NEWS','SENTIMENT')]
        for capability in ('NEWS','SENTIMENT'):
            if not any(m['capability']==capability for m in target['missing']):
                target['missing'].append({'capability':capability,'reason':'NO_INTERNAL_EVIDENCE'})
        attach_news(target, news, now=now)
        thin_empty_coverage()

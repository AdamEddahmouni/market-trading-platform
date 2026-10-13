"""Synthetic integrated demonstration. No provider, inference or order adapter."""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.news.collection import CollectionJob, NewsCollector
from market_platform_foundation.news.knowledge import StoredNewsRepository
from market_platform_foundation.news.normalize import normalize_raw_item
from market_platform_foundation.intelligence.inference.paper_automation import plan_local_inference_dry_run
from market_platform_foundation.intelligence.news_strategy_evaluation.fixture_loader import load_fixture_pack
from market_platform_foundation.intelligence.news_strategy_evaluation.replay import EvaluationReplayHarness
from market_platform_foundation.intelligence.news_strategy_evaluation.features import build_feature_snapshot
from market_platform_foundation.intelligence.news_strategy_evaluation.market_data import FixtureMarketDataProvider
from market_platform_foundation.intelligence.news_strategy_evaluation.decisions import build_evaluation_decision
from market_platform_foundation.intelligence.news_strategy_evaluation.policies import PolicyRegistry
from market_platform_foundation.intelligence.news_strategy_evaluation.config import EvaluationConfig
from market_platform_foundation.intelligence.news_strategy_evaluation.outcomes import measure_outcome
from market_platform_foundation.intelligence.news_strategy_evaluation.journal import (
    capture_decision_snapshot, observe_outcome, build_daily_journal,
)


def run_offline_demo(output_dir: Path) -> dict:
    """Fresh explicit fixture directory; refuses reuse of an existing database."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / 'synthetic-imp-state.sqlite3'
    if path.exists():
        raise ValueError('DEMO_REQUIRES_FRESH_FIXTURE_DIRECTORY')
    pack = load_fixture_pack()
    sample = pack.samples[0]
    clock = [datetime.fromisoformat('2026-09-09T00:01:00+00:00').timestamp()]
    news = [dict(provider_native_id='synthetic-cpi', headline='CPI inflation cooler than expected',
                 summary='Synthetic release for offline software demonstration',
                 published_time='2026-09-09T00:00:00Z', instrument_ids=[sample.instrument_id],
                 url='https://example.test/synthetic-cpi')]

    def fetch(job):
        retrieved = datetime.fromtimestamp(clock[0], timezone.utc).isoformat()
        events = [(normalize_raw_item(raw, provider_id='news.fixture', source_id='globe_newswire',
                   retrieved_time=retrieved),
                   dict(evidence_class='SOFTWARE_FIXTURE_ONLY', license='SYNTHETIC_FIXTURE',
                        source_reference='professor-integration/synthetic-fixture/1')) for raw in news]
        return events, {'state': 'CURRENT'}

    connection = LocalStateConnection(path)
    try:
        collector = NewsCollector(connection, [CollectionJob('finviz', '', 'US_EQUITIES', 120)],
                                  fetch, clock=lambda: clock[0])
        collector.step()
        clock[0] += 180
        collector.step()  # unchanged poll: no duplicate record
        for index in (2, 3):
            news[:] = [{**news[0], 'provider_native_id': f'synthetic-{index}',
                        'url': f'https://example.test/synthetic-{index}'}]
            clock[0] += 180
            collector.step()
        repository = StoredNewsRepository(connection)
        content_records = repository.retrieve(as_of='2026-09-09T07:30:00Z')
        # Explicit fixture-only allowance for request envelope and bounded output. Stored content
        # estimates alone are not eligible for a request budget.
        records = [{**row, 'estimated_tokens': row['estimated_tokens'] + 4096,
                    'token_estimate_scope': 'REQUEST_AND_OUTPUT_BOUND'} for row in content_records]
        options = dict(schedule=dict(max_requests=2, max_tokens=20000, max_backlog=3),
            session_is_trading_day=True, engine='anthropic', model='claude-haiku-5-5',
            provider_configured=True, provider_available=True, resource_allowed=True,
            budget_status=dict(requests=0, tokens=0, max_requests=2, max_tokens=20000),
            provider_gate=dict(allowed=True, reason=None))
        # Availability and allowances here are explicitly SIMULATED, never production claims.
        overnight = plan_local_inference_dry_run(records, now=datetime.fromisoformat('2026-09-09T06:00:00+00:00'), **options)
        morning = plan_local_inference_dry_run(records, now=datetime.fromisoformat('2026-09-09T07:30:00+00:00'), **options)
        blocked = plan_local_inference_dry_run(records, now=datetime.fromisoformat('2026-09-09T07:30:00+00:00'),
            **{**options, 'budget_status': dict(requests=2, tokens=0, max_requests=2, max_tokens=20000)})
        unverified = plan_local_inference_dry_run(records, now=datetime.fromisoformat('2026-09-09T07:30:00+00:00'),
            **{**options, 'provider_available': None, 'provider_gate': dict(allowed=False, reason='ENTITLEMENT_NOT_VERIFIED')})
        bounded_scan = False
        try:
            repository.retrieve(as_of='2026-09-09T07:30:00Z', max_scan_records=1)
        except ValueError as exc:
            bounded_scan = str(exc) == 'NEWS_KNOWLEDGE_SCAN_BOUND'
        stored = connection.fetchone('SELECT COUNT(*) AS n FROM news_collection_records')['n']
        # Later article arrives with an earlier publication date: unavailable to the earlier decision.
        news[:] = [{**news[0], 'provider_native_id': 'synthetic-late', 'url': 'https://example.test/synthetic-late'}]
        clock[0] = datetime.fromisoformat('2026-09-09T16:00:00+00:00').timestamp()
        collector.step()
        decision_records = repository.retrieve(as_of=sample.as_of)
        later_records = repository.retrieve(as_of='2026-09-09T17:00:00Z')
        future_excluded = len(later_records) == len(decision_records) + 1
        # Feed the exact locally saved versions into the existing feature/policy contracts.
        events = tuple(normalize_raw_item(row['article'], provider_id=row['article']['provider_id'],
                       source_id=row['article']['source_id'], retrieved_time=row['article']['retrieved_time'])
                       for row in decision_records)
        provider = FixtureMarketDataProvider.from_fixture_payload(pack.raw_payload)
        snapshot = build_feature_snapshot(as_of=sample.as_of, instrument_id=sample.instrument_id,
            asset_class=sample.asset_class, events=list(events), market_provider=provider)
        config = EvaluationConfig()
        policy = PolicyRegistry().get(config.baseline_policy_id, config.baseline_policy_version)
        decision = build_evaluation_decision(evaluation_run_id='SYNTHETIC-INTEGRATION', sample_id=sample.sample_id,
            policy=policy, snapshot=snapshot, config_hash=config.config_hash())
        journal_snapshot = capture_decision_snapshot(decision=decision, evidence_snapshot=snapshot)
        outcome = measure_outcome(decision=decision, horizon=config.outcome_horizons[0],
                                  market_provider=provider, flat_threshold_bps=config.directional_flat_threshold_bps,
                                  observation_as_of='2026-09-09T17:00:00Z')
        observation = observe_outcome(journal_snapshot, outcome, observed_at='2026-09-09T17:00:00Z')
        early_journal = build_daily_journal([journal_snapshot], day='2026-09-09', observation_as_of=sample.as_of,
                                          outcomes=[observation])
        late_journal = build_daily_journal([journal_snapshot], day='2026-09-09', observation_as_of='2026-09-09T17:00:00Z',
                                         outcomes=[observation])
        replay_pack = replace(pack, samples=(replace(sample, events=events, inference_record=None),))
        harness = EvaluationReplayHarness()
        view = harness.snapshot_at(replay_date='2026-09-09', as_of=sample.as_of, pack=replay_pack)
        second = harness.snapshot_at(replay_date='2026-09-09', as_of=sample.as_of, pack=replay_pack)
        result = dict(evidence_class='SOFTWARE_FIXTURE_ONLY', fixture_date='2026-09-09',
            operating_schedule_timezone='America/New_York', simulated_provider_and_budget_facts=True,
            storage=dict(committed_records=stored + 1, bounded_scan_blocked=bounded_scan,
                         indexed='EXISTING_RECORD_PK', searchable='BOUNDED_LOCAL_QUERY'),
            knowledge=decision_records, overnight=overnight, morning=morning, budget_blocked=blocked,
            provider_unverified=unverified, early_journal=early_journal, late_journal=late_journal,
            future_knowledge_excluded=future_excluded, replay=dict(view=view, deterministic=view == second),
            providers_contacted=0, inference_calls=0, orders_submitted=0,
            limitations=['SYNTHETIC_NEWS_AND_CURATED_PRICE_FIXTURE', 'NO_ACTUAL_TRADES_OR_FILL_COST_MODEL',
                         'NO_EMPIRICAL_STRATEGY_EDGE', 'LEGACY_MARKET_RECEIPT_TIME_UNKNOWN'])
    finally:
        connection.close()
    reopened = LocalStateConnection(path, require_existing=True)
    try:
        result['restart'] = dict(stored_records=reopened.fetchone('SELECT COUNT(*) AS n FROM news_collection_records')['n'],
                                 inference_calls=0, collectors_started=0, automation_resumed=False)
    finally:
        reopened.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    from market_platform_foundation.offline_guard import install_guard
    denials = []
    install_guard(denials)
    result = run_offline_demo(args.output_dir.resolve())
    result['offline_guard_denials'] = denials
    target = args.output_dir / 'demonstration.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(evidence_class=result['evidence_class'], output=str(target),
                         committed_records=result['storage']['committed_records'],
                         planned_requests=result['morning']['planned_requests'],
                         deterministic=result['replay']['deterministic'], inference_calls=0, providers_contacted=0)))


if __name__ == '__main__':
    main()

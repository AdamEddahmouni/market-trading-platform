"""OCT1-10 lifecycle projection timings. SOFTWARE_CONTROLLED, local, in-process.

Builds a controlled experiment through the production decision, stop and Paper
routes (the OCT1-10 test fixtures), then times the two read models. Prints JSON
to stdout. Not a market or strategy measurement.

    PYTHONPATH=src python tools/research/measure_oct1_10_performance.py > artifacts/oct1-10-performance.json
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from tests.trading_correctness.test_trade_lifecycle import A, N, _Lifecycle  # noqa: E402


def _ms(samples):
    ordered = sorted(samples)
    return dict(mean_ms=round(statistics.fmean(ordered), 3), p95_ms=round(ordered[max(0, int(len(ordered) * 0.95) - 1)], 3),
                max_ms=round(ordered[-1], 3), samples=len(ordered))


def _time(call, repeat=30):
    samples = []
    for _ in range(repeat):
        started = time.perf_counter()
        value = call()
        samples.append((time.perf_counter() - started) * 1000)
    return value, _ms(samples)


class _Scenario(_Lifecycle):
    def runTest(self):  # pragma: no cover - driven by main()
        pass


def main():
    case = _Scenario()
    case.setUp()
    try:
        closed = 12
        for _ in range(closed):
            case.enter(quantity=1, price='150.00')
            case.governed(case.exit(price='151.00'), price='151.00')
            case.tick()
        run, _ = case.enter(quantity=6, price='150.00')
        case.stops.configure(dict(enabled=True, sma_window_bars=2))
        case.anchor, case.closes = int(case.t * 1e9), []
        for close in (14000, 14000, 14100, 14200, 14300, 14400):
            case.bar(close)
            case.stops.evaluate(A)
        for _ in range(8):
            case.tick()
            case.decide(case.new_run(A, price=151.0), 'HOLD')
        case.order(N, 'BUY', 2, '300.00')
        latest = case.new_run(A, N)
        ledger = case.store.paper_ledger
        listing, list_timing = _time(lambda: case.service.list(run_id=latest, closed_limit=20))
        open_id = next(row['lifecycle_id'] for row in listing['selected'] if row['symbol'] == A)
        detail, detail_timing = _time(lambda: case.service.detail(open_id, run_id=latest))
        closed_detail, closed_timing = _time(lambda: case.service.detail(listing['recent_closed'][0]['lifecycle_id']))
        evidence = detail['candidate']['evidence']
        print(json.dumps(dict(
            schema_version='oct1-10-performance/1.0.0', classification='SOFTWARE_CONTROLLED', not_market_evidence=True,
            method='in-process time.perf_counter over the production TradeLifecycleService; SQLite local state; controlled fixtures for clock, bars, marks, candidates and model',
            dataset=dict(ledger_events=len(ledger.events), fills=len(ledger.project_trades()), closed_episodes=closed, open_positions=2,
                         decisions_for_instrument=len(case.repo.history(A)), stop_events=case.stops.repository.event_count(ledger.paper_account_id, A)),
            list_projection=dict(selected=len(listing['selected']), active_managed=len(listing['active_managed']), unlinked=len(listing['unlinked']),
                                 recent_closed=len(listing['recent_closed']), payload_bytes=len(json.dumps(listing).encode('utf-8')), **list_timing),
            detail_projection_open=dict(timeline_events=len(detail['timeline']), decisions=len(detail['decisions']),
                                        evidence_items=sum(len(evidence[g]['items']) for g in ('supporting', 'conflicting', 'weak')),
                                        prior_episodes=len(detail['prior_episodes']), prior_episodes_truncated=detail['prior_episodes_truncated'],
                                        payload_bytes=len(json.dumps(detail).encode('utf-8')), **detail_timing),
            detail_projection_closed=dict(timeline_events=len(closed_detail['timeline']), decisions=len(closed_detail['decisions']),
                                          payload_bytes=len(json.dumps(closed_detail).encode('utf-8')), **closed_timing),
            bounds=dict(listing['bounds'], evidence_per_category=8, timeline_events=200, decisions=50, prior_episodes=5),
            browser=dict(requests_per_panel_refresh=1, requests_to_expand_one_lifecycle=1, list_poll_interval_seconds=15),
            model_calls_by_reads=0, provider_calls_by_reads=0), indent=2, sort_keys=True))
    finally:
        case.doCleanups()


if __name__ == '__main__':
    main()

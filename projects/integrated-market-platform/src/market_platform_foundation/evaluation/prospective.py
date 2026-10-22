"""OCT1-11 deterministic evaluation. Financial sums use ledger minor units.

Normalized records reference immutable sources; final runs freeze only the
bounded read model and its source hashes, never another copy of evidence blobs.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from statistics import median
from zoneinfo import ZoneInfo

from ..intelligence.inference.trade_lifecycle import iso_ns

def ns_of(value):
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None:
            return None
        delta = instant.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
        return (delta.days * 86400 + delta.seconds) * 1_000_000_000 + delta.microseconds * 1000
    except (ValueError, TypeError, OverflowError):
        return None
from ..intelligence.paper_forward_bridge.temporal import assert_source_time_at_or_before_decision

SCHEMA = 'prospective-evaluation-run/1.0.0'
METRICS = 'prospective-metrics/1.0.0'
CLASSES = ('PROSPECTIVE_PAPER_WITH_LIVE_OBSERVATIONAL_DATA', 'PROSPECTIVE_SIGNAL_ONLY',
           'SOFTWARE_CONTROLLED', 'HISTORICAL_REPLAY', 'FIXTURE')
DIMENSIONS = ('setup', 'asset', 'regime', 'model', 'prompt', 'direction', 'instrument', 'stop_policy', 'policy')
POLICY = dict(policy_id='outcome-evaluation/1.0.0', schema_version='outcome-evaluation-policy/1.0.0',
              created_at='2026-10-06T00:00:00Z', metric_definition_version=METRICS, currency='USD',
              signal_horizons='SOURCE_NEXT_SESSION_FROZEN_POLICY', execution_outcome_policy='ACTUAL_PAPER_CLOSE',
              reference_price_basis='FROZEN_DECISION_REFERENCE_QUOTE', cost_policy='LEDGER_NET_EXPLICIT_COSTS_ONCE',
              mark_policy='CANONICAL_EQUITY_CURRENT_SNAPSHOTS_ONLY', win_definition='NET_MINOR_GT_ZERO',
              loss_definition='NET_MINOR_LT_ZERO', win_rate_denominator='COMPLETED_NONFLAT',
              flat_streak_policy='BREAK', exposure_clock='ELAPSED_WALL_TIME_INCLUDING_SESSION_GAPS',
              segment_dimensions=list(DIMENSIONS), no_losses_profit_factor='UNDEFINED')


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def ratio(n, d):
    if d is None or d == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        value = Decimal(str(n)) / Decimal(str(d))
        return format(value.normalize(), 'f')


def week(at):
    dt = datetime.fromtimestamp(ns_of(at) / 1e9, UTC).astimezone(ZoneInfo('America/New_York'))
    return (dt.date() - timedelta(days=dt.weekday())).isoformat()


def exclusion(row, cohort, cutoff, episodes):
    if row.get('evidence_class') != cohort:
        return 'EVIDENCE_CLASS_MISMATCH'
    if row.get('origin') == 'MANUAL_UNLINKED':
        return 'MANUAL_UNLINKED_NOT_AI'
    if row.get('currency') != POLICY['currency']:
        return 'CURRENCY_NOT_NORMALIZED'
    decision, frozen = ns_of(row.get('decision_time')), ns_of(row.get('decision_cutoff'))
    if decision is None or frozen is None:
        return 'MISSING_DECISION_CUTOFF'
    if frozen > decision or decision > cutoff:
        return 'DECISION_OUTSIDE_CUTOFF'
    if not all(row.get(k) for k in ('action_decision_id', 'candidate_run_id', 'evidence_snapshot_id', 'source_fingerprint')):
        return 'LINEAGE_UNAVAILABLE'
    for field in ('evidence_max_time', 'evidence_available_time'):
        instant = ns_of(row.get(field))
        if instant is None:
            return 'INPUT_CLOCK_UNAVAILABLE'
        try:
            assert_source_time_at_or_before_decision(source_time_ns=instant, decision_time_ns=frozen)
        except ValueError:
            return 'FUTURE_DECISION_INPUT'
    if row.get('quality') == 'INVALID':
        return 'INVALID_SOURCE_RECORD'
    outcome = row.get('execution_outcome')
    if outcome:
        episode = row.get('trade_episode_id')
        if not episode or episode in episodes:
            return 'DUPLICATE_OR_MISSING_EPISODE'
        entry = ns_of(outcome.get('entry_time'))
        end = ns_of(outcome.get('exit_time')) if outcome['state'] == 'CLOSED' else None
        if entry is None or entry <= decision or entry > cutoff:
            return 'INVALID_FILL_ORDERING'
        if outcome['state'] == 'CLOSED' and (end is None or end < entry or end > cutoff):
            return 'INVALID_CLOSE_ORDERING'
        if outcome.get('lineage_valid') is False:
            return 'CORRUPTED_FILL_LINEAGE'
        if outcome['state'] == 'CLOSED' and (outcome.get('net_pnl_minor') is None or outcome.get('costs_minor') is None):
            return 'ACCOUNTING_UNAVAILABLE'
    for observation in row.get('signal_outcomes', []):
        source, received = ns_of(observation.get('source_time')), ns_of(observation.get('observed_at'))
        if source is None or received is None or source <= decision or received < source or received > cutoff:
            return 'INVALID_OUTCOME_ORDERING'
        if observation.get('state') == 'INVALID':
            return 'INVALID_SIGNAL_PROVENANCE'
    return None


def aggregate(rows, cutoff):
    with localcontext() as ctx:
        ctx.prec = 28
        return _aggregate(rows, cutoff)


def _aggregate(rows, cutoff):
    closed = sorted([r for r in rows if (r.get('execution_outcome') or {}).get('state') == 'CLOSED'],
                    key=lambda r: (ns_of(r['execution_outcome']['exit_time']), r['evaluation_id']))
    values = [r['execution_outcome']['net_pnl_minor'] for r in closed]
    wins, losses = [p for p in values if p > 0], [p for p in values if p < 0]
    costs = sum(r['execution_outcome']['costs_minor'] for r in closed)
    longest = current = 0
    for value in values:
        current = current + 1 if value < 0 else 0
        longest = max(current, longest)
    executions = [r['execution_outcome'] for r in rows if r.get('execution_outcome')]
    intervals = sorted((ns_of(e['entry_time']), ns_of(e.get('exit_time')) or cutoff) for e in executions)
    covered, left, right = 0, None, None
    for start, end in intervals:
        if right is None or start > right:
            if right is not None:
                covered += right-left
            left, right = start, end
        else:
            right = max(right,end)
    if right is not None:
        covered += right-left
    start = min((ns_of(r['decision_time']) for r in rows), default=None)
    signals = [s for r in rows for s in r.get('signal_outcomes', []) if s.get('state') == 'COMPLETE']
    return dict(decisions=len(rows), signal_outcomes=len(signals), completed_trades=len(closed),
                open_censored=sum(e['state'] != 'CLOSED' for e in executions),
                unavailable=sum(not r.get('execution_outcome') and not r.get('signal_outcomes') for r in rows),
                action_counts=dict(sorted(Counter(r['action_state'] for r in rows).items())),
                quality_counts=dict(sorted(Counter(r.get('quality','MISSING') for r in rows).items())),
                wins=len(wins), losses=len(losses), flat=values.count(0), win_rate=ratio(len(wins),len(wins)+len(losses)),
                average_win_minor=ratio(sum(wins),len(wins)), average_loss_minor=ratio(sum(losses),len(losses)),
                median_win_minor=str(median([Decimal(v) for v in wins])) if wins else None, median_loss_minor=str(median([Decimal(v) for v in losses])) if losses else None,
                payoff_ratio=ratio(Decimal(ratio(sum(wins),len(wins))), abs(Decimal(ratio(sum(losses),len(losses))))) if wins and losses else None,
                expectancy_minor=ratio(sum(values),len(values)), profit_factor=ratio(sum(wins),abs(sum(losses))),
                profit_factor_status='DEFINED' if losses else 'UNDEFINED_NO_LOSSES' if wins else 'UNAVAILABLE',
                net_pnl_minor=sum(values) if values else None,
                gross_pnl_minor=sum(values)+costs if values else None, costs_minor=costs if values else None,
                commission_minor=sum(e.get('commission_minor',0) for e in (r['execution_outcome'] for r in closed)),
                fees_minor=sum(e.get('fees_minor',0) for e in (r['execution_outcome'] for r in closed)),
                cost_drag_minor=costs if values else None, slippage='NOT_SEPARATELY_MODELED',
                longest_losing_streak=longest, current_losing_streak=current,
                executed_notional_minor=sum(e.get('executed_notional_minor',0) for e in executions),
                exposure_seconds=ratio(covered,1_000_000_000) if intervals else None,
                time_in_market_fraction=ratio(covered,cutoff-start) if intervals and start is not None else None,
                average_gross_notional_to_equity=None, peak_gross_notional_to_equity=None,
                signal_market_return_mean=ratio(sum(Decimal(s['market_return']) for s in signals if s.get('market_return') is not None),
                                              sum(s.get('market_return') is not None for s in signals)),
                signal_directional_return_mean=ratio(sum(Decimal(s['directional_return']) for s in signals if s.get('directional_return') is not None),
                                                   sum(s.get('directional_return') is not None for s in signals)))


def portfolio_metrics(equity, cutoff):
    eligible = [s for s in equity if int(s['captured_at_ns']) <= cutoff]
    rows = sorted([s for s in eligible if s.get('quality') == 'CURRENT' and s.get('equity_minor') is not None],
                  key=lambda s:(s['captured_at_ns'],s.get('snapshot_id',0)))
    peak = worst = None
    drawdown = None
    for row in rows:
        if peak is None:
            peak = row
            continue
        value, high = row['equity_minor'], peak['equity_minor']
        if value >= high:
            if drawdown and drawdown['recovered_at'] is None and peak['captured_at_ns'] == drawdown['_peak_ns']:
                drawdown['recovered_at'] = iso_ns(row['captured_at_ns'])
                drawdown['duration_seconds'] = ratio(row['captured_at_ns']-drawdown['_peak_ns'],1_000_000_000)
            peak = row
        else:
            amount = high-value
            if worst is None or amount > worst:
                worst = amount
                drawdown = dict(amount_minor=amount, fraction=ratio(amount,high), start=iso_ns(peak['captured_at_ns']),
                                trough=iso_ns(row['captured_at_ns']), recovered_at=None, _peak_ns=peak['captured_at_ns'],
                                duration_seconds=ratio(rows[-1]['captured_at_ns']-peak['captured_at_ns'],1_000_000_000))
    if drawdown:
        drawdown['duration_censored'] = drawdown['recovered_at'] is None
        drawdown['last_observed_at'] = iso_ns(rows[-1]['captured_at_ns'])
        drawdown.pop('_peak_ns')
    elif len(rows) >= 2:
        drawdown = dict(amount_minor=0,fraction='0',start=None,trough=None,recovered_at=None,duration_seconds='0')
    initial, final = (rows[0]['equity_minor'], rows[-1]['equity_minor']) if rows else (None,None)
    return dict(snapshot_count=len(rows), excluded_snapshots=len(eligible)-len(rows),
                resolution='OBSERVED_CANONICAL_SNAPSHOTS_NO_INTERPOLATION', drawdown=drawdown,
                starting_equity_minor=initial, ending_equity_minor=final,
                observed_equity_return=ratio(final-initial,initial) if len(rows)>=2 else None,
                reference_equity_minor=initial, scope='WHOLE_SELECTED_PAPER_ACCOUNT_NOT_AI_CAUSAL_ATTRIBUTION')


def build_run(*, records, equity, policy, cutoff, git_sha, evidence_class, source_refs):
    if policy != POLICY:
        raise ValueError('UNKNOWN_OR_MUTATED_EVALUATION_POLICY')
    cutoff_ns = ns_of(cutoff)
    if cutoff_ns is None or evidence_class not in CLASSES or len(git_sha)!=40:
        raise ValueError('INVALID_EVALUATION_CONFIG')
    if len(records)>10000 or len(equity)>10000:
        raise ValueError('EVALUATION_BOUND_EXCEEDED')
    records = sorted(copy.deepcopy(records),key=lambda r:r['evaluation_id'])
    if len({r['evaluation_id'] for r in records}) != len(records):
        raise ValueError('DUPLICATE_EVALUATION_ID')
    equity=sorted(copy.deepcopy(equity),key=lambda s:(s['captured_at_ns'],s.get('snapshot_id',0)))
    admitted, excluded, episodes = [], [], set()
    for row in records:
        reason = exclusion(row,evidence_class,cutoff_ns,episodes)
        if reason:
            excluded.append(dict(evaluation_id=row['evaluation_id'],reason=reason,evidence_class=row.get('evidence_class'),
                                 origin=row.get('origin'),action_state=row.get('action_state')))
        else:
            admitted.append(row)
            if row.get('execution_outcome'):
                episodes.add(row['trade_episode_id'])
    metrics = aggregate(admitted,cutoff_ns)
    portfolio = portfolio_metrics(equity,cutoff_ns)
    # Snapshots are account-level; do not distribute account equity among model/setup segments.
    metrics['turnover'] = ratio(metrics['executed_notional_minor'],portfolio['reference_equity_minor'])
    metrics['turnover_reference_equity_minor'] = portfolio['reference_equity_minor']
    groups = {}
    for dimension in policy['segment_dimensions']:
        index = {}
        for row in admitted:
            label = row.get('segments',{}).get(dimension) or 'UNAVAILABLE'
            index.setdefault(label,[]).append(row)
        groups[dimension] = [dict(label=label,metrics=aggregate(index[label],cutoff_ns)) for label in sorted(index)]
    weeks = sorted({week(r['execution_outcome']['exit_time']) for r in admitted if (r.get('execution_outcome') or {}).get('state')=='CLOSED'})
    weekly = []
    for label in weeks:
        rows=[r for r in admitted if (r.get('execution_outcome') or {}).get('state')=='CLOSED' and week(r['execution_outcome']['exit_time'])==label]
        m=aggregate(rows,cutoff_ns)
        points=[s for s in equity if int(s['captured_at_ns'])<=cutoff_ns and week(iso_ns(s['captured_at_ns']))==label]
        p=portfolio_metrics(points,cutoff_ns)
        weekly.append(dict(week=label,metrics=m,observed_start_equity_minor=p['starting_equity_minor'],
                           observed_end_equity_minor=p['ending_equity_minor'],return_fraction=p['observed_equity_return'],
                           drawdown=p['drawdown'],coverage='SPARSE_OBSERVED_ENDPOINTS_NOT_FULL_WEEK_RETURN'))
    conclusions='INSUFFICIENT_EVIDENCE'
    review=['Insufficient sample for strong performance conclusions.',
            'Model comparisons are descriptive; no causal superiority or profitability claim.',
            'A human-reviewed methodology change requires a new version and future prospective epoch.']
    if metrics['completed_trades']:
        review.append(f"Observed completed Paper result: {metrics['net_pnl_minor']} USD minor units over {metrics['completed_trades']} trades.")
    if metrics['gross_pnl_minor'] and metrics['gross_pnl_minor']>0:
        review.append('Explicit cost / gross observed profit: '+str(ratio(metrics['costs_minor'],metrics['gross_pnl_minor'])))
    for dimension in ('setup','model','regime'):
        for g in groups[dimension]:
            gm=g['metrics']
            if gm['completed_trades'] and Decimal(gm['expectancy_minor'])<0:
                review.append(f"{dimension} {g['label']}: negative observed expectancy; N={gm['completed_trades']}. Review only.")
    inputs=dict(records=records,equity=equity,policy=copy.deepcopy(policy),cutoff=cutoff,git_sha=git_sha,
                evidence_class=evidence_class,source_refs=sorted(copy.deepcopy(source_refs),key=encode))
    digest=fingerprint(inputs)
    return dict(schema_version=SCHEMA,run_id='PE-'+digest[:32],created_at=cutoff,cutoff=cutoff,git_sha=git_sha,
                metric_definition_version=METRICS,evaluation_policy_id=policy['policy_id'],input_fingerprint=digest,
                evidence_class=evidence_class,currency='USD',inputs=inputs,metrics=metrics,portfolio_metrics=portfolio,
                admission=dict(total_considered=len(records),admitted=len(admitted),excluded=len(excluded),
                               reasons=dict(sorted(Counter(e['reason'] for e in excluded).items()))),
                included_record_ids=[r['evaluation_id'] for r in admitted],excluded_records=excluded,
                segments=groups,weekly=weekly,
                week_characteristics=dict(positive=sum(w['metrics']['net_pnl_minor']>0 for w in weekly),
                                          negative=sum(w['metrics']['net_pnl_minor']<0 for w in weekly),
                                          percentage_positive=ratio(sum(w['metrics']['net_pnl_minor']>0 for w in weekly),len(weekly))),
                conclusion=conclusions,review=review,
                authority=dict(live_capital=False,trading_mutation=False,model_promotion=False,ftep_activation=False),
                limitations=['Paper uses simulated fills. Metrics grant no trading authority.',
                             'Exposure uses elapsed wall time including session gaps; not RTH occupancy.',
                             'Gross-notional/equity exposure unavailable without synchronized per-position mark history.',
                             'Drawdown is limited to stored current equity snapshots; missing periods are not interpolated.',
                             'AI attribution preserves stored proposals; stochastic generation is not reproduced.'])


def rerun(run):
    try:
        reproduced=build_run(**run['inputs'])
    except (ValueError,KeyError,TypeError) as exc:
        return dict(status='NOT_REPRODUCIBLE',reason=str(exc))
    return dict(status='MATCH' if encode(reproduced)==encode(run) else 'DIFFERENT',
                input_fingerprint=reproduced['input_fingerprint'],run_id=reproduced['run_id'])

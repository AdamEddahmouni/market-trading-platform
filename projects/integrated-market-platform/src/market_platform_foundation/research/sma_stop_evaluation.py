"""OCT1-08 point-in-time replay comparison of stop methods on an admitted bar corpus.

The definition below is frozen and committed before any comparative result is
read. It evaluates one reference configuration against matched alternatives;
it does not search parameters and has no vocabulary for a superiority claim.
Replay of a historical-development corpus is neither prospective nor Paper
evidence, and nothing here is a calibration.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..intelligence.inference.hashing import input_hash_from_dict
from ..risk.sma_trailing_stop import (
    EVALUATION_FILL_MODEL, REFERENCE_TEST_CONFIG, advance, build_policy, check_bar_trigger, initial_state, normalize_bars,
    price_to_minor, trail,
)

DEFINITION_SCHEMA = 'sma-stop-evaluation-definition/1.0.0'
RECEIPT_SCHEMA = 'sma-stop-evaluation/1.0.0'
EXPERIMENT_ID = 'oct1-08-sma-trailing-stop-replay-v1'
EVIDENCE_REL = Path('evidence/historical-research') / EXPERIMENT_ID
DEFINITION_REL = EVIDENCE_REL / 'pre_execution_frozen_experiment_definition.json'
RECEIPT_REL = Path('artifacts/oct1-08-evaluation.json')
CORPUS_REL = Path('evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3/corpus_pin')
METHODS = ('SMA_TRAIL', 'RAW_PRICE_TRAIL', 'FIXED_INITIAL_STOP', 'NO_TRAIL')
CONCLUSIONS = ('INSUFFICIENT_EVIDENCE', 'NO_CLEAR_DIFFERENCE', 'SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF', 'SMA_UNDERPERFORMED_REFERENCE')
ET = ZoneInfo('America/New_York')
SCALE = 100


def frozen_definition():
    """Every choice that could move the comparison, fixed before outcomes exist."""
    policy = build_policy(**REFERENCE_TEST_CONFIG)
    return dict(
        schema_version=DEFINITION_SCHEMA, experiment_id=EXPERIMENT_ID, status='FROZEN_BEFORE_RESULTS',
        purpose='Implement and evaluate the proposed SMA trailing stop as downside control. Not a search for a best parameter.',
        evidence_class='HISTORICAL_REPLAY', result_status_if_run='REPLAY_EVALUATED', calibration_status='NOT_CALIBRATED',
        corpus=dict(path=CORPUS_REL.as_posix(), corpus_evidence_authority='HISTORICAL_DEVELOPMENT', bar_capability='BAR_OHLCV_1M',
                    instrument_id='canonical:EQUITY:XNAS:AAPL', provider_id='moomoo.opend', session_policy='US_EQUITY_RTH',
                    dataset_fingerprint='B655E90C3BC4789F8A437DB08CA9CD4F3E12417E88879AE4A9BDFF19BE067D46',
                    known_limitations=['ONE_INSTRUMENT', 'FIVE_SESSIONS', 'PROVIDER_QFQ_NOT_RECONCILED']),
        policy=dict(policy_id=policy['policy_id'], sma_window_bars=policy['sma_window_bars'], bar_interval=policy['bar_interval'],
                    config_label=policy['config_label'], tick_rounding_policy=policy['tick_rounding_policy'],
                    status='REFERENCE_TEST_CONFIG: not optimized, calibrated, recommended or claimed superior'),
        entry_rule=dict(basis='FIXED_SCHEDULE_OUTCOME_BLIND', warmup='FULL_SMA_WINDOW_WITHIN_THE_SESSION',
                        first_signal_bar_index=policy['sma_window_bars'] - 1, signal_spacing_bars=30,
                        entry_reference='OPEN_OF_THE_BAR_AFTER_THE_SIGNAL_BAR', minimum_bars_after_entry=30,
                        sides=['LONG', 'SHORT'], primary_side='LONG',
                        short_note='Short episodes test the policy math only; Paper short authority is unchanged.'),
        matched_initial_risk='D = abs(entry_reference - initial SMA stop); the fixed stop and the raw-price trail start at the same D',
        methods=dict(
            SMA_TRAIL='Policy under test: stop = side-rounded SMA of completed closes, ratcheted, effective for later bars only',
            RAW_PRICE_TRAIL='high-water (low-water for short) of completed bar closes since entry, offset by D, ratcheted, effective for later bars only',
            FIXED_INITIAL_STOP='entry_reference offset by D; never moves',
            NO_TRAIL='no stop; exit at the horizon'),
        horizon='CLOSE_OF_THE_LAST_BAR_OF_THE_ENTRY_SESSION',
        trigger='LONG: bar.low <= stop; SHORT: bar.high >= stop; only a stop effective at the bar start is eligible',
        fill_model=dict(id=EVALUATION_FILL_MODEL, primary='STOP_EXIT_AT_TRIGGER_BAR_WORST_PRICE (bar low for a long exit, bar high for a short exit)',
                        horizon_exit='LAST_BAR_CLOSE', never='FILL_AT_STOP_LEVEL_ASSUMED',
                        sensitivity='ALTERNATE_FILL: worse of stop level and trigger-bar open; reported beside the primary, never replacing it',
                        cost_bps_per_side=5.0, cost_basis='existing historical-research cost_slippage_bps default; gross and net reported separately'),
        exclusion_rules=['INITIAL_STOP_NOT_PROTECTIVE: D <= 0 at entry', 'BAR_GAP_IN_WINDOW at the signal bar', 'SESSION_TOO_SHORT_FOR_ENTRY'],
        metrics=['triggered', 'exit_time', 'exit_price', 'holding_bars', 'gross_return_bps', 'net_return_bps', 'mfe_bps', 'mae_bps',
                 'max_drawdown_bps', 'initial_risk_bps', 'stop_moves', 'gap_through_stop', 'bars_after_invalidation', 'vs_no_trail_bps'],
        definitions=dict(
            invalidation='first held bar whose close is beyond the initial stop level',
            premature_exit='a stop exit whose gross return is below the NO_TRAIL return of the same episode',
            loss_severity='mean gross return of episodes that lost money',
            downside_metrics=['mae_bps', 'max_drawdown_bps', 'loss_severity_bps', 'bars_after_invalidation']),
        independence='Episodes inside one session overlap and are not independent; comparisons are aggregated per session first.',
        conclusion_rule=dict(
            vocabulary=list(CONCLUSIONS), minimum_sessions_for_a_directional_conclusion=20, minimum_instruments_for_a_directional_conclusion=3,
            below_minimum='INSUFFICIENT_EVIDENCE, with the in-sample pattern reported separately as description only',
            pattern='Per alternative on the primary side: SMA downside is BETTER/WORSE when its session-mean MAE is lower/higher in at least 80% of sessions; '
                    'return likewise on session-mean gross return. BETTER downside with WORSE return -> SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF; '
                    'WORSE downside and not BETTER return -> SMA_UNDERPERFORMED_REFERENCE; otherwise NO_CLEAR_DIFFERENCE.',
            superiority='No token asserts superiority. A directional conclusion needs the minimums above and a new frozen definition.'),
        no_parameter_search=True)


def definition_hash(definition=None):
    return input_hash_from_dict(definition or frozen_definition())


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_corpus(repository_root):
    """The pinned admitted corpus, verified against its recorded fingerprint. Read-only."""
    from ..intelligence.historical_research_harness.baseline_pack_v2 import verify_pinned_opend_corpus_fingerprint
    corpus_dir = Path(repository_root) / CORPUS_REL
    verification = verify_pinned_opend_corpus_fingerprint(repository_root=Path(repository_root), corpus_dir=corpus_dir)
    if not verification.get('ok'):
        raise ValueError(str(verification.get('reason_code') or 'DATASET_REPRODUCIBILITY_FAILURE'))
    path = sorted((corpus_dir / 'normalized').glob('*_normalized.json'))[0]
    manifest = json.loads((corpus_dir / 'dataset_manifest.json').read_text(encoding='utf-8'))
    rows = json.loads(path.read_text(encoding='utf-8'))
    return dict(rows=rows, provenance=dict(
        corpus_path=CORPUS_REL.as_posix(), normalized_file=path.name, normalized_sha256=_sha256(path),
        manifest_sha256=_sha256(corpus_dir / 'dataset_manifest.json'), dataset_fingerprint=manifest['dataset_fingerprint'],
        normalized_fingerprint=verification.get('computed_normalized_fingerprint'),
        corpus_evidence_authority=manifest['corpus_evidence_authority'], dataset_id=manifest['dataset_id'],
        session_dates=manifest['interval']['session_dates'], row_count=len(rows),
        corporate_action_status=manifest.get('corporate_action_status'), provider_id=rows[0]['publisher_id'] if rows else None))


def corpus_bars(rows):
    """Canonical BAR_OHLCV_1M events -> policy bars. event_time is bar start, available_time bar end."""
    return [dict(bar_id=str(r['normalized_event_id']), event_time=int(r['event_time']), available_time=int(r['available_time']),
                 **{k: price_to_minor(r['bar_payload'][k], SCALE) for k in ('open', 'high', 'low', 'close')}) for r in rows]


def sessions_of(bars):
    """Bars grouped by ET session date, each ordered and deduplicated by the policy's own normalizer."""
    grouped = {}
    for bar in bars:
        grouped.setdefault(datetime.fromtimestamp(bar['event_time'] / 1e9, UTC).astimezone(ET).date().isoformat(), []).append(bar)
    return {day: normalize_bars(rows, cutoff_ns=max(b['available_time'] for b in rows), interval='1m')['bars'] for day, rows in sorted(grouped.items())}


def _bps(amount, entry):
    return round(amount * 10000 / entry, 2)


def _signed(side, amount):
    return amount if side == 'LONG' else -amount


def _hit(side, bar, stop):
    return bar['low'] <= stop if side == 'LONG' else bar['high'] >= stop


def _worst(side, bar):
    return bar['low'] if side == 'LONG' else bar['high']


def _alternate(side, bar, stop):
    return min(stop, bar['open']) if side == 'LONG' else max(stop, bar['open'])


def simulate_episode(bars, signal_index, side, policy, *, day, cost_bps):
    """One entry, four exits. Only bars already complete are ever read for a stop."""
    entry_bar = bars[signal_index + 1]
    entry = entry_bar['open']
    state = initial_state(account_id='REPLAY', session_id=day, instrument_id='REPLAY', position_epoch_id=f'{day}:{signal_index}:{side}',
                          epoch_basis='REPLAY_EPISODE', side=side, quantity=1, policy=policy, activated_at=bars[signal_index]['available_time'],
                          activation_reason='POSITION_OPENED', price_scale=SCALE)
    state, _ = advance(state, bars[:signal_index + 1], policy)
    episode = dict(episode_id='EP-' + input_hash_from_dict(dict(day=day, signal=bars[signal_index]['bar_id'], side=side, policy=policy['policy_id']))[:24],
                   session_date=day, side=side, signal_bar_id=bars[signal_index]['bar_id'], entry_bar_id=entry_bar['bar_id'],
                   entry_time_ns=entry_bar['event_time'], entry_reference_price=entry, policy_id=policy['policy_id'], bar_interval=policy['bar_interval'])
    if state['active_stop'] is None:
        return dict(episode, evaluable=False, exclusion=state['reason_codes'][0])
    initial = state['active_stop']
    distance = _signed(side, entry - initial)
    if distance <= 0:
        return dict(episode, evaluable=False, exclusion='INITIAL_STOP_NOT_PROTECTIVE', initial_stop=initial)
    fixed = initial
    raw = dict(stop=initial, water=entry, moves=0)
    open_, exits, updates = {'SMA_TRAIL', 'RAW_PRICE_TRAIL', 'FIXED_INITIAL_STOP'}, {}, []
    held = bars[signal_index + 1:]
    invalidated_at = None
    for offset, bar in enumerate(held):
        # 1. Triggers: every stop tested here was fixed before this bar began.
        if 'SMA_TRAIL' in open_:
            hit = check_bar_trigger(state, bar)
            if hit:
                exits['SMA_TRAIL'] = (offset, hit['stop'], hit['gap_through_stop'])
        if 'RAW_PRICE_TRAIL' in open_ and _hit(side, bar, raw['stop']):
            exits['RAW_PRICE_TRAIL'] = (offset, raw['stop'], _hit(side, dict(low=bar['open'], high=bar['open']), raw['stop']))
        if 'FIXED_INITIAL_STOP' in open_ and _hit(side, bar, fixed):
            exits['FIXED_INITIAL_STOP'] = (offset, fixed, _hit(side, dict(low=bar['open'], high=bar['open']), fixed))
        open_ -= set(exits)
        if invalidated_at is None and _signed(side, bar['close'] - initial) < 0:
            invalidated_at = offset
        # 2. Updates from this now-completed bar: in force from the next bar on.
        if 'SMA_TRAIL' in open_:
            before = state['active_stop']
            state, _ = advance(state, bars[:signal_index + 2 + offset], policy)
            if state['active_stop'] != before:
                updates.append(dict(bar_id=bar['bar_id'], stop=state['active_stop'], sma=state['sma_value']))
        if 'RAW_PRICE_TRAIL' in open_:
            raw['water'] = max(raw['water'], bar['close']) if side == 'LONG' else min(raw['water'], bar['close'])
            stop, _ = trail(side, raw['stop'], raw['water'] - _signed(side, distance))
            raw['moves'] += stop != raw['stop']
            raw['stop'] = stop
    last = len(held) - 1
    no_trail = _signed(side, held[last]['close'] - entry)
    results = {}
    for method in METHODS:
        triggered = method in exits
        index, stop, gap = exits.get(method, (last, None, False))
        exit_bar = held[index]
        price = _worst(side, exit_bar) if triggered else exit_bar['close']
        window = held[:index + 1]
        favorable = max(_signed(side, (b['high'] if side == 'LONG' else b['low']) - entry) for b in window)
        adverse = max(_signed(side, entry - (b['low'] if side == 'LONG' else b['high'])) for b in window)
        marks = [entry, *[b['close'] for b in window[:-1]], price]
        peak, drawdown = marks[0], 0
        for mark in marks:
            peak = max(peak, mark) if side == 'LONG' else min(peak, mark)
            drawdown = max(drawdown, _signed(side, peak - mark))
        gross = _signed(side, price - entry)
        results[method] = dict(
            triggered=triggered, exit_bar_id=exit_bar['bar_id'], exit_time_ns=exit_bar['available_time'], exit_price=price,
            stop_at_trigger=stop, gap_through_stop=bool(gap), holding_bars=index + 1, gross_return_bps=_bps(gross, entry),
            net_return_bps=round(_bps(gross, entry) - 2 * cost_bps, 2), mfe_bps=_bps(max(favorable, 0), entry), mae_bps=_bps(max(adverse, 0), entry),
            max_drawdown_bps=_bps(drawdown, entry), bars_after_invalidation=max(0, index - invalidated_at) if invalidated_at is not None and invalidated_at <= index else 0,
            vs_no_trail_bps=round(_bps(gross, entry) - _bps(no_trail, entry), 2), premature_exit=bool(triggered and gross < no_trail),
            alternate_fill_gross_return_bps=_bps(_signed(side, _alternate(side, exit_bar, stop) - entry), entry) if triggered else _bps(gross, entry),
            exit_bar_range_order='UNKNOWN' if triggered else 'NOT_APPLICABLE',
            stop_moves=len(updates) if method == 'SMA_TRAIL' else raw['moves'] if method == 'RAW_PRICE_TRAIL' else 0)
    return dict(episode, evaluable=True, exclusion=None, initial_stop=initial, initial_risk_distance=distance, initial_risk_bps=_bps(distance, entry),
                bars_admitted=len(held), stop_updates=updates[:60], stop_updates_truncated=len(updates) > 60, methods=results)


def _aggregate(rows, method):
    values = [r['methods'][method] for r in rows]
    if not values:
        return dict(episodes=0)
    column = lambda key: [v[key] for v in values]
    losses = [v['gross_return_bps'] for v in values if v['gross_return_bps'] < 0]
    mean = lambda items: round(statistics.fmean(items), 2) if items else None
    return dict(
        episodes=len(values), stop_frequency=round(sum(v['triggered'] for v in values) / len(values), 4),
        mean_gross_return_bps=mean(column('gross_return_bps')), median_gross_return_bps=round(statistics.median(column('gross_return_bps')), 2),
        mean_net_return_bps=mean(column('net_return_bps')), median_net_return_bps=round(statistics.median(column('net_return_bps')), 2),
        mean_alternate_fill_gross_return_bps=mean(column('alternate_fill_gross_return_bps')),
        mean_mae_bps=mean(column('mae_bps')), median_mae_bps=round(statistics.median(column('mae_bps')), 2),
        mean_max_drawdown_bps=mean(column('max_drawdown_bps')), worst_drawdown_bps=max(column('max_drawdown_bps')),
        losing_episodes=len(losses), loss_severity_bps=mean(losses), worst_loss_bps=min(losses) if losses else None,
        mean_mfe_bps=mean(column('mfe_bps')), premature_exit_frequency=round(sum(v['premature_exit'] for v in values) / len(values), 4),
        mean_holding_bars=mean(column('holding_bars')), mean_bars_after_invalidation=mean(column('bars_after_invalidation')),
        gap_through_stop_events=sum(v['gap_through_stop'] for v in values), mean_stop_moves=mean(column('stop_moves')))


def _pattern(rows, alternative, sessions):
    """Session-level sign agreement; overlapping episodes are averaged within a session first."""
    lower_mae = higher_mae = higher_return = lower_return = 0
    per_session = []
    for day in sessions:
        chosen = [r for r in rows if r['session_date'] == day]
        if not chosen:
            continue
        gap = lambda key: statistics.fmean(r['methods']['SMA_TRAIL'][key] for r in chosen) - statistics.fmean(r['methods'][alternative][key] for r in chosen)
        mae, gross = round(gap('mae_bps'), 2), round(gap('gross_return_bps'), 2)
        per_session.append(dict(session_date=day, episodes=len(chosen), mae_bps_difference=mae, gross_return_bps_difference=gross))
        lower_mae += mae < 0; higher_mae += mae > 0; higher_return += gross > 0; lower_return += gross < 0
    count = len(per_session)
    need = 0.8 * count
    downside = 'BETTER' if count and lower_mae >= need else 'WORSE' if count and higher_mae >= need else 'UNCLEAR'
    returns = 'BETTER' if count and higher_return >= need else 'WORSE' if count and lower_return >= need else 'UNCLEAR'
    pattern = 'SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF' if downside == 'BETTER' and returns == 'WORSE' else \
        'SMA_UNDERPERFORMED_REFERENCE' if downside == 'WORSE' and returns != 'BETTER' else 'NO_CLEAR_DIFFERENCE'
    return dict(alternative=alternative, sessions=count, downside=downside, returns=returns, pattern=pattern, per_session=per_session)


def conclude(patterns, *, sessions, instruments, rule):
    """The frozen rule. There is no branch that returns a superiority claim."""
    enough = sessions >= rule['minimum_sessions_for_a_directional_conclusion'] and instruments >= rule['minimum_instruments_for_a_directional_conclusion']
    seen = {p['pattern'] for p in patterns}
    described = seen.pop() if len(seen) == 1 else 'NO_CLEAR_DIFFERENCE'
    token = described if enough else 'INSUFFICIENT_EVIDENCE'
    assert token in CONCLUSIONS
    return dict(conclusion=token, in_sample_pattern=described, in_sample_pattern_status='DESCRIPTION_ONLY_NOT_A_CLAIM',
                sessions=sessions, instruments=instruments, superiority_claim='NONE',
                statement='Evidence is insufficient for a directional or superiority claim.' if not enough else
                'Directional pattern under the frozen rule; not a superiority or profitability claim.')


def evaluate(sessions, definition, *, provenance=None, instruments=1):
    """Pure and deterministic: the same bars and definition give the same result hash."""
    reference = build_policy(sma_window_bars=definition['policy']['sma_window_bars'], bar_interval=definition['policy']['bar_interval'])
    if reference['policy_id'] != definition['policy']['policy_id']:
        raise ValueError('POLICY_IDENTITY_MISMATCH')
    rule, episodes = definition['entry_rule'], []
    for day, bars in sessions.items():
        signal = rule['first_signal_bar_index']
        while signal + 1 + rule['minimum_bars_after_entry'] <= len(bars) - 1:
            for side in rule['sides']:
                episodes.append(simulate_episode(bars, signal, side, reference, day=day, cost_bps=definition['fill_model']['cost_bps_per_side']))
            signal += rule['signal_spacing_bars']
    evaluable = [e for e in episodes if e['evaluable']]
    exclusions = {}
    for e in episodes:
        if not e['evaluable']:
            exclusions[e['exclusion']] = exclusions.get(e['exclusion'], 0) + 1
    by_side = {side: {method: _aggregate([e for e in evaluable if e['side'] == side], method) for method in METHODS} for side in rule['sides']}
    primary = [e for e in evaluable if e['side'] == rule['primary_side']]
    patterns = [_pattern(primary, alternative, list(sessions)) for alternative in METHODS[1:]]
    body = dict(
        schema_version=RECEIPT_SCHEMA, experiment_id=definition['experiment_id'], definition_hash=definition_hash(definition),
        evidence_class=definition['evidence_class'], result_status='REPLAY_EVALUATED', calibration_status='NOT_CALIBRATED',
        policy=definition['policy'], fill_model=definition['fill_model'], provenance=provenance,
        input_hash=input_hash_from_dict(dict(bars=[[b['bar_id'], b['open'], b['high'], b['low'], b['close']] for bars in sessions.values() for b in bars])),
        corpus=dict(sessions=list(sessions), bars=sum(len(b) for b in sessions.values()), instruments=instruments,
                    session_bar_counts={day: len(bars) for day, bars in sessions.items()},
                    missing_intervals={day: sum(1 for a, b in zip(bars, bars[1:]) if b['event_time'] - a['event_time'] != 60_000_000_000) for day, bars in sessions.items()}),
        counts=dict(episodes=len(episodes), evaluable=len(evaluable), excluded=len(episodes) - len(evaluable), exclusions=exclusions,
                    evaluable_by_side={side: sum(1 for e in evaluable if e['side'] == side) for side in rule['sides']}),
        primary_side=rule['primary_side'], aggregates=by_side, comparisons=patterns,
        conclusion=conclude(patterns, sessions=len(sessions), instruments=instruments, rule=definition['conclusion_rule']),
        sample_size_note='Small sample: overlapping episodes from few sessions of one instrument. Descriptive only.',
        episodes=episodes)
    body['result_hash'] = input_hash_from_dict(body)
    return body


def run_frozen_evaluation(repository_root):
    """Reads the committed definition and the pinned corpus; neither is ever written."""
    root = Path(repository_root)
    committed = json.loads((root / DEFINITION_REL).read_text(encoding='utf-8'))
    if committed != json.loads(json.dumps(frozen_definition())):
        raise ValueError('FROZEN_DEFINITION_MISMATCH')
    corpus = load_corpus(root)
    if corpus['provenance']['dataset_fingerprint'] != committed['corpus']['dataset_fingerprint']:
        raise ValueError('DATASET_FINGERPRINT_MISMATCH')
    before = (corpus['provenance']['normalized_sha256'], corpus['provenance']['manifest_sha256'])
    result = evaluate(sessions_of(corpus_bars(corpus['rows'])), committed, provenance=corpus['provenance'])
    after = load_corpus(root)['provenance']
    result['corpus_unchanged'] = before == (after['normalized_sha256'], after['manifest_sha256'])
    return result


def read_receipt(repository_root=None, *, episode_limit=0):
    """Bounded projection for the UI: aggregates and conclusion, never the whole episode list."""
    root = Path(repository_root) if repository_root else Path(__file__).resolve().parents[3]
    path = root / RECEIPT_REL
    if not path.is_file():
        return dict(schema_version=RECEIPT_SCHEMA, result_status='NOT_EXECUTED', reason_codes=['EVALUATION_RECEIPT_NOT_FOUND'])
    receipt = json.loads(path.read_text(encoding='utf-8'))
    episodes = receipt.pop('episodes', [])
    # The response guard treats any key containing "auth" as secret-shaped; the label is the same recorded fact.
    provenance = receipt.get('provenance') or {}
    if 'corpus_evidence_authority' in provenance:
        provenance['corpus_evidence_label'] = provenance.pop('corpus_evidence_authority')
    for comparison in receipt.get('comparisons', []):
        comparison['per_session'] = comparison['per_session'][:20]
    return dict(receipt, episode_count=len(episodes), episodes=episodes[:max(0, min(int(episode_limit), 20))])

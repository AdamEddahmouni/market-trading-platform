"""Canonical source adapters. No model, quote refresh, or trading calls."""
from decimal import Decimal

from ..intelligence.inference.trade_lifecycle import authority_of, episodes_from_trades, iso_ns
from .prospective import fingerprint, ratio, ns_of
from ..intelligence.inference.hashing import input_hash_from_dict
from ..local_state.reevaluation import NEXT_SESSION_MUTABLE


def classification(decision, candidate, experiment):
    packet=(decision.get('evidence_snapshot') or {}).get('evidence') or {}
    inputs=[*packet.get('current_market_evidence',[]),*packet.get('reference_evidence',[])]
    if any(str(e.get('delivery_mode','')).upper() in ('FIXTURE','FIXTURE_REPLAY','SYNTHETIC') for e in inputs):
        return 'SOFTWARE_CONTROLLED'
    if (decision.get('model') or {}).get('simulated') or (candidate or {}).get('simulated'):
        return 'SOFTWARE_CONTROLLED'
    if any(str(e.get('delivery_mode','')).upper() in ('REPLAY','HISTORICAL','HISTORICAL_CAPTURE') for e in inputs):
        return 'HISTORICAL_REPLAY'
    if experiment and experiment.get('data_mode')=='LIVE_OBSERVATIONAL' and inputs and all(e.get('source') and e.get('as_of') and str(e.get('delivery_mode','')).upper() in ('LIVE_OBSERVATIONAL','LIVE','STREAMING','POLLING','REALTIME','PUBLICATION_BASED') for e in inputs):
        return experiment['evidence_class']
    return 'UNTRUSTED'


def signal_outcomes(decision, snapshots, observations, cutoff):
    results=[]
    for snapshot in snapshots:
        policy=snapshot['evaluation_policy']
        end=ns_of(policy['observation_end'])
        locked=ns_of(snapshot.get('locked_at'))
        start=ns_of(policy['observation_start'])
        if snapshot.get('lock_state')!='LOCKED' or locked is None or start is None or locked>=start or end is None or end>cutoff:
            continue
        rows=[o for o in observations(snapshot['snapshot_id']) if ns_of(o.get('observed_at')) is not None and ns_of(o['observed_at'])<=cutoff
              and ns_of(o.get('source_time')) is not None and start<=ns_of(o['source_time'])<=end]
        if not rows:
            continue
        last=max(rows,key=lambda o:(ns_of(o['source_time']),ns_of(o['observed_at']),o['observation_id']))
        reference=snapshot.get('reference_price')
        value=Decimal(str(last['price']))
        base=Decimal(str(reference)) if reference is not None else None
        move=ratio(value-base,base) if base and base>0 else None
        direction=decision.get('direction')
        delivered=str(last.get('delivery_mode') or '').upper()
        invalid=(snapshot.get('content_hash') != input_hash_from_dict({k:v for k,v in snapshot.items() if k not in NEXT_SESSION_MUTABLE and k != 'content_hash'}) or
                 snapshot.get('action_decision_id')!=decision['decision_id'] or
                 snapshot.get('evidence_snapshot_ref')!=decision.get('evidence_snapshot_id') or
                 ns_of(last['source_time'])<=ns_of(decision['decision_time']))
        if delivered in ('FIXTURE','FIXTURE_REPLAY','REPLAY','HISTORICAL') and not (decision.get('model') or {}).get('simulated'):
            invalid=True
        results.append(dict(state='INVALID' if invalid else 'COMPLETE' if move is not None else 'MISSING',
                            horizon=policy['policy_id'],horizon_end=policy['observation_end'],snapshot_id=snapshot['snapshot_id'],
                            observation_id=last['observation_id'],source_time=last['source_time'],observed_at=last['observed_at'],
                            source=last.get('source'),market_return=move,
                            directional_return=ratio(Decimal(move)*(1 if direction=='LONG' else -1),1) if move is not None and direction in ('LONG','SHORT') else None,
                            directional_correct=(Decimal(move)>0 if direction=='LONG' else Decimal(move)<0) if move and direction in ('LONG','SHORT') else None,
                            basis='MARKET_MOVE_NOT_PNL',source_fingerprint=fingerprint(dict(snapshot=snapshot,observation=last))))
    return results


def execution(episode, decisions):
    fills=episode['fills']
    opening=decisions.get(episode['opening_decision_id'])
    valid=episode['opening_basis']=='LEDGER_OPEN_FILL' and opening is not None and bool(opening.get('model_proposal'))
    for fill in fills:
        if fill.get('position_effect') == 'REVERSE':
            valid=False
        d=decisions.get(fill.get('decision_id'))
        if not d or d['instrument_id']!=episode['instrument_id'] or ns_of(d['decision_time']) is None or int(fill.get('fill_time_ns') or 0)<=ns_of(d['decision_time']):
            valid=False
    costs=episode['costs_minor']
    net=episode['realized_pnl_minor']
    entries,exits=episode['entry_fills'],episode['exit_fills']
    quantity=sum(f['filled_quantity'] for f in entries)
    return dict(state='OPEN' if episode['open'] else 'CLOSED',net_pnl_minor=net,gross_pnl_minor=net+costs,costs_minor=costs,
                commission_minor=sum(f['commission_minor'] for f in fills),fees_minor=sum(f['fees_minor'] for f in fills),
                entry_time=iso_ns(fills[0].get('fill_time_ns')),exit_time=None if episode['open'] else iso_ns(fills[-1].get('fill_time_ns')),
                entry_fill_ids=[f['fill_id'] for f in entries],exit_fill_ids=[f['fill_id'] for f in exits],
                quantity=quantity,average_entry_minor=ratio(sum(f['fill_price_minor']*f['filled_quantity'] for f in entries),quantity),
                executed_notional_minor=sum(abs(f['fill_price_minor']*f['filled_quantity']) for f in fills),
                holding_seconds=ratio(fills[-1]['fill_time_ns']-fills[0]['fill_time_ns'],1_000_000_000) if not episode['open'] else None,
                fill_model_versions=sorted({str(f.get('simulator_version') or 'UNAVAILABLE') for f in fills}),
                lineage_valid=valid,source_fingerprint=fingerprint(fills),realized_includes_costs=True,
                unrealized_pnl_minor=None,mark_quality='UNAVAILABLE_AT_FROZEN_CUTOFF')


def construct_records(*, decisions, candidate_reader, trades, experiment, snapshots, observations, cutoff):
    index={d['decision_id']:d for d in decisions}
    account=experiment['paper_account_id']
    episodes=episodes_from_trades([f for f in trades if f.get('fill_time_ns') is not None and f['fill_time_ns']<=cutoff],
                                  account_id=account,experiment_id=experiment['experiment_id'])
    by_open={e['opening_decision_id']:e for e in episodes if e['opening_decision_id']}
    records=[]
    for d in decisions:
        snapshot=d.get('evidence_snapshot') or {}
        run_id=snapshot.get('candidate_run_id')
        candidate=candidate_reader(run_id) if run_id else None
        packet=snapshot.get('evidence') or {}
        evidence=[*packet.get('current_market_evidence',[]),*packet.get('reference_evidence',[])]
        clocks=[ns_of(e.get('as_of')) for e in evidence]
        available=[ns_of(e.get('received_at') or e.get('available_at') or e.get('as_of')) for e in evidence]
        episode=by_open.get(d['decision_id'])
        model=d.get('model') or {}
        origin=authority_of(d)
        parts=[str(model.get(k) or 'UNAVAILABLE') for k in ('provider_id','model_id','model_version')]
        setup=packet.get('setup') or packet.get('strategy_id')
        records.append(dict(schema_version='decision-outcome/1.0.0',evaluation_id='DE-'+d['decision_id'],
                            account_id=account,experiment_id=experiment['experiment_id'],currency=experiment['currency'],
                            instrument_id=d['instrument_id'],symbol=(d.get('instrument') or {}).get('symbol'),
                            action_decision_id=d['decision_id'],candidate_run_id=run_id,evidence_snapshot_id=d.get('evidence_snapshot_id'),
                            decision_time=d['decision_time'],decision_cutoff=snapshot.get('cutoff'),
                            evidence_max_time=iso_ns(max(clocks)) if clocks and all(c is not None for c in clocks) else None,
                            evidence_available_time=iso_ns(max(available)) if available and all(c is not None for c in available) else None,
                            source_fingerprint=fingerprint(dict(decision=d,candidate=candidate)) if candidate else None,
                            model=model,actual_output_ref=d['decision_id'] if d.get('model_proposal') else None,
                            action_state=d['action_state'],direction=d.get('direction'),origin=origin,
                            trade_episode_id=episode['episode_id'] if episode else None,
                            execution_outcome=execution(episode,index) if episode else None,
                            signal_outcomes=signal_outcomes(d,[s for s in snapshots if s['action_decision_id']==d['decision_id']],observations,cutoff),
                            evidence_class=classification(d,candidate,experiment),quality=('INVALID' if not candidate or snapshot.get('candidate_input_hash')!=candidate.get('input_hash') or
                                     d.get('evidence_snapshot_id')!='AS-'+input_hash_from_dict(snapshot) else 'COMPLETE' if evidence else 'MISSING'),
                            segments=dict(setup=setup or 'UNAVAILABLE',asset=packet.get('instrument',{}).get('asset_class') or 'UNAVAILABLE',
                                          regime=packet.get('regime') or 'UNAVAILABLE',model='DETERMINISTIC_RISK' if origin=='DETERMINISTIC_RISK_CONTROL' else '/'.join(parts),
                                          prompt='/'.join(str(model.get(k) or 'UNAVAILABLE') for k in ('prompt_id','prompt_version','prompt_hash')),
                                          direction=d.get('direction') or 'UNAVAILABLE',instrument=d['instrument_id'],
                                          stop_policy=(d.get('risk_control') or {}).get('policy_id') or 'UNAVAILABLE',policy=d.get('policy_id') or 'UNAVAILABLE'),
                            limitations=['MODEL_VERSION_UNAVAILABLE'] if not model.get('model_version') else []))
    for episode in episodes:
        if episode['opening_decision_id'] in index:
            continue
        records.append(dict(schema_version='decision-outcome/1.0.0',evaluation_id='UNLINKED-'+episode['episode_id'],
                            account_id=account,experiment_id=experiment['experiment_id'],currency=experiment['currency'],
                            instrument_id=episode['instrument_id'],origin='MANUAL_UNLINKED',evidence_class=experiment['evidence_class'],
                            action_state='UNLINKED_PAPER_ACTIVITY',trade_episode_id=episode['episode_id'],
                            execution_outcome=execution(episode,index),quality='PARTIAL',signal_outcomes=[],limitations=['LINEAGE_UNAVAILABLE']))
    return records

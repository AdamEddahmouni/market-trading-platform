"""OCT1-07 pure reevaluation policy: cadence truth, material gate, stability.

No clock, provider, model, ledger or order access. A cadence is a runtime
schedule; it never upgrades the freshness of the evidence it reads.
"""
from __future__ import annotations

from enum import StrEnum

from ...market_data.freshness_contract import timestamp
from .action_decision import STOP_BREACH_CONDITION, build_conditions
from .hashing import input_hash_from_dict

POLICY_ID = 'reevaluation-policy/1.0.0'
CYCLE_SCHEMA = 'reevaluation-cycle/1.0.0'
MAX_TRANSITIONS = 24
MAX_RECEIPT_BYTES = 32000


class ReevaluationTrigger(StrEnum):
    MANUAL = 'MANUAL'
    SCHEDULED_CADENCE = 'SCHEDULED_CADENCE'
    SESSION_START = 'SESSION_START'
    SESSION_END = 'SESSION_END'


class TransitionClass(StrEnum):
    UNCHANGED = 'UNCHANGED'
    MATERIAL_EVIDENCE_CHANGED = 'MATERIAL_EVIDENCE_CHANGED'
    STATE_CHANGED = 'STATE_CHANGED'
    POSITION_CHANGED = 'POSITION_CHANGED'
    CANDIDATE_ADDED = 'CANDIDATE_ADDED'
    CANDIDATE_REMOVED = 'CANDIDATE_REMOVED'
    DUPLICATE_SUPPRESSED = 'DUPLICATE_SUPPRESSED'
    CHURN_SUPPRESSED = 'CHURN_SUPPRESSED'
    REVALIDATION_REQUIRED = 'REVALIDATION_REQUIRED'
    BUDGET_BLOCKED = 'BUDGET_BLOCKED'
    MODEL_UNAVAILABLE = 'MODEL_UNAVAILABLE'
    DEFERRED = 'DEFERRED'


class CycleStatus(StrEnum):
    NO_MATERIAL_CHANGE = 'NO_MATERIAL_CHANGE'
    MATERIAL_CHANGE = 'MATERIAL_CHANGE'
    BUDGET_BLOCKED = 'BUDGET_BLOCKED'
    MODEL_UNAVAILABLE = 'MODEL_UNAVAILABLE'
    REEVALUATION_BLOCKED = 'REEVALUATION_BLOCKED'
    FAILED = 'FAILED'
    NOT_OBSERVED = 'NOT_OBSERVED'


# Operational bounds only: none of these is a trading-performance threshold.
DEFAULT_POLICY = dict(
    policy_id=POLICY_ID,
    runtime_min_cadence_seconds=60,
    model_min_interval_seconds=60,
    price_move_bps=50,
    decision_max_age_seconds=900,
    candidate_refresh_min_seconds=300,
    min_state_dwell_seconds=300,
    max_action_calls_per_cycle=2,
    max_model_calls_per_cycle=3,
    max_model_calls_per_hour=30,
    max_model_calls_per_day=120,
    lease_seconds=180,
)
_BOUNDS = dict(
    model_min_interval_seconds=(1, 3600), price_move_bps=(1, 10000), decision_max_age_seconds=(60, 86400),
    candidate_refresh_min_seconds=(60, 86400), min_state_dwell_seconds=(0, 86400),
    max_action_calls_per_cycle=(0, 5), max_model_calls_per_cycle=(0, 6),
    max_model_calls_per_hour=(0, 360), max_model_calls_per_day=(0, 2000),
)
# Becoming unsafe bypasses the dwell; recovering does not.
# OCT1-08: a breached stop is deterministic downside control; churn suppression can never hold it back.
SAFETY_REASONS = frozenset({'POSITION_CHANGED', 'PENDING_ORDER_APPEARED', 'QUOTE_LOST', 'AUTHORITY_LOST', 'EXIT_CONDITION_MET',
                            STOP_BREACH_CONDITION})
# Deterministic stop bookkeeping: recorded, but never by itself a reason to ask a model.
STOP_BOOKKEEPING_REASONS = frozenset({'STOP_INITIALIZED', 'STOP_TIGHTENED', 'STOP_UPDATE_STALE', 'STOP_UPDATE_RESUMED',
                                      'STOP_EPISODE_CHANGED', 'STOP_STATUS_CHANGED'})


def build_policy(overrides=None):
    """Only allowlisted integer bounds; unknown keys are rejected, not ignored."""
    policy = dict(DEFAULT_POLICY)
    for key, value in (overrides or {}).items():
        if key not in _BOUNDS or type(value) is not int or not _BOUNDS[key][0] <= value <= _BOUNDS[key][1]:
            raise ValueError('INVALID_REEVALUATION_POLICY')
        policy[key] = value
    return policy


def effective_cadence(requested, policy):
    """The slowest binding constraint is the honest cadence."""
    if type(requested) is not int or not 10 <= requested <= 3600:
        raise ValueError('INVALID_REQUESTED_CADENCE')
    constraints = [dict(name='REQUESTED', seconds=requested),
                   dict(name='RUNTIME_MINIMUM', seconds=policy['runtime_min_cadence_seconds']),
                   dict(name='MODEL_MINIMUM_INTERVAL', seconds=policy['model_min_interval_seconds'])]
    binding = max(constraints, key=lambda c: c['seconds'])
    return dict(requested_cadence_seconds=requested, effective_cadence_seconds=binding['seconds'],
                limiting_constraint=binding['name'], constraints=constraints,
                degraded=binding['seconds'] > requested)


def slot_at_or_after(anchor, cadence, moment):
    """First schedule slot >= moment. Slots are anchor + n*cadence, never drifted."""
    if moment <= anchor:
        return anchor
    steps = int((moment - anchor) // cadence)
    slot = anchor + steps * cadence
    return slot if slot >= moment else slot + cadence


def missed_slots(last_slot, cadence, moment):
    """Scheduled slots strictly between the last one and the moment: never backfilled."""
    return max(0, int((moment - last_slot - 1e-9) // cadence)) if moment > last_slot else 0


def worst_case_calls(policy, effective_seconds, minutes=390):
    """Projected request volume only. Not a cost: no pricing metadata is used."""
    cycles = int(minutes * 60 // effective_seconds)
    return dict(session_minutes=minutes, cycles=cycles,
                per_cycle_cap=policy['max_model_calls_per_cycle'],
                hourly_cap=policy['max_model_calls_per_hour'], daily_cap=policy['max_model_calls_per_day'],
                worst_case_model_calls=min(cycles * policy['max_model_calls_per_cycle'],
                                           -(-minutes // 60) * policy['max_model_calls_per_hour'],
                                           policy['max_model_calls_per_day']))


def material_fingerprint(candidate, context, now):
    """Material inputs only: no request ids, cutoffs or per-tick clocks.

    Current-market facts are summarized structurally plus one hysteresis price;
    reference evidence is identified by its immutable evidence id.
    """
    conditions = {c['condition_id']: c for c in build_conditions(candidate, context, now)}
    current = candidate['current_market_evidence']
    position = context['position']
    risk = context.get('risk_control')
    # Absent while no stop is configured, so existing baselines compare unchanged.
    stop = dict(stop=[risk['status'], risk['active_stop'], risk['position_epoch_id']]) if risk else {}
    return dict(
        **stop,
        current=sorted([e['capability'], e.get('source'), e.get('delivery_mode'), e.get('freshness_status'),
                        e.get('decision_admissibility'), bool(e.get('weak_reasons'))] for e in current),
        blocked=sorted({b['capability'] for b in candidate.get('blocked', [])}),
        reference=sorted(e['evidence_id'] for e in candidate['reference_evidence']),
        alignments=sorted([a.get('kind'), a.get('result')] for a in candidate.get('alignments', [])),
        quote=conditions['CURRENT_QUOTE']['status'], price=conditions['CURRENT_QUOTE'].get('source_value'),
        direction=conditions['DIRECTION_SUPPORTED'].get('direction'),
        exit_met=position['state'] != 'FLAT' and conditions['THESIS_REVERSED']['status'] == 'MET',
        position=[position['state'], position.get('quantity', 0)], pending=bool(position.get('pending')),
        opportunity=context.get('opportunity_id'), authority=bool(context.get('authority')),
        policy=context.get('policy_id'))


def material_change(prior, current, policy):
    """Reason codes for a material difference; empty means NO_MATERIAL_CHANGE."""
    if prior is None:
        return ['FIRST_EVALUATION']
    reasons = []
    if prior['position'] != current['position']:
        reasons.append('POSITION_CHANGED')
    if prior['pending'] != current['pending']:
        reasons.append('PENDING_ORDER_APPEARED' if current['pending'] else 'PENDING_ORDER_CLEARED')
    if prior['quote'] != current['quote']:
        reasons.append('QUOTE_RESTORED' if current['quote'] == 'MET' else 'QUOTE_LOST')
    if prior['authority'] != current['authority']:
        reasons.append('AUTHORITY_RESTORED' if current['authority'] else 'AUTHORITY_LOST')
    before, after = prior.get('stop'), current.get('stop')
    if before != after and after is not None:
        if after[0] == 'BREACHED':
            reasons.append(STOP_BREACH_CONDITION)
        elif before is None or before[2] != after[2]:
            reasons.append('STOP_EPISODE_CHANGED' if before is not None and before[1] is not None else 'STOP_INITIALIZED')
        elif before[1] != after[1]:
            reasons.append('STOP_INITIALIZED' if before[1] is None else 'STOP_TIGHTENED')
        elif after[0] == 'STALE':
            reasons.append('STOP_UPDATE_STALE')
        else:
            reasons.append('STOP_UPDATE_RESUMED' if before[0] == 'STALE' else 'STOP_STATUS_CHANGED')
    if prior['exit_met'] != current['exit_met']:
        reasons.append('EXIT_CONDITION_MET' if current['exit_met'] else 'EXIT_CONDITION_CLEARED')
    if prior['direction'] != current['direction']:
        reasons.append('DIRECTION_CHANGED')
    if prior['current'] != current['current'] or prior['blocked'] != current['blocked']:
        reasons.append('EVIDENCE_SET_CHANGED')
    if prior['reference'] != current['reference']:
        reasons.append('REFERENCE_EVIDENCE_CHANGED')
    if prior['alignments'] != current['alignments']:
        reasons.append('ALIGNMENT_CHANGED')
    if prior['opportunity'] != current['opportunity']:
        reasons.append('OPPORTUNITY_CHANGED')
    if prior['policy'] != current['policy']:
        reasons.append('POLICY_CHANGED')
    old, new = prior['price'], current['price']
    if isinstance(old, (int, float)) and isinstance(new, (int, float)) and old > 0 \
            and abs(new / old - 1) * 10000 >= policy['price_move_bps']:
        reasons.append('PRICE_MOVED')
    return reasons


def stability_decision(reasons, *, now, last_state_change, policy):
    """Operational anti-churn. Safety reasons always win over the dwell."""
    safety = sorted(SAFETY_REASONS.intersection(reasons))
    if safety:
        return dict(evaluate=True, safety=True, reason_codes=['SAFETY_PRECEDENCE', *safety])
    cutoff, changed = timestamp(now), timestamp(last_state_change)
    if changed and cutoff and 0 <= (cutoff - changed).total_seconds() < policy['min_state_dwell_seconds']:
        return dict(evaluate=False, safety=False, reason_codes=['MIN_STATE_DWELL'],
                    dwell_remaining_seconds=int(policy['min_state_dwell_seconds'] - (cutoff - changed).total_seconds()))
    return dict(evaluate=True, safety=False, reason_codes=[])


def provider_states(candidates, *, now, requested):
    """One row per capability with its own clock. Never labelled by the tick."""
    cutoff = timestamp(now)
    rows = {}
    for candidate in candidates:
        for e in (*candidate['current_market_evidence'], *candidate['reference_evidence']):
            observed = timestamp(e.get('as_of'))
            row = rows.get(e['capability'])
            if row and observed and timestamp(row['as_of']) and timestamp(row['as_of']) >= observed:
                row['instrument_count'] += 1
                continue
            reference = e.get('role') == 'REFERENCE_CONTEXT'
            mode = e.get('delivery_mode')
            semantics = ('PUBLICATION_BASED' if mode == 'PUBLICATION_BASED' else 'REFERENCE') if reference \
                else 'DELAYED' if mode == 'DELAYED' else 'CURRENT'
            age = int((cutoff - observed).total_seconds()) if cutoff and observed else None
            rows[e['capability']] = dict(
                capability=e['capability'], provider=e.get('source'), state=e.get('freshness_status'),
                delivery_mode=mode, role=e.get('role'), cadence_semantics=semantics,
                freshness_policy=e.get('policy'), basis=e.get('basis'), as_of=e.get('as_of'), age_seconds=age,
                next_useful_refresh=e.get('valid_until'),
                within_requested_cadence=bool(semantics == 'CURRENT' and age is not None and age <= requested),
                instrument_count=(row['instrument_count'] if row else 0) + 1)
        for b in candidate.get('blocked', []):
            rows.setdefault(b['capability'], dict(
                capability=b['capability'], provider=b.get('source'), state=b.get('freshness_status') or 'BLOCKED',
                delivery_mode=None, role=b.get('role'), cadence_semantics='BLOCKED', freshness_policy=None,
                basis=None, as_of=b.get('as_of'), age_seconds=None, next_useful_refresh=None,
                within_requested_cadence=False, instrument_count=0, reason_codes=list(b.get('reason_codes', []))[:6]))
    return [rows[key] for key in sorted(rows)][:16]


def cadence_readiness(states, *, ai_state, cadence):
    """A current quote plus an available engine is enough; reference data need not tick."""
    reasons = []
    quote = next((s for s in states if s['capability'] == 'QUOTE'), None)
    if quote is None or quote['cadence_semantics'] == 'BLOCKED':
        reasons.append('QUOTE_STALE_OR_UNAVAILABLE')
    if ai_state.get('state') != 'AVAILABLE':
        reasons.append('BUDGET_BLOCKED' if ai_state.get('reason') == 'SYNTHESIS_DAILY_BUDGET_EXHAUSTED' else 'MODEL_UNAVAILABLE')
    if reasons:
        return dict(readiness='REEVALUATION_BLOCKED', reason_codes=reasons)
    if quote['cadence_semantics'] == 'DELAYED':
        reasons.append('QUOTE_PROVIDER_DELAYED')
    if not quote['within_requested_cadence']:
        reasons.append('QUOTE_OLDER_THAN_REQUESTED_CADENCE')
    if any(s['cadence_semantics'] == 'BLOCKED' for s in states):
        reasons.append('CAPABILITY_BLOCKED')
    if cadence['degraded']:
        reasons.append('EFFECTIVE_CADENCE_SLOWER_THAN_REQUESTED')
    return dict(readiness='REEVALUATION_DEGRADED' if reasons else 'REEVALUATION_READY', reason_codes=reasons)


def reevaluation_pick(candidate, rank):
    """Server-authored selection facts for a fresh packet; no model wording."""
    refs = [*candidate['current_market_evidence'], *candidate['reference_evidence']]
    conflicts = sorted({r for a in candidate.get('alignments', []) if a.get('result') == 'CONFLICTING' for r in a.get('sentiment_refs', [])})
    return dict(instrument_id=candidate['instrument']['instrument_id'], rank=rank,
                rationale='Server-authored reevaluation packet; no model selection text.',
                supporting_refs=[], conflicting_refs=conflicts,
                weak_refs=sorted(e['evidence_id'] for e in refs if e.get('weak_reasons')),
                missing_capabilities=sorted(m['capability'] for m in candidate.get('missing', [])), uncertainties=[])


def loop_identity(account_id, scope):
    scope_hash = input_hash_from_dict(scope)
    return 'RL-' + input_hash_from_dict(dict(account=account_id, scope=scope_hash, policy=POLICY_ID))[:32], scope_hash

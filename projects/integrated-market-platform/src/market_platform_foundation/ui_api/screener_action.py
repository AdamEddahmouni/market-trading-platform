"""Explicit decision requests, server reconstruction, history and Paper drafts."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from ..paper.contracts import quantity_number, quantity_wire

import json
import copy
import threading
import time
from datetime import UTC, datetime

from ..intelligence.contracts.common import ContractReference
from ..intelligence.inference.action_decision import (
    ActionDecisionV1, POLICY_ID, PROMPT_ID, SCHEMA, build_conditions,
    decode_wire, gate_proposal, parse_proposal, server_exit_condition, snapshot_evidence, reasoned_wire_schema as wire_schema,
)
from ..intelligence.inference.candidate_reduction import ScreenerEvidencePacket
from ..intelligence.inference.config import IntelligenceInferenceConfig
from ..intelligence.inference.contracts import IntelligenceTaskType
from ..intelligence.inference.hashing import input_hash_from_dict
from ..intelligence.inference.action_input import VERSION as ACTION_INPUT_ENCODING, encode as encode_action_input, provider_diagnostics
from ..intelligence.inference.prompts import PromptRegistry
from ..local_state.action_decisions import action_repository
from ..local_state.connection import CRITICAL_WRITE_RETRY_SECONDS
from ..market_data.freshness_contract import timestamp
from .paper_ai_direct import ai_direct_enabled, direct_opportunity
from ..rt01.execution_decision_trace.recorder import ExecutionDecisionTraceDraft, materialize_execution_decision_trace
from ..rt01.execution_decision_trace.runtime import execution_decision_trace_repository
from ..rt01.execution_decision_trace.types import EligibilityDecisionSnapshot, ExecutionDecisionKind, RuleEvaluationOutcome, RuleEvaluationV1


def _iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace('+00:00','Z')


def capped_exit_quantity(ledger, instrument_id, quantity):
    """Server-sized, lot-aligned close under the frozen crypto order cap."""
    instrument = ledger.instrument_for(instrument_id)
    if instrument.get('instrument_kind') != 'CRYPTO_PAIR' or not ledger.policy.get('crypto_caps_version'):
        return quantity
    mark = ledger.mark_for(instrument_id) or {}
    if not mark.get('mark_minor'):
        return quantity  # The canonical preview still requires usable market evidence.
    unit_minor = Decimal(mark['mark_minor']) / Decimal(instrument['price_scale']) * Decimal(ledger.policy['price_scale'])
    step = Decimal(instrument['quantity_step'])
    maximum = (Decimal(ledger.policy['crypto_max_order_notional_minor']) / unit_minor / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if quantity <= maximum:
        return quantity
    # A capped close must leave enough for a later venue-valid order: the minimum notional plus a buffer when that
    # still splits the position, else the exact minimum, so the buffer never makes a closable position unclosable.
    from ..execution.simulator import CRYPTO_RESIDUAL_NOTIONAL_BUFFER
    floor = Decimal(instrument['minimum_quantity'])
    notional = instrument.get('minimum_notional')
    exact = max(floor, Decimal(notional) * Decimal(ledger.policy['price_scale']) / unit_minor) if notional is not None else floor
    buffered = max(floor, Decimal(notional) * CRYPTO_RESIDUAL_NOTIONAL_BUFFER * Decimal(ledger.policy['price_scale']) / unit_minor) \
        if notional is not None else floor
    close_buffered, splits_buffered = _capped_close(quantity, maximum, buffered, step)
    close_exact, splits_exact = _capped_close(quantity, maximum, exact, step)
    if close_buffered > 0 and (splits_buffered or not splits_exact):
        return close_buffered
    return close_exact


def _capped_close(quantity, maximum, minimum, step):
    """One capped chunk leaving at least ``minimum``, and whether the whole position splits into legal orders."""
    minimum = (minimum / step).to_integral_value(rounding=ROUND_CEILING) * step
    close = maximum
    if quantity - close < minimum:
        close = ((quantity - minimum) / step).to_integral_value(rounding=ROUND_FLOOR) * step
    if close < minimum:
        return Decimal(0), False  # No legal partition under the frozen cap; preview fails closed.
    # When the whole position splits into capped, venue-valid orders, keep the remainder splittable too:
    # a maximal chunk can otherwise strand an above-minimum remainder that no capped order can close.
    orders = (quantity / maximum).to_integral_value(rounding=ROUND_CEILING)
    if orders * minimum <= quantity:
        return min(close, quantity - (orders - 1) * minimum), True
    return close, False


class ScreenerActionService:
    def __init__(self, store, *, repository=None, ai=None, clock=time.time, trace_repository=None, risk_control=None):
        self.store = store
        self.risk_control = risk_control
        self.repository = repository or action_repository()
        self.ai = ai
        self.clock = clock
        self.trace_repository = trace_repository
        self.lock = threading.RLock()

    def _provider(self):
        if self.ai is None:
            from .screener_ai import screener_ai_service
            self.ai = screener_ai_service()
        return self.ai._news_service().synthesis_provider()

    def _position(self, instrument, now):
        ledger = self.store.paper_ledger
        rows = [p for p in ledger.project_positions() if p['instrument_id']==instrument]
        if len(rows)>1: raise ValueError('AMBIGUOUS_POSITION')
        quantity = quantity_number(rows[0]['quantity']) if rows else 0
        if rows and rows[0].get('side')=='SHORT': quantity=-abs(quantity)
        pending = any(o.get('instrument_id')==instrument and o.get('state') not in ('FILLED','CANCELLED','REJECTED','EXPIRED','RISK_REJECTED') for o in ledger.project_orders())
        # The internal ledger is projected synchronously. Deferred restoration is
        # explicitly unavailable until the existing runtime revalidates it.
        return dict(state='LONG' if quantity>0 else 'SHORT' if quantity<0 else 'FLAT', quantity=quantity_wire(quantity),
                    snapshot_at=None if getattr(self.store,'execution_deferred',False) else now,
                    account_id=ledger.paper_account_id, session_id=ledger.session_id,
                    source='PAPER_LEDGER', pending=pending)

    def _risk_facts(self, instrument):
        """OCT1-08: read-only deterministic stop facts. None while no stop is configured."""
        if self.risk_control is None:
            from .paper_risk_control import risk_control_service
            self.risk_control = risk_control_service(self.store)
        return self.risk_control.decision_facts(instrument)

    def _authority(self):
        ledger = self.store.paper_ledger
        from ..operating_modes import paper_execution_env_enabled, PAPER_EXECUTION_AUTHORITIES
        return bool(paper_execution_env_enabled() and ledger.execution_authority in PAPER_EXECUTION_AUTHORITIES
                    and ledger.execution_mode=='INTERNAL_SIMULATION' and not getattr(self.store,'execution_deferred',False))

    def _opportunity(self, candidate, cutoff, requested=None, *, admission=None):
        """Require shared immutable evidence lineage AND exact instrument identity.

        Symbol similarity alone never creates Opportunity authority.
        """
        evidence = admission if admission is not None else {}
        evidence.update(schema_version='paper-forecast-admission/1.0.0',
                        instrument_id=candidate['instrument']['instrument_id'], decision_time_ns=cutoff,
                        evidence_ids=sorted({e['evidence_id'] for e in
                                             (*candidate.get('current_market_evidence',()),
                                              *candidate.get('reference_evidence',())) if e.get('evidence_id')}),
                        status='UNAVAILABLE', reason_codes=['FORECAST_DISABLED'])
        evidence.setdefault('candidate_run_id',candidate.get('run_id'))
        repo = getattr(self.store,'strategy_repository',None)
        listing = getattr(repo,'list_opportunities',None)
        if not listing:
            evidence['reason_codes']=['STRATEGY_REPOSITORY_UNAVAILABLE']
            return None
        # The candidate's id, or the exact canonical id derived from its own instrument record (asset class and
        # venue included). Both name this one instrument; no other symbol can produce either.
        identities = {candidate['instrument']['instrument_id']}
        try:
            from ..strategy.path_a_live_forecast import qualified_instrument_id
            identities.add(qualified_instrument_id(candidate['instrument']))
        except (KeyError, ValueError):
            pass
        if requested:
            evidence.update(status='NOT_REQUESTED',reason_codes=['EXPLICIT_OPPORTUNITY_LOOKUP'])
            record = repo.get_opportunity(requested)
            if record is None or not identities.intersection(record.scope.instrument_ids):
                raise ValueError('OPPORTUNITY_IDENTITY_MISMATCH')
            from ..intelligence.execution.engine import _validate_opportunity_gate
            _validate_opportunity_gate(record, decision_time_ns=cutoff, scenario_id=None)
            from ..intelligence.contracts.opportunity import opportunity_v1_to_dict
            evidence['matched_opportunity_id']=record.opportunity_id
            return opportunity_v1_to_dict(record)
        try:
            # When an activated live forecast covers this instrument, it gets one governed chance to mint an
            # Opportunity from this very candidate's evidence before the lookup. Off by default; never fails the lookup.
            from .paper_live_forecast import live_forecast_hook
            hook = live_forecast_hook(admission=evidence)
            if hook is not None:
                outcome = hook.ensure_opportunity(self.store, dict(candidate,run_id=evidence.get('candidate_run_id')), cutoff)
                statuses={'FORECAST_UNAVAILABLE':'UNAVAILABLE','NOT_MATCHED':'REJECTED','SUPPRESSED':'REJECTED'}
                if (not isinstance(outcome,dict) or outcome.get('status') not in
                        {'UNAVAILABLE','REJECTED','MINTED','EXISTING','THROTTLED','ERROR',*statuses}
                        or outcome.get('instrument_id',evidence['instrument_id'])!=evidence['instrument_id']):
                    evidence.update(status='ERROR',reason_codes=['FORECAST_OUTCOME_INVALID'])
                else:
                    evidence.update(status=statuses.get(outcome['status'],outcome['status']),
                                    reason_codes=copy.deepcopy(outcome.get('reason_codes') or [outcome['status']]),
                                    outcome=copy.deepcopy(outcome))
        except Exception as exc:  # noqa: BLE001 - diagnostics cannot manufacture Opportunity authority
            evidence.update(status='ERROR',reason_codes=['FORECAST_ADMISSION_UNEXPECTED_ERROR'],
                            error_type=type(exc).__name__)
        refs = {e['evidence_id'] for e in (*candidate['current_market_evidence'],*candidate['reference_evidence'])}
        matches = [o for o in listing() if identities.intersection(o.scope.instrument_ids)
                   and o.created_at_ns <= cutoff and (o.valid_until_ns is None or o.valid_until_ns>cutoff)
                   and refs.intersection(r.id for r in o.lineage_refs)]
        if len(matches)!=1: return None
        from ..intelligence.contracts.opportunity import opportunity_v1_to_dict
        evidence['matched_opportunity_id']=matches[0].opportunity_id
        return opportunity_v1_to_dict(matches[0])

    def _build(self, body):
        started = time.perf_counter()
        if not isinstance(body,dict) or not {'run_id','instrument_id'} <= set(body) or set(body)-{'run_id','instrument_id','opportunity_id'} or any(not isinstance(v,str) or not v or len(v)>120 for v in body.values()):
            raise ValueError('INVALID_ACTION_REQUEST')
        if body["run_id"].startswith("LF-"):
            raise ValueError("EXPERIMENTAL_METHOD_UNAPPROVED")
        run = self.repository.get('candidate_run',body['run_id'])
        if run and (run.get("method") == "STAGED_LOCAL_FIRST_EXPERIMENTAL" or
                    run.get("staged") or str(run.get("method_version", "")).startswith("ai-screener-local-first/")):
            raise ValueError("EXPERIMENTAL_METHOD_UNAPPROVED")
        if run is None: raise ValueError('CANDIDATE_RUN_NOT_FOUND')
        pick = next((p for p in run['candidates'] if p['instrument_id']==body['instrument_id']),None)
        original = next((p for p in run['evidence'] if p['instrument']['instrument_id']==body['instrument_id']),None)
        if run['state']!='CURRENT' or pick is None or original is None:
            raise ValueError('SELECTED_CANDIDATE_REQUIRED')
        now = _iso(self.clock())
        candidate = snapshot_evidence(original,now)
        ledger = self.store.paper_ledger
        from ..paper.preview import portfolio_state_revision
        authority = self._authority()
        forecast_admission=dict(candidate_run_id=body['run_id'])
        context = dict(position=self._position(body['instrument_id'],now), candidate_valid_until=run['valid_until'],
                       opportunity=self._opportunity(candidate,int(timestamp(now).timestamp()*1e9),body.get('opportunity_id'),admission=forecast_admission),
                       forecast_admission=forecast_admission,
                       authority=authority, allow_short=ledger.allows_short(),
                       ai_direct=ai_direct_enabled(ledger),
                       portfolio_revision=portfolio_state_revision(ledger), risk_policy=copy.deepcopy(ledger.policy))
        review = getattr(self, 'overnight_review', lambda iid: None)(body['instrument_id'])
        if review:
            context['overnight_review'] = copy.deepcopy(review)
        risk = self._risk_facts(body['instrument_id'])
        if risk: context['risk_control'] = risk
        provider = self._provider()
        prompt = PromptRegistry().get_by_id(PROMPT_ID)
        conditions = build_conditions(candidate,context,now)
        stable_context = json.loads(json.dumps(context)); stable_context['position'].pop('snapshot_at',None)
        # Attempt clocks and MINTED -> EXISTING are diagnostic transitions. The actual
        # Opportunity remains in the material input hash and all existing gates.
        stable_context.pop('forecast_admission',None)
        material = dict(candidate=candidate, candidate_input_hash=run['input_hash'], candidate_rank=pick['rank'],
                        context=stable_context, policy_id=POLICY_ID, prompt_hash=prompt.content_hash,
                        provider_id=getattr(provider,'provider_id',None),model_id=getattr(provider,'model_id',None),
                        input_encoding=ACTION_INPUT_ENCODING if getattr(provider,'runtime',None)=='LOCAL_MODEL' else 'canonical-json/1.0.0')
        digest = input_hash_from_dict(material)
        data = dict(decision_cutoff=now,candidate=candidate,selection=pick,context=context,conditions=conditions)
        encoded = json.dumps(data,sort_keys=True,allow_nan=False,separators=(',',':'))
        if len(encoded.encode('utf-8'))>96000: raise ValueError('ACTION_PACKET_BOUND_EXCEEDED')
        return dict(run=run,pick=pick,candidate=candidate,context=context,conditions=conditions,provider=provider,
                    prompt=prompt,now=now,digest=digest,data=data,encoded=encoded,
                    build_latency_ms=round((time.perf_counter()-started)*1000,3))

    def preview(self,body):
        b = self._build(body)
        listing = getattr(getattr(self.store,'strategy_repository',None),'list_opportunities',lambda:())
        options = [dict(opportunity_id=o.opportunity_id,direction=str(o.side)) for o in listing()
                   if body['instrument_id'] in o.scope.instrument_ids and o.created_at_ns<=int(timestamp(b['now']).timestamp()*1e9)
                   and (o.valid_until_ns is None or o.valid_until_ns>int(timestamp(b['now']).timestamp()*1e9))]
        return dict(available_opportunities=options, schema_version='action-preview/1.0.0',decision_cutoff=b['now'],position=b['context']['position'],
                    opportunity_id=(b['context']['opportunity'] or {}).get('opportunity_id'),
                    candidate_valid_until=b['run']['valid_until'],conditions=b['conditions'],
                    candidate_current=bool(timestamp(b['run']['valid_until'])>timestamp(b['now'])),
                    paper_authority=b['context']['authority'],allow_short=b['context']['allow_short'],
                    provider_id=getattr(b['provider'],'provider_id',None),model_id=getattr(b['provider'],'model_id',None),
                    prompt_id=PROMPT_ID,input_hash=b['digest'],packet_bytes=len(b['encoded'].encode('utf-8')))

    def run(self,body,*,revalidation_reason=None):
        # OCT1-07: a deterministic fail-safe reason records REVALIDATION_REQUIRED
        # without spending a model call. It can only ever block, never permit.
        # Serial single-owner proposal inference and append: duplicate requests
        # cannot bill concurrently or fork predecessor history.
        with self.lock:
            b = self._build(body)
            now, provider = b['now'],b['provider']
            identity = 'AD-'+b['digest']
            old = self.repository.get('decision',identity)
            latest = self.history(body['instrument_id'])
            if latest and latest[0]['input_hash']==b['digest'] and timestamp(latest[0]['valid_until'])>timestamp(now):
                return dict(latest[0],cache='HIT')
            proposal, error, response = None,None,None
            reasoning_wire = None
            # OCT1-08: a breached stop is a server risk exit. It needs no model call and no model can veto it;
            # the gate still reports every Paper-preview blocker without erasing the EXIT.
            server_exit = server_exit_condition(b['conditions'])
            if server_exit: pass
            elif timestamp(b['run']['valid_until'])<=timestamp(now): error='CANDIDATE_EXPIRED'
            elif revalidation_reason: error=str(revalidation_reason)[:64]
            elif provider is None: error='LOCAL_NOT_CONFIGURED'
            else:
                schema = wire_schema(b['candidate'],b['conditions'])
                local_input = getattr(provider,'runtime',None)=='LOCAL_MODEL'
                encoded = json.dumps(encode_action_input(b['data']),sort_keys=True,allow_nan=False,separators=(',',':')) if local_input else b['encoded']
                rendered = b['prompt'].template.replace('{{evidence_json}}',encoded).replace('{{output_schema}}',json.dumps(schema,separators=(',',':')))
                config = IntelligenceInferenceConfig(prompt_id=PROMPT_ID,default_task_type=IntelligenceTaskType.SCREENER_ACTION_DECISION,
                    max_tokens=2000, timeout_seconds=300 if getattr(provider,'runtime','')=='LOCAL_MODEL' else 45)
                packet = ScreenerEvidencePacket(IntelligenceTaskType.SCREENER_ACTION_DECISION,identity,b['digest'],now,
                    b['context'],[b['candidate']],schema)
                response = provider.infer(packet,rendered_prompt=rendered,config=config)
                if response.error_code: error=response.error_code.value
                else:
                    canonical,error=decode_wire(response.raw_text,b['candidate'],b['conditions'])
                    if not error:
                        proposal,error=parse_proposal(canonical,b['candidate'],b['conditions'])
                        if not error: reasoning_wire=json.loads(response.raw_text)
            finished = _iso(self.clock())
            if not error and self._build(body)['digest'] != b['digest']:
                error = 'ACTION_INPUT_CHANGED_DURING_INFERENCE'
            gated = gate_proposal(proposal,b['candidate'],b['context'],now=finished)
            if error:
                gated.update(action_state='REVALIDATION_REQUIRED',execution_readiness='BLOCKED',
                             blocker_codes=list(dict.fromkeys([error,*gated['blocker_codes']])))
            deadlines = [b['run']['valid_until'], *[e['valid_until'] for e in (*b['candidate']['current_market_evidence'],*b['candidate']['reference_evidence']) if e.get('valid_until')]]
            valid_until = min(deadlines,key=lambda t:timestamp(t))
            # Expired repeat evaluations are new safety records, never rewriting
            # earlier current decisions. Valid equivalent inputs reuse identity.
            if old: identity += '-'+input_hash_from_dict(finished)[:12]
            history = [d for d in self.repository.history(body['instrument_id']) if d['position']['account_id']==b['context']['position']['account_id']]
            prior = history[0] if history else None
            model = dict(provider_id=getattr(provider,'provider_id',None),model_id=getattr(provider,'model_id',None),
                         runtime=getattr(provider,'runtime',None),prompt_id=PROMPT_ID,prompt_hash=b['prompt'].content_hash,
                         prompt_version=b['prompt'].version, simulated=bool(response and response.simulated))
            if server_exit:
                model = dict(provider_id=None,model_id=None,runtime=None,prompt_id=None,prompt_hash=None,prompt_version=None,
                             simulated=False,origin='SERVER_RISK_CONTROL')
            if response:
                model.update(provider_diagnostics(response))
                model.update(run_id=body['run_id'],request_timestamp=now,
                    input_encoding=ACTION_INPUT_ENCODING if getattr(provider,'runtime',None)=='LOCAL_MODEL' else 'canonical-json/1.0.0')
                for field in ('tokens_input','tokens_output','latency_ms','provider_request_id','provider_response_id'):
                    model[field]=getattr(response,field,None)
            snapshot = dict(cutoff=now,evidence=b['candidate'],candidate_run_id=body['run_id'],
                            candidate_input_hash=b['run']['input_hash'],candidate_rank=b['pick']['rank'],
                            selection=b['pick'],context=b['context'],model=model)
            snapshot_id = 'AS-'+input_hash_from_dict(snapshot)
            record = dict(schema_version=SCHEMA,decision_id=identity,instrument_id=body['instrument_id'],
                          instrument=b['candidate']['instrument'],decision_time=now,evaluated_at=finished,valid_until=valid_until,
                          previous_decision_id=prior['decision_id'] if prior else None,previous_state=prior['action_state'] if prior else None,
                          position=b['context']['position'],direction=proposal['direction'] if proposal else None,
                          model_reasoning_wire=reasoning_wire,model_proposal=proposal,rationale=proposal['rationale'] if proposal else
                              'Deterministic SMA trailing-stop risk condition. Server-authored; no model call.' if server_exit else 'Decision requires revalidation: '+str(error),
                          opportunity_id=(b['context']['opportunity'] or {}).get('opportunity_id'),
                          evidence_snapshot_id=snapshot_id,evidence_snapshot=snapshot,model=model,
                          supporting_refs=proposal['supporting_refs'] if proposal else [],
                          conflicting_refs=sorted(set(b['pick']['conflicting_refs'])|set(proposal['conflicting_refs'] if proposal else [])),
                          weak_refs=b['pick']['weak_refs'],missing_capabilities=b['pick']['missing_capabilities'],
                          **gated)
            record['input_hash']=b['digest']
            record['entry_plan']=[c for c in b['conditions'] if c['condition_id'] in (proposal or {}).get('entry_conditions',[])]
            record['hold_plan']=[c for c in b['conditions'] if c['condition_id'] in (proposal or {}).get('hold_conditions',[])]
            record['exit_plan']=[server_exit] if server_exit else [c for c in b['conditions'] if c['condition_id'] in (proposal or {}).get('exit_conditions',[])]
            risk = b['context'].get('risk_control')
            if risk: record['risk_control']=risk
            if server_exit:
                # Why IMP exited: this policy, this stop, this observation. Quantity stays with the ledger.
                record['server_exit']=dict(condition_id=server_exit['condition_id'],reason='DETERMINISTIC_SMA_TRAILING_STOP_RISK_CONDITION',
                    policy_id=risk['policy_id'],stop_state_id=risk['stop_state_id'],position_epoch_id=risk['position_epoch_id'],
                    account_id=risk.get('account_id'),experiment_id=risk.get('experiment_id'),
                    instrument_id=risk.get('instrument_id'),episode_id=risk.get('episode_id'),
                    side=risk['side'],active_stop=risk['active_stop'],previous_stop=risk['previous_stop'],
                    trigger_price=risk['trigger_price'],triggered_at=risk['triggered_at'],trigger_evidence=risk['trigger_evidence'],
                    paper_close='NOT_SUBMITTED',model_call=False)
            quote=next((c for c in b['conditions'] if c['condition_id']=='CURRENT_QUOTE'),None)
            record['reference_quote']=quote
            record['risk_decision_ref']=None; record['paper_preview_ref']=None
            record['performance']=dict(build_latency_ms=b['build_latency_ms'],packet_bytes=len(b['encoded'].encode('utf-8')),
                                       evidence_count=len(b['candidate']['current_market_evidence'])+len(b['candidate']['reference_evidence']))
            trace = materialize_execution_decision_trace(ExecutionDecisionTraceDraft(
                opportunity_id=record['opportunity_id'],decision_time_ns=int(timestamp(now).timestamp()*1e9),mode='PAPER',
                decision_kind=ExecutionDecisionKind.ACTION_ASSESSED,eligibility=EligibilityDecisionSnapshot(),
                provider_state=model,market_data_freshness=dict(cutoff=now,valid_until=valid_until),
                rule_evaluations=(RuleEvaluationV1(POLICY_ID,RuleEvaluationOutcome.FAIL if record['blocker_codes'] else RuleEvaluationOutcome.PASS,
                    tuple(record['reason_codes']), (ContractReference('ActionDecisionV1',identity),ContractReference('ActionEvidenceSnapshotV1',snapshot_id))),
                    *((RuleEvaluationV1(risk['policy_id'],RuleEvaluationOutcome.FAIL,(server_exit['condition_id'],),
                        (ContractReference('SmaTrailingStopStateV1',risk['stop_state_id']),)),) if server_exit else ())),
                blocker_codes=tuple(record['blocker_codes']),config_version_refs=(POLICY_ID,*((risk['policy_id'],) if server_exit else ())),correlation_id=identity,
                immutable_inputs=dict(input_hash=b['digest'],action_decision_id=identity,snapshot_id=snapshot_id,
                    **(dict(stop_state_id=risk['stop_state_id'],stop_policy_id=risk['policy_id'],active_stop=risk['active_stop'],
                            trigger_price=risk['trigger_price'],triggered_at=risk['triggered_at']) if server_exit else {}))))
            record['decision_trace_id']=trace.decision_trace_id
            immutable=ActionDecisionV1.from_dict(record).to_dict()
            # SQLite companions and traces share one transaction. Ephemeral
            # operation publishes the trace before making the decision readable.
            trace_repo = self.trace_repository or execution_decision_trace_repository()
            connection = self.repository.connection
            if connection is not None and getattr(trace_repo, '_connection', None) is connection:
                with connection.transaction(retry_seconds=CRITICAL_WRITE_RETRY_SECONDS):
                    self.repository.put('decision',identity,immutable)
                    trace_repo.put_execution_decision_trace(trace)
            else:
                trace_repo.put_execution_decision_trace(trace)
                self.repository.put('decision',identity,immutable)
            return dict(immutable,cache='MISS')

    def history(self,instrument):
        account=self.store.paper_ledger.paper_account_id
        return [d for d in self.repository.history(instrument) if d['position']['account_id']==account]

    def handoff(self,body):
        if not isinstance(body,dict) or set(body)!={'decision_id'}: raise ValueError('INVALID_ACTION_HANDOFF')
        record=self.repository.get('decision',body['decision_id'])
        if not record: raise ValueError('ACTION_DECISION_NOT_FOUND')
        now=_iso(self.clock())
        if timestamp(record['valid_until'])<=timestamp(now): raise ValueError('ACTION_DECISION_EXPIRED')
        request=dict(run_id=record['evidence_snapshot']['candidate_run_id'],instrument_id=record['instrument_id'])
        if record['opportunity_id']: request['opportunity_id']=record['opportunity_id']
        b=self._build(request)
        if b['digest']!=record['input_hash']: raise ValueError('ACTION_INPUT_CHANGED')
        # Gated at the cutoff the position snapshot was just taken at: an earlier clock read would make that
        # snapshot look like it came from the future and fail POSITION_SNAPSHOT_STALE on any ticking clock.
        current=gate_proposal(record['model_proposal'],b['candidate'],b['context'],now=b['now'])
        if current['execution_readiness']!='PREVIEW_ALLOWED': raise ValueError('ACTION_HANDOFF_BLOCKED')
        state=record['action_state']
        if state not in ('ENTER','EXIT'): raise ValueError('ACTION_NOT_HANDOFF_ELIGIBLE')
        quantity=quantity_wire(abs(quantity_number(b['context']['position']['quantity']))) if state=='EXIT' else 1
        if state=='EXIT':
            quantity=quantity_wire(capped_exit_quantity(self.store.paper_ledger,record['instrument_id'],quantity_number(quantity)))
        # Entry uses the existing minimal operator draft (one unit), not model
        # sizing. Workspace always runs its independent preview/risk pipeline.
        side=('SELL' if b['context']['position']['state']=='LONG' else 'BUY') if state=='EXIT' else ('BUY' if record['direction']=='LONG' else 'SELL')
        return dict(version=1,instrumentId=record['instrument_id'],side=side,quantity=quantity,orderType='MARKET',
                    sourceAttentionId='opportunity:'+record['opportunity_id'] if record['opportunity_id'] else 'lane:order-flow',
                    sourceContext=dict(headline=record['rationale'],source_time=int(timestamp(record['decision_time']).timestamp()*1e9),
                        reasons=[dict(code='ACTION_DECISION',label=record['decision_id']),dict(code='ACTION_SNAPSHOT',label=record['evidence_snapshot_id'])]))

    def validate_order_source(self, parsed, instrument):
        """Revalidate bounded Action provenance at both existing Paper boundaries.

        Operators may size entry drafts in Workspace. Exits use the exact
        server-derived capped close quantity; model proposals never own quantity.
        """
        source=parsed.get('decision_source_snapshot') or {}
        reasons=source.get('reasons',[])
        ids=[r['label'] for r in reasons if r['code']=='ACTION_DECISION']
        snapshots=[r['label'] for r in reasons if r['code']=='ACTION_SNAPSHOT']
        if not ids and not snapshots: return
        if len(ids)!=1 or len(snapshots)!=1: raise ValueError('ACTION_SOURCE_INVALID')
        record=self.repository.get('decision',ids[0])
        if not record or record['evidence_snapshot_id']!=snapshots[0]: raise ValueError('ACTION_SOURCE_INVALID')
        draft=self.handoff(dict(decision_id=ids[0]))
        if draft['instrumentId']!=instrument or draft['side']!=parsed['side']:
            raise ValueError('ACTION_ORDER_IDENTITY_MISMATCH')
        if record['action_state']=='EXIT':
            expected = quantity_number(draft['quantity'])
            from ..intelligence.inference.paper_automation import intent_identity
            if parsed.get('client_order_id') == intent_identity(self.store.paper_ledger.paper_account_id, record['decision_id']):
                # Only the internal automation intent can close its own slice of
                # a mixed position. Manual HTTP routes reserve these IDs.
                from .paper_automation import _automation_quantities
                owned = _automation_quantities(self.store.paper_ledger).get(instrument, 0)
                signed = quantity_number(record['position']['quantity'])
                expected = min(expected, abs(owned)) if owned * signed > 0 else 0
            if not expected or expected != quantity_number(parsed['quantity']):
                raise ValueError('ACTION_EXIT_QUANTITY_CHANGED')
        return record

    def assess_entry_risk(self, record, parsed):
        """Reuse BUILD 22 for governed entry, in addition to interactive Paper risk.

        EXIT is a reduction of current holdings through the existing close path;
        it never fabricates an economic Opportunity to satisfy an entry engine.
        """
        if not record or record['action_state']!='ENTER': return None
        from ..intelligence.execution.engine import PreTradeRiskEngine
        from ..intelligence.execution.policy import build_execution_policy
        from ..intelligence.execution.snapshot import snapshot_from_paper_ledger
        from ..intelligence.execution.types import MarketQuoteV1
        from ..intelligence.execution.serialization import risk_decision_v1_to_dict
        from ..numeric import decimal_to_minor_units
        ledger=self.store.paper_ledger
        now=int(timestamp(_iso(self.clock())).timestamp()*1e9)
        scale=int(ledger.policy.get('price_scale',100))
        from .paper_projections import _admit_focus_instrument
        instrument = parsed.get('_instrument') or (_admit_focus_instrument(self.store, record['instrument_id']) if record['instrument'].get('universe') == 'CRYPTO' else {})
        fractional = instrument.get('instrument_kind') == 'CRYPTO_PAIR'
        if fractional:
            native_scale = int(instrument['price_scale'])
            native_price = int((Decimal(str(record['reference_quote']['source_value'])) * native_scale).to_integral_value(rounding=ROUND_CEILING))
            price = int((Decimal(native_price) * scale / native_scale).to_integral_value(rounding=ROUND_CEILING))
        else:
            price = decimal_to_minor_units(str(record['reference_quote']['source_value']),scale=scale)
        # Existing BUILD 22 defaults govern NAV/exposure; ledger hard caps remain
        # an additional independent authority in the interactive preview below.
        max_trade=int(ledger.policy['max_order_shares'])*price
        max_position=int(ledger.policy['max_position_shares'])*price
        if fractional and ledger.policy.get('crypto_caps_version'):
            # The account's frozen crypto terms are dollar caps (owner decision 5 (b)), not units times price.
            max_trade=int(ledger.policy['crypto_max_order_notional_minor'])
            max_position=int(ledger.policy['crypto_max_position_notional_minor'])
        policy=build_execution_policy(allow_short=ledger.allows_short(),
            max_total_open_orders=int(ledger.policy['max_open_orders']),
            max_open_orders_per_symbol=int(ledger.policy['max_open_orders']),
            max_trade_notional_minor=max_trade,
            max_position_notional_minor=max_position,
            price_scale=scale,currency=ledger.policy.get('currency','USD'),max_portfolio_snapshot_age_ns=30_000_000_000)
        portfolio=snapshot_from_paper_ledger(ledger,captured_at_ns=now)
        if record['opportunity_id']:
            opportunity=self.store.strategy_repository.get_opportunity(record['opportunity_id'])
        elif (record.get('evidence_snapshot') or {}).get('context',{}).get('ai_direct') and ai_direct_enabled(ledger):
            opportunity=direct_opportunity(record)
        else:
            raise ValueError('NO_GOVERNED_OPPORTUNITY')
        # A live screener candidate carries no 'symbol'; the Paper order is keyed by the instrument id itself.
        symbol=record['instrument'].get('symbol') or record['instrument_id']
        engine=PreTradeRiskEngine()
        proposal=engine.build_proposal(opportunity=opportunity,policy=policy,portfolio=portfolio,
            quote=MarketQuoteV1(record['instrument_id'],price,price,int(timestamp(record['reference_quote']['as_of']).timestamp()*1e9)),proposal_time_ns=now,
            instrument_id=record['instrument_id'],symbol=symbol,
            allocation_desired_quantity=parsed['quantity'],instrument=instrument if fractional else None,lineage_refs=(ContractReference('ActionDecisionV1',record['decision_id']),))
        submitted=set()
        for order in ledger.project_orders():
            source=order.get('decision_source_snapshot') or {}
            if source.get('source_type')=='watched_opportunity': submitted.add(source['source_id'])
            correlation=order.get('correlation_id') or ''
            if correlation.startswith('opportunity:'): submitted.add(correlation.split(':',1)[1])
            legacy=(order.get('metadata') or {}).get('opportunity_id')
            if legacy: submitted.add(legacy)
        risk=engine.assess(proposal=proposal,opportunity=opportunity,policy=policy,portfolio=portfolio,
            decision_time_ns=now,symbol=symbol,submitted_opportunity_ids=frozenset(submitted))
        repo=self.store.strategy_repository
        for method,value in (('put_execution_policy',policy),('put_paper_portfolio_snapshot',portfolio),('put_trade_proposal',proposal),('put_risk_decision',risk)):
            getattr(repo,method)(value)
        return dict(risk_decision_v1_to_dict(risk),operator_quantity=parsed['quantity'])


def action_service(store):
    service=getattr(store,'_action_decision_service',None)
    if service is None:
        service=ScreenerActionService(store); store._action_decision_service=service
    return service

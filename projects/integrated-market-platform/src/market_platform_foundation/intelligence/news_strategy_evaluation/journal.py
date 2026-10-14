"""Read-only daily journal over existing decision, feature and outcome records.

This projection is not another ledger or an execution boundary. Its canonical
JSON freezes nested evidence; later measurements are separate immutable values.
The caller supplies clocks. No provider, inference, fitting or persistence runs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

from ...canonical import canonical_bytes, sha256_bytes
from ...rt01.execution_decision_trace.types import ExecutionDecisionTraceV1
from ...rt01.execution_decision_trace.serialization import execution_decision_trace_v1_to_dict
from ..contracts.opportunity import OpportunityV1, opportunity_v1_to_dict
from ..inference.action_decision import ActionDecisionV1, snapshot_evidence
from ..inference.hashing import input_hash_from_dict
from ..trade_review.contracts import TradeReviewV1
from .contracts import RealizedOutcome, StrategyEvaluationDecision, StrategyFeatureSnapshot


def _clock(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None or 'T' not in value:
            raise ValueError
        return parsed.astimezone(UTC)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError('JOURNAL_CLOCK_INVALID') from exc


def _before(value: str, cutoff: datetime) -> None:
    if _clock(value) > cutoff:
        raise ValueError('JOURNAL_AFTER_DECISION_CUTOFF')


def _freeze(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True, slots=True)
class DecisionJournalSnapshot:
    """Projection artifact only; original source repositories retain ownership."""
    canonical_json: str

    def to_dict(self) -> dict:
        return json.loads(self.canonical_json)


@dataclass(frozen=True, slots=True)
class DecisionOutcomeObservation:
    canonical_json: str

    def to_dict(self) -> dict:
        return json.loads(self.canonical_json)


@dataclass(frozen=True, slots=True)
class DecisionReviewObservation:
    canonical_json: str

    def to_dict(self) -> dict:
        return json.loads(self.canonical_json)


def capture_decision_snapshot(
    *, decision: StrategyEvaluationDecision | ActionDecisionV1 | Mapping,
    evidence_snapshot: StrategyFeatureSnapshot | Mapping | None = None,
    opportunity: OpportunityV1 | Mapping | None = None,
    mode: str = 'DEMO', trace: ExecutionDecisionTraceV1 | None = None,
) -> DecisionJournalSnapshot:
    """Freeze existing source IDs and facts; never infer an operator decision.

    Evaluation biases remain research biases. Action receipts retain their own
    proposal/action semantics, including NO_ACTION and revalidation. An optional
    governed Opportunity is checked by instrument, clock and shared evidence.
    """
    if mode not in ('DEMO', 'PAPER', 'LIVE'):
        raise ValueError('JOURNAL_MODE_INVALID')
    research = isinstance(decision, StrategyEvaluationDecision)
    receipt_owned = False
    missing = []
    body = decision.to_dict() if isinstance(decision, (StrategyEvaluationDecision, ActionDecisionV1)) else dict(decision)
    decision_time = body['as_of'] if research else body['decision_time']
    cutoff = _clock(decision_time)
    if research:
        if not decision.simulation_only or decision.execution_authority:
            raise ValueError('JOURNAL_RESEARCH_AUTHORITY_INVALID')
        if not isinstance(evidence_snapshot, StrategyFeatureSnapshot):
            raise ValueError('JOURNAL_FEATURE_SNAPSHOT_REQUIRED')
        source = evidence_snapshot
        if (source.snapshot_id != decision.feature_snapshot_id or source.instrument_id != decision.instrument_id
                or source.asset_class != decision.asset_class or _clock(source.as_of) != cutoff
                or source.news_event_ids != decision.news_event_ids
                or source.market.market_data_ref != decision.market_snapshot_ref
                or source.market.instrument_id != decision.instrument_id):
            raise ValueError('JOURNAL_SNAPSHOT_IDENTITY_MISMATCH')
        for clock in source.deterministic.publication_times:
            if not clock:
                missing.append('NEWS_PUBLICATION_TIME_UNKNOWN')
            else:
                _before(clock, cutoff)
        for clock in (*source.deterministic.retrieval_times, source.market.bar_event_time):
            _before(clock, cutoff)
        frozen_evidence = source.to_dict()
        source_refs = dict(news_event_ids=list(decision.news_event_ids),
            inference_record_ids=list(decision.inference_record_ids),
            feature_snapshot_id=decision.feature_snapshot_id, market_snapshot_ref=decision.market_snapshot_ref,
            source_ids=list(source.deterministic.source_ids), decision_trace_id=None)
        action = dict(evaluation_bias=decision.decision.value, action_state=None, operator_action=None,
                      model_proposal=None, execution_readiness=None)
    else:
        # Validate the existing action contract instead of creating another state enum.
        body = ActionDecisionV1.from_dict(body).to_dict()
        embedded = body.get('evidence_snapshot')
        supplied = dict(evidence_snapshot) if isinstance(evidence_snapshot, Mapping) else None
        if embedded is not None and supplied is not None and _freeze(embedded) != _freeze(supplied):
            raise ValueError('JOURNAL_SNAPSHOT_IDENTITY_MISMATCH')
        frozen_evidence = embedded if embedded is not None else supplied
        if not isinstance(frozen_evidence, dict):
            raise ValueError('JOURNAL_ACTION_SNAPSHOT_REQUIRED')
        if embedded is None and body['evidence_snapshot_id'] != 'AS-' + input_hash_from_dict(frozen_evidence):
            raise ValueError('JOURNAL_SNAPSHOT_IDENTITY_MISMATCH')
        if _clock(frozen_evidence['cutoff']) != cutoff:
            raise ValueError('JOURNAL_SNAPSHOT_IDENTITY_MISMATCH')
        candidate = frozen_evidence['evidence']
        instrument_id = candidate.get('instrument', {}).get('instrument_id')
        selected_instrument_id = frozen_evidence.get('selection', {}).get('instrument_id')
        if ((embedded is None and instrument_id is None)
                or (instrument_id is not None and instrument_id != body['instrument_id'])
                or (selected_instrument_id is not None and selected_instrument_id != body['instrument_id'])
                or (body.get('candidate_run_id') is not None
                    and body['candidate_run_id'] != frozen_evidence.get('candidate_run_id'))):
            raise ValueError('JOURNAL_SNAPSHOT_IDENTITY_MISMATCH')
        admitted = snapshot_evidence(candidate, decision_time)
        if any(admitted[group] != candidate[group] for group in ('current_market_evidence', 'reference_evidence')):
            raise ValueError('JOURNAL_AFTER_DECISION_CUTOFF')
        refs = [e['evidence_id'] for group in ('current_market_evidence', 'reference_evidence') for e in candidate[group]]
        source_refs = dict(evidence_ids=refs, evidence_snapshot_id=body['evidence_snapshot_id'],
            candidate_run_id=frozen_evidence.get('candidate_run_id'), decision_trace_id=body.get('decision_trace_id'))
        action = dict(evaluation_bias=None, action_state=body['action_state'], operator_action=None,
            model_proposal=body.get('model_proposal'), execution_readiness=body.get('execution_readiness'),
            rationale=body.get('rationale'), reason_codes=body.get('reason_codes', []),
            blocker_codes=body.get('blocker_codes', []))
        if opportunity is None:
            opportunity = frozen_evidence.get('context', {}).get('opportunity')
            # The action service admits an operator-selected Opportunity by identity and gate, without
            # shared evidence. A receipt that froze and names that Opportunity is its own lineage.
            receipt_owned = opportunity is not None and body.get('opportunity_id') == dict(opportunity).get('opportunity_id')
    opp = opportunity_v1_to_dict(opportunity) if isinstance(opportunity, OpportunityV1) else dict(opportunity) if opportunity is not None else None
    if opp is not None:
        created = datetime.fromtimestamp(opp['created_at_ns'] / 1_000_000_000, UTC)
        evidence_ids = set(source_refs.get('evidence_ids', source_refs.get('news_event_ids', ())))
        if (body['instrument_id'] not in opp['scope']['instrument_ids'] or created > cutoff
                or not (receipt_owned or evidence_ids.intersection(r['id'] for r in opp.get('lineage_refs', ())))
                or (body.get('opportunity_id') and body['opportunity_id'] != opp['opportunity_id'])):
            raise ValueError('JOURNAL_OPPORTUNITY_LINEAGE_MISMATCH')
    trace_body = None
    if trace is not None:
        if (trace.mode != mode or trace.decision_time_ns != int(cutoff.timestamp() * 1_000_000_000)
                or trace.opportunity_id != (opp or {}).get('opportunity_id', body.get('opportunity_id'))):
            raise ValueError('JOURNAL_TRACE_IDENTITY_MISMATCH')
        trace_body = execution_decision_trace_v1_to_dict(trace)
        source_refs['decision_trace_id'] = trace.decision_trace_id
        action['operator_action'] = trace.operator_action.value if trace.operator_action else None
    payload = dict(decision_id=body['decision_id'], decision_time=decision_time,
        instrument_id=body['instrument_id'], mode=mode, opportunity_id=(opp or {}).get('opportunity_id', body.get('opportunity_id')),
        opportunity=opp, source_refs=source_refs, evidence_snapshot=frozen_evidence, source_decision=body,
        action=action, decision_trace=trace_body, missing_information=list(dict.fromkeys(missing)), execution_authority=False)
    payload['decision_snapshot_hash'] = sha256_bytes(canonical_bytes(payload))
    return DecisionJournalSnapshot(_freeze(payload))


def observe_outcome(snapshot: DecisionJournalSnapshot, outcome: RealizedOutcome, *, observed_at: str) -> DecisionOutcomeObservation:
    """Attach subsequent market measurement without retroactive input edits."""
    entry = snapshot.to_dict()
    body = outcome.to_dict()
    if (outcome.decision_id != entry['decision_id'] or _clock(outcome.start_time) != _clock(entry['decision_time'])
            or (entry['source_decision'].get('sample_id') and outcome.sample_id != entry['source_decision']['sample_id'])):
        raise ValueError('JOURNAL_OUTCOME_IDENTITY_MISMATCH')
    if (_clock(outcome.end_time) < _clock(outcome.start_time) or _clock(observed_at) < _clock(outcome.end_time)
            or (outcome.measured_as_of is not None and _clock(observed_at) < _clock(outcome.measured_as_of))):
        raise ValueError('JOURNAL_OUTCOME_NOT_YET_OBSERVABLE')
    payload = dict(decision_id=entry['decision_id'], decision_snapshot_hash=entry['decision_snapshot_hash'],
        observed_at=observed_at, outcome=body, interpretation='HYPOTHETICAL_MARKET_MOVEMENT',
        execution_authority=False)
    payload['observation_hash'] = sha256_bytes(canonical_bytes(payload))
    return DecisionOutcomeObservation(_freeze(payload))


def observe_review(snapshot: DecisionJournalSnapshot, review: TradeReviewV1) -> DecisionReviewObservation:
    """Project a canonical review's recorded decision, never its editable notes.

    Attribution claims are not evidence of fills. The journal exposes distinct
    order/fill references, leaving realized accounting to the existing ledger.
    """
    entry = snapshot.to_dict()
    if (review.opportunity_id != entry['opportunity_id']
            or review.decision_time_ns != int(_clock(entry['decision_time']).timestamp() * 1_000_000_000)):
        raise ValueError('JOURNAL_REVIEW_IDENTITY_MISMATCH')
    if (review.review_mode.value == 'PAPER_TRADE' and entry['mode'] != 'PAPER'
            or review.review_mode.value == 'LIVE_TRADE' and entry['mode'] != 'LIVE'):
        raise ValueError('JOURNAL_REVIEW_MODE_MISMATCH')
    if review.created_at_ns < review.decision_time_ns:
        raise ValueError('JOURNAL_REVIEW_CLOCK_INVALID')
    attribution = review.execution_attribution
    payload = dict(decision_id=entry['decision_id'], decision_snapshot_hash=entry['decision_snapshot_hash'],
        review_id=review.review_id, review_mode=review.review_mode.value, decision=review.decision,
        observed_at=datetime.fromtimestamp(review.created_at_ns / 1_000_000_000, UTC).isoformat().replace('+00:00', 'Z'),
        order_refs=[dict(kind=ref.kind, id=ref.id) for ref in attribution.order_refs] if attribution else [],
        fill_refs=[dict(kind=ref.kind, id=ref.id) for ref in attribution.fill_refs] if attribution else [],
        evidence_snapshot_refs=[dict(kind=ref.kind, id=ref.id) for ref in review.evidence_snapshot_refs],
        execution_decision_trace_id=review.execution_decision_trace_id, execution_authority=False)
    return DecisionReviewObservation(_freeze(payload))


def project_decision_outcomes(
    snapshot: DecisionJournalSnapshot, *, outcomes: Iterable[DecisionOutcomeObservation] = (), observation_as_of: str,
    reviews: Iterable[DecisionReviewObservation] = (),
) -> dict:
    """As-of projection: a late observation is absent from earlier cutoffs."""
    row = snapshot.to_dict()
    cutoff = _clock(observation_as_of)
    if cutoff < _clock(row['decision_time']):
        raise ValueError('JOURNAL_BEFORE_DECISION')
    visible = {}
    for observation in outcomes:
        body = observation.to_dict()
        if body['decision_snapshot_hash'] != row['decision_snapshot_hash']:
            raise ValueError('JOURNAL_OUTCOME_IDENTITY_MISMATCH')
        if _clock(body['observed_at']) <= cutoff:
            visible[body['observation_hash']] = body
    row['outcomes'] = sorted(visible.values(), key=lambda item: (_clock(item['observed_at']), item['observation_hash']))
    row['outcome_status'] = ('UNAVAILABLE' if not visible else 'AVAILABLE'
        if all(item['outcome']['quality'] == 'COMPLETE' for item in visible.values()) else 'INCOMPLETE')
    row['observation_as_of'] = observation_as_of
    row['reviews'] = []
    for review in reviews:
        body = review.to_dict()
        if body['decision_snapshot_hash'] != row['decision_snapshot_hash']:
            raise ValueError('JOURNAL_REVIEW_IDENTITY_MISMATCH')
        if _clock(body['observed_at']) <= cutoff:
            row['reviews'].append(body)
    row['reviews'].sort(key=lambda item: (_clock(item['observed_at']), item['review_id']))
    # Research returns and directional units cannot establish filled-trade P&L.
    row['realized_pnl'] = None
    row['realized_pnl_status'] = 'NOT_MEASURED_BY_RESEARCH_JOURNAL'
    return row


def build_daily_journal(
    snapshots: Iterable[DecisionJournalSnapshot], *, day: str, observation_as_of: str,
    outcomes: Iterable[DecisionOutcomeObservation] = (),
    reviews: Iterable[DecisionReviewObservation] = (), timezone: str = 'America/New_York',
) -> dict:
    """Market-day projection, using source decision time rather than arrival day."""
    selected_day = date.fromisoformat(day)
    zone = ZoneInfo(timezone)
    cutoff = _clock(observation_as_of)
    observations = tuple(outcomes)
    review_observations = tuple(reviews)
    entries = {}
    for snapshot in snapshots:
        entry = snapshot.to_dict()
        decision_time = _clock(entry['decision_time'])
        if decision_time.astimezone(zone).date() != selected_day or decision_time > cutoff:
            continue
        if entry['decision_id'] in entries and entries[entry['decision_id']].canonical_json != snapshot.canonical_json:
            raise ValueError('JOURNAL_IMMUTABLE_DECISION_COLLISION')
        entries[entry['decision_id']] = snapshot
    items = [project_decision_outcomes(snapshot, observation_as_of=observation_as_of,
        outcomes=(item for item in observations if item.to_dict()['decision_id'] == decision_id),
        reviews=(item for item in review_observations if item.to_dict()['decision_id'] == decision_id))
        for decision_id, snapshot in entries.items()]
    items.sort(key=lambda item: (_clock(item['decision_time']), item['decision_id']))
    return dict(day=day, day_basis=timezone, observation_as_of=observation_as_of, items=items,
        execution_authority=False, source='EXISTING_DECISION_AND_OUTCOME_RECORDS')


__all__ = ['DecisionJournalSnapshot', 'DecisionOutcomeObservation', 'DecisionReviewObservation', 'capture_decision_snapshot',
           'observe_outcome', 'observe_review', 'project_decision_outcomes', 'build_daily_journal']

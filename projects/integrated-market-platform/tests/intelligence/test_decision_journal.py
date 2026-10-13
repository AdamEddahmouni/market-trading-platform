"""Daily journal truth: frozen inputs and separately timed research observations."""
from __future__ import annotations

import importlib
import unittest
from dataclasses import replace
from datetime import datetime

from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import (
    DeterministicNewsFeatures, EvaluationDecision, MarketFeatures, OutcomeQuality,
    PolicyClassification, RealizedOutcome, StrategyEvaluationDecision, StrategyFeatureSnapshot,
)
from market_platform_foundation.intelligence.trade_review.contracts import (
    TradeReviewV1, TradeReviewMode, TradeExecutionAttribution,
)
from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict

try:
    journal = importlib.import_module('market_platform_foundation.intelligence.news_strategy_evaluation.journal')
except ModuleNotFoundError:
    journal = None


def sources():
    snapshot = StrategyFeatureSnapshot(
        snapshot_id='SNAP-1', as_of='2026-10-12T14:00:00Z', instrument_id='SIM:AAA', asset_class='EQUITY',
        news_event_ids=('NEWS-1',),
        deterministic=DeterministicNewsFeatures(1, ('CAT-1',), ('SOURCE-1',), ('CURATED',), 60, 60,
            ('2026-10-12T13:59:00Z',), ('2026-10-12T13:59:30Z',)),
        market=MarketFeatures('SIM:AAA', 'EQUITY', 100.0, None, '2026-10-12T14:00:00Z', 'SERIES-1'),
        snapshot_hash='frozen-source-hash')
    decision = StrategyEvaluationDecision(
        'EVDEC-1', 'RUN-1', 'SAMPLE-1', 'POLICY-1', '1', PolicyClassification.BASELINE_DETERMINISTIC,
        'config-hash', snapshot.as_of, snapshot.instrument_id, snapshot.asset_class,
        EvaluationDecision.NEUTRAL, 0, True, False, snapshot.news_event_ids, (), snapshot.snapshot_id,
        snapshot.market.market_data_ref)
    outcome = RealizedOutcome('EVOUT-1', 'EVDEC-1', 'SAMPLE-1', '1H', snapshot.as_of,
        '2026-10-12T15:00:00Z', 100.0, 102.0, 103.0, 99.0, .02, 0.0, .03, -.01,
        None, OutcomeQuality.COMPLETE, 'SERIES-1')
    return snapshot, decision, outcome


def ns(clock):
    return int(datetime.fromisoformat(clock.replace('Z', '+00:00')).timestamp() * 1_000_000_000)


class DecisionJournalTests(unittest.TestCase):
    def test_outcome_measurement_cutoff_cannot_be_backdated(self):
        self.assertIn('measured_as_of', self.outcome.__dataclass_fields__)
        late = replace(self.outcome, measured_as_of='2026-10-12T16:00:00Z')
        with self.assertRaisesRegex(ValueError, 'OUTCOME_NOT_YET_OBSERVABLE'):
            journal.observe_outcome(self.capture(), late, observed_at='2026-10-12T15:30:00Z')

    def setUp(self):
        self.assertIsNotNone(journal, 'Decision journal projection is not implemented')
        self.source, self.decision, self.outcome = sources()

    def capture(self, **kwargs):
        return journal.capture_decision_snapshot(decision=self.decision, evidence_snapshot=self.source, **kwargs)

    def test_decision_snapshot_is_isolated_from_mutable_inputs_and_reads(self):
        entry = self.capture()
        first = entry.to_dict()
        first['evidence_snapshot']['market']['price_at_as_of'] = 999
        self.assertEqual(entry.to_dict()['evidence_snapshot']['market']['price_at_as_of'], 100.0)
        self.assertEqual(entry.to_dict()['source_refs']['news_event_ids'], ['NEWS-1'])
        self.assertEqual(entry.to_dict()['decision_time'], '2026-10-12T14:00:00Z')

    def test_neutral_evaluation_never_invents_an_operator_trade_or_confidence(self):
        row = journal.project_decision_outcomes(self.capture(), observation_as_of='2026-10-12T16:00:00Z')
        self.assertEqual(row['action']['evaluation_bias'], 'NEUTRAL')
        self.assertIsNone(row['action']['operator_action'])
        self.assertIsNone(row['action']['action_state'])
        self.assertEqual(row['outcome_status'], 'UNAVAILABLE')
        self.assertIsNone(row['realized_pnl'])
        self.assertNotIn('confidence', row['action'])
        self.assertNotIn('entry_price', row)

    def test_future_retrieval_cannot_enter_decision_snapshot(self):
        late = replace(self.source, deterministic=replace(self.source.deterministic,
            retrieval_times=('2026-10-12T14:00:01Z',)))
        with self.assertRaisesRegex(ValueError, 'AFTER_DECISION_CUTOFF'):
            journal.capture_decision_snapshot(decision=self.decision, evidence_snapshot=late)

    def test_future_market_feature_and_naive_clock_fail_closed(self):
        future = replace(self.source, market=replace(self.source.market, bar_event_time='2026-10-12T14:01:00Z'))
        with self.assertRaisesRegex(ValueError, 'AFTER_DECISION_CUTOFF'):
            journal.capture_decision_snapshot(decision=self.decision, evidence_snapshot=future)
        with self.assertRaisesRegex(ValueError, 'CLOCK_INVALID'):
            journal.capture_decision_snapshot(decision=replace(self.decision, as_of='2026-10-12T14:00:00'), evidence_snapshot=self.source)

    def test_snapshot_and_outcome_identity_mismatch_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_IDENTITY_MISMATCH'):
            journal.capture_decision_snapshot(decision=self.decision, evidence_snapshot=replace(self.source, instrument_id='SIM:BBB'))
        with self.assertRaisesRegex(ValueError, 'OUTCOME_IDENTITY_MISMATCH'):
            journal.observe_outcome(self.capture(), replace(self.outcome, decision_id='OTHER'), observed_at='2026-10-12T16:00:00Z')

    def test_outcome_requires_reached_horizon_and_remains_hypothetical(self):
        entry = self.capture()
        with self.assertRaisesRegex(ValueError, 'OUTCOME_NOT_YET_OBSERVABLE'):
            journal.observe_outcome(entry, self.outcome, observed_at='2026-10-12T14:59:59Z')
        observation = journal.observe_outcome(entry, self.outcome, observed_at='2026-10-12T15:05:00Z')
        row = journal.project_decision_outcomes(entry, outcomes=(observation,), observation_as_of='2026-10-12T16:00:00Z')
        self.assertEqual(row['outcome_status'], 'AVAILABLE')
        self.assertEqual(row['outcomes'][0]['outcome']['raw_return'], .02)
        self.assertEqual(row['outcomes'][0]['interpretation'], 'HYPOTHETICAL_MARKET_MOVEMENT')
        self.assertIsNone(row['realized_pnl'])
        self.assertEqual(entry.to_dict()['evidence_snapshot']['market']['price_at_as_of'], 100.0)

    def test_late_outcome_is_withheld_from_earlier_daily_cutoff(self):
        entry = self.capture()
        late = journal.observe_outcome(entry, self.outcome, observed_at='2026-10-13T12:00:00Z')
        early = journal.project_decision_outcomes(entry, outcomes=(late,), observation_as_of='2026-10-12T23:00:00Z')
        self.assertEqual(early['outcome_status'], 'UNAVAILABLE')
        self.assertEqual(early['outcomes'], [])
        self.assertNotIn('EVOUT-1', str(early))
        later = journal.project_decision_outcomes(entry, outcomes=(late,), observation_as_of='2026-10-13T12:00:00Z')
        self.assertEqual(later['outcome_status'], 'AVAILABLE')

    def test_missing_outcome_quality_is_not_reported_as_complete(self):
        missing = replace(self.outcome, quality=OutcomeQuality.INSUFFICIENT_MARKET_DATA,
            start_price=None, end_price=None, raw_return=None, normalized_directional_return=None)
        observation = journal.observe_outcome(self.capture(), missing, observed_at='2026-10-12T16:00:00Z')
        row = journal.project_decision_outcomes(self.capture(), outcomes=(observation,), observation_as_of='2026-10-12T16:00:00Z')
        self.assertEqual(row['outcome_status'], 'INCOMPLETE')
        self.assertIsNone(row['outcomes'][0]['outcome']['raw_return'])

    def test_daily_journal_uses_utc_day_and_filters_future_decisions(self):
        entry = self.capture()
        future_source = replace(self.source, as_of='2026-10-13T00:00:00Z')
        future_decision = replace(self.decision, as_of=future_source.as_of, decision_id='EVDEC-2')
        future = journal.capture_decision_snapshot(decision=future_decision, evidence_snapshot=future_source)
        daily = journal.build_daily_journal((future, entry), day='2026-10-12', timezone='UTC', observation_as_of='2026-10-12T16:00:00Z')
        self.assertEqual([r['decision_id'] for r in daily['items']], ['EVDEC-1'])
        self.assertEqual(daily['day_basis'], 'UTC')

    def test_action_receipt_keeps_no_action_proposal_and_paper_separate(self):
        candidate = {'current_market_evidence': [], 'reference_evidence': [], 'blocked': []}
        receipt = {'schema_version': 'action-decision/1.0.0', 'decision_id': 'AD-1', 'instrument_id': 'SIM:AAA',
            'decision_time': self.source.as_of, 'action_state': 'NO_ACTION', 'model_proposal': {'proposal_state': 'NO_ACTION'},
            'evidence_snapshot_id': 'AS-1', 'evidence_snapshot': {'cutoff': self.source.as_of, 'evidence': candidate},
            'opportunity_id': None, 'decision_trace_id': 'TRACE-1'}
        entry = journal.capture_decision_snapshot(decision=receipt, mode='PAPER')
        receipt['evidence_snapshot']['evidence']['blocked'].append('MUTATION')
        row = journal.project_decision_outcomes(entry, observation_as_of='2026-10-12T16:00:00Z')
        self.assertEqual(row['action']['action_state'], 'NO_ACTION')
        self.assertEqual(row['mode'], 'PAPER')
        self.assertEqual(row['evidence_snapshot']['evidence']['blocked'], [])
        self.assertIsNone(row['realized_pnl'])
        self.assertEqual(row['source_refs']['decision_trace_id'], 'TRACE-1')

    def test_explicit_reject_and_defer_reviews_stay_observations(self):
        self.assertTrue(callable(getattr(journal, 'observe_review', None)), 'Review projection adapter is missing')
        entry = self.capture()
        for decision, mode in (('REJECT', TradeReviewMode.REJECTED_OPPORTUNITY), ('DEFER', TradeReviewMode.WATCHED_OPPORTUNITY)):
            review = TradeReviewV1('REVIEW-'+decision, 'intelligence/trade_review/1.0.0', mode, decision,
                ns(self.source.as_of), ns('2026-10-12T15:00:00Z'))
            observation = journal.observe_review(entry, review)
            row = journal.project_decision_outcomes(entry, reviews=(observation,), observation_as_of='2026-10-12T16:00:00Z')
            self.assertEqual(row['reviews'][0]['decision'], decision)
            self.assertEqual(row['reviews'][0]['review_mode'], mode.value)
            self.assertIsNone(row['action']['operator_action'])
            self.assertIsNone(row['realized_pnl'])

    def test_review_pnl_claim_without_fills_cannot_become_journal_pnl(self):
        self.assertTrue(callable(getattr(journal, 'observe_review', None)), 'Review projection adapter is missing')
        entry = self.capture(mode='PAPER')
        review = TradeReviewV1('REVIEW-1', 'intelligence/trade_review/1.0.0', TradeReviewMode.PAPER_TRADE,
            'ENTER', ns(self.source.as_of), ns('2026-10-12T15:00:00Z'),
            execution_attribution=TradeExecutionAttribution(realized_pnl_minor=999))
        observation = journal.observe_review(entry, review)
        row = journal.project_decision_outcomes(entry, reviews=(observation,), observation_as_of='2026-10-12T16:00:00Z')
        self.assertIsNone(row['realized_pnl'])
        self.assertNotIn('realized_pnl_minor', row['reviews'][0])
        live = replace(review, review_mode=TradeReviewMode.LIVE_TRADE)
        with self.assertRaisesRegex(ValueError, 'REVIEW_MODE_MISMATCH'):
            journal.observe_review(entry, live)

    def test_daily_journal_rejects_same_decision_rewritten_with_new_facts(self):
        original = self.capture()
        changed = replace(self.source, market=replace(self.source.market, price_at_as_of=999))
        rewritten = journal.capture_decision_snapshot(decision=self.decision, evidence_snapshot=changed)
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE_DECISION_COLLISION'):
            journal.build_daily_journal((original, rewritten), day='2026-10-12', observation_as_of='2026-10-12T16:00:00Z')

    def test_late_operator_review_is_withheld_from_prior_cutoff(self):
        self.assertTrue(callable(getattr(journal, 'observe_review', None)), 'Review projection adapter is missing')
        entry = self.capture()
        review = TradeReviewV1('REVIEW-LATE', 'intelligence/trade_review/1.0.0', TradeReviewMode.WATCHED_OPPORTUNITY,
            'DEFER', ns(self.source.as_of), ns('2026-10-13T12:00:00Z'))
        observation = journal.observe_review(entry, review)
        daily = journal.build_daily_journal((entry,), day='2026-10-12', reviews=(observation,), observation_as_of='2026-10-12T16:00:00Z')
        self.assertEqual(daily['items'][0]['reviews'], [])

    def test_missing_publication_is_retained_as_unknown(self):
        unknown = replace(self.source, deterministic=replace(self.source.deterministic, publication_times=('',)))
        captured = journal.capture_decision_snapshot(decision=self.decision, evidence_snapshot=unknown).to_dict()
        self.assertEqual(captured['evidence_snapshot']['deterministic']['publication_times'], [''])
        self.assertIn('NEWS_PUBLICATION_TIME_UNKNOWN', captured['missing_information'])

    def test_market_day_groups_midnight_utc_under_prior_new_york_day(self):
        source = replace(self.source, as_of='2026-10-13T00:00:00Z')
        entry = journal.capture_decision_snapshot(decision=replace(self.decision, as_of=source.as_of), evidence_snapshot=source)
        daily = journal.build_daily_journal((entry,), day='2026-10-12', observation_as_of='2026-10-13T02:00:00Z')
        self.assertEqual(daily['day_basis'], 'America/New_York')
        self.assertEqual(len(daily['items']), 1)

    def test_market_day_handles_both_instances_of_dst_fall_back_hour(self):
        entries = []
        for i, clock in enumerate(('2026-11-01T05:30:00Z', '2026-11-01T06:30:00Z')):
            source = replace(self.source, as_of=clock)
            entries.append(journal.capture_decision_snapshot(decision=replace(self.decision, as_of=clock, decision_id='DST-'+str(i)), evidence_snapshot=source))
        daily = journal.build_daily_journal(entries, day='2026-11-01', observation_as_of='2026-11-01T08:00:00Z')
        self.assertEqual([r['decision_id'] for r in daily['items']], ['DST-0', 'DST-1'])

    def action_receipt(self):
        snapshot = {'cutoff': self.source.as_of, 'candidate_run_id': 'RUN-1',
            'evidence': {'instrument': {'instrument_id': 'SIM:AAA'},
                'current_market_evidence': [], 'reference_evidence': [], 'blocked': []},
            'selection': {'instrument_id': 'SIM:AAA'}}
        return {'schema_version': 'action-decision/1.0.0', 'decision_id': 'AD-1', 'instrument_id': 'SIM:AAA',
            'decision_time': self.source.as_of, 'action_state': 'NO_ACTION',
            'evidence_snapshot_id': 'AS-'+input_hash_from_dict(snapshot), 'evidence_snapshot': snapshot}

    def test_explicit_snapshot_cannot_replace_embedded_action_receipt_evidence(self):
        receipt = self.action_receipt()
        override = dict(receipt['evidence_snapshot'], evidence={
            'instrument': {'instrument_id': 'SIM:AAA'}, 'reference_evidence': [], 'blocked': [],
            'current_market_evidence': [{'evidence_id': 'WRONG-EVIDENCE', 'capability': 'QUOTE',
                'as_of': self.source.as_of, 'facts': {'price': 999}}]})
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_IDENTITY_MISMATCH'):
            journal.capture_decision_snapshot(decision=receipt, evidence_snapshot=override, mode='PAPER')
        equivalent = journal.capture_decision_snapshot(decision=receipt, evidence_snapshot=receipt['evidence_snapshot'], mode='PAPER')
        self.assertEqual(equivalent.to_dict()['source_decision']['evidence_snapshot'], equivalent.to_dict()['evidence_snapshot'])

    def test_detached_action_snapshot_requires_existing_snapshot_digest(self):
        receipt = self.action_receipt()
        snapshot = receipt.pop('evidence_snapshot')
        captured = journal.capture_decision_snapshot(decision=receipt, evidence_snapshot=snapshot, mode='PAPER')
        self.assertEqual(captured.to_dict()['source_refs']['evidence_snapshot_id'], receipt['evidence_snapshot_id'])
        receipt['evidence_snapshot_id'] = 'AS-WRONG'
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_IDENTITY_MISMATCH'):
            journal.capture_decision_snapshot(decision=receipt, evidence_snapshot=snapshot, mode='PAPER')

    def test_detached_action_snapshot_rejects_wrong_instrument_even_with_valid_digest(self):
        receipt = self.action_receipt()
        snapshot = receipt.pop('evidence_snapshot')
        snapshot['evidence']['instrument']['instrument_id'] = 'SIM:WRONG'
        receipt['evidence_snapshot_id'] = 'AS-'+input_hash_from_dict(snapshot)
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_IDENTITY_MISMATCH'):
            journal.capture_decision_snapshot(decision=receipt, evidence_snapshot=snapshot, mode='PAPER')

    def test_action_snapshot_rejects_wrong_selection_instrument(self):
        receipt = self.action_receipt()
        receipt['evidence_snapshot']['selection']['instrument_id'] = 'SIM:WRONG'
        with self.assertRaisesRegex(ValueError, 'SNAPSHOT_IDENTITY_MISMATCH'):
            journal.capture_decision_snapshot(decision=receipt, mode='PAPER')


if __name__ == '__main__':
    unittest.main()

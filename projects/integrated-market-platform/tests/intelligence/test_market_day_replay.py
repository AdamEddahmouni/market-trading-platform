"""Selected-day replay must isolate late receipt and future evaluation."""
from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from market_platform_foundation.intelligence.news_strategy_evaluation import replay
from market_platform_foundation.intelligence.news_strategy_evaluation.features import build_feature_snapshot
from market_platform_foundation.intelligence.news_strategy_evaluation.fixture_loader import load_fixture_pack
from market_platform_foundation.intelligence.news_strategy_evaluation.market_data import FixtureMarketDataProvider
from market_platform_foundation.intelligence.news_strategy_evaluation.outcomes import measure_outcome
from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import OutcomeHorizon


class MarketDayReplayTests(unittest.TestCase):
    def test_existing_harness_exposes_selected_day_clock(self):
        self.assertTrue(hasattr(replay.EvaluationReplayHarness, 'snapshot_at'))

    def test_late_bar_is_not_decision_input(self):
        payload = {'market_bars': {'ES': [
            dict(event_time='2026-09-09T12:00:00Z', open=100, high=100, low=100, close=100,
                 received_time='2026-09-09T12:00:01Z'),
            dict(event_time='2026-09-09T12:01:00Z', open=999, high=999, low=999, close=999,
                 received_time='2026-09-09T14:00:00Z'),
            dict(event_time='2026-09-09T12:02:00Z', open=101, high=101, low=101, close=101,
                 received_time='2026-09-09T12:02:01Z')]}}
        provider = FixtureMarketDataProvider.from_fixture_payload(payload)
        self.assertEqual(provider.price_at_as_of('ES', '2026-09-09T12:01:30Z')[0], 100)
        snapshot = build_feature_snapshot(as_of='2026-09-09T12:02:30Z', instrument_id='ES',
            asset_class='FUTURES', events=[], market_provider=provider)
        self.assertAlmostEqual(snapshot.market.return_1_bar, 0.01)

    def test_bar_receipt_and_provenance_are_preserved(self):
        row = dict(event_time='2026-09-09T12:00:00Z', open=100, high=100, low=100, close=100,
                   received_time='2026-09-09T12:01:00Z', provider_id='fixture', revision_id='v2')
        bar = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {'ES': [row]}}).get_series('ES').bars[0]
        self.assertEqual(bar.to_dict()['received_time'], row['received_time'])
        self.assertEqual(bar.to_dict()['revision_id'], 'v2')

    def test_invalid_receipt_is_unavailable(self):
        row = dict(event_time='2026-09-09T12:00:00Z', open=100, high=100, low=100, close=100,
                   received_time='unknown')
        provider = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {'ES': [row]}})
        self.assertIsNone(provider.price_at_as_of('ES', '2026-09-09T13:00:00Z')[0])
        row['received_time'] = '2026-09-09T12:00:00'
        provider = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {'ES': [row]}})
        self.assertIsNone(provider.price_at_as_of('ES', '2026-09-09T13:00:00Z')[0])

    def test_day_view_uses_same_snapshot_for_policies_and_no_future_outcomes(self):
        pack = load_fixture_pack()
        clock = pack.samples[0].as_of
        view = replay.EvaluationReplayHarness().snapshot_at(replay_date='2026-09-09', as_of=clock, pack=pack)
        self.assertTrue(view['simulation_only'])
        self.assertFalse(view['execution_authority'])
        self.assertTrue(view['decisions'])
        for row in view['decisions']:
            self.assertEqual(len({d['feature_snapshot_id'] for d in row['policy_decisions']}), 1)
            self.assertEqual(len(row['policy_decisions']), 3)
            self.assertNotIn('outcomes', row)
        self.assertIn('LEGACY_MARKET_RECEIPT_TIME_UNKNOWN', view['limitations'])

    def test_snapshot_is_deterministic_and_does_not_mutate_input(self):
        pack = load_fixture_pack()
        before = copy.deepcopy(pack.raw_payload)
        harness = replay.EvaluationReplayHarness()
        kwargs = dict(replay_date='2026-09-09', as_of=pack.samples[0].as_of, pack=pack)
        self.assertEqual(harness.snapshot_at(**kwargs), harness.snapshot_at(**kwargs))
        self.assertEqual(pack.raw_payload, before)

    def test_wrong_selected_day_and_naive_clock_rejected(self):
        harness = replay.EvaluationReplayHarness()
        for day, clock in [('2026-09-10', '2026-09-09T14:00:00Z'),
                           ('2026-09-09', '2026-09-09T14:00:00')]:
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                harness.snapshot_at(replay_date=day, as_of=clock)

    def test_later_news_and_inference_withheld(self):
        pack = load_fixture_pack()
        sample = next(s for s in pack.samples if s.events and s.inference_record)
        later = replace(sample.events[0], retrieved_time='2026-09-10T00:00:00Z')
        sample = replace(sample, events=sample.events + (later,),
                         inference_record=replace(sample.inference_record,
                            result=replace(sample.inference_record.result, completed_time='2026-09-10T00:00:00Z')))
        pack = replace(pack, samples=(sample,))
        view = replay.EvaluationReplayHarness().snapshot_at(replay_date='2026-09-09', as_of=sample.as_of, pack=pack)
        self.assertEqual(view['coverage']['withheld_news'], 1)
        self.assertEqual(view['coverage']['withheld_inference'], 1)
        self.assertIsNone(view['decisions'][0]['snapshot']['intelligence'])

    def test_future_sample_excluded_from_clock(self):
        pack = load_fixture_pack()
        first = min(pack.samples, key=lambda s: s.as_of)
        view = replay.EvaluationReplayHarness().snapshot_at(replay_date='2026-09-09', as_of=first.as_of, pack=pack)
        self.assertTrue(all(row['as_of'] <= first.as_of for row in view['decisions']))

    def test_output_with_unmatched_input_lineage_is_withheld(self):
        pack = load_fixture_pack()
        sample = next(s for s in pack.samples if s.events and s.inference_record)
        sample = replace(sample, inference_record=replace(sample.inference_record,
            result=replace(sample.inference_record.result, source_event_ids=('future-unseen-source',))))
        view = replay.EvaluationReplayHarness().snapshot_at(replay_date='2026-09-09', as_of=sample.as_of,
                                                           pack=replace(pack, samples=(sample,)))
        self.assertEqual(view['coverage']['withheld_inference'], 1)
        self.assertIsNone(view['decisions'][0]['snapshot']['intelligence'])

    def test_valid_output_lineage_is_used_but_naive_output_clock_is_withheld(self):
        from market_platform_foundation.intelligence.inference.contracts import ArticleInputRef
        pack = load_fixture_pack()
        sample = next(s for s in pack.samples if s.events and s.inference_record)
        packet = replace(sample.inference_record.input_packet, articles=tuple(
            ArticleInputRef(e.event_id, e.source_id, e.provider_id, e.published_time,
                            e.retrieved_time, e.headline, e.summary, (sample.instrument_id,)) for e in sample.events))
        result = replace(sample.inference_record.result, source_event_ids=tuple(e.event_id for e in sample.events))
        sample = replace(sample, inference_record=replace(sample.inference_record, input_packet=packet, result=result))
        harness = replay.EvaluationReplayHarness()
        view = harness.snapshot_at(replay_date='2026-09-09', as_of=sample.as_of, pack=replace(pack, samples=(sample,)))
        self.assertIsNotNone(view['decisions'][0]['snapshot']['intelligence'])
        sample = replace(sample, inference_record=replace(sample.inference_record,
            result=replace(result, completed_time=result.completed_time.rstrip('Z'))))
        view = harness.snapshot_at(replay_date='2026-09-09', as_of=sample.as_of, pack=replace(pack, samples=(sample,)))
        self.assertEqual(view['coverage']['withheld_inference'], 1)

    def test_truncated_horizon_is_not_complete(self):
        from market_platform_foundation.intelligence.news_strategy_evaluation.evaluator import NewsStrategyEvaluator
        report = NewsStrategyEvaluator().evaluate_fixture_pack()
        decision = next(s.baseline_decision for s in report.sample_results if s.baseline_decision)
        row = dict(event_time=decision.as_of, open=100, high=100, low=100, close=100)
        from datetime import datetime, timedelta
        later = (datetime.fromisoformat(decision.as_of.replace('Z', '+00:00')) + timedelta(minutes=1)).isoformat()
        provider = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {decision.instrument_id:
            [row, {**row, 'event_time': later}]}})
        outcome = measure_outcome(decision=decision, horizon=OutcomeHorizon('5m', 300, 'five minutes'),
                                  market_provider=provider, flat_threshold_bps=5)
        self.assertEqual(outcome.quality.value, 'PARTIAL_HORIZON')

    def test_market_correction_order_cannot_choose_older_revision(self):
        row = dict(event_time='2026-09-09T12:00:00Z', open=100, high=100, low=100, close=100)
        provider = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {'ES': [
            {**row, 'close': 102, 'received_time': '2026-09-09T12:05:00Z'},
            {**row, 'received_time': '2026-09-09T12:00:01Z'}]}})
        self.assertEqual(provider.price_at_as_of('ES', '2026-09-09T12:06:00Z')[0], 102)

    def test_equivalent_timestamp_revision_is_one_bar(self):
        row = dict(event_time='2026-09-09T12:00:00Z', open=100, high=100, low=100, close=100,
                   received_time='2026-09-09T12:00:01Z')
        provider = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {'ES': [row,
            {**row, 'event_time': '2026-09-09T12:00:00+00:00', 'close': 102,
             'received_time': '2026-09-09T12:00:02Z'}]}})
        snapshot = build_feature_snapshot(as_of='2026-09-09T12:01:00Z', instrument_id='ES',
            asset_class='FUTURES', events=[], market_provider=provider)
        self.assertIsNone(snapshot.market.return_1_bar)
        self.assertEqual(snapshot.market.price_at_as_of, 102)

    def test_late_horizon_bar_uses_measurement_clock_without_revising_start(self):
        from market_platform_foundation.intelligence.news_strategy_evaluation.evaluator import NewsStrategyEvaluator
        from datetime import datetime, timedelta
        decision = next(s.baseline_decision for s in NewsStrategyEvaluator().evaluate_fixture_pack().sample_results if s.baseline_decision)
        start = datetime.fromisoformat(decision.as_of.replace('Z', '+00:00'))
        horizon_end = (start + timedelta(minutes=5)).isoformat()
        receipt = (start + timedelta(minutes=5, seconds=1)).isoformat()
        measurement = (start + timedelta(minutes=10)).isoformat()
        row = dict(event_time=decision.as_of, open=100, high=100, low=100, close=100)
        provider = FixtureMarketDataProvider.from_fixture_payload({'market_bars': {decision.instrument_id: [
            row, {**row, 'event_time': horizon_end, 'received_time': receipt, 'close': 110, 'high': 112},
            {**row, 'received_time': measurement, 'close': 999}]}})
        outcome = measure_outcome(decision=decision, horizon=OutcomeHorizon('5m', 300, 'five minutes'),
            market_provider=provider, flat_threshold_bps=5, observation_as_of=measurement)
        self.assertEqual(outcome.quality.value, 'COMPLETE')
        self.assertEqual(outcome.start_price, 100)
        self.assertEqual(outcome.end_price, 110)
        self.assertAlmostEqual(outcome.raw_return, .1)
        self.assertEqual(outcome.to_dict()['measured_as_of'], measurement)


if __name__ == '__main__':
    unittest.main()

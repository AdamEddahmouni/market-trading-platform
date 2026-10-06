"""OCT1-08 replay comparison: matched risk, point-in-time safety, reproducibility, honest conclusions."""
import copy
import json
import unittest
from pathlib import Path

from market_platform_foundation.research.sma_stop_evaluation import (
    CONCLUSIONS, CORPUS_REL, DEFINITION_REL, METHODS, conclude, corpus_bars, definition_hash, evaluate, frozen_definition,
    load_corpus, read_receipt, sessions_of, simulate_episode,
)
from market_platform_foundation.risk.sma_trailing_stop import build_policy

ROOT = Path(__file__).resolve().parents[2]
DAY_NS = 1789047000000000000  # 2026-09-10 09:30 ET, the first bar of the pinned corpus
MINUTE = 60_000_000_000


def bar(index, close, *, low=None, high=None, open_=None, day=0):
    open_ = close if open_ is None else open_
    start = DAY_NS + day * 24 * 60 * MINUTE + index * MINUTE
    return dict(bar_id=f'D{day}B{index}', event_time=start, available_time=start + MINUTE, open=open_,
                high=max(high or close, open_, close), low=min(low or close, open_, close), close=close)


def definition(window=2, spacing=30, after=3):
    value = copy.deepcopy(frozen_definition())
    policy = build_policy(sma_window_bars=window)
    value['policy'].update(policy_id=policy['policy_id'], sma_window_bars=window)
    value['entry_rule'].update(first_signal_bar_index=window - 1, signal_spacing_bars=spacing, minimum_bars_after_entry=after)
    return value


def episode(bars, side='LONG', signal=1, window=2):
    return simulate_episode(bars, signal, side, build_policy(sma_window_bars=window), day='2026-09-10', cost_bps=5.0)


class FrozenDefinitionTests(unittest.TestCase):
    def test_committed_definition_is_the_code_definition(self):
        committed = json.loads((ROOT / DEFINITION_REL).read_text(encoding='utf-8'))
        self.assertEqual(committed, json.loads(json.dumps(frozen_definition())))
        self.assertEqual((committed['status'], committed['no_parameter_search'], committed['calibration_status']),
                         ('FROZEN_BEFORE_RESULTS', True, 'NOT_CALIBRATED'))
        self.assertEqual((committed['policy']['sma_window_bars'], committed['policy']['bar_interval'], committed['policy']['config_label']),
                         (20, '1m', 'REFERENCE_TEST_CONFIG'))
        self.assertEqual(set(committed['methods']), set(METHODS))
        self.assertEqual(definition_hash(committed), definition_hash())

    def test_no_superiority_token_exists(self):
        for token in CONCLUSIONS:
            for word in ('BEST', 'SUPERIOR', 'BETTER', 'OUTPERFORM', 'WINS', 'PROFIT'):
                self.assertNotIn(word, token)
        rule = frozen_definition()['conclusion_rule']
        favourable = [dict(pattern='SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF')] * 3
        small = conclude(favourable, sessions=5, instruments=1, rule=rule)
        self.assertEqual((small['conclusion'], small['superiority_claim'], small['in_sample_pattern_status']),
                         ('INSUFFICIENT_EVIDENCE', 'NONE', 'DESCRIPTION_ONLY_NOT_A_CLAIM'))
        large = conclude(favourable, sessions=40, instruments=5, rule=rule)
        self.assertEqual((large['conclusion'], large['superiority_claim']), ('SMA_REDUCED_DOWNSIDE_WITH_RETURN_TRADEOFF', 'NONE'))
        mixed = conclude([dict(pattern='NO_CLEAR_DIFFERENCE'), dict(pattern='SMA_UNDERPERFORMED_REFERENCE')], sessions=40, instruments=5, rule=rule)
        self.assertEqual(mixed['conclusion'], 'NO_CLEAR_DIFFERENCE')


class EpisodeTests(unittest.TestCase):
    def test_baselines_start_with_the_same_initial_risk(self):
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10100, open_=10100), bar(3, 10100), bar(4, 10100)]
        result = episode(bars)
        self.assertEqual((result['entry_reference_price'], result['initial_stop'], result['initial_risk_distance']), (10100, 10000, 100))
        # A drop to exactly the matched level on the entry bar stops all three stop methods at the same level.
        dropped = episode([*bars[:2], bar(2, 10100, open_=10100, low=10000), bar(3, 10050), bar(4, 10050)])
        for method in ('SMA_TRAIL', 'RAW_PRICE_TRAIL', 'FIXED_INITIAL_STOP'):
            self.assertEqual((dropped['methods'][method]['triggered'], dropped['methods'][method]['stop_at_trigger']), (True, 10000), method)
        self.assertFalse(dropped['methods']['NO_TRAIL']['triggered'])
        short = episode([bar(0, 10000), bar(1, 10000), bar(2, 9900, open_=9900, high=10000), bar(3, 9950), bar(4, 9950)], side='SHORT')
        self.assertEqual(short['initial_risk_distance'], 100)
        self.assertTrue(all(short['methods'][m]['stop_at_trigger'] == 10000 for m in ('SMA_TRAIL', 'RAW_PRICE_TRAIL', 'FIXED_INITIAL_STOP')))

    def test_unprotective_initial_stop_is_excluded_and_counted(self):
        result = episode([bar(0, 10000), bar(1, 10000), bar(2, 9900, open_=9900), bar(3, 9900), bar(4, 9900)])
        self.assertEqual((result['evaluable'], result['exclusion']), (False, 'INITIAL_STOP_NOT_PROTECTIVE'))

    def test_raw_trail_cannot_use_a_bar_to_stop_out_that_same_bar(self):
        # Bar 3 closes far higher (raising the raw stop to 104.00) but traded down to 102.00 first.
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10100, open_=10100), bar(3, 10500, low=10200), bar(4, 10500, low=10450), bar(5, 10500, low=10390)]
        result = episode(bars)['methods']['RAW_PRICE_TRAIL']
        self.assertEqual((result['triggered'], result['exit_bar_id'], result['stop_at_trigger']), (True, 'D0B5', 10400))

    def test_sma_trail_cannot_use_a_bar_to_stop_out_that_same_bar(self):
        # Bar 3's close lifts the SMA stop to 103.00; bar 3 itself traded at 100.60, above the 100.50 stop then in force.
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10100, open_=10100), bar(3, 10500, low=10060), bar(4, 10500), bar(5, 10500, low=10290)]
        result = episode(bars)
        self.assertEqual((result['methods']['SMA_TRAIL']['exit_bar_id'], result['methods']['SMA_TRAIL']['stop_at_trigger']), ('D0B5', 10500))
        self.assertEqual([u['stop'] for u in result['stop_updates']], [10050, 10300, 10500])

    def test_gap_through_stop_fills_at_the_bar_extreme_not_the_stop(self):
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10100, open_=10100), bar(3, 9650, open_=9700, low=9600), bar(4, 9650)]
        result = episode(bars)['methods']['FIXED_INITIAL_STOP']
        self.assertEqual((result['triggered'], result['gap_through_stop'], result['stop_at_trigger'], result['exit_price']), (True, True, 10000, 9600))
        self.assertEqual((result['gross_return_bps'], result['net_return_bps'], result['alternate_fill_gross_return_bps'], result['exit_bar_range_order']),
                         (-495.05, -505.05, -396.04, 'UNKNOWN'))

    def test_no_trail_exits_at_the_horizon_and_untriggered_stops_are_kept(self):
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10100, open_=10100), bar(3, 10200), bar(4, 10300)]
        result = episode(bars)['methods']
        self.assertEqual((result['NO_TRAIL']['exit_price'], result['NO_TRAIL']['gross_return_bps'], result['NO_TRAIL']['holding_bars']), (10300, 198.02, 3))
        self.assertEqual((result['FIXED_INITIAL_STOP']['triggered'], result['FIXED_INITIAL_STOP']['vs_no_trail_bps']), (False, 0.0))

    def test_downside_and_opportunity_cost_are_both_reported(self):
        bars = [bar(0, 10000), bar(1, 10000), bar(2, 10100, open_=10100), bar(3, 9990, low=9950), bar(4, 9900, low=9800), bar(5, 10400)]
        result = episode(bars)['methods']
        stopped, held = result['FIXED_INITIAL_STOP'], result['NO_TRAIL']
        self.assertLess(stopped['mae_bps'], held['mae_bps'])               # the stop cut the adverse excursion
        self.assertLess(stopped['gross_return_bps'], held['gross_return_bps'])  # and missed the recovery
        self.assertTrue(stopped['premature_exit'])
        self.assertEqual((stopped['bars_after_invalidation'], held['bars_after_invalidation']), (0, 2))


class EvaluationTests(unittest.TestCase):
    def sessions(self, days=2, length=40):
        result = {}
        for day in range(days):
            closes = [10000 + ((i * 37 + day * 11) % 23) * 10 - (i % 5) * 15 for i in range(length)]
            result[f'2026-09-{10 + day}'] = [bar(i, c, low=c - 20, high=c + 20, day=day) for i, c in enumerate(closes)]
        return result

    def test_same_inputs_give_the_same_path_and_hash(self):
        first = evaluate(self.sessions(), definition(spacing=5))
        second = evaluate(copy.deepcopy(self.sessions()), definition(spacing=5))
        self.assertEqual(first, second)
        self.assertEqual((first['result_status'], first['calibration_status'], first['evidence_class']), ('REPLAY_EVALUATED', 'NOT_CALIBRATED', 'HISTORICAL_REPLAY'))
        changed = self.sessions()
        changed['2026-09-10'][5] = dict(changed['2026-09-10'][5], close=changed['2026-09-10'][5]['close'] + 1)
        other = evaluate(changed, definition(spacing=5))
        self.assertNotEqual((other['input_hash'], other['result_hash']), (first['input_hash'], first['result_hash']))
        self.assertNotEqual(evaluate(self.sessions(), definition(window=3, spacing=5))['definition_hash'], first['definition_hash'])

    def test_every_episode_is_reported_including_excluded_and_untriggered(self):
        result = evaluate(self.sessions(), definition(spacing=5))
        counts = result['counts']
        self.assertEqual(counts['episodes'], len(result['episodes']))
        self.assertEqual(counts['evaluable'] + counts['excluded'], counts['episodes'])
        self.assertEqual(sum(counts['exclusions'].values()), counts['excluded'])
        self.assertEqual(set(result['aggregates']), {'LONG', 'SHORT'})
        for side in ('LONG', 'SHORT'):
            self.assertEqual({a['episodes'] for a in result['aggregates'][side].values()}, {counts['evaluable_by_side'][side]})
        self.assertEqual([c['alternative'] for c in result['comparisons']], list(METHODS[1:]))
        self.assertEqual((result['conclusion']['conclusion'], result['conclusion']['superiority_claim']), ('INSUFFICIENT_EVIDENCE', 'NONE'))

    def test_a_policy_other_than_the_frozen_one_is_refused(self):
        tampered = definition()
        tampered['policy']['sma_window_bars'] = 9
        with self.assertRaisesRegex(ValueError, 'POLICY_IDENTITY_MISMATCH'):
            evaluate(self.sessions(), tampered)

    def test_pinned_corpus_loads_point_in_time_and_is_not_modified(self):
        before = (ROOT / CORPUS_REL / 'normalized' / 'AAPL_normalized.json').read_bytes()
        corpus = load_corpus(ROOT)
        sessions = sessions_of(corpus_bars(corpus['rows']))
        self.assertEqual((corpus['provenance']['corpus_evidence_authority'], corpus['provenance']['row_count'], list(sessions)),
                         ('HISTORICAL_DEVELOPMENT', 1950, corpus['provenance']['session_dates']))
        self.assertEqual({len(bars) for bars in sessions.values()}, {390})
        for bars in sessions.values():
            self.assertTrue(all(b['available_time'] - b['event_time'] == MINUTE for b in bars))
            self.assertEqual([b['event_time'] for b in bars], sorted(b['event_time'] for b in bars))
        self.assertEqual((ROOT / CORPUS_REL / 'normalized' / 'AAPL_normalized.json').read_bytes(), before)

    def test_receipt_projection_is_bounded(self):
        receipt = read_receipt(ROOT, episode_limit=100000)
        if receipt['result_status'] == 'NOT_EXECUTED':
            self.assertEqual(receipt['reason_codes'], ['EVALUATION_RECEIPT_NOT_FOUND'])
            return
        self.assertLessEqual(len(receipt['episodes']), 20)
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload
        assert_no_secrets_in_payload(receipt)  # the API response guard must accept the projection
        self.assertEqual(receipt['provenance']['corpus_evidence_label'], 'HISTORICAL_DEVELOPMENT')
        self.assertEqual(receipt['definition_hash'], definition_hash())
        self.assertIn(receipt['conclusion']['conclusion'], CONCLUSIONS)
        self.assertEqual((receipt['conclusion']['superiority_claim'], receipt['corpus_unchanged']), ('NONE', True))


if __name__ == '__main__':
    unittest.main()

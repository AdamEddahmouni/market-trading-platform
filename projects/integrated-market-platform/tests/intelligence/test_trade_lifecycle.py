"""OCT1-10 pure lifecycle derivation: episode identity, decision placement and ordering."""
import unittest

from market_platform_foundation.intelligence.inference.trade_lifecycle import (
    LINEAGE_UNAVAILABLE, assign_decisions, entry_block, episodes_from_trades, exit_block, sort_timeline, stage_of,
)


def fill(sequence, effect, before, after, *, instrument='AAPL', decision=None, price=15000, quantity=None, realized=0):
    return dict(fill_id=f'F{sequence}', sequence=sequence, instrument_id=instrument, symbol=instrument, position_effect=effect,
                position_before=before, position_after=after, decision_id=decision, fill_price_minor=price,
                filled_quantity=quantity or abs(after - before), realized_pnl_delta_minor=realized, costs_minor=0,
                fill_time_ns=sequence * 1_000_000_000, submit_time_ns=sequence * 1_000_000_000 - 1, side='BUY' if after > before else 'SELL')


def decision(identifier, state, position, run='run-a'):
    return dict(decision_id=identifier, action_state=state, position=dict(state=position, quantity=0), run=run,
                decision_time='2026-10-06T14:00:00Z', valid_until='2026-10-06T14:10:00Z', execution_readiness='PREVIEW_ALLOWED')


def episodes(trades):
    return episodes_from_trades(trades, account_id='acct', experiment_id='PPE-1')


def two_trades():
    return [fill(1, 'OPEN', 0, 5, decision='D1'), fill(2, 'CLOSE', 5, 0, realized=500),
            fill(3, 'OPEN', 0, 3, decision='D2'), fill(4, 'OPEN', 0, 2, instrument='NVDA')]


class EpisodeTests(unittest.TestCase):
    def test_same_symbol_trades_are_separate_episodes_keyed_by_their_opening_fill(self):
        rows = episodes(two_trades())
        self.assertEqual([(e['instrument_id'], e['open'], e['opening_fill_id']) for e in rows],
                         [('AAPL', False, 'F1'), ('AAPL', True, 'F3'), ('NVDA', True, 'F4')])
        self.assertEqual(len({e['episode_id'] for e in rows}), 3)
        self.assertEqual([e['realized_pnl_minor'] for e in rows], [500, 0, 0])
        # Ledger sequence decides, not the order rows were handed over.
        self.assertEqual(rows, episodes(list(reversed(two_trades()))))

    def test_identity_changes_with_account_and_experiment(self):
        trades = [fill(1, 'OPEN', 0, 5)]
        self.assertNotEqual(episodes(trades)[0]['episode_id'],
                            episodes_from_trades(trades, account_id='other', experiment_id='PPE-1')[0]['episode_id'])
        self.assertNotEqual(episodes(trades)[0]['episode_id'],
                            episodes_from_trades(trades, account_id='acct', experiment_id='PPE-2')[0]['episode_id'])

    def test_scale_in_and_partial_exit_stay_in_one_open_episode(self):
        row, = episodes([fill(1, 'OPEN', 0, 4), fill(2, 'ADD', 4, 8), fill(3, 'REDUCE', 8, 5, realized=300)])
        self.assertTrue(row['open'])
        self.assertEqual(([f['fill_id'] for f in row['entry_fills']], [f['fill_id'] for f in row['exit_fills']]), (['F1', 'F2'], ['F3']))
        self.assertEqual((row['realized_pnl_minor'], row['closing_decision_id']), (300, None))
        self.assertEqual(exit_block([], row, [])['status'], 'PARTIALLY_CLOSED')

    def test_a_fill_without_an_opening_fill_has_no_invented_lineage(self):
        row, = episodes([fill(7, 'REDUCE', 5, 2, decision='D9')])
        self.assertEqual((row['opening_basis'], row['opening_decision_id']), (LINEAGE_UNAVAILABLE, None))

    def test_reversal_ends_one_episode_and_begins_another(self):
        first, second = episodes([fill(1, 'OPEN', 0, 5), fill(2, 'REVERSE', 5, -3, realized=200)])
        self.assertEqual((first['open'], first['realized_pnl_minor'], second['open'], second['side'], second['realized_pnl_minor']),
                         (False, 200, True, 'SHORT', 0))


class AssignmentTests(unittest.TestCase):
    def assign(self, chain, trades):
        return assign_decisions(chain, episodes(trades), lambda d: d['run'])

    def test_decisions_follow_fill_ids_and_the_predecessor_chain(self):
        chain = [decision('C1', 'CONSIDER_ENTRY', 'FLAT'), decision('D1', 'ENTER', 'FLAT'), decision('H1', 'HOLD', 'LONG'),
                 decision('X1', 'EXIT', 'LONG'), decision('N1', 'NO_ACTION', 'FLAT', 'run-b'), decision('D2', 'ENTER', 'FLAT', 'run-b'),
                 decision('H2', 'HOLD', 'LONG', 'run-c')]
        trades = [fill(1, 'OPEN', 0, 5, decision='D1'), fill(2, 'CLOSE', 5, 0, decision='X1'), fill(3, 'OPEN', 0, 3, decision='D2')]
        assigned, flat, unplaced = self.assign(chain, trades)
        first, second = episodes(trades)
        self.assertEqual([d['decision_id'] for d in assigned[first['episode_id']]], ['C1', 'D1', 'H1', 'X1'])
        self.assertEqual([d['decision_id'] for d in assigned[second['episode_id']]], ['N1', 'D2', 'H2'])
        self.assertEqual((flat, unplaced), ([], []))

    def test_flat_decisions_of_another_run_are_not_pulled_into_an_episode(self):
        chain = [decision('N0', 'NO_ACTION', 'FLAT', 'run-z'), decision('D1', 'ENTER', 'FLAT')]
        assigned, flat, _ = self.assign(chain, [fill(1, 'OPEN', 0, 5, decision='D1')])
        self.assertEqual([d['decision_id'] for d in next(iter(assigned.values()))], ['D1'])
        self.assertEqual([d['decision_id'] for d in flat], ['N0'])

    def test_positioned_decisions_are_not_guessed_onto_one_of_several_unlinked_episodes(self):
        chain = [decision('H1', 'HOLD', 'LONG')]
        assigned, _, unplaced = self.assign(chain, [fill(1, 'OPEN', 0, 5), fill(2, 'CLOSE', 5, 0), fill(3, 'OPEN', 0, 2)])
        self.assertEqual(([len(v) for v in assigned.values()], [d['decision_id'] for d in unplaced]), ([0, 0], ['H1']))
        only, _, none = self.assign(chain, [fill(1, 'OPEN', 0, 5)])
        self.assertEqual(([len(v) for v in only.values()], none), ([1], []))

    def test_enter_and_exit_decisions_are_never_fills(self):
        enter, leave = decision('D1', 'ENTER', 'FLAT'), decision('X1', 'EXIT', 'LONG')
        entry = entry_block([enter], None, [], now_ns=0)
        self.assertEqual((entry['status'], entry['fill'], entry['paper']), ('DECIDED_ENTER', None, 'NO_FILL'))
        self.assertEqual(stage_of([enter], None, entry, exit_block([enter], None, [])), 'ENTER_NOT_EXECUTED')
        row, = episodes([fill(1, 'OPEN', 0, 5, decision='D1')])
        leaving = exit_block([enter, leave], row, [])
        self.assertEqual((leaving['status'], leaving['fill'], leaving['paper_close']), ('EXIT_DECIDED', None, 'NOT_SUBMITTED'))
        self.assertEqual(stage_of([enter, leave], row, entry_block([enter, leave], row, [], now_ns=0), leaving), 'EXIT_NOT_EXECUTED')
        named = lambda label: dict(state='WORKING', decision_source_snapshot=dict(reasons=[dict(code='ACTION_DECISION', label=label)]))
        self.assertEqual(exit_block([enter, leave], row, [named('X1')])['status'], 'EXIT_SUBMITTED')
        self.assertEqual(entry_block([enter], None, [named('D1')], now_ns=0)['status'], 'SUBMITTED_PAPER')
        self.assertEqual(entry_block([enter], None, [], now_ns=10**19)['status'], 'EXPIRED')


class OrderingTests(unittest.TestCase):
    def test_order_is_event_time_then_causal_kind_and_ignores_input_order(self):
        rows = [dict(kind='PAPER_FILL', at='2026-10-06T14:00:02Z', sequence=9, ref=dict(id='f')),
                dict(kind='DECISION', at='2026-10-06T14:00:01Z', ref=dict(id='d')),
                dict(kind='STOP', at='2026-10-06T14:00:01Z', sequence=99, ref=dict(id='s')),
                dict(kind='PAPER_ORDER', at='2026-10-06T14:00:02Z', sequence=8, ref=dict(id='o')),
                dict(kind='CANDIDATE_SELECTED', at='2026-10-06T14:00:00Z', ref=dict(id='r')),
                dict(kind='DECISION', at=None, ref=dict(id='undated'))]
        expected = ['r', 's', 'd', 'o', 'f', 'undated']
        self.assertEqual([r['ref']['id'] for r in sort_timeline(rows)], expected)
        self.assertEqual([r['ref']['id'] for r in sort_timeline(list(reversed(rows)))], expected)


if __name__ == '__main__':
    unittest.main()

"""SOFTWARE_CONTROLLED: bounded exit-completion stress for capped crypto closes under the residual guard.

Prints, marks and clocks are fixtures; every fill is a simulated fill, never market truth. Each case drives
fresh sizing -> new intent -> print for at most MAX_ATTEMPTS attempts and checks the safety of every
transition. Completion is required only under the stated assumptions (a stable eventual price, per-print
liquidity and a legal capped partition according to an independent oracle); otherwise the expected
non-completion is classified and recorded, never treated as liquidation.
"""
import json
import unittest
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from market_platform_foundation.paper.execution import cancel_interactive_order, submit_interactive_order
from market_platform_foundation.risk.policy import build_risk_policy
from market_platform_foundation.ui_api.paper_market_evidence import PaperMarketEvidence
from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
from tests.trading_correctness import test_paper_crypto_shorts as short
from tests.trading_correctness import test_paper_crypto_residual_retry as retry

IID, S = short.IID, short.S
REASON = 'SIM_CRYPTO_CLOSE_RESIDUAL_BELOW_MINIMUM'
MAX_ATTEMPTS = 12
STEP = Decimal('0.001')
MIN_NOTIONAL = Decimal('0.5')
POLICY_SCALE = Decimal(100)  # short.book(): account minor units per dollar
DEEP = 100_000.0  # print size that never binds participation
ALLOWED = {'COMPLETED', 'EXPECTED_NON_COMPLETION', 'KNOWN_LIMIT_POST_FILL_DUST', 'NON_COMPLETION_LIQUIDITY_GUARD'}


def floor_step(value):
    return (value / STEP).to_integral_value(rounding=ROUND_FLOOR) * STEP


def ceil_step(value):
    return (value / STEP).to_integral_value(rounding=ROUND_CEILING) * STEP


def bounds(price, cap_minor, minimum_quantity=Decimal('0.001'), eligible=None):
    """Independent oracle: smallest venue-valid order and largest capped, liquidity-limited order."""
    price = Decimal(str(price))
    lo = ceil_step(max(Decimal(minimum_quantity), MIN_NOTIONAL / price))
    hi = floor_step(Decimal(cap_minor) / POLICY_SCALE / price) if cap_minor is not None else Decimal('1e9')
    if eligible is not None:
        hi = min(hi, floor_step(Decimal(eligible)))
    return lo, hi


def partitionable(quantity, lo, hi):
    """A position is closable at a fixed price iff it splits into orders each within [lo, hi]."""
    if quantity == 0:
        return True
    if hi < lo or quantity < lo:
        return False
    return (quantity / hi).to_integral_value(rounding=ROUND_CEILING) * lo <= quantity


def pieces(quantity, lo, hi):
    count = int((quantity / hi).to_integral_value(rounding=ROUND_CEILING))
    plan, extra = [lo] * count, quantity - lo * count
    assert extra >= 0, (quantity, lo, hi)
    for index in range(count):
        add = min(extra, hi - lo); plan[index] += add; extra -= add
    return plan


class StressBase(unittest.TestCase):
    """Fresh ledger per case with the fractional-short fixture economics: step/min 0.001, $0.50 minimum notional."""
    results = None

    @classmethod
    def setUpClass(cls):
        cls.results = []

    @classmethod
    def tearDownClass(cls):
        for row in cls.results:
            print('EXIT_STRESS_RESULT ' + json.dumps(row, sort_keys=True))

    def fresh(self, cap, *, minimum_quantity='0.001', minimum_notional='0.5', legacy=False):
        self.instrument = dict(short.nano(), minimum_quantity=minimum_quantity, quantity_step='0.001')
        if minimum_notional is None:
            self.instrument.pop('minimum_notional')
        else:
            self.instrument['minimum_notional'] = minimum_notional
        self.tape = short.Tape(100 * S); self.tape.ack(IID, 101 * S)
        self.t, self.n, self.last, self.cap = 110, 0, None, cap
        if legacy:
            self.book = short.PaperExecutionLedger.open_session(replay_session_id='stress-legacy', instrument_id='SEED',
                symbol='SEED', policy=build_risk_policy(), execution_mode='INTERNAL_SIMULATION',
                execution_authority='PAPER_ONLY', experiment_id='stress-legacy')
        else:
            self.book = short.book(crypto_max_order_notional_minor=cap, crypto_max_position_notional_minor=10_000_000)
        self.participation = Decimal(self.book.policy['participation_cap_numerator']) / Decimal(self.book.policy['participation_cap_denominator'])

    # -- fixture actions -------------------------------------------------------------------------------------
    def submit(self, quantity, side, price, volume=DEEP, *, fresh_print=True, key=None):
        self.n += 1; self.t += 10; t = self.t
        if fresh_print:
            self.tape.trade(IID, float(price), float(volume), received_ns=(t + 1) * S)
        bars = PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID, now_ns=(t + 5) * S)
        key = key or f'stress-{self.n}'
        self.last = dict(ledger=self.book, bars=bars, symbol=IID, instrument_id=IID, instrument=self.instrument,
                         quantity=str(quantity), side=side, observation_time=t * S, client_order_id=key, idempotency_key=key)
        return submit_interactive_order(**self.last)

    def mark(self, price):
        self.book.apply_live_mark(instrument_id=IID, mark_minor=int(Decimal(str(price)) * 1_000_000),
                                  mark_provider='FIXTURE', mark_as_of_ns=(self.t + 5) * S, mark_quality='CURRENT')

    def position(self):
        rows = self.book.project_positions()
        return Decimal(rows[0]['quantity']) if rows else Decimal(0)

    def open(self, quantity, *, is_short, price='1.0'):
        """Open through ordinary capped orders, splitting with the oracle when the cap binds."""
        quantity, price = Decimal(quantity), Decimal(price)
        lo, hi = bounds(price, self.cap, self.instrument['minimum_quantity']) if self.cap else (quantity, quantity)
        plan = pieces(quantity, lo, hi) if self.cap and quantity > hi else [quantity]
        for piece in plan:
            result = self.submit(piece, 'SELL' if is_short else 'BUY', price)
            self.assertEqual(result['order']['state'], 'FILLED', result['order'])
        self.assertEqual(self.position(), -quantity if is_short else quantity)

    # -- invariants ------------------------------------------------------------------------------------------
    def snapshot(self):
        simulator = getattr(self.book, '_bar_simulator', None)
        return dict(events=list(self.book.events), cash=self.book.project_account()['cash_minor'], position=self.position(),
                    allocations=dict(simulator._bar_allocations) if simulator is not None else {},
                    trades=len(self.book.project_trades()), policy=json.dumps(self.book.policy, sort_keys=True, default=str),
                    authority=(str(self.book.execution_mode), str(getattr(self.book, 'execution_authority', ''))))

    def check_transition(self, before, result, requested):
        """No reversal, append-only audit, frozen policy/authority, no mutation or capacity use without a fill."""
        after = self.snapshot()
        self.assertEqual(after['events'][:len(before['events'])], before['events'])
        self.assertEqual(after['policy'], before['policy'])
        self.assertEqual(after['authority'], before['authority'])
        old, new = before['position'], after['position']
        self.assertTrue(new == 0 or (new > 0) == (old > 0), ('reversal', old, new))
        fill = None if result is None else result.get('fill')
        if fill is None:
            self.assertEqual((after['cash'], new, after['allocations'], after['trades']),
                             (before['cash'], old, before['allocations'], before['trades']))
            return Decimal(0)
        quantity = Decimal(fill['fill_quantity'])
        self.assertTrue(0 < quantity <= Decimal(requested), (quantity, requested))
        self.assertEqual(abs(old) - abs(new), quantity)
        self.assertEqual(after['trades'], before['trades'] + 1)
        key = (IID, int(fill['fill_time']))
        self.assertEqual(Decimal(str(after['allocations'][key])) - Decimal(str(before['allocations'].get(key, 0))), quantity)
        if new != 0:
            price = Decimal(fill['fill_price_minor']) / Decimal(fill['price_scale'])
            self.assertGreaterEqual(abs(new), Decimal(self.instrument['minimum_quantity']))
            if self.instrument.get('minimum_notional') is not None:
                self.assertGreaterEqual(abs(new) * price, Decimal(self.instrument['minimum_notional']))
        return quantity

    def check_duplicate(self, result):
        events = list(self.book.events)
        duplicate = submit_interactive_order(**self.last)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['order_id'], result['order_id'])
        self.assertEqual(list(self.book.events), events)

    def attempt(self, size, side, price, volume=DEEP, *, disruption=None):
        before = self.snapshot(); entry = dict(sized=str(size), fill_price=str(price), volume=str(volume))
        if disruption:
            entry['disruption'] = disruption
        try:
            if disruption == 'disconnected':
                self.tape.lifecycle.connection_state = 'RECONNECTING'
            result = self.submit(size, side, price, volume, fresh_print=disruption != 'no_post_intent_print')
        except ValueError as exc:
            result = None; entry['outcome'] = f'GATE:{exc}'
        else:
            entry['outcome'] = result['order']['state']; entry['reason_codes'] = list(result['order'].get('reason_codes') or [])
        finally:
            self.tape.lifecycle.connection_state = 'CONNECTED'
        entry['filled'] = str(self.check_transition(before, result, size))
        if result is not None:
            self.check_duplicate(result)
            if result['order']['state'] == 'PARTIALLY_FILLED':
                # As the controller does, end the unfilled remainder; cancellation never touches the retained fill.
                before_cancel = self.snapshot()
                cancel_interactive_order(ledger=self.book, order_id=result['order_id'])
                after_cancel = self.snapshot()
                self.assertEqual(after_cancel['events'][:len(before_cancel['events'])], before_cancel['events'])
                self.assertEqual((after_cancel['cash'], after_cancel['position'], after_cancel['trades']),
                                 (before_cancel['cash'], before_cancel['position'], before_cancel['trades']))
                entry['remainder_cancelled'] = True
        if disruption:
            self.assertEqual(entry['filled'], '0', entry)
        return entry

    # -- bounded completion driver ---------------------------------------------------------------------------
    def drive(self, close_side, prices, volumes=(DEEP,), disruptions=None):
        log = []
        for index in range(MAX_ATTEMPTS):
            position = self.position()
            if position == 0:
                break
            price = Decimal(str(prices[min(index, len(prices) - 1)]))
            volume = volumes[min(index, len(volumes) - 1)]
            size = capped_exit_quantity(self.book, IID, abs(position))
            if disruptions and index in disruptions:
                log.append(dict(attempt=index, position=str(position), **self.attempt(size or abs(position), close_side, price,
                                volume, disruption=disruptions[index])))
                continue
            if size <= 0:
                log.append(dict(attempt=index, position=str(position), sized='0', outcome='NO_LEGAL_SIZE'))
                break
            log.append(dict(attempt=index, position=str(position), **self.attempt(size, close_side, price, volume)))
            self.mark(price)  # the next decision is fresh: it sizes from the latest print
        return log

    def classify(self, case, log, start_position, final_price, eligible=None):
        final = self.position()
        lo, hi = bounds(final_price, self.cap, self.instrument['minimum_quantity'], eligible)
        lo_unlimited, hi_unlimited = bounds(final_price, self.cap, self.instrument['minimum_quantity'])
        if final == 0:
            verdict = 'COMPLETED'
        elif len(log) == MAX_ATTEMPTS and log[-1].get('filled', '0') != '0':
            verdict = 'BOUND_EXHAUSTED'  # still progressing: the bound, not the system, stopped the case
        elif not partitionable(abs(start_position), lo, hi):
            verdict = 'EXPECTED_NON_COMPLETION'
        elif abs(final) < lo:
            verdict = 'KNOWN_LIMIT_POST_FILL_DUST'
        elif eligible is not None and partitionable(abs(start_position), lo_unlimited, hi_unlimited) and any(
                REASON in row.get('reason_codes', []) for row in log[-2:]):
            verdict = 'NON_COMPLETION_LIQUIDITY_GUARD'
        else:
            verdict = 'SUSPECTED_DEFECT'
        row = dict(family=type(self).__name__, case=case, verdict=verdict, start_position=str(start_position),
                   final_position=str(final), cap_minor=self.cap, final_price=str(final_price),
                   oracle=dict(lo=str(lo), hi=str(hi), eligible=None if eligible is None else str(eligible),
                               partitionable=partitionable(abs(start_position), lo, hi)),
                   attempts=len(log), max_attempts=MAX_ATTEMPTS, log=log)
        type(self).results.append(row)
        return row


PATHS = {
    'flat': ['2.0'], 'tick_down': ['1.999999'], 'tick_up': ['2.000001'], 'adverse_small': ['1.99'],
    'adverse_large': ['1.8'], 'favorable_small': ['2.01'], 'whipsaw': ['1.99', '2.01', '1.99', '2.0'],
}


class PricePathStressTests(StressBase):
    """Decision at a $2.00 mark; actual prints follow each path, then stay at its final price."""

    def test_capped_and_uncapped_exits_complete_or_classify_under_price_paths(self):
        for cap in (300, 1000):
            for is_short in (False, True):
                for name, path in PATHS.items():
                    with self.subTest(cap=cap, short=is_short, path=name):
                        self.fresh(cap); self.open('1.6', is_short=is_short); self.mark('2.0')
                        log = self.drive('BUY' if is_short else 'SELL', path)
                        row = self.classify(dict(cap=cap, short=is_short, path=name, quantity='1.6'), log, Decimal('1.6'), path[-1])
                        self.assertIn(row['verdict'], ALLOWED, row)


class CapPartitionStressTests(StressBase):
    """Caps near the legal-partition thresholds at a stable $2.00 price (lo 0.25 units)."""
    CASES = [(cap, quantity) for cap in (50, 55, 60, 65, 70, 100, 150, 300) for quantity in ('1.6', '1.0', '2.2')]

    def test_capped_exit_partitions_complete_when_a_legal_split_exists(self):
        for cap, quantity in self.CASES:
            for is_short in (False, True):
                with self.subTest(cap=cap, quantity=quantity, short=is_short):
                    self.fresh(cap)
                    open_price = next(p for p in ('1.0', '1.25', '0.8', '1.6', '2.0', '0.625', '2.5')
                                      if partitionable(Decimal(quantity), *bounds(p, cap)))
                    self.open(quantity, is_short=is_short, price=open_price); self.mark('2.0')
                    log = self.drive('BUY' if is_short else 'SELL', ['2.0'])
                    row = self.classify(dict(cap=cap, short=is_short, quantity=quantity, open_price=open_price), log,
                                        Decimal(quantity), '2.0')
                    self.assertIn(row['verdict'], ALLOWED, row)
                    if row['verdict'] != 'COMPLETED':
                        self.assertGreaterEqual(abs(self.position()), Decimal('0.25'))  # stops safely, never as dust


class ResidualBoundaryStressTests(StressBase):
    """Direct close orders whose residual lands just below, at, or above each venue minimum at the fill price."""
    CASES = [
        ('notional', '0.5', '0.001', '1.351', 'REJECTED'), ('notional', '0.5', '0.001', '1.350', 'FILLED'),
        ('notional', '0.5', '0.001', '1.349', 'FILLED'),
        ('quantity', None, '0.3', '1.301', 'REJECTED'), ('quantity', None, '0.3', '1.300', 'FILLED'),
        ('quantity', None, '0.3', '1.299', 'FILLED'),
        ('both_quantity_binds', '0.5', '0.3', '1.301', 'REJECTED'), ('both_notional_binds', '0.7', '0.3', '1.300', 'REJECTED'),
        ('both_ok', '0.5', '0.3', '1.299', 'FILLED'),
    ]

    def test_residual_minimum_boundaries_for_long_and_short_closes(self):
        for kind, notional, minimum, close, expected in self.CASES:
            for is_short in (False, True):
                with self.subTest(kind=kind, close=close, short=is_short):
                    self.fresh(1000, minimum_quantity=minimum, minimum_notional=notional)
                    self.open('1.6', is_short=is_short); self.mark('2.0')
                    entry = self.attempt(Decimal(close), 'BUY' if is_short else 'SELL', Decimal('2.0'))
                    self.assertEqual(entry['outcome'], expected, entry)
                    if expected == 'REJECTED':
                        self.assertEqual(entry['reason_codes'], [REASON])
                    type(self).results.append(dict(family=type(self).__name__, verdict='BOUNDARY_' + entry['outcome'],
                        case=dict(kind=kind, minimum_notional=notional, minimum_quantity=minimum, close=close, short=is_short,
                                  expected=expected), log=[entry]))


class LiquidityStressTests(StressBase):
    """Participation-limited prints: eligible quantity = print size x policy participation (1/100 here)."""
    CASES = {
        'thin_constant': ([140.0], Decimal('1.4')),
        'thin_then_recover': ([140.0, 140.0, 140.0, DEEP], None),
        'single_partial': ([100.0, DEEP], None),
        'repeated_partial': ([30.0], Decimal('0.3')),
        'below_minimum_liquidity': ([20.0], Decimal('0.2')),
    }

    def test_participation_limited_exits(self):
        for name, (volumes, eligible) in self.CASES.items():
            for is_short in (False, True):
                with self.subTest(case=name, short=is_short):
                    self.fresh(1000); self.open('1.6', is_short=is_short); self.mark('2.0')
                    self.assertEqual(self.participation, Decimal('0.01'))
                    log = self.drive('BUY' if is_short else 'SELL', ['2.0'], volumes)
                    row = self.classify(dict(case=name, short=is_short, volumes=[str(v) for v in volumes]), log,
                                        Decimal('1.6'), '2.0', eligible)
                    self.assertIn(row['verdict'], ALLOWED, row)
                    if eligible is None or name in ('thin_constant', 'repeated_partial'):
                        # Liquidity recovers within the bound, or each print holds at least one legal lot: owner decision (b)
                        # trims a participation-limited close to a legal residual instead of rejecting it.
                        self.assertEqual(row['verdict'], 'COMPLETED', row)


class DisruptionStressTests(StressBase):
    """Freshness/connection rejections and bad prints interleaved with residual rejections, then recovery."""
    CASES = {
        'no_post_intent_print_then_fresh': (['2.0'], {0: 'no_post_intent_print', 1: 'no_post_intent_print'}),
        'disconnected_then_reconnected': (['2.0'], {0: 'disconnected', 2: 'disconnected'}),
        'off_tick_prints_then_valid': (['2.0000005', '2.0000005', '2.0000005', '2.0'], {}),
        # $1.95 is below the buffered residual (0.255 x $1.95 < $0.50), so the guard still rejects first.
        'residual_reject_then_stale_then_fresh': (['1.95', '1.95', '1.95'], {1: 'no_post_intent_print', 2: 'disconnected'}),
    }

    def test_interleaved_rejections_never_mutate_and_recovery_completes(self):
        for name, (path, disruptions) in self.CASES.items():
            for is_short in (False, True):
                with self.subTest(case=name, short=is_short):
                    self.fresh(300); self.open('1.6', is_short=is_short); self.mark('2.0')
                    log = self.drive('BUY' if is_short else 'SELL', path, disruptions=disruptions)
                    row = self.classify(dict(case=name, short=is_short, path=path,
                                             disruptions={str(k): v for k, v in disruptions.items()}), log, Decimal('1.6'), path[-1])
                    self.assertEqual(row['verdict'], 'COMPLETED', row)
                    if name.startswith('residual_reject'):
                        self.assertIn(REASON, log[0].get('reason_codes', []), log)


class LegacyPolicyStressTests(StressBase):
    """A legacy crypto-long policy (no crypto caps) keeps its identity; the guard still protects its residual."""

    def test_legacy_crypto_long_exit_under_adverse_print_and_thin_liquidity(self):
        for name, path, volumes, eligible in (('adverse_then_fresh', ['1.99'], (DEEP,), None),
                                              ('thin_constant', ['2.0'], (140.0,), Decimal('1.4'))):
            with self.subTest(case=name):
                self.fresh(None, legacy=True)
                self.open('1.6', is_short=False); self.mark('2.0')
                identity = self.book.policy['risk_policy_identity_hash']
                self.assertFalse(self.book.policy.get('crypto_caps_version'))
                if name == 'adverse_then_fresh':
                    first = self.attempt(Decimal('1.35'), 'SELL', Decimal('1.99'))  # sized at the $2.00 mark
                    self.assertEqual(first['reason_codes'], [REASON])
                log = self.drive('SELL', path, volumes)
                row = self.classify(dict(case=name, legacy=True), log, Decimal('1.6'), path[-1], eligible)
                self.assertEqual(row['verdict'], 'COMPLETED', row)
                self.assertEqual(self.book.policy['risk_policy_identity_hash'], identity)


class ControllerStressTests(retry.ResidualControllerRetryTests):
    """Actual controller: a thin print trims the close to a legal residual, then a feed gap, then recovery; bounded cycles."""

    def open_position(self, is_short):
        short.paper_experiment.close_experiment(self.store, self.experiment['experiment_id'])
        self.experiment = short.paper_experiment.create_experiment(self.store, dict(allow_short=True, allow_crypto_short=True,
            crypto_notional_caps=dict(crypto_max_order_notional_minor=90000, crypto_max_position_notional_minor=90000)))['experiment']
        a = self.auto; self.tape.market(self.iid, 8000.0, 1000.0)
        a.quote(self.iid, 8000, -2 if is_short else 2)
        a.opportunity(self.iid, side=short.OpportunitySide.SHORT if is_short else short.OpportunitySide.LONG)
        body = short.policy_body(risk=dict(allow_short=True, allowed_universes=['US_EQUITIES', 'CRYPTO'], max_position_notional_minor=90000))
        body['scopes'] = [dict(scope=body['scope'], sessions=['REGULAR']), dict(scope=dict(universe='CRYPTO'), sessions=['CONTINUOUS'])]
        a.session_label = 'CLOSED'; a.service.configure(body); a.arm(); a.service.start(threaded=False)
        a.cycle(); a.runs.finish(a.service._controller()['universes']['CRYPTO']['universe']['active_run_id'], [self.iid])
        opened = [row for _ in range(3) for row in a.cycle()['actions'] if row['outcome'] == 'SUBMITTED']
        self.assertEqual([row['filled_quantity'] for row in opened], ['0.112'], opened)
        return a

    def exits(self, a, seconds, is_short):
        a.quote(self.iid, 8000, 2 if is_short else -2)
        return [row for row in a.cycle(seconds)['actions'] if row['action'] == 'EXIT' and row['outcome'] == 'SUBMITTED']

    def thin_then_gap_then_recover(self, is_short):
        a = self.open_position(is_short)
        trades = len(self.store.paper_ledger.project_trades())
        self.tape.market(self.iid, 8000.0, 10.0)  # 1/100 participation: 0.1 eligible < 0.112; a 0.1 fill would leave $96 < $200
        thin = self.exits(a, 400, is_short)
        self.assertEqual([(row['order_state'], row['filled_quantity']) for row in thin], [('PARTIALLY_FILLED', '0.086')], thin)  # trim keeps the 2% buffer
        self.assertNotIn(REASON, thin[0].get('reason_codes') or [])
        self.assertEqual(len(self.store.paper_ledger.project_trades()), trades + 1)
        self.assertEqual(abs(Decimal(a.position(self.iid)['quantity'])), Decimal('0.026'))  # $208 at $8,000: $200 + 2% buffer
        self.tape.market(self.iid, 8000.0, 1000.0, prints=0)  # feed gap: no fresh prints
        gap = [row for seconds in (900, 900) for row in self.exits(a, seconds, is_short)]
        self.assertTrue(all(Decimal(str(row.get('filled_quantity') or 0)) == 0 for row in gap), gap)
        self.assertEqual(len(self.store.paper_ledger.project_trades()), trades + 1)
        self.tape.market(self.iid, 8000.0, 1000.0)  # liquidity and freshness recover
        filled = [row for seconds in (900, 900, 5, 5, 5) for row in self.exits(a, seconds, is_short)
                  if Decimal(str(row.get('filled_quantity') or 0)) > 0]
        self.assertEqual([row['filled_quantity'] for row in filled], ['0.026'], filled)
        self.assertIsNone(a.position(self.iid))
        print('EXIT_STRESS_RESULT ' + json.dumps(dict(family='ControllerStressTests', verdict='COMPLETED_AFTER_RECOVERY',
            case=dict(short=is_short, thin_print='10', eligible='0.1', position='0.112', clamp=True),
            log=dict(thin=[r['filled_quantity'] for r in thin], gap_submissions=len(gap), filled=[r['filled_quantity'] for r in filled])),
            sort_keys=True))

    def test_short_cover_thin_liquidity_gap_then_recovery(self):
        self.thin_then_gap_then_recover(True)

    def test_long_close_thin_liquidity_gap_then_recovery(self):
        self.thin_then_gap_then_recover(False)


ControllerStressTests.test_short_cover_rejection_uses_backoff_and_fresh_decisions = None
ControllerStressTests.test_long_close_rejection_uses_backoff_and_fresh_decisions = None

if __name__ == '__main__':
    unittest.main()

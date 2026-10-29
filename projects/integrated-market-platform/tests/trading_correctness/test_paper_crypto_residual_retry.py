"""SOFTWARE_CONTROLLED: reject a crypto close that would strand its residual at the actual fill price."""
import unittest
from decimal import Decimal
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.risk.policy import build_risk_policy
from market_platform_foundation.ui_api.paper_market_evidence import PaperMarketEvidence
from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
from tests.trading_correctness import test_paper_crypto_shorts as short

IID,S=short.IID,short.S
REASON='SIM_CRYPTO_CLOSE_RESIDUAL_BELOW_MINIMUM'


class ResidualExecutionGuardTests(unittest.TestCase):
    setUp=short.CryptoShortTests.setUp
    order=short.CryptoShortTests.order
    mark=short.CryptoShortTests.mark

    def opened(self,is_short=True,cap=300):
        self.book=short.book(crypto_max_order_notional_minor=cap,crypto_max_position_notional_minor=cap)
        result=self.order('1.6',side='SELL' if is_short else 'BUY',price=1.0)
        self.assertEqual(result['order']['state'],'FILLED')
        self.mark(2.0)

    def assert_rejected_unchanged(self,result,cash,quantity):
        self.assertEqual(result['order']['state'],'REJECTED')
        self.assertEqual(result['order']['reason_codes'],[REASON])
        self.assertIsNone(result['fill'])
        self.assertEqual(self.book.project_account()['cash_minor'],cash)
        self.assertEqual(self.book.project_positions()[0]['quantity'],quantity)

    def test_lower_execution_price_rejects_long_and_short_residual_without_financial_mutation(self):
        for is_short in (False,True):
            with self.subTest(short=is_short):
                self.setUp();self.opened(is_short)
                close=capped_exit_quantity(self.book,IID,Decimal('1.6'))
                self.assertEqual(close,Decimal('1.35'))
                cash=self.book.project_account()['cash_minor'];quantity=self.book.project_positions()[0]['quantity']
                result=self.order(str(close),side='BUY' if is_short else 'SELL',price=1.99)
                self.assert_rejected_unchanged(result,cash,quantity)

    def test_participation_partial_fill_is_trimmed_to_a_legal_residual(self):
        # Owner decision (b): eligible 1.4 would leave 0.2 x $1.99 < $0.50, so the fill is trimmed to keep 0.252.
        self.opened(cap=1000)
        self.tape.trade(IID,1.99,140,received_ns=131*S,event_ns=131*S)
        bars=PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID,now_ns=135*S)
        result=submit_interactive_order(ledger=self.book,bars=bars,symbol=IID,instrument_id=IID,
            instrument=self.instrument,quantity='1.6',side='BUY',observation_time=130*S,
            client_order_id='partial',idempotency_key='partial')
        self.assertEqual((result['order']['state'],result['fill']['fill_quantity']),('PARTIALLY_FILLED','1.348'))
        self.assertEqual(self.book.project_positions()[0]['quantity'],'-0.252')

    def test_rejected_fill_does_not_consume_print_participation_capacity(self):
        self.opened()
        self.tape.trade(IID,1.99,135,received_ns=131*S,event_ns=131*S)
        bars=PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID,now_ns=135*S)
        kwargs=dict(ledger=self.book,bars=bars,symbol=IID,instrument_id=IID,
            instrument=self.instrument,side='BUY',observation_time=130*S)
        before=dict(self.book._bar_simulator._bar_allocations)
        bad=submit_interactive_order(**kwargs,quantity='1.35',client_order_id='bad',idempotency_key='bad')
        self.assertEqual(bad['order'].get('reason_codes',[]),[REASON])
        self.assertEqual(self.book._bar_simulator._bar_allocations,before)
        good=submit_interactive_order(**kwargs,quantity='1.348',client_order_id='good',idempotency_key='good')
        self.assertEqual(good['order']['state'],'FILLED')
        self.assertEqual(good['fill']['fill_quantity'],'1.348')
        self.assertEqual(self.book.project_positions()[0]['quantity'],'-0.252')

    def test_full_close_remains_allowed_when_there_is_no_residual(self):
        for is_short in (False,True):
            with self.subTest(short=is_short):
                self.setUp();self.opened(is_short,cap=1000)
                result=self.order('1.6',side='BUY' if is_short else 'SELL',price=1.99)
                self.assertEqual(result['order']['state'],'FILLED')
                self.assertEqual(self.book.project_positions(),[])

    def test_fresh_price_resizing_and_new_intent_can_finish_the_close(self):
        self.opened()
        first=self.order('1.35',side='BUY',price=1.99)
        self.assertEqual(first['order'].get('reason_codes',[]),[REASON])
        self.mark(1.99)
        resized=capped_exit_quantity(self.book,IID,Decimal('1.6'))
        self.assertEqual(resized,Decimal('1.348'))
        second=self.order(str(resized),side='BUY',price=1.99)
        self.assertEqual(second['order']['state'],'FILLED')
        self.assertNotEqual(second['order_id'],first['order_id'])
        self.assertEqual(self.book.project_positions()[0]['quantity'],'-0.252')
        self.assertEqual(self.order('0.252',side='BUY',price=1.99)['order']['state'],'FILLED')
        self.assertEqual(self.book.project_positions(),[])

    def test_venue_quantity_minimum_is_checked_even_without_a_notional_minimum(self):
        self.instrument=dict(self.instrument,minimum_quantity='0.3')
        self.instrument.pop('minimum_notional')
        self.opened()
        cash=self.book.project_account()['cash_minor']
        result=self.order('1.4',side='BUY',price=2)
        self.assert_rejected_unchanged(result,cash,'-1.6')

    def test_existing_crypto_long_account_is_guarded_without_changing_its_policy(self):
        policy=build_risk_policy()
        self.book=short.PaperExecutionLedger.open_session(replay_session_id='legacy-guard',instrument_id='SEED',
            symbol='SEED',policy=policy,execution_mode='INTERNAL_SIMULATION',execution_authority='PAPER_ONLY',experiment_id='legacy-guard')
        self.order('1.6',side='BUY',price=1.0)
        identity=self.book.policy['risk_policy_identity_hash'];cash=self.book.project_account()['cash_minor']
        result=self.order('1.35',side='SELL',price=1.99)
        self.assert_rejected_unchanged(result,cash,'1.6')
        self.assertEqual(self.book.policy['risk_policy_identity_hash'],identity)

    def test_rejected_intent_is_idempotent_and_cannot_be_reused_for_a_resized_retry(self):
        self.opened()
        self.tape.trade(IID,1.99,100_000,received_ns=131*S,event_ns=131*S)
        bars=PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID,now_ns=135*S)
        kwargs=dict(ledger=self.book,bars=bars,symbol=IID,instrument_id=IID,instrument=self.instrument,
            side='BUY',observation_time=130*S,quantity='1.35',client_order_id='one-intent',idempotency_key='one-intent')
        first=submit_interactive_order(**kwargs)
        self.assertEqual(first['order']['reason_codes'],[REASON])
        events=list(self.book.events);cash=self.book.project_account()['cash_minor']
        duplicate=submit_interactive_order(**kwargs)
        self.assertTrue(duplicate['duplicate'])
        self.assertEqual(duplicate['order_id'],first['order_id'])
        self.assertEqual(self.book.events,events)
        with self.assertRaisesRegex(ValueError,'IDEMPOTENCY_CONFLICT'):
            submit_interactive_order(**dict(kwargs,quantity='1.348'))
        self.assertEqual(self.book.project_account()['cash_minor'],cash)
        self.assertEqual(self.book.events,events)

    def test_guard_uses_actual_fill_bar_even_if_the_latest_bar_would_make_the_residual_valid(self):
        self.opened()
        self.tape.trade(IID,1.99,100_000,received_ns=131*S,event_ns=131*S)
        self.tape.trade(IID,2.0,100_000,received_ns=132*S,event_ns=132*S)
        bars=PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID,now_ns=135*S)
        cash=self.book.project_account()['cash_minor']
        result=submit_interactive_order(ledger=self.book,bars=bars,symbol=IID,instrument_id=IID,
            instrument=self.instrument,side='BUY',observation_time=130*S,quantity='1.35',
            client_order_id='actual-bar',idempotency_key='actual-bar')
        self.assert_rejected_unchanged(result,cash,'-1.6')


class ResidualControllerRetryTests(short.CryptoShortAutomationTests):
    """Actual controller → handoff → preview → submit → existing bounded retry path."""
    def setUp(self):
        super().setUp()
        from types import SimpleNamespace
        from unittest.mock import patch
        from market_platform_foundation.ui_api import screener_crypto
        payload={'error':[],'result':{'BTC/USD':dict(base='BTC',quote='USD',aclass_base='currency',aclass_quote='currency',
            status='online',ordermin='0.001',costmin='200',tick_size='0.0001',lot_decimals=3,pair_decimals=4,cost_decimals=2)}}
        self.crypto_source=screener_crypto.CryptoScreener(client=SimpleNamespace(asset_pairs=lambda:payload),env={'IMP_CRYPTO_LIVE':'1'})
        rows,_,error=self.crypto_source._catalog()
        self.assertIsNone(error);self.assertEqual(rows[0]['instrument']['instrument_id'],self.iid)
        patcher=patch.object(screener_crypto,'_SERVICE',self.crypto_source);patcher.start();self.addCleanup(patcher.stop)

    def scenario(self,is_short):
        from unittest.mock import patch
        short.paper_experiment.close_experiment(self.store,self.experiment['experiment_id'])
        self.experiment=short.paper_experiment.create_experiment(self.store,dict(allow_short=True,allow_crypto_short=True,
            crypto_notional_caps=dict(crypto_max_order_notional_minor=90000,crypto_max_position_notional_minor=90000)))['experiment']
        a=self.auto;self.tape.market(self.iid,8000.0,1000.0)
        a.quote(self.iid,8000,-2 if is_short else 2)
        a.opportunity(self.iid,side=short.OpportunitySide.SHORT if is_short else short.OpportunitySide.LONG)
        body=short.policy_body(risk=dict(allow_short=True,allowed_universes=['US_EQUITIES','CRYPTO'],max_position_notional_minor=90000))
        body['scopes']=[dict(scope=body['scope'],sessions=['REGULAR']),dict(scope=dict(universe='CRYPTO'),sessions=['CONTINUOUS'])]
        a.session_label='CLOSED';a.service.configure(body);a.arm();a.service.start(threaded=False)
        a.cycle();a.runs.finish(a.service._controller()['universes']['CRYPTO']['universe']['active_run_id'],[self.iid])
        opened=[row for _ in range(3) for row in a.cycle()['actions'] if row['outcome']=='SUBMITTED']
        self.assertEqual([row['filled_quantity'] for row in opened],['0.112'],opened)
        self.assertEqual(Decimal(self.store.paper_ledger.instrument_for(self.iid)['minimum_notional']),Decimal('200'))
        self.tape.market(self.iid,10000.0,1000.0);a.quote(self.iid,10000,2 if is_short else -2)
        original=a.service._submit
        def drift_after_preview(order_body):
            self.tape.market(self.iid,9000.0,1000.0)
            return original(order_body)
        before_fills=len(self.store.paper_ledger.project_trades())
        with patch.object(a.service,'_submit',side_effect=drift_after_preview):
            rejected=[row for row in a.cycle(400)['actions'] if row['action']=='EXIT' and row['outcome']=='SUBMITTED']
        self.assertEqual(len(rejected),1,rejected)
        self.assertEqual(rejected[0]['order_state'],'REJECTED',rejected)
        self.assertIn(REASON,rejected[0]['reason_codes'])
        self.assertEqual(Decimal(str(rejected[0]['filled_quantity'])),0)
        self.assertEqual(len(self.store.paper_ledger.project_trades()),before_fills)
        self.assertEqual(abs(Decimal(a.position(self.iid)['quantity'])),Decimal('0.112'))
        after_rejection_orders=len(self.store.paper_ledger.project_orders())
        a.quote(self.iid,9000,2 if is_short else -2)
        with patch.object(a.service,'_submit',wraps=original) as submitted:
            a.cycle(1)
            self.assertEqual(submitted.call_count,0)
        self.assertEqual(len(self.store.paper_ledger.project_orders()),after_rejection_orders)
        outcomes=[row for row in a.cycle(400)['actions'] if row['action']=='EXIT' and row['outcome']=='SUBMITTED']
        outcomes += [row for _ in range(6) for row in a.cycle(5)['actions'] if row['action']=='EXIT' and row['outcome']=='SUBMITTED']
        filled=[row for row in outcomes if Decimal(str(row.get('filled_quantity') or 0))>0]
        self.assertEqual([row['filled_quantity'] for row in filled],['0.089','0.023'],outcomes)
        self.assertIsNone(a.position(self.iid))
        self.assertEqual(len({row['decision_id'] for row in [rejected[0],*filled]}),3)
        self.assertEqual(len({row['order_id'] for row in [rejected[0],*filled]}),3)

    def test_short_cover_rejection_uses_backoff_and_fresh_decisions(self):
        self.scenario(True)

    def test_long_close_rejection_uses_backoff_and_fresh_decisions(self):
        self.scenario(False)


for name in short.CryptoShortAutomationTests.__dict__:
    if name.startswith('test_'):setattr(ResidualControllerRetryTests,name,None)

if __name__=='__main__':unittest.main()

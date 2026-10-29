"""SOFTWARE_CONTROLLED: draft B, exact fractional crypto shorts; no live stores or providers."""
import unittest
from decimal import Decimal
from types import SimpleNamespace
from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.paper.short_gate import enforce_equity_sell
from market_platform_foundation.risk.policy import build_risk_policy
from market_platform_foundation.ui_api.paper_market_evidence import PaperMarketEvidence
from tests.trading_correctness.test_paper_crypto_live_execution import IID,S,Tape,nano


def book(**terms):
    policy=build_risk_policy(initial_cash_minor=100_000,allow_short=True,allow_crypto_short=True,**terms)
    return PaperExecutionLedger.open_session(replay_session_id='draft-b',instrument_id='SEED',symbol='SEED',policy=policy,
        execution_mode='INTERNAL_SIMULATION',execution_authority='PAPER_ONLY',experiment_id='draft-b')


class CryptoShortTests(unittest.TestCase):
    def setUp(self):
        self.book=book(); self.n=0
        self.instrument=dict(nano(),minimum_quantity='0.001',quantity_step='0.001')
        self.tape=Tape(100*S); self.tape.ack(IID,101*S)

    def order(self,quantity,side='SELL',price=2.0,book_override=None):
        self.n+=1; t=110+10*self.n
        self.tape.trade(IID,price,100_000.0,received_ns=(t+1)*S)
        bars=PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars(IID,now_ns=(t+5)*S)
        return submit_interactive_order(ledger=book_override or self.book,bars=bars,symbol=IID,instrument_id=IID,
            instrument=self.instrument,quantity=quantity,side=side,observation_time=t*S,
            client_order_id=str(self.n),idempotency_key=str(self.n))

    def opened(self):
        result=self.order('1.5')
        self.assertEqual(result['order']['state'],'FILLED',result)
        return result

    def mark(self,price):
        self.book.apply_live_mark(instrument_id=IID,mark_minor=int(Decimal(str(price))*1_000_000),
            mark_provider='FIXTURE',mark_as_of_ns=200*S,mark_quality='CURRENT')

    def test_fractional_short_open_and_account_scale_margin(self):
        self.opened(); self.mark(2)
        row=self.book.project_positions()[0]
        self.assertEqual(row['quantity'],'-1.5')
        self.assertEqual(row['market_value_minor'],-300)
        s=self.book.short_margin_status()
        self.assertEqual((s['short_market_value_minor'],s['short_margin_reserved_minor'],s['maintenance_requirement_minor']),(300,600,150))
        self.assertEqual(self.book.project_account()['buying_power_minor'],99_700)
        self.assertEqual(s['short_positions'][0]['quantity'],'-1.5')

    def test_partial_then_full_cover_realizes_exact_pnl(self):
        self.opened()
        self.assertEqual(self.order('0.5','BUY',1.0)['order']['state'],'FILLED')
        self.assertEqual(self.book.project_positions()[0]['quantity'],'-1')
        self.assertEqual(self.order('1','BUY',1.0)['order']['state'],'FILLED')
        self.assertEqual(self.book.project_positions(),[])
        self.assertEqual(self.book.project_account()['cash_minor'],100_150)
        self.assertEqual(self.book.project_account()['buying_power_minor'],100_150)

    def test_crypto_borrow_terms_and_fractional_quantity_are_idempotent(self):
        self.opened(); self.mark(2)
        events=self.book.accrue_short_borrow_fees(accrual_date='2026-10-28',as_of_ns=200*S)
        self.assertEqual(len(events),1)
        p=events[0]['payload']
        self.assertEqual((p['quantity'],p['fee_bps_per_year'],p['fee_minor']),('-1.5',4380,1))
        self.assertEqual(self.book.accrue_short_borrow_fees(accrual_date='2026-10-28',as_of_ns=201*S),[])
        self.assertEqual(self.book.project_account()['cash_minor'],100_299)

    def test_maintenance_uses_crypto_terms_and_current_account_value(self):
        self.opened(); self.mark(500)
        s=self.book.short_margin_status()
        self.assertEqual((s['short_market_value_minor'],s['maintenance_requirement_minor']),(75_000,37_500))
        self.assertTrue(s['maintenance_breached'])

    def test_missing_mark_does_not_invent_equity_or_margin_breach(self):
        self.opened(); self.book.clear_mark(IID)
        s=self.book.short_margin_status()
        self.assertIsNone(s['equity_minor']); self.assertFalse(s['maintenance_breached'])
        self.assertEqual((s['short_market_value_minor'],s['short_margin_reserved_minor']),(300,600))
        self.assertEqual(s['unmarked_short_instruments'],[IID])

    def test_cover_can_realize_loss_beyond_cash_but_cannot_reverse(self):
        self.opened()
        with self.assertRaisesRegex(ValueError,'POSITION_REVERSAL_NOT_ALLOWED'):
            self.order('2','BUY',3.0)
        self.assertEqual(self.order('1.5','BUY',1000.0)['order']['state'],'FILLED')
        self.assertEqual(self.book.project_account()['cash_minor'],-49_700)

    def test_long_cannot_reverse_to_short(self):
        self.assertEqual(self.order('1.5','BUY')['order']['state'],'FILLED')
        with self.assertRaisesRegex(ValueError,'POSITION_REVERSAL_NOT_ALLOWED'):
            self.order('2','SELL')

    def test_equity_short_enabled_account_still_rejects_crypto_short(self):
        p=build_risk_policy(allow_short=True)
        old=PaperExecutionLedger.open_session(replay_session_id='old',instrument_id='SEED',symbol='SEED',policy=p,
            execution_mode='INTERNAL_SIMULATION',execution_authority='PAPER_ONLY',experiment_id='old')
        with self.assertRaisesRegex(ValueError,'SHORT_INSTRUMENT_UNSUPPORTED'):
            self.order('1.5',book_override=old)

    def test_insufficient_crypto_initial_margin_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_SHORT_MARGIN'):
            self.order('100',price=20.0)

    def test_gate_keeps_equity_price_and_day_change_rules(self):
        kwargs=dict(ledger=self.book,intent={'desired_quantity':1},kind='TRADABLE_SECURITY',position_qty=0,
            reserved_sell=0,costs_minor=0,buying_power_minor=100_000)
        with self.assertRaisesRegex(ValueError,'SHORT_PRICE_BELOW_MINIMUM'):
            enforce_equity_sell(price_minor=200,**kwargs)
        with self.assertRaisesRegex(ValueError,'SHORT_SALE_RESTRICTION_UNKNOWN'):
            enforce_equity_sell(price_minor=1000,**kwargs)

    def test_existing_policy_identity_and_opt_in_validation(self):
        self.assertEqual(build_risk_policy(allow_short=True),build_risk_policy(allow_short=True,allow_crypto_short=False))
        self.assertNotEqual(self.book.policy['risk_policy_identity_hash'],build_risk_policy(allow_short=True)['risk_policy_identity_hash'])
        with self.assertRaisesRegex(ValueError,'CRYPTO_SHORT_REQUIRES_ALLOW_SHORT'):
            build_risk_policy(allow_crypto_short=True)


from unittest.mock import patch
from market_platform_foundation.ui_api import paper_experiment
from tests.trading_correctness import test_paper_crypto_live_execution as live
from tests.trading_correctness.test_paper_automation_shorts import ShortProvider
from tests.support.paper_automation_harness import Automation,policy_body
from market_platform_foundation.intelligence.contracts.common import OpportunitySide

class _CryptoFixture(live.CryptoAutonomousExecutionTests): pass
for name in dir(live.CryptoAutonomousExecutionTests):
    if name.startswith('test_'): setattr(_CryptoFixture,name,None)

class CryptoShortAutomationTests(_CryptoFixture):
    def setUp(self):
        super().setUp()
        paper_experiment.close_experiment(self.store,self.experiment['experiment_id'])
        self.experiment=paper_experiment.create_experiment(self.store,{'allow_short':True,'allow_crypto_short':True})['experiment']
        provider=ShortProvider()
        ai=type(self.auto.ai)(self.clock,provider); ai.rows={};ai.selected=[]
        self.auto=Automation(self.store,clock=self.clock,feed=self.feed,ai=ai,provider=provider)

    def test_automated_crypto_short_opens_then_covers_with_fixture_prints(self):
        a=self.auto; self.tape.market(self.iid,8000.0,1000.0)
        a.quote(self.iid,8000,-2); a.opportunity(self.iid,side=OpportunitySide.SHORT)
        body=policy_body(risk=dict(allow_short=True,allowed_universes=['US_EQUITIES','CRYPTO'],max_position_notional_minor=90000))
        body['scopes']=[dict(scope=body['scope'],sessions=['REGULAR']),dict(scope=dict(universe='CRYPTO'),sessions=['CONTINUOUS'])]
        a.session_label='CLOSED';a.service.configure(body);a.arm();a.service.start(threaded=False)
        a.cycle(); a.runs.finish(a.service._controller()['universes']['CRYPTO']['universe']['active_run_id'],[self.iid])
        outcomes=[row for _ in range(3) for row in a.cycle()['actions']]
        entered=[row for row in outcomes if row['outcome']=='SUBMITTED']
        self.assertEqual([(row['side'],row['filled_quantity']) for row in entered],[('SELL','0.112')],outcomes)
        self.assertEqual(a.position(self.iid)['quantity'],'-0.112')
        self.tape.market(self.iid,7000.0,1000.0);a.quote(self.iid,7000,2)
        closed=[row for row in a.cycle(400)['actions'] if row['outcome']=='SUBMITTED']
        self.assertEqual([row['side'] for row in closed],['BUY'])
        self.assertIsNone(a.position(self.iid))

    def test_creation_records_opt_in_and_rejects_non_boolean_flag(self):
        self.assertTrue(self.store.paper_ledger.allows_crypto_short())
        paper_experiment.close_experiment(self.store,self.experiment['experiment_id'])
        with self.assertRaisesRegex(ValueError,'EXPERIMENT_ALLOW_CRYPTO_SHORT_INVALID'):
            paper_experiment.create_experiment(self.store,{'allow_short':True,'allow_crypto_short':'true'})

    def _normal_exit_above_order_cap(self, short):
        paper_experiment.close_experiment(self.store,self.experiment['experiment_id'])
        self.experiment=paper_experiment.create_experiment(self.store,dict(allow_short=True,allow_crypto_short=True,
            crypto_notional_caps=dict(crypto_max_order_notional_minor=90000,crypto_max_position_notional_minor=90000)))['experiment']
        a=self.auto;self.tape.market(self.iid,8000.0,1000.0)
        a.quote(self.iid,8000,-2 if short else 2)
        a.opportunity(self.iid,side=OpportunitySide.SHORT if short else OpportunitySide.LONG)
        body=policy_body(risk=dict(allow_short=True,allowed_universes=['US_EQUITIES','CRYPTO'],max_position_notional_minor=90000))
        body['scopes']=[dict(scope=body['scope'],sessions=['REGULAR']),dict(scope=dict(universe='CRYPTO'),sessions=['CONTINUOUS'])]
        a.session_label='CLOSED';a.service.configure(body);a.arm();a.service.start(threaded=False)
        a.cycle();a.runs.finish(a.service._controller()['universes']['CRYPTO']['universe']['active_run_id'],[self.iid])
        opened=[row for _ in range(3) for row in a.cycle()['actions'] if row['outcome']=='SUBMITTED']
        self.assertEqual([row['filled_quantity'] for row in opened],['0.112'],opened)
        self.tape.market(self.iid,10000.0,1000.0);a.quote(self.iid,10000,2 if short else -2)
        outcomes=[row for row in a.cycle(400)['actions'] if row['action']=='EXIT']
        closed=[row for row in outcomes if row['outcome']=='SUBMITTED']
        self.assertEqual([(row['side'],row['filled_quantity']) for row in closed],[('BUY' if short else 'SELL','0.09')],outcomes)
        self.assertEqual(abs(Decimal(a.position(self.iid)['quantity'])),Decimal('0.022'))
        remainder=[row for _ in range(3) for row in a.cycle(5)['actions'] if row['action']=='EXIT' and row['outcome']=='SUBMITTED']
        self.assertEqual([row['filled_quantity'] for row in remainder],['0.022'],remainder)
        self.assertIsNone(a.position(self.iid))
        self.assertNotEqual(closed[0]['decision_id'],remainder[0]['decision_id'])

    def test_normal_short_cover_above_order_cap_completes_in_two_decisions(self):
        self._normal_exit_above_order_cap(True)

    def test_normal_long_exit_above_order_cap_completes_in_two_decisions(self):
        self._normal_exit_above_order_cap(False)

class CryptoShortEdgeTests(CryptoShortTests):
    # Reuse only fixture helpers; inherited checks are disabled below.
    def test_working_short_uses_exact_quantity_and_native_price_conversion(self):
        from unittest.mock import patch
        self.opened();self.mark(2)
        order=self.book.project_orders()[0]
        working=dict(order,state='PARTIALLY_FILLED',direction='short',working_remaining='0.5',order_type='MARKET')
        with patch.object(self.book,'project_orders',return_value=[working]):
            status=self.book.short_margin_status()
        self.assertEqual((status['working_short_sale_value_minor'],status['short_margin_reserved_minor']),(100,800))

    def test_old_crypto_long_cannot_spend_short_collateral(self):
        self.order('100',price=5.0);self.mark(5)
        # Cash 1500, reserved 1000: only 500 available, not 1500.
        other=dict(self.instrument,instrument_id='OTHER',symbol='OTHER')
        self.tape.ack('OTHER',101*S);self.tape.trade('OTHER',10.0,100_000.0,received_ns=141*S)
        bars=PaperMarketEvidence(kraken_runtime=self.tape).crypto_trade_bars('OTHER',now_ns=145*S)
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT_CASH'):
            submit_interactive_order(ledger=self.book,bars=bars,instrument=other,instrument_id='OTHER',symbol='OTHER',quantity='60',
                side='BUY',observation_time=140*S,client_order_id='other',idempotency_key='other')

    def test_policy_opt_in_requires_a_boolean(self):
        for bad in ('yes',1,None):
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'CRYPTO_SHORT_FLAG_INVALID'):
                build_risk_policy(allow_short=True,allow_crypto_short=bad)

for name in CryptoShortTests.__dict__:
    if name.startswith('test_'): setattr(CryptoShortEdgeTests,name,None)



class ReviewRegressionTests(CryptoShortTests):
    def test_existing_working_buy_reservation_is_counted_once(self):
        with patch.object(self.book,'working_order_obligations_by_currency',return_value={'USD':40_000}):
            result=self.order('50','BUY',10.0)
        self.assertEqual(result['order']['state'],'FILLED')

    def test_crypto_cover_is_split_to_respect_frozen_order_notional(self):
        from market_platform_foundation.ui_api.paper_automation import PaperAutomationService
        self.book=book(crypto_max_order_notional_minor=300,crypto_max_position_notional_minor=300)
        self.opened();self.mark(4)
        service=SimpleNamespace(store=SimpleNamespace(paper_ledger=self.book),_event=lambda *args,**kw:None)
        with patch('market_platform_foundation.ui_api.paper_projections.preview_paper_order',return_value={'preview':{'risk_status':'FAIL','reason_codes':['CONTROLLED']}}) as preview:
            PaperAutomationService._close_position(service,{'arming':{'arming_id':'fixture'}},{'policy_id':'fixture'},
                {'actions':[]},200,iid=IID,held=Decimal('-1.5'),key='cover',action='MARGIN_COVER',event='fixture',headline='fixture',reason={})
        self.assertEqual(preview.call_args.args[1]['quantity'],'0.75')

    def test_crypto_maintenance_retries_after_terminal_partial_cover(self):
        from market_platform_foundation.ui_api.paper_automation import PaperAutomationService
        from market_platform_foundation.intelligence.inference.hashing import input_hash_from_dict
        self.opened();self.mark(4)
        rows=self.book.project_positions();entry=rows[0].get('first_entry_time_ns')
        base='PAI-MARGIN-'+input_hash_from_dict(dict(account=self.book.paper_account_id,instrument=IID,entry=entry))[:32]
        previous=dict(order_id='previous',instrument_id=IID,state='CANCELLED',client_order_id=base+'-0')
        status=dict(self.book.short_margin_status(),maintenance_breached=True)
        calls=[]
        service=SimpleNamespace(store=SimpleNamespace(paper_ledger=self.book),actions=SimpleNamespace(_authority=lambda:True),_event=lambda *args,**kw:None,
            _block=lambda *args:None,_close_position=lambda *args,**kw:calls.append(kw))
        with patch.object(self.book,'project_orders',return_value=[previous]),patch.object(self.book,'short_margin_status',return_value=status), \
             patch.object(self.book,'lookup_intent_for_order',return_value={'client_order_id':base+'-0'}), \
             patch.object(self.book,'lookup_idempotent_order',side_effect=lambda key:previous if key in (base,base+'-0') else None):
            PaperAutomationService._maintenance_cover(service,{}, {}, {'actions':[]},{'session_date':'2026-10-28'},200)
        self.assertEqual([c['key'] for c in calls],[base+'-1'])

for name in CryptoShortTests.__dict__:
    if name.startswith('test_'): setattr(ReviewRegressionTests,name,None)

class BackgroundExitBoundaryTests(unittest.TestCase):
    """Probe frozen caps and venue minima using the existing fractional-short fixture."""
    setUp=CryptoShortTests.setUp
    order=CryptoShortTests.order
    mark=CryptoShortTests.mark

    def test_exit_cap_rounds_down_in_native_price_scale(self):
        from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
        self.book=book(crypto_max_order_notional_minor=301,crypto_max_position_notional_minor=301)
        self.order('2',side='SELL',price=1.0);self.mark(2.01)
        quantity=capped_exit_quantity(self.book,IID,Decimal('2'))
        self.assertEqual(quantity,Decimal('1.497'))
        self.assertLessEqual(quantity*Decimal('201'),Decimal('301'))
        self.assertGreater((quantity+Decimal('0.001'))*Decimal('201'),Decimal('301'))

    def test_long_and_short_capped_partial_then_full_exit_keep_exact_pnl(self):
        from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
        for short in (False,True):
            with self.subTest(short=short):
                self.setUp()
                self.book=book(crypto_max_order_notional_minor=300,crypto_max_position_notional_minor=300)
                self.order('2',side='SELL' if short else 'BUY',price=1.0);self.mark(2.0)
                quantity=capped_exit_quantity(self.book,IID,Decimal('2'))
                self.assertEqual(quantity,Decimal('1.5'))
                self.assertEqual(self.order(str(quantity),side='BUY' if short else 'SELL',price=2.0)['order']['state'],'FILLED')
                self.assertEqual(abs(Decimal(self.book.project_positions()[0]['quantity'])),Decimal('0.5'))
                self.assertEqual(self.order('0.5',side='BUY' if short else 'SELL',price=2.0)['order']['state'],'FILLED')
                self.assertEqual(self.book.project_positions(),[])
                self.assertEqual(self.book.project_account()['cash_minor'],99_800 if short else 100_200)

    def test_price_increase_after_capped_sizing_is_rejected_without_extra_fill(self):
        from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
        self.book=book(crypto_max_order_notional_minor=300,crypto_max_position_notional_minor=300)
        self.order('2',price=1.0);self.mark(2.0)
        quantity=capped_exit_quantity(self.book,IID,Decimal('2'))
        cash=self.book.project_account()['cash_minor'];positions=self.book.project_positions()
        result=self.order(str(quantity),side='BUY',price=2.1)
        self.assertIsNone(result['fill'])
        self.assertEqual(result['order']['reason_codes'],['SIM_RISK_NOT_APPROVED'])
        self.assertEqual(result['decision'],'REJECT')
        decision=next(e['payload']['decision'] for e in reversed(self.book.events) if e['event_type']=='RiskDecisionRecorded')
        self.assertIn('RISK_MAX_ORDER_NOTIONAL_EXCEEDED',decision['reason_codes'])
        self.assertEqual(self.book.project_account()['cash_minor'],cash)
        self.assertEqual(self.book.project_positions(),positions)

    def test_sub_minimum_capped_exit_cannot_submit_or_invent_a_fill(self):
        from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
        self.book=book(crypto_max_order_notional_minor=300,crypto_max_position_notional_minor=300)
        self.order('2',price=1.0);self.mark(4000)
        quantity=capped_exit_quantity(self.book,IID,Decimal('2'))
        self.assertEqual(quantity,Decimal('0.000'))
        cash=self.book.project_account()['cash_minor']
        with self.assertRaisesRegex(ValueError,'ORDER_QUANTITY'):
            self.order(str(quantity),side='BUY',price=4000)
        self.assertEqual(self.book.project_account()['cash_minor'],cash)
        self.assertEqual(self.book.project_positions()[0]['quantity'],'-2')

    def test_borrow_across_dates_and_partial_cover_never_double_charges(self):
        self.order('1.5');self.mark(2)
        first=self.book.accrue_short_borrow_fees(accrual_date='2026-10-28',as_of_ns=200*S)
        self.assertEqual(first[0]['payload']['fee_minor'],1)
        self.order('0.5',side='BUY',price=1.0);self.mark(2)
        self.assertEqual(self.book.accrue_short_borrow_fees(accrual_date='2026-10-28',as_of_ns=210*S),[])
        second=self.book.accrue_short_borrow_fees(accrual_date='2026-10-29',as_of_ns=220*S)
        self.assertEqual((second[0]['payload']['quantity'],second[0]['payload']['fee_minor']),('-1',1))
        with self.assertRaisesRegex(ValueError,'POSITION_REVERSAL_NOT_ALLOWED'):
            self.order('1.001',side='BUY',price=1.0)
        self.order('1',side='BUY',price=1.0)
        self.assertEqual(self.book.accrue_short_borrow_fees(accrual_date='2026-10-30',as_of_ns=230*S),[])
        self.assertEqual(self.book.project_account()['cash_minor'],100_148)

    def test_capped_long_and_short_exits_preserve_a_tradable_remainder(self):
        from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
        for short in (False,True):
            with self.subTest(short=short):
                self.setUp()
                self.book=book(crypto_max_order_notional_minor=300,crypto_max_position_notional_minor=300)
                self.order('1.6',side='SELL' if short else 'BUY',price=1.0);self.mark(2.0)
                quantity=capped_exit_quantity(self.book,IID,Decimal('1.6'))
                self.assertEqual(quantity,Decimal('1.345'))  # $0.50 + 2% buffer
                self.assertEqual(self.order(str(quantity),side='BUY' if short else 'SELL',price=2.0)['order']['state'],'FILLED')
                self.assertEqual(abs(Decimal(self.book.project_positions()[0]['quantity'])),Decimal('0.255'))
                self.assertEqual(self.order('0.255',side='BUY' if short else 'SELL',price=2.0)['order']['state'],'FILLED')
                self.assertEqual(self.book.project_positions(),[])
                self.assertEqual(self.book.project_account()['cash_minor'],99_840 if short else 100_160)

    def test_capped_exit_without_a_legal_two_order_partition_fails_closed(self):
        from market_platform_foundation.ui_api.screener_action import capped_exit_quantity
        self.book=book(crypto_max_order_notional_minor=300,crypto_max_position_notional_minor=300)
        self.instrument=dict(self.instrument,minimum_quantity='1.1')
        self.order('2',price=1.0);self.mark(2.0)
        quantity=capped_exit_quantity(self.book,IID,Decimal('2'))
        self.assertEqual(quantity,Decimal('0'))
        before=list(self.book.events)
        with self.assertRaisesRegex(ValueError,'ORDER_QUANTITY'):
            self.order(str(quantity),side='BUY',price=2.0)
        self.assertEqual(self.book.events,before)


if __name__=='__main__':unittest.main()

import unittest
from dataclasses import replace
from market_platform_foundation.intelligence.production.live_feature_corpus import RollingEventWindow, compute_decision, settle
from market_platform_foundation.market_data.provider_time import event_time_ns_from_payload, parse_provider_datetime_ns
from tests.intelligence.test_live_feature_corpus import populated_window, HORIZON
from tests.intelligence.test_signal_fixtures import INSTRUMENT, ONE_SEC, T, quote_event, trade_event

class CorpusSourceFreshnessTests(unittest.TestCase):
    def test_actual_ingress_preserves_unknown_source_clock(self):
        from market_platform_foundation.intelligence.observation_ingress.live_observation_dispatch import normalize_admitted_live_observation
        from market_platform_foundation.intelligence.production.live_feature_corpus import _source_reason
        record=dict(provider='moomoo',capability='US_EQUITY_L1',instrument_id='AAPL',provider_symbol='US.AAPL',sequence=1,
                    clocks=dict(event_time_ns=T,provider_time_ns=T,received_time_ns=T),source_time_basis='RECEIPT_FALLBACK',
                    raw_payload=dict(bid_price=100,ask_price=100.1,bid_vol=1,ask_vol=1))
        event=normalize_admitted_live_observation(record).event
        self.assertEqual(event.metadata['source_time_basis'],'RECEIPT_FALLBACK')
        self.assertEqual(_source_reason(event,5*ONE_SEC),'SOURCE_CLOCK_UNVERIFIED')

    def test_recent_receipt_does_not_make_old_reference_current(self):
        window=populated_window(until_ns=T-ONE_SEC)
        window.dispatch(quote_event('old-reference',event_time_ns=T-600*ONE_SEC,available_time_ns=T))
        row=compute_decision(window,INSTRUMENT,T)
        self.assertFalse(row['accepted'])
        self.assertEqual(row['reason'],'REFERENCE_SOURCE_STALE')

    def test_stale_trade_in_feature_window_refuses_decision(self):
        window=populated_window(until_ns=T)
        window.dispatch(trade_event('old-trade',event_time_ns=T-600*ONE_SEC,available_time_ns=T-ONE_SEC,price=200,quantity=100,aggressor_side='BUY'))
        row=compute_decision(window,INSTRUMENT,T)
        self.assertFalse(row['accepted'])
        self.assertEqual(row['reason'],'SOURCE_EVENT_STALE')

    def test_unverified_receipt_clock_is_not_a_source_clock(self):
        window=populated_window(until_ns=T-ONE_SEC)
        event=replace(quote_event('unknown-clock',event_time_ns=T),metadata={'source_time_basis':'RECEIPT_FALLBACK'})
        window.dispatch(event)
        row=compute_decision(window,INSTRUMENT,T)
        self.assertFalse(row['accepted'])
        self.assertEqual(row['reason'],'SOURCE_CLOCK_UNVERIFIED')

    def test_stale_terminal_quote_never_becomes_a_settled_label(self):
        window=populated_window(until_ns=T)
        row=compute_decision(window,INSTRUMENT,T)
        due=T+HORIZON
        window.dispatch(quote_event('stale-terminal',event_time_ns=T-600*ONE_SEC,available_time_ns=due,bid=200,ask=200.1))
        label=settle(window,row,now_ns=due+61*ONE_SEC,horizon_ns=HORIZON)
        self.assertEqual(label['status'],'UNLABELABLE')

    def test_terminal_label_waits_for_its_actual_availability(self):
        window=populated_window(until_ns=T)
        row=compute_decision(window,INSTRUMENT,T)
        due=T+HORIZON
        window.dispatch(quote_event('future-terminal',event_time_ns=due+ONE_SEC,available_time_ns=due+ONE_SEC,bid=110,ask=110.1))
        self.assertIsNone(settle(window,row,now_ns=due,horizon_ns=HORIZON))
        self.assertEqual(settle(window,row,now_ns=due+ONE_SEC,horizon_ns=HORIZON)['status'],'SETTLED')

    def test_valid_terminal_after_stale_one_is_used_with_original_clocks(self):
        window=populated_window(until_ns=T)
        row=compute_decision(window,INSTRUMENT,T)
        due=T+HORIZON
        window.dispatch(quote_event('stale-terminal',event_time_ns=T-600*ONE_SEC,available_time_ns=due,bid=200,ask=200.1))
        window.dispatch(quote_event('fresh-terminal',event_time_ns=due+ONE_SEC,available_time_ns=due+2*ONE_SEC,bid=110,ask=110.1))
        label=settle(window,row,now_ns=due+3*ONE_SEC,horizon_ns=HORIZON)
        self.assertEqual(label['terminal_event_id'],'fresh-terminal')
        self.assertEqual(label['terminal_event_time_ns'],due+ONE_SEC)
        self.assertEqual(label['label_available_time_ns'],due+2*ONE_SEC)

    def test_regular_quote_push_uses_its_provider_date_and_time(self):
        received=parse_provider_datetime_ns('2026-10-14 10:16:29')
        source=parse_provider_datetime_ns('2026-10-14 10:05:00.780')
        payload={'data_date':'2026-10-14','data_time':'10:05:00.780','last_price':345.47}
        self.assertEqual(event_time_ns_from_payload(payload,received_ns=received,quote_trade_time=True),source)

    def test_extended_hours_does_not_relabel_regular_close_as_current(self):
        received=parse_provider_datetime_ns('2026-10-14 18:00:00')
        payload={'data_date':'2026-10-14','data_time':'16:00:00','last_price':345,'after_price':346}
        self.assertEqual(event_time_ns_from_payload(payload,received_ns=received,quote_trade_time=True),received)

    def test_valid_input_retains_source_and_receipt_clocks(self):
        row=compute_decision(populated_window(until_ns=T),INSTRUMENT,T)
        self.assertTrue(row['accepted'])
        self.assertEqual(row['reference']['event_time_ns'],T)
        self.assertEqual(row['reference']['received_time_ns'],T)

if __name__=='__main__':unittest.main()

"""Bounded quote-only SPY transport using SDK doubles; no network."""
import unittest
from types import SimpleNamespace
from tools.moomoo.opend_quote_transport import fetch_spy_performance_day
from market_platform_foundation.evaluation.performance_calendar import session_bounds, NS
from datetime import date

class Context:
    def __init__(self):
        self.closed=False;self.calls=[];self.actions=[];self.page=None;self.ret=0
    def request_history_kline(self,code,**kwargs):
        self.calls.append((code,kwargs))
        return self.ret,[dict(code="US.SPY",time_key="2026-10-27 00:00:00",open=100,close=101)],self.page
    def get_rehab(self,code):
        return self.ret,self.actions
    def close(self): self.closed=True
    def set_sync_query_connect_timeout(self,value): self.timeout=value

class BenchmarkTransportTests(unittest.TestCase):
    def sdk(self,ctx):
        return SimpleNamespace(RET_OK=0,KLType=SimpleNamespace(K_DAY="DAY"),
            AuType=SimpleNamespace(NONE="RAW"),OpenQuoteContext=lambda **_:ctx)

    def fetch(self,ctx,**kwargs):
        return fetch_spy_performance_day("2026-10-27",sdk=self.sdk(ctx),enabled=True,
            as_of_ns=session_bounds(date(2026,10,27))[1]+NS,**kwargs)

    def test_raw_spy_only_bounded_and_closes(self):
        ctx=Context()
        result=self.fetch(ctx)
        self.assertTrue(result["ready"])
        self.assertEqual(result["bar"]["close"],"101")
        self.assertEqual(ctx.calls[0][0],"US.SPY")
        self.assertEqual(ctx.calls[0][1]["autype"],"RAW")
        self.assertTrue(ctx.closed)
        self.assertTrue(ctx.timeout>0)
        self.assertIn("raw",result)


    def test_malformed_adjustment_response_cannot_mean_no_dividends(self):
        ctx=Context();ctx.actions="malformed"
        self.assertFalse(self.fetch(ctx)["ready"])


    def test_missing_nonfinite_adjustments_are_not_verified_no_actions(self):
        for action in (
            dict(ex_div_date="2026-10-27"),
            dict(ex_div_date="2026-10-27",per_cash_div=float("nan"),split_ratio=None),
            dict(ex_div_date="2026-10-27",per_cash_div=0,split_ratio=float("inf")),
            dict(ex_div_date="2026-10-27",per_cash_div=None,split_ratio=None),
        ):
            with self.subTest(action=action):
                ctx=Context();ctx.actions=[action]
                self.assertFalse(self.fetch(ctx)["ready"])

    def test_exact_reverse_split_cannot_turn_a_spy_tie_into_a_pass(self):
        from market_platform_foundation.evaluation.performance_benchmark import total_return
        from market_platform_foundation.evaluation.paper_performance import verdict
        ctx=Context()
        ctx.actions=[dict(ex_div_date="2026-10-27",per_cash_div=0,split_ratio=3)]
        actions=self.fetch(ctx)["actions"]
        bars=[dict(date="2026-10-26",open="100",close="100"),dict(date="2026-10-27",open="300",close="303")]
        change=total_return(bars,actions,actions_complete=True)[-1]["return_ratio"]
        self.assertEqual(change,["1","100"])
        self.assertEqual(verdict(day=20,initial=100,equity=101,completed=30,
            spy_return=change,due=True,reasons=[])["status"],"Fail")


    def test_nonfinite_other_action_and_exact_split_pair(self):
        from market_platform_foundation.evaluation.performance_benchmark import total_return
        ctx=Context()
        ctx.actions=[dict(ex_div_date="2026-10-27",per_cash_div=1,split_ratio=None,spin_off_ratio=float("inf"))]
        self.assertFalse(self.fetch(ctx)["ready"])
        ctx.actions=[dict(ex_div_date="2026-10-27",per_cash_div=0,split_ratio=1/3,split_base=1,split_ert=3)]
        actions=self.fetch(ctx)["actions"]
        bars=[dict(date="2026-10-26",open="300",close="300"),dict(date="2026-10-27",open="100",close="101")]
        self.assertEqual(total_return(bars,actions,actions_complete=True)[-1]["return_ratio"],["1","100"])

    def test_dividend_and_split_are_explicit_not_adjusted_prices(self):
        ctx=Context()
        ctx.actions=[dict(ex_div_date="2026-10-27",per_cash_div=1,split_ratio=None)]
        self.assertEqual(self.fetch(ctx)["actions"][0]["cash_dividend"],"1")
        ctx.actions=[dict(ex_div_date="2026-10-27",per_cash_div=0,split_ratio=0.5)]
        self.assertEqual(self.fetch(ctx)["actions"][0]["share_multiplier"],"2")

    def test_unentitled_truncated_unsupported_and_gate_fail_closed(self):
        ctx=Context();ctx.ret=-1
        self.assertFalse(self.fetch(ctx)["ready"])
        ctx=Context();ctx.page="continuation"
        self.assertFalse(self.fetch(ctx)["ready"])
        ctx=Context();ctx.actions=[dict(ex_div_date="2026-10-27",per_cash_div=0,split_ratio=None,spin_off_ratio=1)]
        self.assertFalse(self.fetch(ctx)["ready"])
        ctx=Context()
        result=fetch_spy_performance_day("2026-10-27",sdk=self.sdk(ctx),enabled=False)
        self.assertFalse(result["ready"]);self.assertEqual(ctx.calls,[])
        self.assertFalse(self.fetch(Context(),host="example.com")["ready"])

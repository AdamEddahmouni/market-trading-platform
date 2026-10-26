"""Step 8: calendar, completed episodes, strict milestones, coverage and SPY."""
import unittest
from datetime import date
from decimal import Decimal
from market_platform_foundation.evaluation import paper_performance as p
from market_platform_foundation.evaluation.performance_calendar import session_bounds, sessions_after
from market_platform_foundation.evaluation.performance_benchmark import total_return

def trade(before,after,client="PAI-X",instrument="A"):
    return dict(instrument_id=instrument,position_before=str(before),position_after=str(after),client_order_id=client)

class PaperPerformanceTests(unittest.TestCase):
    def test_episodes_not_fills_and_reversal(self):
        rows=[trade(0,10),trade(10,15),trade(15,5),trade(5,0),trade(0,-3),trade(-3,2),trade(2,0)]
        self.assertEqual(p.completed_trades(rows)["completed"],3)
        self.assertEqual(p.completed_trades(rows[:3])["completed"],0)
        self.assertFalse(p.completed_trades(rows)["mixed"])
        self.assertTrue(p.completed_trades([trade(0,1,"manual")])["mixed"])

    def test_strict_unrounded_thresholds_and_independent_day20(self):
        def verdict(day=20,initial=100,equity=102,completed=30,spy_return="0.01",due=True,reasons=None):
            return p.verdict(day=day,initial=initial,equity=equity,completed=completed,
                             spy_return=spy_return,due=due,reasons=reasons or [])
        self.assertEqual(verdict()["status"],"Pass")
        self.assertEqual(verdict(day=10,equity=100)["status"],"Fail")
        self.assertEqual(verdict(completed=29)["status"],"Fail")
        self.assertEqual(verdict(initial=10000000,equity=10000001,spy_return="0.0000001")["status"],"Fail")
        self.assertEqual(verdict(day=10,equity=101,spy_return=None)["status"],"Pass")
        self.assertEqual(verdict(due=False,equity=None,spy_return=None)["status"],"Not due")
        for reason in ("MANUAL_FILLS","CONFIGURATION_CHANGED","COVERAGE_GAP"):
            self.assertEqual(verdict(reasons=[reason])["status"],"Cannot determine")
        self.assertEqual(verdict(spy_return=None)["status"],"Cannot determine")

    def test_coverage_requires_endpoints_and_no_large_gaps(self):
        start,end=session_bounds(date(2026,10,27))
        rows=[dict(captured_at_ns=t,quality="CURRENT",equity_minor=100) for t in range(start,end+1,60*10**9)]
        self.assertTrue(p.session_coverage(rows,start,end,benchmark_ready=True)["covered"])
        self.assertFalse(p.session_coverage(rows[:10]+rows[13:],start,end,benchmark_ready=True)["covered"])
        self.assertFalse(p.session_coverage(rows,start,end,benchmark_ready=False)["covered"])
        self.assertFalse(p.session_coverage([dict(r,quality="DEGRADED") for r in rows],start,end,benchmark_ready=True)["covered"])

    def test_both_clocks_keep_fixed_dates_and_all_returns(self):
        dates=sessions_after(date(2026,10,26),25)
        rows=[dict(session_date=d.isoformat(),covered=i!=3,equity_minor=100+i,completed_trades=35,
                   spy_return="0",reasons=[],cutoff_ns=session_bounds(d)[1]) for i,d in enumerate(dates)]
        result=p.milestones(initial=100,sessions=rows,now_ns=rows[-1]["cutoff_ns"])
        self.assertEqual(result["fixed_10"]["session_date"],dates[9].isoformat())
        self.assertEqual(result["covered_10"]["session_date"],dates[10].isoformat())
        self.assertEqual(result["covered_10"]["equity_minor"],110)
        self.assertEqual(result["fixed_10"]["status"],"Cannot determine")
        self.assertTrue(result["covered_10"]["supplemental"])
        self.assertEqual(result["fixed_20"]["session_date"],dates[19].isoformat())

    def test_calendar_holidays_dst_early_close_unknown_year(self):
        self.assertEqual(sessions_after(date(2026,11,25),2),[date(2026,11,27),date(2026,11,30)])
        start,end=session_bounds(date(2026,11,27))
        self.assertEqual(end-start,int(3.5*3600*1e9))
        self.assertEqual(session_bounds(date(2026,12,24))[1]-session_bounds(date(2026,12,24))[0],int(3.5*3600*1e9))
        self.assertEqual((session_bounds(date(2026,11,2))[0]-session_bounds(date(2026,10,30))[0])//10**9,3*86400+3600)
        with self.assertRaisesRegex(ValueError,"CALENDAR_UNAVAILABLE"):
            session_bounds(date(2027,1,4))

class TotalReturnTests(unittest.TestCase):
    def test_reinvestment_start_day_entitlement_and_split(self):
        bars=[dict(date="2026-10-27",open="100",close="100"),dict(date="2026-10-28",open="99",close="99"),
              dict(date="2026-10-29",open="100",close="100")]
        actions=[dict(date="2026-10-27",cash_dividend="5",share_multiplier="1"),
                 dict(date="2026-10-28",cash_dividend="1",share_multiplier="1")]
        values=total_return(bars,actions,actions_complete=True)
        self.assertEqual(Decimal(values[0]["return"]),0)
        self.assertEqual(Decimal(values[1]["return"]),0)
        self.assertAlmostEqual(float(values[2]["return"]),1/99)
        bars[1]=dict(bars[1],open="50",close="50")
        values=total_return(bars[:2],[dict(date="2026-10-28",cash_dividend="0",share_multiplier="2")],actions_complete=True)
        self.assertEqual(Decimal(values[-1]["return"]),0)

    def test_missing_unsupported_duplicate_and_invalid_data(self):
        bars=[dict(date="2026-10-27",open="100",close="100")]
        with self.assertRaisesRegex(ValueError,"ADJUSTMENTS_UNVERIFIED"):
            total_return(bars,[],actions_complete=False)
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_CORPORATE_ACTION"):
            total_return(bars,[dict(date="2026-10-27",unsupported=True)],actions_complete=True)
        for bad in (bars+bars,[dict(bars[0],close="NaN")],[dict(bars[0],open="0")]):
            with self.assertRaises(ValueError):
                total_return(bad,[],actions_complete=True)

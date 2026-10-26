"""Pure step 8 scorecards. No store, network, clock or trading side effects."""
from decimal import Decimal
from fractions import Fraction
from .performance_calendar import NS

POLICY_VERSION="paper-performance/1.0.0"
OBSERVATION_SECONDS=60
GAP_SECONDS=120

def completed_trades(trades):
    active=set()
    completed=0
    mixed=False
    for row in trades:
        iid=str(row["instrument_id"])
        before,after=Decimal(str(row["position_before"])),Decimal(str(row["position_after"]))
        mixed |= not str(row.get("client_order_id","")).startswith("PAI-")
        if before==0 and after!=0:
            active.add(iid)
        elif before!=0 and (after==0 or before*after<0):
            if iid in active:
                completed+=1
            active.discard(iid)
            if after!=0:
                active.add(iid)
    return dict(completed=completed,mixed=bool(mixed),open_episodes=len(active))

def _fraction(value):
    if isinstance(value,(tuple,list)):
        return Fraction(int(value[0]),int(value[1]))
    return Fraction(value)

def verdict(*,day,initial,equity,completed,spy_return,due,reasons):
    reasons=list(dict.fromkeys(reasons))
    net=(Fraction(equity-initial,initial) if equity is not None and initial>0 else None)
    conditions=dict(above_start=net>0 if net is not None else None)
    if day==20:
        conditions.update(completed_30_trades=completed>=30,
                          above_spy=(net>_fraction(spy_return) if net is not None and spy_return is not None else None))
    if not due:
        status="Not due"
    elif reasons or any(v is None for v in conditions.values()):
        status="Cannot determine"
    else:
        status="Pass" if all(conditions.values()) else "Fail"
    return dict(status=status,conditions=conditions,reasons=reasons,equity_minor=equity,
                completed_trades=completed)

def session_coverage(observations,start,end,*,benchmark_ready):
    rows=sorted((r for r in observations if start<=int(r["captured_at_ns"])<=end+60*NS
                 and not r.get("reconstructed",False)),key=lambda r:r["captured_at_ns"])
    valid=[r for r in rows if r.get("quality")=="CURRENT" and r.get("equity_minor") is not None]
    reasons=[]
    if not benchmark_ready:
        reasons.append("BENCHMARK_UNAVAILABLE")
    if len(valid)!=len(rows):
        reasons.append("INCOMPLETE_VALUATION")
    if not valid or int(valid[0]["captured_at_ns"])-start>60*NS:
        reasons.append("OPEN_NOT_OBSERVED")
    if not valid or abs(int(valid[-1]["captured_at_ns"])-end)>60*NS:
        reasons.append("CLOSE_NOT_OBSERVED")
    gaps=[]
    points=[start]+[min(end,int(r["captured_at_ns"])) for r in valid]+[end]
    for a,b in zip(points,points[1:]):
        if b-a>GAP_SECONDS*NS:
            gaps.append(dict(start_ns=a,end_ns=b,seconds=(b-a)//NS))
    if gaps:
        reasons.append("COVERAGE_GAP")
    return dict(covered=not reasons,reasons=reasons,gaps=gaps,observations=len(rows))

def milestones(*,initial,sessions,now_ns):
    result={}
    completed=[r for r in sessions if r["cutoff_ns"]<=now_ns]
    for clock in ("fixed","covered"):
        for day in (10,20):
            candidates=sessions if clock=="fixed" else [r for r in completed if r["covered"]]
            row=candidates[day-1] if len(candidates)>=day else None
            due=row is not None and row["cutoff_ns"]<=now_ns
            prefix=[r for r in completed if row is None or r["cutoff_ns"]<=row["cutoff_ns"]]
            reasons=[reason for r in prefix for reason in r.get("reasons",[])]
            if any(not r["covered"] for r in prefix):
                reasons.append("COVERAGE_GAP")
            record=verdict(day=day,initial=initial,equity=row.get("equity_minor") if row else None,
                           completed=row.get("completed_trades",0) if row else 0,
                           spy_return=row.get("spy_return") if row else None,due=due,reasons=reasons)
            record.update(clock=clock,day=day,session_date=row["session_date"] if row else None,
                          cutoff_ns=row["cutoff_ns"] if row else None,supplemental=clock=="covered")
            result[f"{clock}_{day}"]=record
    return result

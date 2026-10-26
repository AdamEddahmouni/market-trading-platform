"""Exact fractional-share SPY total return; raw prices, explicit distributions."""
from decimal import Decimal, localcontext
from fractions import Fraction
from datetime import date

def ratio(value) -> Fraction:
    try:
        dec=Decimal(str(value))
        if not dec.is_finite():
            raise ValueError("NONFINITE_BENCHMARK_VALUE")
        return Fraction(dec)
    except (ArithmeticError,TypeError,ValueError) as exc:
        raise ValueError("INVALID_BENCHMARK_VALUE") from exc

def decimal_string(value: Fraction) -> str:
    with localcontext() as ctx:
        ctx.prec=60
        return str(Decimal(value.numerator)/Decimal(value.denominator))

def total_return(bars, actions, *, actions_complete):
    if not actions_complete:
        raise ValueError("ADJUSTMENTS_UNVERIFIED")
    if not bars:
        raise ValueError("BENCHMARK_PRICES_MISSING")
    dates=[str(b["date"]) for b in bars]
    if dates!=sorted(set(dates)):
        raise ValueError("BENCHMARK_DATES_INVALID")
    for day in dates:
        date.fromisoformat(day)
    grouped={}
    for action in actions:
        if action.get("unsupported"):
            raise ValueError("UNSUPPORTED_CORPORATE_ACTION")
        day=str(action["date"])
        if day in grouped:
            raise ValueError("DUPLICATE_CORPORATE_ACTION")
        cash=ratio(action.get("cash_dividend","0"))
        try:
            pair=action.get("share_multiplier_ratio")
            split=Fraction(int(pair[0]),int(pair[1])) if pair is not None else ratio(action.get("share_multiplier","1"))
        except (ValueError,TypeError,IndexError,ZeroDivisionError) as exc:
            raise ValueError("INVALID_CORPORATE_ACTION") from exc
        if cash<0 or split<=0:
            raise ValueError("INVALID_CORPORATE_ACTION")
        # The provider does not establish per-share dividend basis for simultaneous
        # split/dividend events. Do not guess the ordering.
        if cash and split!=1:
            raise ValueError("UNSUPPORTED_CORPORATE_ACTION")
        grouped[day]=(cash,split)
    start=ratio(bars[0]["open"])
    if start<=0:
        raise ValueError("BENCHMARK_PRICE_INVALID")
    shares=1/start
    result=[]
    for index,bar in enumerate(bars):
        opening,closing=ratio(bar["open"]),ratio(bar["close"])
        if opening<=0 or closing<=0:
            raise ValueError("BENCHMARK_PRICE_INVALID")
        dividend,split=grouped.get(str(bar["date"]),(Fraction(0),Fraction(1)))
        if index:
            # Entitlement is based on shares held before the ex-date.
            cash=shares*dividend
            shares=shares*split+cash/closing
        value=shares*closing
        change=value-1
        result.append(dict(session_date=bar["date"],return_ratio=[str(change.numerator),str(change.denominator)],
                           **{"return":decimal_string(change),"growth":decimal_string(value)}))
    return result

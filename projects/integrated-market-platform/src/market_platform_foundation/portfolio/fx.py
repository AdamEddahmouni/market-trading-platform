"""Explicit FX conversion boundary for base-currency portfolio aggregation (G2).

The portfolio never sums currencies blindly: ``USD 100 + EUR 100`` is never
reported as ``USD 200``. Every conversion carries its rate, provider,
source time, and freshness; a missing or stale rate makes the aggregate
explicitly incomplete instead of falling back to 1:1 or silently dropping
the amount.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .canonical import (
    CashBalance,
    PortfolioError,
    PortfolioErrorCode,
    PortfolioPosition,
    ValuationStatus,
    _as_decimal,
)


@dataclass(frozen=True, slots=True)
class FxRate:
    """One explicit FX observation: source currency -> target currency."""

    source_currency: str
    target_currency: str
    rate: Decimal
    provider: str = "UNKNOWN"
    source_time_ns: int = 0
    observed_at_ns: int = 0
    fresh: bool = True

    def __post_init__(self) -> None:
        source = str(self.source_currency).upper()
        target = str(self.target_currency).upper()
        if not source or not target:
            raise PortfolioError(PortfolioErrorCode.INVALID_CURRENCY, "currency required", {})
        if source == target:
            raise PortfolioError(
                PortfolioErrorCode.INVALID_CURRENCY,
                "source and target currencies must differ",
                {"source": source, "target": target},
            )
        rate = _as_decimal(self.rate, field_name="rate")
        if rate <= 0:
            raise PortfolioError(
                PortfolioErrorCode.INVALID_DECIMAL,
                "fx rate must be positive",
                {"rate": str(rate)},
            )
        object.__setattr__(self, "source_currency", source)
        object.__setattr__(self, "target_currency", target)
        object.__setattr__(self, "rate", rate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_currency": self.source_currency,
            "target_currency": self.target_currency,
            "rate": format(self.rate, "f"),
            "provider": self.provider,
            "source_time_ns": self.source_time_ns,
            "observed_at_ns": self.observed_at_ns,
            "fresh": self.fresh,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FxRate":
        return cls(
            source_currency=str(payload["source_currency"]),
            target_currency=str(payload["target_currency"]),
            rate=_as_decimal(payload["rate"], field_name="rate"),
            provider=str(payload.get("provider", "UNKNOWN")),
            source_time_ns=int(payload.get("source_time_ns", 0)),
            observed_at_ns=int(payload.get("observed_at_ns", 0)),
            fresh=bool(payload.get("fresh", True)),
        )


@dataclass(frozen=True, slots=True)
class FxFactsBundle:
    """A set of explicit FX observations for one aggregation run."""

    facts: dict[tuple[str, str], FxRate]

    def __init__(self, facts: Iterable[FxRate] = ()) -> None:
        normalized: dict[tuple[str, str], FxRate] = {}
        for rate in facts:
            normalized[(rate.source_currency, rate.target_currency)] = rate
        object.__setattr__(self, "facts", normalized)

    def __iter__(self):
        return iter(self.facts.values())

    def __len__(self) -> int:
        return len(self.facts)

    def get(self, source: str, target: str) -> FxRate | None:
        return self.facts.get((str(source).upper(), str(target).upper()))


def convert(
    amount: Decimal,
    *,
    source_currency: str,
    target_currency: str,
    rate: FxRate | None = None,
    facts: FxFactsBundle | None = None,
) -> tuple[Decimal, FxRate | None]:
    """Convert ``amount`` from source to target using an explicit rate.

    The rate may be supplied directly or looked up in ``facts``. When only the
    inverse pair is known (target->source), the inverse rate is derived by
    exact Decimal division and the resulting ``FxRate`` is returned with the
    original provenance. Missing rates raise ``MISSING_FX`` — there is never a
    1:1 fallback and never an invented rate.
    """
    source = str(source_currency).upper()
    target = str(target_currency).upper()
    if source == target:
        # Identity conversion needs no rate; None marks "already in target".
        return _as_decimal(amount, field_name="amount"), None
    effective = rate
    if effective is None and facts is not None:
        effective = facts.get(source, target)
    if effective is None and facts is not None:
        inverse = facts.get(target, source)
        if inverse is not None:
            effective = FxRate(
                source_currency=source,
                target_currency=target,
                rate=Decimal("1") / inverse.rate,
                provider=f"{inverse.provider}.INVERTED",
                source_time_ns=inverse.source_time_ns,
                observed_at_ns=inverse.observed_at_ns,
                fresh=inverse.fresh,
            )
    if effective is None:
        raise PortfolioError(
            PortfolioErrorCode.MISSING_FX,
            f"no explicit FX rate for {source}->{target}",
            {"source_currency": source, "target_currency": target},
        )
    if effective.source_currency != source or effective.target_currency != target:
        raise PortfolioError(
            PortfolioErrorCode.MISSING_FX,
            "fx rate pair does not match conversion direction",
            {
                "rate_pair": f"{effective.source_currency}->{effective.target_currency}",
                "requested_pair": f"{source}->{target}",
            },
        )
    amount_dec = _as_decimal(amount, field_name="amount")
    converted = amount_dec * effective.rate
    return converted, effective


def aggregate_to_base(
    *,
    positions: tuple[PortfolioPosition, ...],
    cash_balances: tuple[CashBalance, ...],
    native_totals: Mapping[str, Decimal],
    base_currency: str,
    fx_facts: Mapping[tuple[str, str], FxRate] | None = None,
) -> tuple[dict[str, Decimal], ValuationStatus]:
    """Aggregate native totals into ``base_currency`` with explicit FX.

    Returns ``(base_totals, valuation_status)``:

    - COMPLETE: every currency in ``native_totals`` converted with a fresh rate.
    - PARTIAL: at least one currency converted, at least one missing/stale.
    - MISSING_FX: no conversion was possible for some currency.

    Currencies are never dropped silently and never summed without a rate;
    a missing rate is reported through the status, not hidden.
    """
    base = str(base_currency).upper()
    bundle = FxFactsBundle(fx_facts.values() if fx_facts is not None else ())
    converted_total = Decimal("0")
    unconverted: list[str] = []
    stale_currencies: list[str] = []
    converted_currencies: list[str] = []

    # Cash is aggregated by currency first, then converted once per currency.
    for currency, amount in sorted(native_totals.items()):
        currency = str(currency).upper()
        if currency == base:
            converted_total += amount
            converted_currencies.append(currency)
            continue
        try:
            converted, rate = convert(
                amount,
                source_currency=currency,
                target_currency=base,
                facts=bundle,
            )
        except PortfolioError:
            unconverted.append(currency)
            continue
        converted_total += converted
        converted_currencies.append(currency)
        if not rate.fresh:
            stale_currencies.append(currency)

    if unconverted:
        status = ValuationStatus.MISSING_FX
    elif stale_currencies:
        status = ValuationStatus.STALE
    elif converted_currencies:
        status = ValuationStatus.COMPLETE
    else:
        status = ValuationStatus.COMPLETE

    base_totals = {base: converted_total}
    return base_totals, status


def cash_to_base(
    cash_balances: Iterable[CashBalance],
    *,
    base_currency: str,
    fx_facts: Mapping[tuple[str, str], FxRate] | None = None,
) -> tuple[dict[str, Decimal], ValuationStatus]:
    """Aggregate per-currency cash into the base currency (test-friendly helper)."""
    totals: dict[str, Decimal] = {}
    for balance in cash_balances:
        totals[balance.currency] = totals.get(balance.currency, Decimal("0")) + balance.settled
    return aggregate_to_base(
        positions=(),
        cash_balances=tuple(cash_balances),
        native_totals=totals,
        base_currency=base_currency,
        fx_facts=fx_facts,
    )


__all__ = [
    "FxFactsBundle",
    "FxRate",
    "aggregate_to_base",
    "cash_to_base",
    "convert",
]
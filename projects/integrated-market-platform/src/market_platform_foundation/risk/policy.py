"""Preregistered risk policy specification."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

POLICY_VERSION = "phase7.bar-conservative/1.0.0"
SHORT_POLICY_VERSION = "paper-equity-short/1.0.0"

# Paper-only equity/ETF short selling (owner decision 2, 2026-10-23; 50% initial margin chosen 2026-10-25).
# A policy that does not allow shorts carries none of these keys, so every existing policy keeps its exact
# body and identity hash. Allowing shorts is a content change and yields a new hash, as it must.
SHORT_POLICY_DEFAULTS = dict(
    short_initial_margin_bps=5000,        # Reg T style: proceeds held plus 50% of the short's value
    short_maintenance_margin_bps=3000,    # equity must stay at or above 30% of open short value
    short_borrow_fee_bps_per_year=50,     # simulated easy-to-borrow fee, charged on shorts held over the close
    short_min_price_minor=500,            # no shorts below $5.00
    short_ssr_drop_bps=1000,              # no new shorts in a name down 10% or more on the day
)


def build_risk_policy(
    *,
    max_position_shares: int = 500,
    max_order_shares: int = 100,
    max_open_orders: int = 3,
    participation_cap_numerator: int = 1,
    participation_cap_denominator: int = 100,
    commission_minor_per_share: int = 0,
    fee_minor_per_order: int = 0,
    initial_cash_minor: int = 1_000_000_00,
    currency: str = "USD",
    price_scale: int = 100,
    allow_short: bool = False,
    **short_terms: int,
) -> dict[str, Any]:
    if set(short_terms) - set(SHORT_POLICY_DEFAULTS):
        raise TypeError("unknown short policy terms: " + ",".join(sorted(set(short_terms) - set(SHORT_POLICY_DEFAULTS))))
    if short_terms and not allow_short:
        raise ValueError("SHORT_TERMS_WITHOUT_ALLOW_SHORT")
    body = {
        "commission_minor_per_share": commission_minor_per_share,
        "currency": currency,
        "fee_minor_per_order": fee_minor_per_order,
        "initial_cash_minor": initial_cash_minor,
        "max_open_orders": max_open_orders,
        "max_order_shares": max_order_shares,
        "max_position_shares": max_position_shares,
        "participation_cap_denominator": participation_cap_denominator,
        "participation_cap_numerator": participation_cap_numerator,
        "policy_version": POLICY_VERSION,
        "price_scale": price_scale,
    }
    if allow_short:
        terms = {**SHORT_POLICY_DEFAULTS, **short_terms}
        if any(type(value) is not int or value < 0 for value in terms.values()):
            raise ValueError("SHORT_POLICY_TERM_INVALID")
        body.update(allow_short=True, short_policy_version=SHORT_POLICY_VERSION, **terms)
    return {
        **body,
        "risk_policy_identity_hash": sha256_bytes(canonical_bytes(body)),
    }


DEFAULT_RISK_POLICY = build_risk_policy()

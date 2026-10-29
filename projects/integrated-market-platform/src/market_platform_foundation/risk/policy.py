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

# Paper-only crypto notional caps (owner decision 5, draft 2026-10-28). The share caps are whole-share equity
# limits; a spot pair is bounded by dollars instead. A policy without these keys keeps its exact body and hash and
# applies the share caps to CRYPTO_PAIR as before; choosing them is a content change and yields a new account.
CRYPTO_CAPS_VERSION = "paper-crypto-notional-caps/1.0.0"
CRYPTO_CAP_TERMS = ("crypto_max_order_notional_minor", "crypto_max_position_notional_minor")

# Paper-only spot-crypto short selling (owner decision 3, draft 2026-10-28). Requires the equity short terms (the
# margin book, maintenance cover and borrow accrual are shared) and adds its own, stricter, crypto terms. There is no
# borrow market behind this: the simulator lends any pair at any size (SIMULATED_EASY_TO_BORROW).
CRYPTO_SHORT_POLICY_VERSION = "paper-crypto-short/1.0.0"
CRYPTO_SHORT_POLICY_DEFAULTS = dict(
    crypto_short_initial_margin_bps=10000,       # proceeds held plus 100% of the short's value: no leverage
    crypto_short_maintenance_margin_bps=5000,    # account equity must stay at or above 50% of open crypto short value
    crypto_short_borrow_fee_bps_per_year=4380,   # illustrative simulated annual rate, accrued daily; not a venue quote
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
    crypto_max_order_notional_minor: int | None = None,
    crypto_max_position_notional_minor: int | None = None,
    allow_crypto_short: bool = False,
    **short_terms: int,
) -> dict[str, Any]:
    if type(allow_crypto_short) is not bool:
        raise ValueError("CRYPTO_SHORT_FLAG_INVALID")
    known = set(SHORT_POLICY_DEFAULTS) | set(CRYPTO_SHORT_POLICY_DEFAULTS)
    if set(short_terms) - known:
        raise TypeError("unknown short policy terms: " + ",".join(sorted(set(short_terms) - known)))
    crypto_terms = {key: short_terms.pop(key) for key in list(short_terms) if key in CRYPTO_SHORT_POLICY_DEFAULTS}
    if short_terms and not allow_short:
        raise ValueError("SHORT_TERMS_WITHOUT_ALLOW_SHORT")
    if (allow_crypto_short or crypto_terms) and not allow_short:
        raise ValueError("CRYPTO_SHORT_REQUIRES_ALLOW_SHORT")
    if crypto_terms and not allow_crypto_short:
        raise ValueError("CRYPTO_SHORT_TERMS_WITHOUT_ALLOW_CRYPTO_SHORT")
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
    caps = (crypto_max_order_notional_minor, crypto_max_position_notional_minor)
    if any(value is not None for value in caps):
        if any(type(value) is not int or value <= 0 for value in caps):
            raise ValueError("CRYPTO_CAP_TERM_INVALID")
        body.update(crypto_caps_version=CRYPTO_CAPS_VERSION, **dict(zip(CRYPTO_CAP_TERMS, caps)))
    if allow_crypto_short:
        terms = {**CRYPTO_SHORT_POLICY_DEFAULTS, **crypto_terms}
        if any(type(value) is not int or value < 0 for value in terms.values()):
            raise ValueError("SHORT_POLICY_TERM_INVALID")
        body.update(allow_crypto_short=True, crypto_short_policy_version=CRYPTO_SHORT_POLICY_VERSION, **terms)
    return {
        **body,
        "risk_policy_identity_hash": sha256_bytes(canonical_bytes(body)),
    }


DEFAULT_RISK_POLICY = build_risk_policy()

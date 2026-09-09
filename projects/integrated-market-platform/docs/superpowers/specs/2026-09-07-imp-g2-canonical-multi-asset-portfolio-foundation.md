# IMP G2 — Canonical Multi-Asset Portfolio Foundation

| Field | Value |
|---|---|
| Document ID | `IMP-G2-PORTFOLIO` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Established | 2026-09-07 (G2 / BL-0105) |
| Prerequisite | G1 — Canonical Multi-Asset Identity Foundation (XA-01) |
| Architecture home | This document is the **single canonical home** for the multi-asset portfolio contract; other docs link here instead of duplicating it |
| Supersedes | none (new authority; legacy equity ledger remains the Paper execution parity baseline) |

This is the canonical architecture for the account-scoped, mode-scoped,
instrument-keyed portfolio truth model that later trading/risk work consumes.
G2 is not a UI goal and not a trading/risk redesign: it establishes the
portfolio/accounting/valuation foundation beneath those systems.

## 1. Mission statement

> For any IMP operational account and mode, the platform has one canonical
> portfolio truth keyed by G1 instrument identity, with explicit quantity
> units, currencies, valuation semantics, provenance, and asset-aware
> accounting — and it never silently treats Options, Futures, Crypto, Bonds,
> or multi-currency cash as though everything were ordinary USD equity shares.

## 2. Ownership and scope

**Canonical portfolio owner:** `src/market_platform_foundation/portfolio/` —
the `portfolio.canonical` model is the single authoritative portfolio state
model (BL-0105). Supporting modules:

| Module | Responsibility |
|---|---|
| `portfolio/canonical.py` | PortfolioKey, CashBalance, ValuationMark, PortfolioPosition, PortfolioSnapshot, ValuationStatus, CanonicalPortfolio store, deterministic serialization |
| `portfolio/admission.py` | Position admission gate (XA-01 tradability reuse) |
| `portfolio/valuation.py` | Asset-aware valuation dispatch + valuation context |
| `portfolio/fx.py` | Explicit FX conversion boundary + base-currency aggregation |
| `portfolio/provider_normalization.py` | Provider/broker snapshot normalization (PROVIDER_INPUT → canonical) |
| `portfolio/paper_adapter.py` | Paper ledger → canonical snapshot (dual-run, read-side only) |
| `portfolio/ledger.py` (legacy) | Fill-driven equity ledger — **parity baseline**, not the canonical multi-asset model |

Provider DTOs are `PROVIDER_INPUT`, never canonical state. UI projections are
`DERIVED_PROJECTION`, never canonical truth. There is exactly one mutable
canonical ledger; the legacy equity ledger remains only as the Paper execution
parity baseline (dual-run) until migration completes.

## 3. Operational scope

Every portfolio state is scoped by `PortfolioKey`:

```text
PortfolioKey
    account_id      (mandatory)
    mode            (mandatory: DEMO / PAPER / LIVE)
    broker          (participates only when the operational identity requires it)
    portfolio_id    (optional)
    environment     (optional)
```

There is no user-global singleton portfolio state. Account A + Paper can never
leak into Account B, Demo, or Live through cache, persistence, snapshot, API,
or projection.

## 4. Position key

Positions are keyed by canonical XA-01 `instrument_id` within their
operational account:

```text
(account_id, mode, instrument_id)
```

Never by ticker alone, provider symbol, display symbol, underlying symbol,
contract root, futures family, option underlying, or provider contract number.
All contract-specific dimensions (option strike/expiry, futures month, crypto
venue/pair, bond maturity) live inside the canonical identity, not in a second
ad-hoc portfolio key.

## 5. Position model

```text
PortfolioPosition
    instrument_id     canonical XA-01 id
    asset_class       XA-01 class (EQUITY / ETF_FUND / OPTION / FUTURE / CRYPTO / ...)
    instrument_kind   XA-01 kind (TRADABLE_SECURITY / OPTION_CONTRACT / FUTURE_CONTRACT / CRYPTO_PAIR / ...)
    quantity          Decimal, signed
    quantity_unit     SHARES | CONTRACTS | BASE_UNITS | FACE_VALUE
    native_currency   explicit (never implied USD)
    multiplier        Decimal, separate from quantity (options/futures)
    average_cost      optional
    cost_basis        optional (never inferred silently)
    realized_pnl_native
    price_basis       PAR_PERCENT | CURRENCY_PER_FACE_UNIT (bonds)
    valuation         PositionValuation: market_value_native, unrealized_pnl_native,
                      notional_native, reference_price, valuation_status, mark
    source_time_ns / observed_at_ns / data_status
```

Quantity units are not interchangeable: shares, contracts, base units, and
face value have distinct semantics and are enforced by the typed model.

## 6. Cash ledger

Cash is held per currency:

```text
CashBalance
    currency    (USD, EUR, GBP, JPY, CAD, CHF, AUD, USDT, ...)
    settled     (minimum required truth)
    unsettled   (optional, only where a source provides it)
    reserved    (optional)
    available   (optional)
```

Currencies are never summed without an explicit conversion. `cash: Decimal`
as a single implicit-USD scalar is not canonical state.

## 7. Native currency first

Every position valuation exists in its native/mark currency before any
base-currency aggregation:

```text
AAPL          native = USD
EUR bond      native = EUR
BTC/USDT      native = USDT
JPY equity    native = JPY
```

The canonical snapshot preserves native values even when a base-currency total
is available. A portfolio may declare a base/reporting currency; that is a
reporting choice, not an identity, mark, cash, or settlement currency claim.

## 8. FX conversion boundary

Base-currency aggregation passes through `portfolio.fx`:

- every conversion carries source currency, target currency, rate, provider,
  source time, and fresh/stale status;
- a missing rate is reported (`MISSING_FX`), never replaced by 1:1 and never
  silently dropped;
- only an explicit rate for the pair (or its exact inverse) is used;
- a stale rate makes the aggregate `STALE`, never silently fresh.

A portfolio total explicitly reports `COMPLETE`, `PARTIAL`, `STALE`,
`MISSING_FX`, `MISSING_MARK`, `UNSUPPORTED`, or `UNVALUED` — the strongest
status wins, and incomplete aggregation is never labeled complete.

## 9. Valuation mark contract

```text
ValuationMark
    instrument_id
    price         Decimal
    currency
    mark_type     LAST | MIDPOINT | CLOSE | SETTLEMENT | PROVIDER_MARK | CLEAN_PRICE | DIRTY_PRICE
    source
    source_time_ns
    observed_at_ns
    data_status   FRESH | STALE | MISSING
```

The portfolio never fetches its own data; it consumes normalized marks from
existing market-data/provider boundaries. A mark for the wrong instrument or
the wrong currency is rejected (`WRONG_INSTRUMENT_MARK` /
`WRONG_CURRENCY_MARK`). A missing mark never produces a zero value.

## 10. Asset-aware valuation rules

| Asset | Quantity unit | Native value rule |
|---|---|---|
| Equity / ETF | SHARES | qty × mark |
| Option | CONTRACTS | contracts × premium × multiplier (multiplier from contract metadata, never assumed 100) |
| Future | CONTRACTS | notional (contracts × multiplier × mark) is informational exposure; P&L = contracts × multiplier × (mark − reference); **never** equity-style cash market value |
| Crypto spot | BASE_UNITS | base qty × pair price (quote currency native) |
| Bond | FACE_VALUE | face × price-basis conversion (PAR_PERCENT / CURRENCY_PER_FACE_UNIT); accrued interest optional (clean/dirty preserved, never invented) |
| Reference identity | N/A | rejected as a portfolio position |

Short positions are signed quantities; market value, cost basis, and P&L
semantics hold for negative quantities. Decimals are never rounded before
presentation boundaries.

## 11. Cost basis and P&L

- `cost_basis` is signed total basis for the net position; `average_cost` is
  the derived unit basis. Existing Paper accounting (weighted cost across
  partial closes and reversals) is preserved through the parity baseline.
- `unrealized = market_value − remaining cost_basis` for securities; futures
  use mark-to-market variation P&L against a reference/settlement price.
- Realized P&L is recorded by the authoritative mutation path; missing cost
  basis is never inferred silently.

## 12. Admission rule

Reference-only identities can never become positions, enforced at the
mutation boundary via `portfolio.admission` (which reuses XA-01 tradability):

- **rejected:** futures family/root, continuous futures series, economic
  commodities, commodity spot/reference identities, index benchmarks,
  currencies, FX pairs, sovereign securities, reference-only bonds;
- **admitted:** tradable securities/ETFs, option contracts, specific future
  contracts, tradable crypto pairs.

A provider-supplied quantity for an ambiguously mapped symbol never creates a
position by guessing (`UNRESOLVED_INSTRUMENT`).

## 13. Mutation boundary

One controlled boundary mutates canonical portfolio truth:

```text
apply_position_input  (fill/adjustment-derived state)
apply_snapshot        (provider/broker snapshot, same-key enforced)
apply_cash            (cash ledger)
apply_adjustment      (explicit operator/reconciliation adjustment)
```

Multiple sources never independently mutate portfolio truth. A provider
snapshot cannot silently overwrite unrelated account/mode state, and no
"last writer wins" semantics exist between fundamentally different
authorities (broker snapshot vs local Paper state).

## 14. Provider normalization

```text
provider account row
    → provider adapter
    → canonical instrument identity (XA-01 alias resolution)
    → canonical position input
    → account-scoped portfolio state
```

Provider symbols are never persisted as canonical portfolio keys. Unknown or
ambiguous rows are recorded as `UNRESOLVED_INSTRUMENT` and canonical truth is
unchanged for those instruments until resolved. Local state and provider
snapshot discrepancies are exposed (`local_quantity`, `provider_quantity`,
`difference`, `reconciliation_status`) rather than silently rewritten.

## 15. Persistence / serialization

The canonical snapshot serializes deterministically (Decimal → string,
sorted keys); decode is version-aware and safe for legacy minimal shapes.
Decimal exactness, account/mode scope, canonical instrument ids, cash by
currency, multiplier/price-basis, and incomplete valuation status all survive
the round trip. Paper persisted state remains readable; nothing in G2 deletes
or rewrites the legacy Paper schema.

## 16. Scope protection (explicit)

G2 does **not** implement: buying-power formulas, margin engines (Reg-T,
SPAN, portfolio margin, initial/maintenance), risk limits/risk engines, VaR,
scenario stress, tax-lot accounting, settlement engines, new provider
connectivity, Live execution, preview tokens, order lifecycle redesign, or
frontend redesign. Portfolio truth created here is input to that later work,
never a substitute for it.

## 17. Dispositions of prior truth sources

| Truth source | Disposition |
|---|---|
| `portfolio/ledger.py` equity ledger | `PARITY_BASELINE` — Paper execution semantics unchanged; consumed read-side by `paper_adapter` |
| `portfolio/options_ledger.py` | `COMPATIBILITY_ADAPTER` — options analytics/exercise semantics remain (BL-0106 ledger merge is separate follow-on work) |
| `paper/ledger.py` event-sourced ledger | `KEEP_CANONICAL` for Paper lifecycle; canonical portfolio is the multi-asset projection authority |
| `intelligence/execution` PaperPortfolioSnapshotV1 | `DERIVED_PROJECTION` — strategy sizing snapshot; unchanged, not canonical portfolio truth |
| `intelligence/live_canary` LivePortfolioSnapshotV1 | `DERIVED_PROJECTION` — unchanged |
| provider position DTOs | `PROVIDER_INPUT` — normalized, never canonical |
| frontend portfolio models | `DERIVED_PROJECTION` — render only; not touched by G2 |
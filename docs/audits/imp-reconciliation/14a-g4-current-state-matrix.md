# G4 Phase 0 — current-state accounting matrix (2026-09-08)

G4 (Multi-Asset Accounting Kernel) begins from the G3.1 green baseline:
FAST 21/0/0, CHANGED 3233/48/0, FULL 3870/48/0 (evidence: 15 G3.1 section).
This document captures the Phase 0 current-state map only — no code changed.

## Inventory of accounting surfaces inspected

| Surface | Module | Status |
|---|---|---|
| XA-01 identity kernel | `xa01/contracts.py` (`InstrumentDescriptor`, `DenominationMetadata`), `xa01/registry.py`, `xa01/tradability.py` | canonical identity + tradability authority; economics as strings (`contract_multiplier`, `currency`, `quantity_unit`) |
| Canonical portfolio (G2) | `portfolio/canonical.py` (CanonicalPortfolio, PortfolioPosition, CashBalance, QuantityUnit, PositionValuation), `portfolio/admission.py`, `portfolio/valuation.py`, `portfolio/fx.py` | Decimal throughout; per-currency cash; asset-aware valuation |
| Paper execution | `paper/ledger.py` (event-sourced, equity-only projections), `paper/contracts.py` (instrument ref carries kind/multiplier/currency), `paper/execution.py`, `paper/broker_paper.py` (cash gates) | minor-unit ints; single policy currency |
| Risk gate | `risk/financial.py`, `risk/pretrade.py` | minor-unit ints; USD-centric; multiplier fail-closed for OPTION/FUTURE |
| Options accounting | `portfolio/options_ledger.py` (float-based, independent), consumed by `options/execution.py` (O9) and `execution/options_conservative.py` | **float** authoritative in the O9 simulation lane |
| Futures | `contracts/futures.py` (FuturesContractSpec Decimal), `futures/notional.py` (Decimal), `futures/roll.py`, `futures/spec_registry.py` (ES spec) | Decimal already; margin not modeled |
| Parity adapter | `portfolio/paper_adapter.py`, `portfolio/ledger.py` (legacy equity ledger) | equity parity baseline |

## Accounting matrix

| Concern | Equity | Option | Future | Current authority | Problem |
|---|---|---|---|---|---|
| Quantity unit | SHARES (`paper.ledger` position_shares; `portfolio.ledger`) | CONTRACTS (options ledger `quantity`; canonical `QuantityUnit.CONTRACTS`) | CONTRACTS (futures notional `contracts`) | paper.ledger; portfolio.options_ledger; contracts.futures | options ledger independent; paper path single-instrument |
| Price unit | minor units (paper) / Decimal (canonical) | premium per share — **float** in options lane | tick/point Decimal (spec_registry) | paper (minor); options lane float; futures spec Decimal | float at options authoritative boundary |
| Contract multiplier | 1 implicit | **float default 100 from provider rows** — not canonical | Decimal from FuturesContractSpec (ES=50) | provider rows (options); spec_registry (futures) | options multiplier not canonical |
| Currency | USD (policy currency) | USD assumed | USD | paper policy; XA-01 denomination.currency | no per-currency cash at gate |
| Cost basis | position_cost_basis_minor int | **float** entry_premium in options ledger | not tracked as held position | paper.ledger; options ledger | float option cost |
| Market value | shares × mark | contracts × premium × multiplier (canonical valuation Decimal) | notional (contracts × multiplier × mark) — never owned cash | portfolio.valuation (canonical); paper | options lane separate |
| Realized P&L | realized_pnl_minor int | **float** realized_pnl (options ledger) | not tracked as held position (notional P&L Decimal) | paper.ledger; options ledger | options float |
| Unrealized P&L | (mark − avg) × shares | payoff_at_spot float (analytics); canonical valuation Decimal | variation P&L Decimal (canonical; needs reference) | canonical valuation | options analytics float separate |
| Working obligation | working_remaining × price × multiplier (minor) | same via financial.py | same formula (gate fails closed UNSUPPORTED_RISK_MODEL) | risk/financial.py | USD-only obligation bucket |
| Buying power | cash − obligations (USD) | N/A (long premium gate) | UNSUPPORTED_RISK_MODEL | risk/financial.py | USD-only |
| Position identity | instrument_id (single per ledger) | call/put/strike/expiry/side tuple (options ledger — not canonical ID) | contract_id | paper; options ledger; futures | options ledger keyed by tuple |
| Settlement semantics | T+0 minor | cash settlement at expiry (float lane) | margin (not modeled; notional ≠ cash) | options lane | float |

## Blocker → increment mapping (from the G4 mandate)

| Architecture blocker | G4 resolution | Target surface |
|---|---|---|
| equity-only authoritative portfolio/risk foundation | canonical `PortfolioPosition` + instrument economics + per-kind calculation policies | portfolio/canonical.py + new portfolio/instrument_economics.py + portfolio/accounting.py |
| fragmented options ledger | Decimal rewrite + canonical adapter; marked NON-AUTHORITATIVE compatibility | portfolio/options_ledger.py, options/execution.py boundary |
| futures float accounting | already Decimal in contracts.futures / futures.notional; centralize variation/notional formulas + sign correctness tests | portfolio/accounting.py + tests |
| incomplete multiplier/notional semantics | fail-closed multiplier for OPTION/FUTURE everywhere; multiplier never symbol-derived | instrument_economics.py + canonical.py + financial.py |
| USD-only settlement assumptions | per-currency working obligations + currency-aware gate; unknown FX fails closed (already via portfolio.fx) | risk/financial.py + risk/pretrade.py |
| incorrect cross-asset working-order obligations | obligations keyed by settlement currency; working_remaining × price × multiplier with kind-aware cash requirement | risk/financial.py + paper gates |

## Numeric representation decision (recorded here; implemented in Checkpoint B)

- stored settled money/cash: integer minor units in the Paper path (unchanged); Decimal in canonical portfolio (unchanged); the options ledger converts to **Decimal** (exact) with float only at the JSON/presentation boundary.
- calculations requiring fractional precision: `Decimal`; `Decimal(str(float))` at boundary conversion (never raw float arithmetic).
- new canonical kernel (`portfolio/accounting.py`) rejects binary float input with a typed error.
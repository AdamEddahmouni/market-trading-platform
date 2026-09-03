# Crypto Simulation and Risk

**Status:** `PROPOSED` — future architecture guidance

**Extends:** Phase 7 bar-conservative simulator — does not replace it.

## Canonical simulation

The platform's **deterministic simulator** remains canonical. Broker paper trading
is not the simulation system. Crypto extends simulation; it does not bypass
independent risk, ledger exactness, or reconciliation.

## Crypto simulation requirements

Model per venue and instrument type:

| Parameter | Notes |
|---|---|
| Spread | venue-specific, time-varying when data supports |
| Maker/taker fees | tier-aware when entitled |
| Minimum size / tick / step | venue rules |
| Slippage | liquidity-aware |
| Latency | order arrival delay |
| Market impact | approximation with documented assumptions |
| Liquidity | depth consumption, partial fills |
| Session | 24/7 with maintenance windows |
| Funding | perpetual payment schedule |
| Liquidation | when leveraged derivatives modeled |
| Leverage / borrow | constraints |
| Venue outage | stale book, reject, or degrade explicitly |
| Stale books | quality-gated |

## Instrument-type fill models

Spot, perpetual, dated future, and option require **distinct fill models**.
Do not assume bar-conservative fills for L2-capable crypto experiments without
explicit simulator authorization and evidence.

Phase 7 `BarConservativeSimulator` remains valid for bar-only crypto research
when capability and preregistration declare bar-only semantics.

## Risk adaptations

Future crypto-specific limits:

- max per-token exposure
- max venue exposure
- stablecoin exposure policy
- leverage and funding exposure
- illiquidity and spread gates
- market depth minimums
- token concentration
- correlated crypto exposure
- exchange counterparty concentration
- drawdown and tail limits

Risk rejects or resizes — evidence and models cannot override.

## Stablecoin risk

Depeg detection; liquidity loss; issuer events; redemption stress; cross-venue
dispersion. Stablecoins are risk-bearing instruments, not implicit cash.

## 24/7 accounting

UTC canonical boundaries; rolling windows; explicit daily P&L definition for
crypto portfolios; maintenance and restart behavior documented in accounting
policy (future ADR-CRYPTO-002).

## Shadow mode

Especially valuable for fast influence strategies:

```text
Would have acted: 14:03:12.381
Expected entry: 0.1824
Observed market at decision: ...
No order transmitted.
```

## Live trading gate (future — not authorized)

Separate authorization requiring: verified provider; reconciliation; kill switch;
max exposure; rolling loss limits; venue limits; order limits; duplicate
prevention; stale-data prevention; disconnect behavior; idempotency; full audit trail.

## Paper-before-live sequence

```text
historical research → deterministic simulation → shadow → paper (if supported)
→ tightly controlled live
```

Crypto 24/7 trading does not skip stages.

## Proposed ADR

ADR-SIM-CRYPTO-001 — crypto simulation extensions and bar vs microstructure
simulator boundaries.

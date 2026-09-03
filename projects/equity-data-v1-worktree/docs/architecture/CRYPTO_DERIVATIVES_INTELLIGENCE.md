# Crypto Derivatives Intelligence

**Status:** `PROPOSED` — future architecture guidance

## Purpose

Planned subsystem for crypto perpetual, futures, and options intelligence —
distinct from spot market data. Inputs feed research, Market Story, and
strategy context; they do not authorize trades independently.

## Inputs

| Category | Examples |
|---|---|
| Perpetual funding | rate, predicted rate, payment schedule |
| Open interest | level, change, venue-specific |
| Mark/index | basis, mark price, index price |
| Liquidations | long/short volume, price level, venue |
| Leverage proxies | long/short ratios where supportable |
| Futures curve | dated futures term structure |
| Options | IV, skew, term structure, Greeks, volume, OI |

## Derived evidence (hypotheses, not signals)

Leverage expansion; leverage washout; crowded longs/shorts; short/long
liquidation pressure; funding extremes; basis dislocation.

Do not infer trader intent from a single metric.

## Liquidation intelligence

`LiquidationEvent` with optional `LiquidationContext`:

- long/short liquidation volume
- rolling liquidation intensity
- price-normalized intensity
- liquidation clustering
- cascade detection candidates
- leverage reset observations

Liquidation maps from unverifiable third-party approximations require explicit
methodology labeling and quality gates. Unverifiable sources may be `QUARANTINED`.

## Integration with contradiction engine

Derivatives may confirm or contradict influence and order-flow readings:

```text
Influence event       bullish
Order flow            bullish
On-chain exchange flow bearish
Funding               extremely bullish / crowded
Liquidations          long-heavy
```

Preserve conflict. Strategy may abstain when crowding offsets momentum.

## Research families (candidates — not validated)

- **Liquidation cascade:** leverage extreme + liquidation acceleration + liquidity
- **Funding mean reversion:** extreme funding + OI + price structure + catalyst absence
- **Derivatives confirmation:** influence event + OI expansion + acceptable funding

All require preregistration and point-in-time tests.

## Capability honesty

`CRYPTO_PERP_FUNDING`, `CRYPTO_PERP_OPEN_INTEREST`, `CRYPTO_PERP_LIQUIDATIONS`,
and options capabilities are separate entitlements. Missing capability →
`UNAVAILABLE` in UI and abstention in strategies that declare dependency.

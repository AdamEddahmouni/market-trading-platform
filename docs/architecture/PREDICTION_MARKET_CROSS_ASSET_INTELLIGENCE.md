# Prediction Market Cross-Asset Intelligence

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3,
[CROSS_VENUE_INTELLIGENCE.md](./CROSS_VENUE_INTELLIGENCE.md),
[INFLUENCE_INTELLIGENCE.md](./INFLUENCE_INTELLIGENCE.md), and
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Prediction markets as intelligence for other assets; cross-platform prediction
intelligence; information lead/lag — empirically tested, not assumed.

## Intelligence layer (no position required)

Market prices provide crowd-derived event probabilities usable as features:

```text
Election probability → sector / policy-sensitive equities
Fed outcome probability → rates / equities / crypto
Regulation probability → crypto / exchanges / affected equities
FDA outcome probability → biotech equities / options
Economic-release probability → index futures / rates / FX
Technology-policy event → semiconductors / AI equities
Crypto-policy event → BTC / ETH / crypto equities
```

Part of the **Information Intelligence Layer** even without prediction-market positions.

## MarketImpliedProbabilityFeature

Future feature family feeding non-prediction strategies:

```text
election probability | recession probability | Fed decision probability
inflation outcome | regulatory outcome | crypto-policy outcome
corporate-event outcome
```

Test relationships — do not assume propagation paths.

## Probability change vs level

Study:

```text
current probability | Δ1m | Δ5m | Δ1h | Δ1d
probability velocity | probability acceleration
```

A move 45% → 61% may matter more to another asset than absolute 61%.

## Information lead/lag

Determine empirically — do not assume prediction markets always lead:

```text
prediction market → equity | equity → prediction market
prediction market → crypto | crypto → prediction market
social event → prediction market → asset
```

## Cross-platform prediction intelligence

When events mapped via `CanonicalRealWorldEvent`, research:

- probability disagreement
- bid/ask disagreement
- liquidity and price discovery
- lead/lag across venues
- volatility
- response to news and whale activity

Example (not automatic arbitrage):

```text
Kalshi YES midpoint 0.63 | Polymarket YES midpoint 0.68 | Internal model 0.71
```

Inspect first: executable prices, fees, liquidity, settlement semantics, account
restrictions, capital movement, execution latency.

Fourth research track:

> When legitimately comparable contracts diverge across venues, which market leads
> and does an executable convergence opportunity remain?

## Influence integration

```text
Political/public statement
  → Influence event
  → Prediction-market probability changes
  → Sector / crypto reaction
```

Verifies whether information events are economically repriced.

## Prediction market as confirmation

```text
Regulatory rumor → social/news detection
  → crypto-policy market reprices
  → BTC order flow confirms
```

Supporting evidence — not proof.

## Cross-asset Market Story

One event connecting multiple markets:

```text
FED DECISION EVENT
  Prediction markets | Treasuries | ES | NQ | BTC | USD
```

Exposes information propagation through the financial system.

## Third research track

> Do changes in prediction-market probabilities contain incremental point-in-time
> information for related equities, futures, or crypto markets?

Examples: macro, regulation, elections, corporate events.

## Abstention

Cross-asset signals require executable downstream markets — wide spread, stale
features, or semantic mismatch between prediction contract and target asset should
trigger abstention.

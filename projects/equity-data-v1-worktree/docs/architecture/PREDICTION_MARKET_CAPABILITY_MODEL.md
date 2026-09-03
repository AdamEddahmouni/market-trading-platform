# Prediction Market Capability Model

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3 and
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Define how prediction-market instruments, events, venues, and provider capabilities
plug into the existing provider-neutral canonical contract system without treating
event contracts as equities or creating provider-specific engines (`KalshiEngine`
is not the conceptual core).

## Instrument and event identity

Future contracts bind:

| Dimension | Requirement |
|---|---|
| Asset class | `PREDICTION_MARKET` (or explicit extension) |
| Provider | Adapter identity — Kalshi, Polymarket, … |
| Venue | Regulatory/operational venue where distinct from provider |
| Event ID | Provider event/series reference |
| Market ID | Canonical stable ID across revisions |
| Outcome set | Binary YES/NO, multi-outcome, scalar threshold, … |
| Contract payoff | Venue-specific semantics — explicit |
| Tick / min size | Venue-specific |
| Quote currency | USD, USDC, … — explicit |
| Jurisdiction / eligibility | Account and market eligibility metadata |

Provider ticker strings are source metadata, not canonical IDs.

## Capability taxonomy

Capabilities remain closed, versioned, and capability-honest.

### Discovery and metadata

`PREDICTION_MARKET_DISCOVERY` — events, series, categories, lifecycle metadata

### Market data

`PREDICTION_MARKET_QUOTES`
`PREDICTION_MARKET_TRADES`
`PREDICTION_MARKET_ORDERBOOK`
`PREDICTION_MARKET_HISTORY`
`PREDICTION_MARKET_LIFECYCLE`
`PREDICTION_MARKET_RESOLUTION` — rules, sources, amendments, settlement outcomes

### Execution and portfolio

`PREDICTION_MARKET_EXECUTION`
`PREDICTION_MARKET_POSITIONS`
`PREDICTION_MARKET_SETTLEMENTS`

### Public participant data (only where legitimately exposed)

`PREDICTION_PUBLIC_PARTICIPANT_ACTIVITY`
`PREDICTION_PUBLIC_HOLDERS`
`PREDICTION_PUBLIC_WALLET_POSITIONS`

A provider with trades but no public identity must not satisfy participant-copy
capabilities. Execution capability and data-research capability are independently
declared per adapter and jurisdiction.

## Canonical hierarchy

```text
PredictionEvent
  └─ PredictionMarket
        ├─ Outcome
        ├─ OrderBook
        ├─ Trade
        ├─ ResolutionRule (versioned)
        └─ Settlement
```

Potential `PredictionMarket` fields (finalize against existing canonical conventions):

```text
market_id, provider, venue, event_id
title, description, market_type, outcomes
created_at, opens_at, closes_at, expected_resolution_at
status
resolution_rules, resolution_sources, resolution_version
tick_size, minimum_size
volume, open_interest, liquidity
provenance, quality
```

## Market lifecycle

Canonical states accommodate provider capability with provenance retained:

```text
CREATED → OPEN → PAUSED → CLOSED → DETERMINING → DISPUTED → SETTLED → VOIDED
```

Provider-native states preserved as provenance — not silently collapsed.

## Data quality conditions

Prediction-market-specific quality — not all generic errors:

```text
STALE_BOOK, WIDE_SPREAD, LOW_LIQUIDITY
RESOLUTION_AMBIGUITY, RULES_CHANGED, MARKET_PAUSED
OUTCOME_DISPUTED, PROVIDER_UNAVAILABLE
PARTICIPANT_DATA_UNAVAILABLE
```

## Implied probability types

Distinguish stored and displayed semantics:

| Type | Use |
|---|---|
| `LAST_TRADE` | Observed print |
| `BEST_BID` / `BEST_ASK` | Executable sides |
| `MIDPOINT` | Display/research only unless strategy declares |
| `MODEL_FAIR` | `OutcomeProbabilityModel` output with calibration metadata |

Strategies default to executable prices for edge computation.

## Provider adapter rules

1. Adapters normalize to canonical contracts; strategies never see SDK objects.
2. Kalshi and Polymarket are future candidate adapters — verify API at implementation.
3. Polymarket settlement may involve Polygon (network) — never conflate with platform.
4. Demo environments (Kalshi demo) supplement but do not replace canonical simulation.
5. Licensing, retention, and redistribution recorded per provider.

## Integration points

- Traditional market data: shared provenance, replay, quality frameworks
- Crypto/on-chain: Polymarket wallet data may intersect on-chain intelligence
- Influence: public events feed and consume prediction repricing
- Research: `OutcomeProbabilityModel`, `MarketImpliedProbabilityFeature`
- Simulation: distinct payoff and capital-lock semantics

See [PREDICTION_MARKET_RESOLUTION_AND_EVENTS.md](./PREDICTION_MARKET_RESOLUTION_AND_EVENTS.md).

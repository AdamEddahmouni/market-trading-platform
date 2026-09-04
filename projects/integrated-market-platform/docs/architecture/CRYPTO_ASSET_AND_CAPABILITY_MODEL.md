# Crypto Asset and Capability Model

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3 and
[2026-08-16-crypto-influence-expansion-design.md](../superpowers/specs/2026-08-16-crypto-influence-expansion-design.md)

## Purpose

Define how cryptocurrency instruments, venues, and provider capabilities plug
into the existing provider-neutral canonical contract system without treating
crypto as equities with 24/7 sessions.

## Instrument identity

Future `CryptoInstrument` (or generalized instrument extension) must bind:

| Dimension | Requirement |
|---|---|
| Asset class | `CRYPTO_SPOT`, `CRYPTO_PERP`, `CRYPTO_FUTURE`, `CRYPTO_OPTION`, `STABLECOIN` |
| Base asset | Canonical asset ID (e.g. BTC, ETH, DOGE) |
| Quote asset | USD, USDT, USDC, EUR, … — explicit |
| Venue / upstream | Exchange, DEX protocol, or index source — never collapsed |
| Contract spec | Perpetual vs dated; expiry; option strike/expiry where applicable |
| Tick / lot / min size | Venue-specific |
| Settlement | On-chain, internal ledger, or hybrid — explicit |

Instrument identity is stable across provider adapters. Provider symbol strings
are source metadata, not canonical IDs.

## Capability taxonomy

Capabilities remain closed, versioned, and capability-honest. Proposed families:

### Spot

`CRYPTO_SPOT_QUOTES`, `CRYPTO_SPOT_TRADES`, `CRYPTO_SPOT_DEPTH`,
`CRYPTO_SPOT_EXECUTION`

### Perpetuals / dated futures

`CRYPTO_PERP_QUOTES`, `CRYPTO_PERP_TRADES`, `CRYPTO_PERP_DEPTH`,
`CRYPTO_PERP_FUNDING`, `CRYPTO_PERP_OPEN_INTEREST`,
`CRYPTO_PERP_LIQUIDATIONS`, `CRYPTO_PERP_EXECUTION`

Dated futures may share or extend perp capabilities with explicit expiry semantics.

### Options

`CRYPTO_OPTIONS_CHAIN`, `CRYPTO_OPTIONS_QUOTES`, `CRYPTO_OPTIONS_GREEKS`,
`CRYPTO_OPTIONS_EXECUTION`

### On-chain (independent ingestion path)

`ONCHAIN_BLOCKS`, `ONCHAIN_TRANSACTIONS`, `ONCHAIN_TOKEN_TRANSFERS`,
`ONCHAIN_ENTITY_LABELS`, `ONCHAIN_DEX_TRADES`

### Social / influence

`SOCIAL_EVENTS`, `PUBLIC_INFLUENCE_EVENTS`

Unsupported capabilities return explicit `UNAVAILABLE` — never synthetic depth
from bars or invented aggressor identity from quotes.

## Canonical market-data event types

Every event preserves venue and source identity:

`Trade`, `Quote`, `BookSnapshot`, `BookDelta`, `Ticker`, `OHLCV`, `IndexPrice`,
`MarkPrice`, `FundingRate`, `OpenInterestObservation`, `LiquidationEvent`,
`BasisObservation`, `VolumeAggregate`, `ExchangeStatusEvent`

Cross-venue aggregates are **derived** datasets with their own manifest and
provenance pointing to venue-native inputs.

## Provider adapter rules

1. Adapters normalize to canonical contracts; strategies never see SDK objects.
2. Multiple providers may report different prices for the same logical pair on
   different venues — not automatically an error.
3. Preserve: `provider_id`, `venue_id` / upstream source, instrument, price,
   `event_time`, receive/availability time.
4. Rate limits, entitlements, licensing, and retention are adapter metadata.
5. Moomoo is a future candidate — characterize at implementation time from
   current official API documentation, not stale assumptions.

## Market intelligence subsystem

Future **Crypto Market Intelligence** ingests venue-native feeds, applies quality
gates, and exposes capability-honest features. It does not replace the global
replay engine or risk layer.

## Order flow generalization

Crypto order-flow features reuse existing concepts where semantically valid:

CVD, signed volume, OFI, top-N depth imbalance, large-trade concentration,
trade-size anomalies, liquidity consumption, sweeps, replenishment, absorption,
exhaustion, divergence.

Aggressor provenance sources: `NATIVE`, `QUOTE_RULE`, `TICK_RULE`,
`MODEL_INFERRED`, `UNKNOWN`. Never mix without disclosure.

## Microcap / meme token eligibility

Researching an asset does not imply execution eligibility. Future gates may
require: verified contract, minimum age, liquidity, venue coverage, spread
limits, holder concentration, market-cap floor, volume, and contract-risk
indicators where supportable.

## Future contracts (conceptual)

`CryptoInstrument`, `FundingEvent`, `OpenInterestObservation`, `LiquidationEvent`,
`LiquidationContext`, `ExchangeStatusEvent`, `VenueIdentity`

Exact names follow accepted ADRs and schema compatibility rules (ADR-SCH-001).

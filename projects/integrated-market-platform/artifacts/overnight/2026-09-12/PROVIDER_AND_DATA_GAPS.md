# Provider and data gaps

**Lanes:** A + B | **Date:** 2026-09-12

## Critical path (FTEP ES)

- Missing: **verified entitled `US_FUTURES_QUOTE`** (Moomoo).
- Secondary: IBKR delayed L1 only.
- Blockers: `PROBE-MOOMOO`, `EXT-MOOMOO-FUTURES-ENTITLEMENT`, `OWNER-OD-1-11`.

## News / event data

- Canonical fixture path: **verified offline**.
- Live Finviz Elite: **cataloged**, probe stale.
- Seven headline vendor ids: **configured_not_operational**.

## Regulatory / macro

- Strong fixture coverage (SEC, FINRA, CFTC, FRED, EIA, weather).
- Live activation not required for BUILD35 acceptance.

## Broker / paper

- Tradier + Moomoo paper slots: fixture-first.
- No accepted production live broker transport.

## Detail artifact

[PROVIDER_UNIVERSE_MASTER_AUDIT.json](./PROVIDER_UNIVERSE_MASTER_AUDIT.json)

## ES research

[ES market data alternatives](../../docs/research/ES_MARKET_DATA_ALTERNATIVES_2026-09-12.md)

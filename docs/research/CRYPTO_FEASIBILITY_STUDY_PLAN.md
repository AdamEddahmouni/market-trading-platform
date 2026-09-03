# Crypto Data Feasibility Study Plan

**Status:** `PROPOSED` — not authorized until principal authorization

## Objective

Before broad crypto implementation, characterize lawful data availability for a
**minimal asset set** without assuming capabilities.

Suggested starting assets: BTC, ETH, DOGE — or better alternatives supported by
characterized providers.

## Scope

Characterize only — no ingestion implementation, no network fetches without
separate authorization, no adapter code in canonical `src/` without phase gate.

## Dimensions per asset and source

| Dimension | Record |
|---|---|
| Symbol / pair identity | provider string vs canonical mapping |
| Venue / upstream source | explicit |
| Timestamps | event vs receive vs availability semantics |
| Historical depth | trades, quotes, L2, bars |
| Derivatives | funding, OI, liquidations, options |
| Tick / lot / min size | venue-specific |
| Fee schedule | maker/taker tiers if published |
| Rate limits | requests, subscriptions |
| Entitlements | subscription tier required |
| Licensing / retention | storage, redistribution, training |
| Paper / simulation | provider paper only — not canonical sim |
| API version | document version reviewed |
| Gaps | explicit unsupported list |

## Moomoo characterization (candidate)

At study time, re-read current official Moomoo API documentation. Do not rely
on stale assumptions. Record crypto-specific capabilities separately from
equity capabilities.

## Deliverables

1. `crypto_feasibility_report.json` — structured characterization (no secrets)
2. Gap analysis vs proposed capability taxonomy
3. Minimum validating dataset recommendation
4. Provider comparison memo referencing [PROVIDER_AND_DATA_RESEARCH_MATRIX.md](./PROVIDER_AND_DATA_RESEARCH_MATRIX.md)
5. Recommendation: proceed / defer / reject per asset

## Success criteria

- No inferred capabilities — only documented or observed characterization
- Venue identity preserved in all examples
- Licensing gaps explicitly flagged
- No phase or ADR falsely advanced

## Authorization required

Principal authorization for characterization activity and any lawful network
queries used in the study.

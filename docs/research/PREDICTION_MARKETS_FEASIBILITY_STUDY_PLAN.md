# Prediction Market Feasibility Study Plan

**Status:** `PROPOSED` — not authorized until principal authorization

## Objective

Before prediction-market implementation, characterize lawful data and execution
availability for initial provider candidates without assuming capabilities.

Initial platforms to investigate:

- Kalshi
- Polymarket / Polymarket US
- other lawful, API-accessible prediction exchanges discovered during research

**Terminology:** Polymarket is the platform. Polygon is a blockchain/network used in
Polymarket settlement architecture. Do not confuse the two.

## Scope

Characterize only — no ingestion implementation, no network fetches without
separate authorization, no adapter code in canonical `src/` without phase gate.

## Dimensions per provider

| Dimension | Record |
|---|---|
| Legal/regulatory status | jurisdiction, user eligibility |
| Market coverage | categories, event types, liquidity |
| Discovery APIs | events, series, markets |
| Market data | quotes, trades, order books, history |
| WebSockets | subscriptions, rate limits |
| Resolution | rules, sources, amendments, settlement process |
| Execution | order types, fills, positions, demo environment |
| Participant visibility | public trades only vs wallet/holder data |
| Fees | trading, settlement, withdrawal |
| Historical depth | trades, books, rules versioning |
| Chain/settlement | where applicable — network vs platform |
| Licensing | storage, redistribution, training, commercial use |
| API version | document version reviewed |
| Gaps | explicit unsupported list |

## Kalshi characterization checklist

- market discovery, events, series, market rules, settlement sources
- order books, trades, historical trades, lifecycle
- WebSockets, order entry, fills, positions, settlement
- fees, demo environment, rate limits
- participant visibility (assume anonymous unless API proves otherwise)

## Polymarket characterization checklist

- Gamma API, Data API, CLOB API, WebSockets
- user/wallet activity, positions, top holders, trades, open interest
- resolution process, chain/settlement architecture (Polygon as network)
- U.S. availability vs international — execution vs research-only
- jurisdiction restrictions

## Other candidates

Research lawful alternatives during study. Do not assume Kalshi and Polymarket
remain the only useful providers.

## Deliverables

1. `prediction_markets_feasibility_report.json` — structured characterization (no secrets)
2. Gap analysis vs proposed capability taxonomy
3. Provider selection memo (data-only vs demo vs execution per jurisdiction)
4. Minimum validating dataset recommendation
5. Recommendation: proceed / defer / reject per provider and use case

## Success criteria

- No inferred capabilities — only documented or observed characterization
- Polymarket vs Polygon terminology preserved in all records
- Licensing gaps explicitly flagged
- Public data vs execution capability separated per provider
- No phase or ADR falsely advanced

## Authorization required

Principal authorization for characterization activity and any lawful network queries
used in the study.

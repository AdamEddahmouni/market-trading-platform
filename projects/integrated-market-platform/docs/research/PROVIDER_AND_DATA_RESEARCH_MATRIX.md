# Provider and Data Research Matrix

**Status:** `PROPOSED` — characterization planning only

**Authority:** No vendor selection, procurement, or network access authorized.

## Selection principle

```text
incremental economic research value / total data cost
```

Do not buy every feed because it sounds useful. For each paid source estimate:
unique capability; overlap; hypotheses enabled; expected usage; cost; alternatives.

When multiple providers supply comparable information, A/B compare: accuracy,
completeness, latency, uptime, historical depth, cost.

## Categories

### Broker / unified API (execution + data candidates)

| Candidate | Research dimensions | Notes |
|---|---|---|
| Moomoo | crypto market data, symbols, markets, quote types, trades, depth, historical, account types, order types, rate limits, entitlements, fees, venue identity, paper/sim, API version, licensing | Re-read official docs at implementation time |
| Other lawful brokers/APIs | same matrix | No selection before comparison |

### Centralized exchange data

| Candidate | Research dimensions |
|---|---|
| To be characterized | spot/perp trades, quotes, L2, funding, OI, liquidations, historical depth, licensing, retention |

Evaluate overlap with broker APIs before duplicate procurement.

### Derivatives / analytics

| Candidate | Research dimensions |
|---|---|
| To be characterized | options chains, IV surfaces, liquidation feeds, methodology transparency |

Unverifiable liquidation approximations require methodology labeling.

### On-chain

| Candidate | Research dimensions |
|---|---|
| Node/RPC direct | finality, cost, throughput, historical backfill |
| Indexers / analytics | entity labels, DEX swaps, exchange flows, label versioning, cost |

Select **one chain first** (likely Bitcoin or Ethereum depending on hypothesis).

### Social / influence

| Candidate | Research dimensions |
|---|---|
| X (official API) | pricing, recent/full-history access, actor query semantics, publication timestamps, edit behavior, historical availability, licensing, retention, achievable latency |
| Other lawful public sources | same matrix |

Influence feasibility must determine whether event-study data can be obtained
legally and economically.

### Prediction / event markets

| Candidate | Research dimensions | Notes |
|---|---|---|
| Kalshi | discovery, events, series, rules, settlement sources, books, trades, history, lifecycle, WebSockets, order entry, fills, positions, fees, demo, rate limits, participant visibility, licensing | Re-read official API at implementation; whale identity only if API proves it |
| Polymarket / Polymarket US | Gamma API, Data API, CLOB API, WebSockets, wallet activity, positions, holders, trades, OI, resolution, chain/settlement, U.S. jurisdiction, licensing | **Polymarket** is the platform; **Polygon** is a settlement network — do not conflate |
| Other lawful API-accessible exchanges | same matrix | Discover during feasibility — do not assume only Kalshi/Polymarket |

Separate **public data / research** capability from **lawful execution** capability per
provider and jurisdiction. See
[PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md](./PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md).

## Minimum validating dataset

First crypto research dataset should answer **one specific hypothesis** — example:

> Can verified high-impact public events produce a reproducible, executable
> short-horizon effect in DOGE after realistic API and execution latency?

Required data may include only: historical public events; DOGE trades/quotes;
market context; publication/availability timing.

Add on-chain/derivatives only when ablation proves incremental economic value.

## Feature ablation protocol

```text
baseline
baseline + social event
baseline + social + order flow
baseline + social + order flow + derivatives
baseline + all + on-chain
```

Remove costly sources that fail out-of-sample economic improvement.

## Data licensing checklist (per provider)

- permissible storage
- historical retention
- redistribution
- derived data rights
- display rights
- model-training rights
- API costs and rate limits

## Security

Secrets in private stores; `.env` excluded; least privilege; separate read/trade
credentials; audit logs; no keys in research artifacts or model prompts.

## Next step

Authorize feasibility characterization studies — not procurement — per
[CRYPTO_FEASIBILITY_STUDY_PLAN.md](./CRYPTO_FEASIBILITY_STUDY_PLAN.md),
[INFLUENCE_FEASIBILITY_STUDY_PLAN.md](./INFLUENCE_FEASIBILITY_STUDY_PLAN.md),
[ON_CHAIN_FEASIBILITY_STUDY_PLAN.md](./ON_CHAIN_FEASIBILITY_STUDY_PLAN.md),
[PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md](./PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md).

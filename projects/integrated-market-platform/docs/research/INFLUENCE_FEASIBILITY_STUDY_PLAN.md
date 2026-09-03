# Influence Data Feasibility Study Plan

**Status:** `PROPOSED` — not authorized until principal authorization

## Objective

Determine whether the data necessary for rigorous influence event studies can
be obtained **legally, economically, and with sufficient point-in-time fidelity**.

## Primary source characterization: X (official API)

| Question | Required answer |
|---|---|
| Current pricing tiers | documented |
| Recent vs full-history access | what is actually available |
| Actor/user query semantics | IDs, handles, verification |
| Publication timestamps | granularity and trust |
| Edit and delete behavior | observable vs not |
| Historical availability | backfill limits |
| Licensing and retention | storage, redistribution, training |
| Achievable polling/stream latency | realistic detection delay |
| Engagement metrics | snapshot availability vs final totals |
| Rate limits and cost at scale | budget projection |

## Secondary lawful public sources

Official blogs, press releases, regulatory feeds, Reddit/YouTube where lawful —
same characterization matrix.

## Critical feasibility questions

1. Can we reconstruct **first_observed_at** honestly for historical research?
2. Can we store engagement **snapshots** at multiple horizons?
3. Can we detect edits/deletions without hindsight leakage?
4. Is latency compatible with any short-horizon hypothesis under test?
5. What is monthly cost for prioritized actor/asset monitoring?

## Social API cost model (planning)

- prioritized actors and assets
- event-driven queries vs full firehose
- caching and deduplication
- backfill separate from live monitoring
- explicit spend caps

## Deliverables

1. `influence_feasibility_report.json`
2. Latency budget estimate for pipeline stages
3. Licensing risk memo
4. Go/no-go for first influence experiment design
5. Budget projection for minimum validating dataset

## Authorization required

Principal authorization for API pricing review and any lawful test queries.

No scraping. No bypass of access controls.

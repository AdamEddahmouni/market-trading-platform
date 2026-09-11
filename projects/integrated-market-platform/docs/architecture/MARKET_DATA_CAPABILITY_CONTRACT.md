# Market Data Capability Contract

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`  
**Purpose:** establish what must be known about a market/news/reference source before it can support historical, shadow, Paper, or forward evidence.

A provider being reachable does not make its data campaign-valid. A source is admitted only for the exact role its verified capability record supports.

## Required record

| Field | Requirement |
|---|---|
| `capability_contract_id` | Stable versioned identifier |
| provider / dataset / endpoint | Exact external source |
| asset classes / venues / instruments | Explicit coverage |
| data mode | `REALTIME`, `DELAYED`, `HISTORICAL`, `REPLAY`, or defined equivalent |
| observation type | trade, quote/L1, depth/L2/MBO, bar, news/event, reference, derived |
| source/event time | Origin timestamp and semantics |
| receive/observation time | IMP observation timestamp |
| timestamp precision | Resolution and clock semantics |
| venue/consolidation scope | Single venue, consolidated, partial, unknown |
| freshness rule | Max age and stale behavior for the intended use |
| gaps / backfills / revisions | Known mutation and recovery semantics |
| PIT reconstructability | Whether historical state can be reproduced without future revisions |
| entitlement status | Account-level entitlement actually verified |
| permitted use | Research, runtime, storage, non-display, display, redistribution as applicable |
| reliability / limits | Rate limits, quotas, uptime/SLA observations, reconnect behavior |
| known limitations | Material omissions or transformations |
| campaign role | `AUTHORITY`, `CHALLENGER`, `CONTEXT_ONLY`, `COMPARATOR_ONLY`, or `PROHIBITED` |
| verification evidence | Dated evidence and source documentation |
| last verified | Date/time of capability verification |

## Sufficiency rule

Capability is claim-specific. For example, a real-time top-of-book feed may support directional/event reaction studies while being insufficient for queue-position or full depth execution claims. A delayed source may be operationally useful but cannot silently stand in for a campaign declared as real-time prospective evidence.

## Time and provenance requirements

For each admitted observation preserve, where available:

- provider/source identity;
- canonical instrument identity;
- event/source timestamp;
- IMP receive/observation timestamp;
- publication/revision timestamp for news/fundamental/macro records;
- data mode;
- venue or consolidation scope;
- freshness/quality flags;
- entitlement/use-right state or reference;
- derivation lineage for transformed features.

Missing timestamp semantics must be explicit. Do not invent exchange time from receive time or vice versa.

## Rights and entitlement rule

Technical access is not permission. Research use, runtime/non-display use, storage, derived-data use, display and redistribution are separate permissions. Campaign admission requires the rights relevant to the intended use, not merely a successful API response.

## Promotion states

Recommended capability lifecycle:

`RESEARCHED -> CONFIGURED -> ENTITLED -> REACHABLE -> SAMPLE_VERIFIED -> ROLE_VALIDATED -> CAMPAIGN_BOUND`

These states are independent from adapter implementation. An adapter can exist while credentials, entitlement or campaign suitability remain unverified.

## Revalidation triggers

Revalidate when any of these change materially:

- provider product or methodology;
- endpoint/version;
- account entitlement;
- pricing/licensing terms;
- venue or consolidation coverage;
- timestamp semantics;
- history availability;
- campaign claim or asset class;
- source reliability or rate limits.

## Campaign binding

A frozen FTEP campaign manifest must reference the exact capability-contract version for every market/news/reference source that can affect candidate generation, eligibility, execution simulation, evaluation or claimed evidence quality.

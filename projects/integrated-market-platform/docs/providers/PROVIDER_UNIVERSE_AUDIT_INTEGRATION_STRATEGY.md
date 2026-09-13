# IMP Provider Universe, Audit & Integration Strategy

**Classification:** `CURRENT_CANONICAL_GOVERNANCE`  
**Established:** 2026-09-11  
**Applies to:** provider research, procurement, data-source integration, broker/sandbox comparators, FTEP campaign binding, Opportunity Engine inputs

> **Banner:** The 2026-09-11 access table below is a planning baseline, not current campaign entitlement. Distinguish **code-supported** (an adapter exists in IMP) from **available-now** (live access verified for a named campaign). Alpaca has **no** adapter. IBKR observational code exists; it is not execution authority and is not claimed currently available.

## Canonical rule

IMP should **research and catalog the broadest useful provider universe, but must not integrate every provider by default**.

The provider lifecycle is:

`PROVIDER_UNIVERSE -> RESEARCH_CATALOG -> CURRENT_ACCESS_AUDIT -> CAPABILITY_MATRIX -> COVERAGE_GAP_MAP -> PRIORITY_STACK -> CANONICAL_ADAPTER -> FROZEN_COMPARISON -> ROLE_PROMOTION -> CAMPAIGN_BINDING -> HEALTH/RE-SCORE`

Provider count is not a success metric. The objective is maximum useful evidence coverage, cross-source confidence, replaceability and reproducibility with minimum unnecessary cost, lock-in, duplicated semantics and maintenance burden.

This document is subordinate to the Market Data Capability Contract, FTEP activation gates, safety/mode authority and provider-rights rules. It does not grant Live execution, campaign activation, account binding, paid-product activation or procurement authority.

## Current user-confirmed access

The current planning baseline includes:

| Resource | Current fact | Immediate role | What still requires audit |
|---|---|---|---|
| Finviz | Access is available to the project | Discovery, screening, market/news/fundamental context unless stronger capability is verified | exact subscription/tier, permitted automation/export, timing/history, rights, campaign suitability |
| Moomoo OpenD | Available/running under the user's free plan | First-audit observational/data source; possible comparator only to the extent verified | exact assets/instruments, realtime vs delayed state, L1/depth/trades/history, session coverage, rate limits, Paper/simulation account capability, rights |
| IBKR | Existing live-verified read-only IMP path | Current brokerage/observational baseline | campaign-specific entitlements; current known L1 entitlement is delayed and L2/tick access is limited |
| Tradier | Existing broker-paper/sandbox implementation | Existing sandbox/broker-paper candidate | current account/token/environment, delayed-vs-realtime data separation, campaign suitability |
| Alpaca | Possible prior/local setup, not currently claimed | Audit candidate | whether configuration/account still exists; exact data tier and Paper capability |
| Existing news/data APIs | Existing IMP integrations/research candidates | Source-specific roles | current credentials, terms, timestamps, limits, rights and campaign binding |

User confirmation proves **availability**, not every capability. `ACCESS_AVAILABLE`, `CONNECTED`, `ENTITLED`, `CAPABILITY_VERIFIED`, `CAMPAIGN_SUITABLE` and `PROMOTED` are separate states.

No secret value belongs in repository documentation or Notion.

## Phase 0 — broad provider universe

Research and catalog materially relevant providers across:

- equities, futures, options, fixed income/rates, FX and crypto;
- quotes/L1, trades, depth/L2/MBO, bars, reference data and corporate actions;
- corporate releases, filings, FDA/regulatory events, earnings/transcripts and news wires;
- fundamentals, estimates/consensus and revisions;
- macro/vintage data, curves and positioning;
- short interest, short volume, borrow/locate and securities lending where available;
- options/volatility/flow and institutional/whale/alternative data;
- social and on-chain intelligence;
- Paper/sandbox brokers and independent execution simulators;
- historical datasets and replay/backtest/research engines;
- terminals/scanners used as UX/product benchmarks.

Cataloging is cheap and broad. It is **research, not integration**.

## Phase 1 — audit current access before procurement

Audit in this order unless a campaign-specific blocker requires otherwise:

1. Finviz;
2. Moomoo OpenD;
3. IBKR;
4. Tradier;
5. Alpaca/local/private state;
6. existing news/data APIs and direct feeds.

For each, record only non-secret operational truth: access state, environment, entitlements, capabilities, evidence date, data mode, limits, rights, reliability and candidate roles.

### Audit-state vocabulary

Use independent states:

- `CATALOGED`
- `ACCESS_AVAILABLE`
- `CONNECTED`
- `ENTITLED`
- `CAPABILITY_VERIFIED`
- `CAMPAIGN_SUITABLE`
- `PROMOTED`
- `BLOCKED`
- `NOT_NEEDED`

Do not collapse these into one "working" flag.

## Phase 2 — Provider Capability Matrix

Maintain one capability matrix for current and candidate providers. At minimum capture:

- provider/product/dataset/endpoint;
- current access state and evidence date;
- cost/tier/trial/student availability;
- asset, venue and instrument coverage;
- `REALTIME` / `DELAYED` / `HISTORICAL` / `REPLAY` mode;
- trades, quote/L1, depth/L2, MBO/order-level, bars, news/events, fundamentals/reference;
- source/event and receive timestamps plus precision/semantics;
- venue/consolidation scope;
- history depth and PIT reconstructability;
- revisions/backfills/corrections;
- session/calendar coverage;
- rate limits, reliability and operational dependencies;
- research/runtime/storage/display/non-display/redistribution rights;
- Paper/sandbox environment and supported order types where applicable;
- known simulation omissions;
- normalized IMP role(s);
- named strategies/experiments supported;
- unique coverage versus current stack;
- implementation and maintenance effort;
- blocker status and evidence links.

This extends, rather than replaces, the Market Data Capability Contract.

## Phase 3 — Coverage-Gap Map

After the current-access audit, derive what IMP is actually missing by strategy and evidence type.

Examples:

- If Moomoo already supplies sufficient equity observations for a use case, another equity quote adapter is not automatically needed.
- If Finviz already covers discovery/screening requirements adequately, retain it in that role rather than rebuilding the same discovery layer across multiple APIs.
- If the first ES campaign lacks lawful prospective futures evidence at the required granularity, that becomes a named provider gap.
- A futures-capable independent Paper comparator is a different gap from futures market data.
- Short-squeeze research may expose borrow/locate/short-interest gaps.
- Options research may expose chain/surface/Greeks and assignment/exercise gaps.
- Order-flow work may expose true L2/MBO gaps.

Every proposed new integration must close a named gap, provide a deliberate challenger/redundancy role, or remove a measured operational bottleneck.

## Phase 4 — explicit provider roles

Providers do not compete for one universal slot. Assign roles per asset/dataset/experiment:

- `DISCOVERY`
- `PRIMARY_MARKET_EVIDENCE`
- `SECONDARY_CHALLENGER`
- `CONTEXT_ONLY`
- `NEWS_EVENT_AUTHORITY`
- `FUNDAMENTAL_REFERENCE`
- `HISTORICAL_RESEARCH`
- `ALTERNATIVE_DATA`
- `PAPER_COMPARATOR`
- `BROKER_ACTION_ENDPOINT`
- `FALLBACK`
- `UX_BENCHMARK`

A provider may be authoritative for one observation and context-only for another.

## Phase 5 — smallest sufficient provider stack

Prioritize provider work using a documented decision model rather than provider count:

`priority ~ evidence_importance * uniqueness * opportunity_value * reliability * rights_clarity / integration_cost / operating_cost / maintenance_burden`

Do not pay for or implement overlapping providers simply because each offers attractive coverage. Redundancy is justified when the redundancy itself improves validation, reliability or a named experiment.

## Phase 6 — canonical normalization

Every promoted provider must remain behind IMP contracts. Strategies and the Opportunity Engine must not depend directly on provider SDK objects when a canonical model can express the fact.

Normalize at least:

- canonical instrument/entity identity;
- event/source/receive timestamps;
- raw/provenance/hash/version references;
- data mode, freshness and staleness;
- quality/gap/revision state;
- entitlement and rights metadata;
- provider health;
- deterministic fixture/replay capture;
- account/environment identity for brokers;
- canonical order, acknowledgement, reject, fill, partial-fill and cancel state for action-capable providers.

## Phase 7 — frozen cross-source comparison

Where providers overlap, compare on frozen instruments/time windows. Measure:

- first-seen/receive latency;
- price/value disagreement;
- missingness/staleness;
- duplicate/correction/revision behavior;
- identifier/corporate-action/contract-roll differences;
- uptime/recovery behavior;
- coverage differences.

Retain disagreements as evidence. Never silently choose whichever source creates a more favorable strategy result.

## Phase 8 — campaign-specific binding

A provider can have an adapter and still be unsuitable for a specific FTEP campaign. Campaign manifests bind exact sources only after capability, rights and role verification.

For the candidate first campaign (`FTEP-V1-001 / ES-news`), resolve provider work in this order:

1. establish what Finviz, Moomoo OpenD, IBKR and existing APIs already contribute;
2. determine whether current access supplies lawful prospective ES evidence at the granularity required by the claims;
3. name the remaining ES data gap, if any;
4. audit one or more futures-capable external Paper/sandbox candidates for comparator suitability;
5. implement only missing canonical adapter/normalization/comparison capabilities;
6. calibrate IMP simulation against observed market evidence and the comparator;
7. freeze numeric divergence tolerances;
8. bind exact provider/data/comparator IDs in the immutable campaign manifest.

## Phase 9 — lane-by-lane expansion

After the first complete evidence path works, add providers according to measured strategy gaps:

- **Short squeeze:** short interest/volume, float, borrow/locate, halts, catalysts and social/context data.
- **Options/volatility:** chains, bid/ask/depth, IV surfaces, Greeks provenance, expiration/assignment/exercise and multi-leg evidence.
- **Microstructure/order flow:** trades, depth/L2/MBO where required, sequence/session integrity.
- **Macro/cross-asset:** official releases, vintages, curves, positioning and consensus only when needed.
- **Quant factors:** PIT/survivorship-safe security, fundamentals and factor datasets.
- **Crypto:** venue-specific feeds plus separately governed on-chain/entity intelligence.
- **Risk/execution:** fees, margin, borrow/funding, fills and capacity evidence.

## Phase 10 — later redundancy and failover

Heavy automated source failover is a later operational-hardening concern. Before multiple production-quality observational lanes exist, redundancy should primarily improve validation and confidence.

Future controls may include provider-health scoring, schema-drift alarms, disagreement alerts, outage routing and non-authoritative fallback. Action-provider failover requires a separate safety decision and must never silently redirect Live orders.

## Immediate execution sequence

1. Keep the pre-implementation architecture closed.
2. Audit current access: Finviz -> Moomoo OpenD -> IBKR -> Tradier -> Alpaca/local state -> existing news/data APIs.
3. Complete the Provider Capability Matrix.
4. Generate the strategy/evidence Coverage-Gap Map.
5. Select the smallest sufficient ES/news provider stack.
6. Implement only missing canonical adapters/normalization/comparison tooling.
7. Verify prospective ES evidence and an appropriate external comparator.
8. Run simulator calibration/shakedown and freeze quantitative gates.
9. Resolve the remaining FTEP activation decisions and freeze the campaign manifest.
10. Run the first qualifying prospective campaign.
11. Expand provider coverage strategy-by-strategy from measured gaps.

## Definition of done for provider planning

Provider planning is complete when:

- the broad provider universe is cataloged enough to prevent blind procurement;
- current user-accessible resources are represented truthfully;
- one capability matrix and role vocabulary govern provider choices;
- coverage gaps can be derived from strategy/evidence needs;
- every integration has a named gap, challenger or measured operational purpose;
- canonical adapters/comparison rules prevent vendor lock-in;
- FTEP source binding is explicitly downstream of capability/rights verification;
- cost, rights and maintenance burden are first-class decision variables;
- no document equates cataloging, connectivity or entitlement with evidence authority.

## Explicit non-goals

This strategy does **not** authorize bulk provider integrations, paid subscriptions/trials, Live trading, private account binding, automatic broker failover or campaign activation.

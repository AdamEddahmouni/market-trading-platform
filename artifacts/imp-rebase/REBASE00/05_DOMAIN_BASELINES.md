# Domain Baselines

## Evidence track — `EXISTING`, operational acceptance pending

`VERIFIED` EVIDENCE-01 freezes evidence-sufficiency policy and preserves BUILD26 historical truth. EVIDENCE-01A adds a live-forward-only campaign with append-only persistence; fixture/replay/synthetic observations cannot qualify. EVIDENCE-01B implements the Moomoo/OpenD observational runtime, frozen configuration fingerprint, and settlement integration.

Isolation requirements:

- No autonomous live trading; evidence runtime submits zero orders.
- No modification to prediction ledger, settlement policies, horizons, cohort rules, or frozen sufficiency thresholds.
- Human session authorization and per-order confirmation remain mandatory elsewhere.
- Automatic broker failover remains prohibited.
- EVIDENCE-01C must be a separate bounded shakedown/operational-acceptance record and remains excluded from qualification unless policy explicitly says otherwise.

Next safe milestone: run/document EVIDENCE-01C against the frozen runtime/configuration, with no REBASE semantic changes mixed into the campaign.

## Cross-asset — `PARTIAL`

Existing domains/foundations:

- U.S. macro/rates/yield curve/liquidity/credit/USD via governed FRED/ALFRED registries, release IDs, revision sensitivity, usage rights, and PIT vintages.
- Energy fundamentals via governed EIA petroleum/natural-gas releases.
- Futures families and CFTC positioning across index, rates, FX, energy, metals, and agriculture.
- Equity institutional intelligence via SEC/13F snapshots and quarter-over-quarter changes, participant contracts, crowding, derivatives, and PI11 equity/COT alignment.
- Options, order flow, market context, and cross-lane evidence contracts.

Missing or not verified as canonical domains:

- Sovereign bond/instrument and curve ontology beyond U.S. macro series/futures.
- Spot/forward FX instruments, calendars, fixing/settlement, and central-bank reserve flows.
- TIC and auction source adapters; broader international macro/policy/revision calendars.
- CBDC/stablecoin/crypto market and on-chain admitted sources.
- One cross-asset identity/exposure/relationship graph and domain-neutral opportunity comparison.

First safe implementation milestone: define a cross-asset kernel extension contract and source-admission template, then implement one bounded domain/source vertical. FRED rates are the lowest-risk reference because clocks, revisions, rights, and registry patterns already exist; it must not be mislabeled as tradable bond data.

## Real-time Opportunity Fabric — `PARTIAL`

Current path:

```text
OpenD callback (QUOTE/TICKER/ORDER_BOOK)
  -> minimal envelope
  -> bounded in-memory queue
  -> ingest thread normalization/admission
  -> in-memory observational state (quote/book/500 trades)
  -> UI projections / bounded research consumers

Polling/control plane
  -> reachability + capability probe + subscription sync
  -> reconnect + diagnostics
```

Existing timing: event-to-local-receipt and local processing p50/p95/max, queue depth/drop/overflow, duplicates and sequence anomalies. This is not exchange latency. Other subsystems record individual delivery or validation durations, but no end-to-end trace joins provider/network/platform/features/model/risk/UI/human/broker stages.

Existing features: snapshot book imbalance/depth/microprice/liquidity walls, explicit prior/current book diff, window-recomputed CVD/NSS, realized volatility, event detection/routing/scheduling, opportunity economics/policy, and UI evidence projection.

Likely bottlenecks (`INFERRED`, not measured): Python normalization/feature recomputation on growing windows, synchronous file persistence in some paths, UI polling/projection rebuilds, provider callback/queue pressure, and human authorization. Unknown: provider/network distribution, model/risk contribution, broker round trip, GC/contention, and sustained multi-symbol load.

Instrument before optimization: canonical run/correlation/trace IDs, stage timestamps, queue wait vs processing, feature window size/cost, persistence cost, UI publish/render age, human-decision time, broker request/ack/fill times, and benchmark environment. Do not authorize Rust/event-bus migration until measurements identify a binding SLO gap.

## Narrative and motive — `PARTIAL`

`VERIFIED` Market-context event clustering, keyword sentiment, optional frozen FinBERT labels, catalyst synthesis, experimental narrative prevalence/velocity/acceleration, and fixture-precomputed multi-document synthesis exist. They are PIT-gated, model-versioned in selected contracts, display/research-only, and explicitly avoid a universal news score.

`ABSENT` A canonical actor/motive ontology, source credibility model, durable thesis graph across domains, live LLM synthesis pipeline, causal validation standard, and admitted influence-intelligence runtime. Proposed influence/crypto/prediction-market documents remain experimental.

Reuse the event/document/revision clocks, participant identity/action contracts, hypothesis/evidence model, model-version refs, and contradiction/quality flags. Keep motive as uncertain evidence, never as a fact or execution authority.

## AI/Agent — `PARTIAL`

`VERIFIED` The assistant has a provider-neutral read-only inference protocol, abstaining and grounded fallbacks, one Anthropic Messages adapter, bounded evidence packs, citation refs, conversation/message persistence, model/provider/token/citation provenance, and a `READ_ONLY_NO_EXECUTION` boundary. MC5/MC16 fixture-precomputed LLM labels carry model/prompt/schema/feature versions.

Gaps:

- Assistant system prompt and evidence pack are not versioned/hashed into each message record.
- Exact inference parameters, request/response identifiers, code/config/run identity, latency, retries, raw response hash, and tool invocations are absent.
- Conversation JSON is rewritten as an array and supports deletion, so “append-only” is logical behavior, not immutable/WORM evidence.
- If a live response lacks citations, current fallback behavior can attach fallback citations while retaining the live model text; citation provenance therefore needs stricter claim-to-source validation before any higher-stakes use.
- No agent workflow, skill/tool registry, approval lifecycle, sandbox identity, or universal agent-run record exists.

Minimum safe foundation: bind every AI operation to the Universal Run Ledger; freeze/hash prompt template, evidence pack, model/provider/settings, tool inputs/outputs, citations, response, approvals, and code/config. Preserve read-only/no-execution authority. A skill registry is deferred until actual reusable agent workflows exist.

# Integrated Market Platform: Canonical Foundation Design and Roadmap

**Status:** Conditionally approved architecture; foundation specification requires revision before implementation.  
**Date:** 2026-08-13  
**Initial vertical slice:** Historical ES futures and order flow  
**Operating mode:** Offline replay and simulated execution only

## 1. Executive decision

The five supplied projects can become one coherent platform, but they should not
be merged by copying their applications into a single process or by connecting
all of their current APIs and databases. They are prototypes with valuable,
unevenly mature capabilities and incompatible assumptions.

The canonical direction is to build a new, provider-agnostic platform core and
migrate capabilities into it incrementally. Existing applications remain usable
as references, demonstrations, test oracles, and sources of proven logic until
each selected capability is represented behind a canonical contract and has
passed migration acceptance tests.

The first milestone proves the architecture with one narrow, end-to-end path:

```text
historical ES market events
  -> provider-specific input adapter
  -> canonical, point-in-time-safe events
  -> data-integrity and quality evaluation
  -> order-flow features
  -> one explicit strategy hypothesis
  -> independent risk decision
  -> conservative simulated execution
  -> positions, performance, and full attribution
```

This milestone validates research infrastructure, not trading profitability.
It includes no live broker connection and no live-order path.

## 2. Goals

### 2.1 Immediate goals

1. Establish one authoritative definition of the platform and its boundaries.
2. Remove permanent broker or data-vendor assumptions from the core design.
3. Make point-in-time correctness and data quality enforceable invariants.
4. Create deterministic event replay from raw input through attributed results.
5. Migrate only capability-supported CVD, OFI, or depth calculations behind
   canonical events.
6. Prove separation among features, strategies, risk, and execution.
7. Produce a reproducible ES replay report that explains every decision.
8. Preserve useful prototypes without treating them as production architecture.

### 2.2 Long-term goals

The eventual system is a provider-agnostic market-intelligence, quantitative
research, strategy-validation, risk, and execution platform. It may present
Futures, Order Flow, Short Squeeze, and Options as product-facing areas, while
its backend remains organized by technical responsibility rather than by four
equivalent score-producing engines.

### 2.3 Non-goals for the first milestone

- Live market-data ingestion.
- Live, broker-routed, or paper-broker order submission.
- A unified production dashboard.
- Multi-user accounts, billing, or public deployment.
- Cross-domain score averaging or a portfolio meta-engine.
- A claim of profitable edge.
- A premium provider commitment.
- Kafka, microservices, Kubernetes, or a cloud data lake.
- Machine learning or an LLM in the trading decision path.
- Full-depth exchange queue reconstruction unless the chosen input supports it.
- Rewriting or deleting all prototype code.

## 3. Current repository state

The workspace root is a collection folder, not currently a Git repository. It
contains five independent projects plus cross-project notes.

| Project | Current role | Useful assets | Important limitations |
|---|---|---|---|
| FuturesX | Futures/Level-2 experiment | Metadata and code references for ES artifacts, DOM parsing, IBKR contract/session knowledge, backtest experiments, order abstractions | Event data is unverified and unavailable locally; principal CSV/database files are 134-byte Git LFS pointers; provider coupling, inconsistent backtests, and unsafe live TP/SL behavior |
| Trading CVD Bubble | Order-flow measurement dashboard | Aggressor classification, CVD, OFI, depth metrics, quality-ranked rollups, demo dataset | IBKR/FinViz and MongoDB coupling, incomplete consolidated coverage, application-sized modules |
| Short Squeeze Core | Evidence-driven research screener | Provenance, freshness, explicit missingness, readiness gates, versioned methodology, deterministic frozen mode | Separate product architecture; not a validated squeeze predictor; existing test-collection issue |
| Internship project | Paper news/options agent | Scheduling, review workflow, audit concepts, options liquidity gate, offline evaluation patterns | Unprofitable paper evidence, arbitrary voting semantics, fragile providers, strategy and orchestration coupling |
| L1 Volume Bubble | TradingView visualization | Bubble visual language, anomaly and absorption heuristics | Pine/TradingView-specific, bar-feed dependent, not an internal market-data engine |

Existing cross-project notes correctly identify several constraints: incompatible
stores, provider coupling, mixed execution safety, and no validated edge. The
new direction strengthens that plan by replacing coarse provider abstractions,
making replay foundational, and preventing arbitrary engine-score comparison.

## 4. Rejected integration approaches

### 4.1 Rewrite all projects into one application

Rejected because it would discard mature evidence and measurement behavior,
create a large untestable change, and make it difficult to distinguish intended
semantic changes from migration defects.

### 4.2 Keep all applications and integrate them through network APIs

Rejected as the canonical target because it preserves incompatible contracts,
stores, clocks, provider assumptions, and score semantics. It also introduces
distributed-system complexity before the domain boundaries are stable.

### 4.3 Incremental core and capability migration

Accepted. The platform begins as a modular monolith with explicit internal
interfaces. Network boundaries may be introduced later only where operational
evidence justifies them.

## 5. Canonical architecture

### 5.1 Logical repository layout

```text
market-trading-platform/
  platform/
    contracts/
    reference_data/
    providers/
    normalization/
    data_quality/
    storage/
    replay/
    features/
      order_flow/
    strategies/
    risk/
    execution/
    portfolio/
    attribution/
    reporting/
  tests/
    contract/
    integration/
    replay/
    parity/
    acceptance/
  prototypes/                 # logical classification first; move later
  docs/
    architecture/
    decisions/
    providers/
    research/
    roadmap/
    audits/
```

The existing directories should initially remain in place. Moving them is a
separate, low-value operation that can break paths, imports, data references,
and demonstrations. Documentation will classify them as prototypes before any
physical relocation is considered.

### 5.2 Layer responsibilities

| Layer | Owns | Must not own |
|---|---|---|
| Contracts | Stable schemas, identifiers, versions, enums | Provider SDK objects or strategy rules |
| Reference data | Instruments, contracts, sessions, calendars, ticks, multipliers | Live quote state or alpha |
| Providers | Capability interfaces and source adapters | Strategy logic or platform-wide data models |
| Normalization | Provider payload to canonical-event conversion | Feature computation or trading decisions |
| Data quality | Integrity states, gaps, staleness, clock and sequence checks | Quiet data repair that changes evidence |
| Storage | Immutable raw inputs and queryable derived records | Business meaning or strategy selection |
| Replay | Ordered event delivery and deterministic clock | Feature formulas or broker-specific behavior |
| Features | Versioned measurements of market state | Trades, sizing, or broker calls |
| Strategies | Explicit hypotheses, scores, directional signals, and abstentions | Order sizing, position actions, broker calls, or fill assumptions |
| Risk | Eligibility, limits, rejection, and resize decisions | Creating alpha or rewriting strategy evidence |
| Execution | Order lifecycle and simulated/eventual broker routing | Deciding whether a thesis has edge |
| Portfolio | Positions, cash, exposure, and later allocation | Provider normalization |
| Attribution | Why a decision happened and why performance differed | Changing historical decisions |
| Reporting | Human-readable research and operational views | Becoming the authoritative data store |

### 5.3 Dependency direction

Core domain modules depend on canonical contracts, never on provider SDKs.
Provider adapters depend inward on contracts. Strategy modules may consume
features, context, and quality state but may not import execution adapters.
Execution may consume approved order intents but may not invoke strategies.

Dependency enforcement should eventually be automated with import-boundary tests.

## 6. Provider architecture

### 6.1 Capability-based interfaces

A monolithic `BrokerProvider` or `MarketDataProvider` is too coarse. Interfaces
should represent independently replaceable capabilities, including:

```text
EquityQuoteProvider         OptionQuoteProvider
EquityTradeProvider         OptionTradeProvider
EquityDepthProvider         OptionChainProvider
                            OptionAnalyticsProvider

FuturesQuoteProvider        ShortInterestProvider
FuturesTradeProvider        ShortVolumeProvider
FuturesDepthProvider        BorrowProvider
FuturesMBOProvider

NewsProvider                EconomicEventProvider
ReferenceDataProvider       ExecutionBroker
```

One adapter may implement several interfaces. A runtime composition selects one
or more adapters per capability. Strategies receive canonical data and do not
know which provider produced it.

### 6.2 Current candidates are configuration, not architecture

| Capability | Initial research candidate | Alternative or future candidate | First-slice status |
|---|---|---|---|
| Historical futures events | FuturesX references a Databento export, but event data is unverified and unavailable locally | A lawfully obtained, capability-verified export | Required but blocked |
| Live futures trades/quotes | tastytrade, IBKR, Webull, Databento | Other entitled provider | Deferred |
| Live futures depth | Undecided | IBKR, Webull, Databento | Deferred |
| Equity trades/depth | Moomoo candidate | Webull or another entitled source | Deferred |
| Consolidated equity/options | Tradier candidate | Moomoo or premium source | Deferred |
| Historical option detail | Existing artifacts where lawful | ThetaData or another source | Deferred |
| Short interest/volume | FINRA/public authoritative sources | Broker or specialist supplement | Later |
| Equity/options execution | Tradier candidate | IBKR or another broker | Future |
| Futures execution | tastytrade candidate | IBKR or another broker | Future |

Capabilities, prices, promotions, entitlements, coverage, redistribution rights,
and account requirements must be maintained in a dated provider matrix. None of
those mutable facts belongs in strategy logic.

The only readable FuturesX evidence for the large Databento object is metadata
for dataset `GLBX.MDP3`, schema `ohlcv-1m`, and symbol request `ES.FUT`. The
867,774,289-byte payload is represented locally by a 134-byte Git LFS pointer.
The 231,641,168-byte Level-2 CSV and 180,203,520-byte depth database are also
134-byte pointers. They are unavailable data, not fixtures, and no capability
claim may be inferred from their names. One-minute OHLCV metadata establishes
neither event-level trades nor quotes, depth, MBO, aggressor direction, or queue
semantics.

### 6.3 Adapter obligations

Every adapter documents:

- Implemented capability and unsupported operations.
- Provider, venue, entitlement, and coverage assumptions.
- Provider timestamp definitions and precision.
- Symbol and contract mapping.
- Snapshot versus incremental semantics.
- Sequence and reconnect behavior.
- Raw-payload retention and redaction policy.
- Rate and historical-range limits.
- Licensing and redistribution restrictions.
- Test fixtures with no live-network dependency.

## 7. Canonical contracts

### 7.1 Shared envelope

Every canonical observation uses a versioned envelope. Fields are not made
optional merely because an adapter cannot populate them; the schema declares the
requirement state and the record carries the corresponding value and provenance.

```text
normalized_event_id
source_record_id
source_revision_id
normalization_version
schema_version
event_type
instrument_id
venue_id
publisher_id
channel_id
source_instance_id
event_time
source_publish_time
live_received_time
historical_ingested_time
available_time
source_sequence
ingest_run_id
raw_reference
quality_observation_refs[]
operation
supersedes_event_id
```

The four timestamp requirement states are normative:

- `REQUIRED`: a source or canonical value must be present; absence rejects the
  record.
- `DERIVED`: a value must be present together with `derivation_method`, source
  fields, and uncertainty. A derivation may reduce precision but may not invent
  it.
- `UNAVAILABLE`: the source does not supply a defensible value; the value is
  null and quality/capability policy decides whether the event is usable.
- `FORBIDDEN`: the concept does not apply or would be misleading; the field must
  be absent. Populating it rejects the record.

Each event schema declares one of these states for every timestamp field. An
adapter may be stricter than the family default but may not weaken it:

| Event family and acquisition mode | `event_time` | `source_publish_time` | `live_received_time` | `historical_ingested_time` | `available_time` |
|---|---|---|---|---|---|
| Live trade, quote, depth update, or market status | `REQUIRED` at source precision | `UNAVAILABLE` unless native | `REQUIRED` from monotonic collector boundary | `FORBIDDEN` | `DERIVED` as no earlier than `live_received_time` |
| Historical event-level trade, quote, or depth export | `REQUIRED` | `UNAVAILABLE` unless export supplies a real publication boundary | `FORBIDDEN` | `REQUIRED` for lineage only | `DERIVED` from documented historical-observability semantics; never from ingestion time |
| Interval aggregate such as a bar | interval start/end `REQUIRED`; timestamp meaning explicit | `REQUIRED`, `DERIVED`, or `UNAVAILABLE` by source | live only: `REQUIRED`; historical: `FORBIDDEN` | historical only: `REQUIRED`; live: `FORBIDDEN` | `DERIVED` no earlier than interval close and any known publication delay |
| Published or revised evidence, including news and short interest | observation/effective time `REQUIRED` or `UNAVAILABLE` by domain | `REQUIRED` or conservatively `DERIVED` | live only: `REQUIRED`; historical: `FORBIDDEN` | historical only: `REQUIRED`; live: `FORBIDDEN` | `DERIVED` from the defensible publication boundary and, live, receipt boundary |
| Correction, revision, cancel, or bust | original event time preserved when known | correction publication time `REQUIRED` or `DERIVED` | mode-specific as above | mode-specific as above | `DERIVED` from when the correction became knowable |
| Quality observation | affected interval `REQUIRED` | `FORBIDDEN` | `UNAVAILABLE` unless detected live | `UNAVAILABLE` unless detected during ingestion | detection `available_time` `REQUIRED` |

`historical_ingested_time` says when an export entered this platform. It is
operational lineage and must not be substituted for a historical
`live_received_time` or used to reveal the record in replay. A live collector's
`live_received_time` records the collector boundary; it is not backfilled after
the fact. Replay visibility is governed exclusively by `available_time`.

All canonical timestamps are signed 64-bit UTC epoch nanoseconds. Each value
also records `source_timestamp_precision` and `timestamp_derivation`; adapters
preserve coarser source precision and never add false subsecond significance.
Calendar dates and exchange-local timestamps remain explicit source fields until
resolved through a versioned timezone and session-calendar record. Leap-second
and ambiguous local-time policy is fixed by ADR before affected data is admitted.

### 7.2 Identity, sequence, and idempotency

Source identity and normalized identity serve different purposes:

- `source_record_id` is the provider-native record identity within the tuple
  `(provider_id, venue_id, publisher_id, channel_id, source_instance_id)`. When a
  provider supplies no native identifier, the adapter derives one from immutable
  raw bytes plus documented record boundaries and marks it `DERIVED`.
- `normalized_event_id` is deterministic UUIDv5 over the fully qualified source
  identity, semantic event family, source revision, and subrecord discriminator.
  It identifies one immutable normalized fact, not a mutable business entity.
- `source_revision_id` distinguishes corrections or versions of one source
  record. `supersedes_event_id` links normalized revisions. Neither identifier is
  silently reused when content changes.
- Idempotent ingestion of the same identity and canonical bytes is a no-op. The
  same identity with different bytes is an integrity conflict: quarantine both,
  emit a quality observation, and fail the affected partition.

`source_sequence` is meaningful only with an explicit `sequence_scope`. The
minimum scope is `(provider_id, venue_id, publisher_id, channel_id,
source_instance_id, trading_session_or_reset_epoch)`. A reconnect creates a new
source instance unless the provider proves sequence continuity. Sequences from
different scopes are never compared. Missing sequence values remain unavailable;
arrival order is not promoted to native sequence.

Canonical deterministic ordering is the ascending tuple:

```text
(available_time,
 event_time_state_rank,
 event_time_or_minimum,
 sequence_scope_or_empty,
 source_sequence_or_minimum,
 event_type_precedence,
 normalized_event_id)
```

`event_time_state_rank` and `event_type_precedence` are versioned run inputs. A
missing value uses an explicit sentinel, not platform iteration order. This
ordering controls delivery, but it does not repair source history: late arrival,
time regression, and sequence gaps remain observable quality facts.

### 7.3 Schema and numeric compatibility

Schemas use semantic versions. A reader may accept the same major version only
when unknown fields are preserved or explicitly ignored and all declared
invariants still hold. Removing a field, changing units, changing null meaning,
or changing identity/timestamp semantics requires a new major version. Migrations
are pure, versioned transformations with input/output hashes; no in-place rewrite
of raw or completed-run data is allowed. Every run pins exact writer, reader, and
migration versions.

Prices and money never use binary floating point in authoritative records:

- Exchange prices are signed 64-bit integers in `price_increment_units` plus the
  bitemporal reference to the exact rational minimum increment.
- Fees, cash, and P&L use signed integers in a declared currency minor-unit scale;
  products requiring finer precision declare an exact rational scale.
- Quantities are signed integers with an explicit unit such as contracts, shares,
  or native size units. Fractional quantities require a declared rational scale.
- Rounding mode is an enum and part of every calculation contract. Buy limits
  round down and sell limits round up unless a separately approved order policy
  documents a more conservative rule.
- Overflow, non-integral conversion, unknown multiplier, or absent tick rule is a
  hard rejection, never an implicit float conversion.

### 7.4 Initial event set

- `TradeEvent`
- `QuoteEvent`
- `DepthSnapshotEvent`
- `DepthUpdateEvent`
- `MarketStatusEvent`
- `QualityObservation`
- `DataQualityEvent`, a persisted transition that references one or more quality
  observation identifiers and never duplicates inline quality state

Later event families include option quotes/trades/chains, short-interest and
borrow observations, news, economic releases, halts, corporate actions, and
public disclosures.

### 7.5 Corrections, revisions, busts, and late events

`operation` is one of `ORIGINAL`, `CORRECTION`, `REVISION`, `CANCEL`, or `BUST`.
Corrections never overwrite a prior event. The new event links to the superseded
event, retains its own source identity and `available_time`, and becomes visible
only when the correction was knowable. A replay at an earlier clock retains the
old state; a later replay applies the correction prospectively according to the
event-family reducer. Busts reverse the eligible prior trade contribution from
their own `available_time`; revisions replace published evidence prospectively.
An orphan correction or bust is quarantined unless an event-specific policy
explicitly supports it.

An event is late when its delivery or availability violates its source's declared
ordering/watermark contract. It is dispatched at its actual `available_time` and
must not be silently inserted into a previously evaluated state. Feature reducers
declare whether they recompute, apply a compensating update, mark a window
invalid, or fail closed. Strategy decisions already emitted are immutable; any
later reevaluation is a new decision linked to the late evidence.

### 7.6 Order-flow metadata

Classified trades include:

```text
aggressor_side       = BUY | SELL | UNKNOWN
aggressor_source     = EXCHANGE_NATIVE | QUOTE_INFERRED | TICK_INFERRED | UNKNOWN
aggressor_confidence = 0.0..1.0
classifier_version
```

Inferred equity aggressor information must never be silently represented as
equivalent to exchange-native futures aggressor information.

### 7.7 Futures and bitemporal reference data

The contract master includes:

```text
contract_id, root, provider_symbols, exchange, currency,
first_trade, last_trade, expiry, roll_window,
tick_size, multiplier, timezone, session_calendar,
volume, open_interest, metadata_version
```

Reference records are bitemporal: `valid_from`/`valid_to` describe when the fact
applies in the market, and `known_from`/`known_to` describe when the platform
could know that version. Queries require both an effective market time and an
as-of knowledge time. Corrections append a new version. Contract multipliers,
tick rules, sessions, symbol mappings, rolls, and corporate actions may not be
overwritten. Actual historical contracts are preserved in execution research.
Continuous series may be used only for explicitly labeled analysis or
visualization and never for fill or cash accounting.

### 7.8 Score, signal, intent, risk, order, fill, and position semantics

The decision chain is strictly one-way:

```text
feature measurements
  -> strategy score
  -> directional signal or abstention
  -> order intent
  -> independent risk decision
  -> order lifecycle
  -> fill lifecycle
  -> position action and accounting
```

The contracts remain distinct:

| Contract | Responsibility | Required separation |
|---|---|---|
| `StrategyEvaluation` | Records features, raw score, hypothesis result, and reasons | `ABSTAIN` is an evaluation outcome, not direction or an order |
| `StrategySignal` | States `LONG` or `SHORT`, horizon, expiration, invalidation, and evidence | Cannot contain sizing, broker fields, `EXIT`, or `REDUCE` |
| `OrderIntent` | Requests `OPEN`, `INCREASE`, `REDUCE`, `CLOSE`, or `REVERSE` with desired quantity/exposure and constraints | Cannot claim approval, order status, or fill |
| `RiskDecision` | Returns `APPROVE`, `REJECT`, or `RESIZE` with policy version and reasons | Cannot change direction or manufacture a signal |
| `Order` | Tracks `CREATED`, `ACTIVATED`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_PENDING`, `CANCELLED`, `EXPIRED`, or `REJECTED` | Order status is not strategy conviction or position state |
| `Fill` | Records an immutable execution allocation | Cannot exist before order activation |
| `PositionAction` | Applies fills to `OPEN`, `INCREASE`, `REDUCE`, `CLOSE`, or `REVERSE` a position | Derived from fills and accounting rules, never emitted as a directional signal |

`raw_score`, `calibrated_probability`, `confidence`, `expected_return`, expected
adverse movement, and expected value are different fields with versioned
definitions. Until empirical calibration exists, probability and expected-return
fields are null. `ABSTAIN` requires structured reasons such as insufficient
capability, ineligible quality, no setup, conflicting evidence, or expired setup;
it is not encoded as a zero score, flat direction, `HOLD`, or rejected order.

## 8. Point-in-time correctness

Point-in-time correctness is a platform invariant, enforced at storage and replay
boundaries. No component may consume information before its `available_time`.

The visibility predicate is machine-enforced:

```text
visible(event, replay_clock) =
  event.available_time <= replay_clock
  AND referenced_bitemporal_records.known_from <= replay_clock
  AND replay_clock < referenced_bitemporal_records.known_to
```

`event_time`, observation date, reporting period, market-effective time,
historical ingestion time, database insertion time, and file modification time
cannot independently grant visibility. Required controls include:

- Short interest uses publication availability, not only observation date.
- News and filings retain publication, acceptance, ingestion, and revision times.
- Economic releases retain scheduled and actual release times.
- Options research uses historically available chain snapshots.
- Corporate actions and symbol mappings are historically versioned.
- Futures research uses the correct actual contract and roll state.
- Corrections are new versioned facts rather than silent overwrites.
- Feature snapshots record the maximum input-availability time used.
- Replay rejects future-visible records and reports the exact evidence.

The existing Short Squeeze contract uses `effective_timestamp` as its replay key
and often defines it as the maximum of source publication and ingestion/receipt.
The canonical contract uses `available_time` and distinguishes historical
ingestion from live receipt. These names are not assumed equivalent. Blocking ADR
`ADR-TIME-001` must choose one of the following before Short Squeeze primitives
are reused: (a) prove and encode a lossless field mapping by event family, (b)
retain `effective_timestamp` as a domain field while deriving canonical
`available_time`, or (c) migrate the prototype contract and fixtures. The ADR
must test historical exports, live capture, date-only publication, corrections,
and replay ordering. Until accepted, Short Squeeze records cannot enter the
canonical event store.

## 9. Data quality engine

### 9.1 Scoped quality observations

Quality is not a flat flag list attached to an event. A `QualityObservation`
evaluates one dimension over an explicit scope and interval:

```text
quality_observation_id
dimension
state
severity
scope = provider/venue/publisher/channel/source_instance/
        instrument/event_family/field/sequence_scope
affected_from, affected_to
detected_at, available_time
evidence_refs[]
rule_id, rule_version
expected, observed
recovery_rule
supersedes_quality_observation_id
```

Initial dimensions and example states are:

| Dimension | Example states; not a single global enum |
|---|---|
| Completeness | `COMPLETE`, `PARTIAL`, `MISSING_TRADES`, `MISSING_QUOTES`, `MISSING_DEPTH` |
| Timeliness | `ON_TIME`, `STALE`, `CLOCK_DRIFT`, `LATE` |
| Sequencing | `CONTIGUOUS`, `GAP`, `REGRESSION`, `DUPLICATE`, `UNSCOPED` |
| Validity | `VALID`, `INVALID_TIMESTAMP`, `INVALID_QUOTE`, `CROSSED_BOOK` |
| Consistency | `CONSISTENT`, `SNAPSHOT_UPDATE_MISMATCH`, `CONTRACT_MAPPING_INVALID` |
| Reference integrity | `RESOLVED`, `UNKNOWN_INSTRUMENT`, `SESSION_STATE_UNKNOWN` |
| Provenance | `TRACEABLE`, `RAW_REFERENCE_MISSING`, `IDENTITY_CONFLICT` |
| Availability/entitlement | `AVAILABLE`, `UNAVAILABLE`, `PROVIDER_DISCONNECTED`, `ENTITLEMENT_UNKNOWN` |

Absence of one dimension is `NOT_EVALUATED`, not `FEED_OK`. An aggregate
eligibility decision is a versioned policy over required dimensions for a
specific consumer, event family, scope, and time. It never erases the underlying
observations.

### 9.2 Persistence without circularity

Canonical market-event envelopes contain only
`quality_observation_refs[]` known when that record version is written. A
`DataQualityEvent` records the creation, transition, recovery, or supersession of
one or more `QualityObservation` records. It does not contain another inline list
of quality flags, and a quality observation never cites the `DataQualityEvent`
that persists it. Later-discovered quality facts append observations and events;
they do not mutate prior market events.

### 9.3 Quality policy

- Detection persists the observation, rule version, evidence, scope, interval,
  and availability boundary.
- Repair, if allowed, creates an explicit transformation record and a new event;
  it does not hide or delete the original evidence.
- Unknown, unavailable, and not evaluated are distinct and never converted to
  zero, false, complete, or healthy.
- Features and strategies publish a capability-and-quality requirement profile.
- Risk independently reevaluates eligibility at intent time.
- Missing mandatory evidence produces strategy `ABSTAIN`; a later intent with
  ineligible evidence produces risk `REJECT`.
- Recovery has a rule, scope, effective interval, and test; a healthy event does
  not implicitly close an earlier gap.
- Replay reports duration and event counts by dimension, state, scope, and rule
  version.

The decision invariant is:

```text
order_allowed = signal_valid AND intent_valid AND data_valid AND risk_approved
```

## 10. Storage design

### 10.1 First-milestone storage

The logical layout is fixed even if the physical database engine changes:

```text
data/
  raw/<license_class>/<source_artifact_sha256>/...
  canonical/<schema_major>/<event_family>/<instrument_id>/<session_date>/...
  reference/<schema_major>/<reference_family>/...
runs/<run_id>/
  staging/
  manifest.json
  decisions/
  execution/
  reports/
  COMPLETE | FAILED
```

Raw objects and completed canonical partitions are immutable and addressed by
SHA-256. Partition manifests contain ordered member hashes, row counts, schema
version, min/max times, adapter version, and source references. Derived outputs
are separate from raw licensed data. Paths are manifest data, never inferred from
the current working directory. `ADR-STORE-001` chooses DuckDB, SQLite, or a split
control/data plane only after a usable fixture establishes row counts, query
patterns, atomicity behavior, and packaging constraints; that engine choice may
not alter the logical layout or contracts.

### 10.2 Licensing boundary

The storage model distinguishes:

1. Raw licensed market data.
2. Normalized internal events.
3. Derived internal features.
4. Results that may legally be displayed, exported, or redistributed.

Provider entitlement does not imply redistribution permission. Raw artifacts
must carry a source and license classification. Public dashboards and APIs must
not be designed until permitted outputs are known.

### 10.3 Retention and reproducibility

- Never mutate a completed run.
- New logic produces a new version and run identifier.
- Preserve negative and failed experiments.
- Store code revision when a Git root exists; until then store source hashes.
- Document retention, backup, and deletion policy before live collection.

Run lifecycle is atomic: `CREATED -> VALIDATING -> RUNNING -> FINALIZING ->
COMPLETE` or terminal `FAILED`. All writes occur below `staging/`. Finalization
flushes outputs, verifies reconciliation, writes and hashes the terminal manifest,
then atomically publishes the run directory and terminal marker. A run without a
valid terminal marker is incomplete and cannot be an input to acceptance or
research comparison. Recovery creates a new attempt identifier; it never resumes
by mutating a completed bundle.

## 11. Deterministic replay

### 11.1 Replay responsibilities

The replay engine:

1. Loads an immutable input manifest.
2. Validates schema, instrument, contract, and time boundaries.
3. Orders events using documented deterministic rules.
4. Advances a simulated clock.
5. Reveals events only at their availability time.
6. Dispatches events to quality and feature processors.
7. Invokes strategy evaluation at explicit triggers.
8. Sends approved intent to simulated execution.
9. Updates orders, fills, positions, and portfolio state.
10. Persists attribution and a terminal run manifest.

### 11.2 Ordering policy

Ordering uses the exact tuple in Section 7.2. Ties must never depend on
filesystem, database, process scheduling, locale, or hash-map iteration order.
Late and out-of-order events are retained and surfaced to quality logic rather
than silently resorted into perfect history.

### 11.3 Reproducibility requirement

The same input hashes, canonical configuration, clock rules, dependency lock,
ordering-policy version, schema/migration versions, component versions, and
declared random seed must produce byte-identical canonical artifacts. Canonical
JSON uses UTF-8, sorted keys, fixed numeric rendering, UTC timestamps, and LF line
endings; partition and run hashes use ordered SHA-256 Merkle manifests. Wall
clock, host path, thread scheduling, and nondeterministic object identifiers are
excluded from canonical artifacts or normalized into a separate operational
manifest. The run fails closed when required versions or inputs are unavailable.

## 12. Order-flow engine

### 12.1 Feature hierarchy

CVD and volume bubbles are not independent domains. They belong within order
flow, which contains:

- Aggressor-side buy/sell volume, delta, and CVD.
- Rolling delta, velocity, acceleration, and trade intensity.
- Large-trade and anomalous-size detection.
- Bid/ask depth, order-book imbalance, OFI, and multi-level OFI.
- Microprice, queue depletion, replenishment, cancel/add behavior, and depth
  concentration when the input supports them.
- Higher-level candidates such as absorption, exhaustion, sweeps, failed
  auctions, CVD divergence, and liquidity instability.

Each feature has a version, formula, parameters, reset rule, required inputs,
quality prerequisites, and unit tests. Visual bubbles consume these features;
they do not define a separate source of trading truth.

### 12.2 First migrated calculations

An adapter emits a signed capability manifest based on inspected records, not
filenames or provider marketing. Initial capability identifiers include
`BAR_OHLCV_1M`, `TRADES`, `BBO_QUOTES`, `MBP_DEPTH_N`, `MBO`,
`NATIVE_AGGRESSOR_SIDE`, `SOURCE_SEQUENCE`, `CORRECTIONS`, and
`SESSION_STATUS`. A capability states coverage, venues/publishers, depth level,
timestamp precision, sequence scope, snapshot/update semantics, and measured
quality limitations.

| Feature or claim | Minimum verified source capability | Prohibited inference |
|---|---|---|
| Trade delta and CVD | `TRADES` plus `NATIVE_AGGRESSOR_SIDE`, or `TRADES` plus `BBO_QUOTES` and a documented, versioned quote-classification method | OHLCV or total bar volume cannot be split into aggressor volume without independent evidence |
| Best-level OFI | sequenced `BBO_QUOTES` with size and update semantics | Bar high/low or trade direction cannot stand in for quote updates |
| Top-N imbalance | verified `MBP_DEPTH_N` snapshots/updates and recovery rules | A Level-2 filename does not prove level count or semantics |
| Liquidity consumption/sweep | verified multi-level depth semantics, trades or execution events linkable to depleted levels, and adequate sequencing | One-minute bars, best quote alone, or unsequenced snapshots cannot establish a sweep |
| Queue position, adds/cancels by order, or queue fidelity | `MBO` with order identity, priority, sequence, and lifecycle semantics | MBP depth cannot support queue-position claims |

Only calculations whose capability rows pass may migrate into the initial slice.
Advanced iceberg, spoofing, or full-queue claims remain prohibited until their
data semantics and validation contracts are separately approved.

## 13. Initial strategy hypothesis

The first strategy is selected only after the data-feasibility and strategy-
capability assertions pass. Its role is to exercise contracts, feature timing,
abstention, risk, simulation, and attribution; its identity is not fixed in
advance of usable evidence.

The preferred candidate is a deliberately narrow ES liquidity-sweep reversal,
but it is eligible only with verified multi-level depth semantics and linkable
consumption evidence. Queue-position language or queue-faithful fills require
MBO and are otherwise prohibited. Its conceptual conditions are:

1. Visible liquidity is consumed across configured adjacent levels.
2. Price fails to continue and rejects within a bounded interval.
3. CVD or OFI behavior meets an explicitly defined confirmation condition.
4. Session, quality, and event-window prerequisites are satisfied.
5. The strategy records its score and emits a directional signal with horizon,
   invalidation, and evidence, or a distinct `ABSTAIN` outcome with reasons. A
   later `OrderIntent` is separate.

All thresholds are configuration values recorded in the run manifest. No
data-dependent threshold is specified until a usable fixture has been inspected.
The initial study may explore parameter regions but must not select a single
optimum based on maximum historical profit.

If sweep capability fails, a CVD-divergence candidate may be proposed only when
verified trades plus native aggressor direction exist, or when verified trades
and quotes support a documented quote-classification method with version,
coverage, unknown handling, and error characterization. Failure of both gates
leaves strategy selection blocked; it does not authorize a bar-based proxy. The
currently readable `ohlcv-1m` metadata and a one-minute OHLCV payload alone fail
the first-strategy capability gate.

## 14. Risk engine

Risk is independent from strategy generation. The initial engine evaluates:

- Data-quality eligibility.
- Allowed instrument and contract.
- Session and economic-event windows.
- Maximum loss per simulated trade.
- Maximum position and gross exposure.
- Daily realized and mark-to-market loss.
- Drawdown and consecutive-loss limits.
- Minimum liquidity and maximum modeled slippage.
- Signal expiration and invalidation.
- Duplicate/conflicting intent.
- Kill-switch state.

It returns `APPROVE`, `REJECT`, or `RESIZE`, plus structured reasons and policy
version. A profitable-looking signal may still be rejected. Strategy code cannot
override risk.

## 15. Simulated execution

The initial engine is source-capability aware. An approved intent creates an
order at `created_time`; submission latency produces `submitted_time`; modeled
exchange latency produces `activation_time`. No fill may use an event with
`available_time < activation_time`, an event that triggered the decision, or an
aggregate interval that was not complete and visible after activation. Same-
timestamp fills require an ordering key proving the eligible execution evidence
followed activation; otherwise they are rejected.

Execution modes are explicit:

| Source capability | Permitted baseline | Required limit |
|---|---|---|
| Trades plus quotes, no MBO | Conservative touch/trade model | Fill quantity cannot exceed eligible post-activation observed trade volume at or through the order price, multiplied by a preregistered participation cap |
| MBP depth, no MBO | Depth-aware conservative model | Displayed size may bound liquidity but cannot establish queue priority; fills still require eligible subsequent executions or conservative depletion evidence |
| MBO | Queue model only after separate validation | Allocation follows verified venue priority and order lifecycle; model/version and queue initialization are recorded |
| Bars only | Bar-level sensitivity model, if separately approved for a bar strategy | No intrabar path, queue, sweep, aggressor, or same-bar fill claim; pessimistic ambiguity rules are mandatory |

Without MBO, simulated allocation cannot claim FIFO position. Eligible observed
volume is allocated in deterministic order by `(activation_time, order_id)` after
subtracting a configured ahead-volume assumption and prior simulated allocations.
Pro-rata or venue-specific allocation is allowed only when source and venue
semantics support it and the policy is versioned. Participation caps,
ahead-volume assumptions, and ambiguous-bar rules are preregistered parameters;
they are not tuned after observing P&L. A sensitivity scenario may be more or less
optimistic, but the conservative scenario remains the headline result.

Every order records quantity unit, exact tick rule, contract multiplier,
currency, price-rounding rule, fee schedule version, commission schedule version,
latency model, allocation model, and source capability manifest. Market and limit
behavior, partial fill, no fill, cancellation, expiration, rejection, end-of-
session policy, spread cost, slippage, and adverse movement are explicit state
transitions. Unknown multiplier, off-tick price, missing fee rule, or unit mismatch
rejects the order before activation.

Accounting is exact and fill-driven:

```text
signed_position_after = signed_position_before + signed_fill_quantity
cash_after = cash_before - signed_fill_quantity * fill_price * multiplier
             - commission - exchange_fees - other_fees
realized_pnl = exact matched-lot proceeds - exact matched-lot cost - allocated_costs
equity = cash + sum(mark_price * signed_position * multiplier)
```

All terms use the exact numeric rules in Section 7.3. For every run and each
instrument/currency, ordered fills must reproduce position lots, realized P&L,
cash ledger, fees, and terminal balances exactly. Orders cannot directly mutate
positions. Reconciliation failure makes the run `FAILED` and blocks reporting.

## 16. Performance and attribution

Every decision should answer:

- Which strategy and version produced it?
- Which canonical events and feature versions supported it?
- What quality state and session context existed?
- Why did the strategy act or abstain?
- What did risk approve, reject, or resize, and why?
- What order became active, when, and under which fill assumptions?
- Which fees, spread, latency, and slippage affected the outcome?
- What was predicted, what occurred, and when did invalidation happen?

Initial reports include event coverage, quality-state duration, signal and
abstention counts, rejection reasons, fill rates, turnover, gross and net P&L,
expectancy, average win/loss, drawdown, slippage, fees, and sensitivity. Sharpe,
Sortino, or calibrated probabilities are reported only when the sample design and
size make them meaningful.

## 17. Verification strategy

### 17.1 Contract and normalization tests

- Schema validation and version compatibility.
- Known/unknown field handling.
- Contract and symbol mapping.
- UTC, exchange timezone, RTH/ETH, holiday, and DST behavior.
- Duplicate, late, and out-of-order events.
- Timestamp precision and availability rules.
- Tick size, multiplier, expiry, and roll correctness.
- Raw-reference traceability.

### 17.2 Order-flow tests

- Native, quote-inferred, tick-inferred, and unknown aggressor behavior.
- Locked/crossed or missing quotes.
- CVD session reset and no unintended reset.
- OFI price and size transitions.
- Snapshot plus incremental depth reconstruction.
- Sequence-gap behavior and recovery.
- Numerical and missing-input edge cases.
- Deterministic output.
- Fixture parity with selected CVD Bubble calculations.

### 17.3 Replay and execution tests

- Identical-run reproducibility.
- Strict future-information rejection.
- Stable tie ordering.
- Late-event treatment.
- Latency and no-impossible-fill rules.
- Partial fill, cancellation, rejection, and session close.
- Fees, spread, and slippage arithmetic.
- Restart/checkpoint equivalence if checkpointing is added.
- Futures expiry and roll scenarios.

### 17.4 Strategy and risk tests

- Positive, negative, boundary, and `ABSTAIN` fixtures.
- Null probability/expected return before calibration.
- Data-quality rejection.
- Position, loss, drawdown, event-window, and kill-switch controls.
- Strategy inability to bypass risk or call execution.
- Structured reason stability.

### 17.5 Machine-checkable foundation assertions

Every gate emits a machine-readable assertion result with `assertion_id`, version,
status (`PASS`, `FAIL`, or `BLOCKED`), observed values, expected predicate,
evidence hashes, and run identifier. `BLOCKED` is not a pass and cannot be waived
by prose. Thresholds that depend on source behavior remain blocked until a usable
fixture is characterized and the threshold is preregistered.

| ID | Area | Passing predicate | Required evidence |
|---|---|---|---|
| `DF-001` | Data feasibility | Selected source object exists, is not an LFS pointer, its bytes match the pinned SHA-256, parser reads at least one record, and license/entitlement classification is present | Source manifest, object hash, parser report, license record |
| `DF-002` | Data feasibility | Every claimed capability maps to observed fields and documented source semantics; unsupported capabilities are explicitly false | Capability manifest, sampled schema report, source-semantics review |
| `SC-001` | Strategy capability | Strategy requirement set is a subset of verified adapter capabilities and required quality dimensions are eligible | Strategy requirement manifest joined to adapter capability/quality manifests |
| `SC-002` | Strategy capability | `BAR_OHLCV_1M` without required event capabilities deterministically returns `BLOCKED` for sweep and CVD candidates | Negative fixture assertion report |
| `TC-001` | Temporal correctness | For every consumed input, `input.available_time <= decision_time`; zero violations | Decision-input lineage query and violation count |
| `TC-002` | Temporal correctness | Historical records contain no fabricated `live_received_time`; live records contain no `historical_ingested_time`; all fields satisfy their declared requirement state | Contract validation report |
| `TC-003` | Temporal correctness | Corrections, revisions, busts, and late events affect state no earlier than their own `available_time`; prior decisions remain byte-unchanged | Temporal adversarial fixtures and before/after hashes |
| `DET-001` | Determinism | Two clean, network-denied runs with identical canonical inputs produce identical ordered artifact manifests and canonical run-root SHA-256 | Two run bundles and hash comparison |
| `ADP-001` | Adapter integrity | Every canonical event resolves to one immutable raw reference and source record identity; zero dangling or identity-conflict records | Bidirectional provenance query and counts |
| `ADP-002` | Adapter integrity | Re-ingesting identical source bytes is a no-op; changed bytes under an existing identity fail and quarantine | Idempotency/conflict fixture results |
| `EXE-001` | Execution | Zero fills precede activation or consume decision-trigger/same-event evidence without proven ordering | Fill eligibility audit |
| `EXE-002` | Execution | Per source scope, allocated simulated quantity never exceeds policy-eligible post-activation observed volume | Allocation ledger reconciliation |
| `EXE-003` | Execution | Recomputed orders, fills, positions, cash, realized P&L, multipliers, commissions, and fees equal authoritative ledgers exactly | Independent reconciliation report |
| `SAFE-001` | Offline/no-live safety | Offline lock/install contains no broker SDK package and succeeds with network disabled using only approved local artifacts | Dependency lock scan and offline install log |
| `SAFE-002` | Offline/no-live safety | Adapter registry contains no live market-data or execution adapter; static import graph contains no path from core/features/strategies to broker modules | Registry snapshot and import-boundary report |
| `SAFE-003` | Offline/no-live safety | Network-denied replay passes; route reachability from any milestone entry point to live order submission is empty | Denied-network run log and reachability analysis |
| `AE-001` | Acceptance evidence | A terminal `COMPLETE` run contains all required artifacts, every referenced hash resolves, and all preceding mandatory assertions are `PASS` | Acceptance index and artifact verifier output |

### 17.6 Acceptance bundle

One pinned ES session must run from immutable source artifact to a terminal report
containing validated input and contract manifests, canonical events, scoped
quality observations, versioned features, strategy evaluations/signals/
abstentions, intents, risk decisions, conservative orders and fills, positions,
cash, exact reconciliation, attribution, assertion results, and the deterministic
run-root hash. Reviewers consume an index that resolves every result to raw
evidence and component versions. Until `DF-001` passes, the acceptance bundle is
formally `BLOCKED`.

## 18. Research-validation policy

The platform follows this hierarchy:

```text
hypothesis
  -> historical exploration
  -> training/calibration where necessary
  -> temporal validation
  -> untouched out-of-sample evaluation
  -> walk-forward evaluation
```

Shadow/paper observation and controlled live validation are not automatic next
steps in this hierarchy. Each is a separately approved conditional horizon under
Section 20 and may never be authorized for a given strategy.

Controls include temporal rather than random splits, purge/embargo for overlapping
labels, multiple-testing records, sensitivity analysis, stable parameter regions,
transaction-cost stress, session/regime breakdowns, and retention of negative
results. No research result becomes a trading claim merely because it is
profitable on one session or one parameter setting.

## 19. Prototype migration map

### 19.1 Trading CVD Bubble

**Preserve:** demo dataset, aggressor rules, CVD/OFI formulas, quality metadata,
depth metrics, auction handling, and visualization behavior.

**Migrate when eligible:** pure calculations required by the first ES slice only
after source-capability gates pass and inputs/outputs are canonical and versioned.

**Migrate later:** rollup ideas, coverage reporting, and selected visualizations.

**Do not carry forward:** direct IBKR/MongoDB dependencies inside feature logic,
assumption that estimated and tick-derived volume are equivalent, or the large
Dash application as the core UI.

### 19.2 FuturesX

**Preserve:** readable metadata and expected identities for historical ES
artifacts, parsers, futures/session utilities, DOM experiments, and comparison
backtests. The pointer-only payloads themselves are unavailable.

**Migrate when eligible:** only input parsing and reference knowledge needed for
a separately verified, non-pointer pinned ES session.

**Migrate later:** useful order-book visualization and carefully validated
strategy hypotheses.

**Do not carry forward:** direct broker calls from strategies, unsafe live trader,
unrealistic fill assumptions, working-directory-dependent data access, or a
permanent IBKR dependency.

### 19.3 Short Squeeze Core

**Preserve:** provenance, explicit unknown state, evidence freshness, readiness
gates, frozen deterministic mode, methodology/versioning discipline, and release
audit ideas.

**Adopt after ADR review:** its principles and selected generic evidence-contract
patterns, not squeeze-specific application code, only after `ADR-TIME-001` and
`ADR-PROT-001` define the semantic and reuse boundaries.

**Conditional horizon:** structural-pressure observations and point-in-time
evidence only after `ADR-TIME-001` and `ADR-PROT-001` are accepted.

**Do not carry forward:** any composite score as calibrated probability or any
assumption that structural pressure alone is ignition.

### 19.4 Internship project

**Preserve:** scheduling, review/audit workflow, liquidity rejection, outcome
logging, offline evaluation, and near-miss research concepts.

**Conditional horizon:** provider-neutral orchestration patterns and research
review require separate scope and approval.

**Do not carry forward:** arbitrary directional-vote aggregation, human override
that bypasses safety gates, 0DTE-default behavior, fragile provider plumbing, or
uncontrolled LLM involvement.

### 19.5 L1 Volume Bubble

**Preserve:** visualization concepts and anomaly/absorption hypotheses.

**Conditional horizon:** optional UI representation of canonical order-flow
features requires separate scope and approval.

**Keep separate:** Pine source remains a TradingView artifact and does not become
the platform's source of canonical market data.

## 20. Foundation roadmap and conditional horizons

Phases 0 through 8 are the foundation sequence. Advancement requires every
listed assertion to emit `PASS`; prose review cannot override `FAIL` or
`BLOCKED`. A later implementation plan may decompose only an approved phase.

### Phase 0: Governance and structural no-live safety

**Outcome:** one canonical source of truth, explicit repository ownership, and a
foundation environment in which live routing is structurally absent.

**Work:**

- Classify plans and prototype components; record discrepancies, suggested
  owners, evidence, status, and supersession.
- Decide Git ownership before implementation without moving prototype paths.
- Define the offline dependency lock, registry allowlist, import boundaries, and
  milestone entry points.
- Exclude broker SDKs and live adapters from the offline installation and
  registry; prohibit imports from core/features/strategies to broker modules.
- Define network-denied execution and route-reachability checks.
- Audit credential locations without printing values; credential rotation or
  external changes require separate authorization.

**Required assertions:** `SAFE-001`, `SAFE-002`, and the static reachability part
of `SAFE-003` pass on a structural skeleton; governance verifier reports exactly
one canonical specification and all unresolved decisions have owner/evidence.

### Phase 0A: Data feasibility and prototype characterization

**Outcome:** a usable, lawful fixture and defensible source capabilities are
known before contracts or strategy behavior are tailored to imagined data.

**Work:**

- Verify a non-pointer ES object locally without retrieving unavailable LFS data.
- Pin raw bytes, license classification, record count, schema, timestamp fields,
  coverage, venue/publisher/channel identity, sequences, correction behavior,
  and trade/quote/depth/MBO semantics.
- Characterize selected prototype formulas and contracts as potential test
  oracles; do not copy them before the extract/adapt/reimplement ADR.
- Create positive and negative capability manifests, including the known
  `ohlcv-1m`-only failure case.
- Preregister any data-dependent completeness or performance threshold only
  after the fixture report exists.

**Required assertions:** `DF-001` and `DF-002` pass. At present `DF-001` is
`BLOCKED`; therefore Phase 1 implementation may not begin.

### Phase 1: Foundational ADRs

**Outcome:** every decision that can change identity, time, arithmetic,
determinism, storage, safety, or prototype reuse is accepted with evidence.

**Work:**

- Accept the ADRs in Section 23, resolving any fixture-dependent options using
  Phase 0A evidence.
- Record alternatives, consequences, owners, approval, and evidence hashes.
- Resolve the Short Squeeze `effective_timestamp`/`available_time` mapping and
  extract/adapt/reimplement boundary before reuse.

**Required assertion:** the ADR verifier reports no `BLOCKING` row without an
accepted decision and resolvable evidence.

### Phase 2: Contracts and minimal availability-aware replay

**Outcome:** provider-neutral contracts can round-trip and a synthetic fixture
proves `available_time` visibility before any real adapter is trusted.

**Work:**

- Implement the envelope, event/quality/reference contracts, decision chain,
  schema compatibility, exact numeric types, and run manifests.
- Implement only deterministic ordering, visibility, dispatch, and terminal run
  lifecycle against adversarial synthetic fixtures.
- Cover corrections, busts, revisions, late events, timestamp requirement states,
  bitemporal reference lookup, and historical-versus-live receipt separation.

**Required assertions:** contract round-trip/compatibility assertions and
`TC-001`, `TC-002`, `TC-003`, and `DET-001` pass on synthetic fixtures.

### Phase 3: Verified adapter and static integrity

**Outcome:** the Phase 0A object normalizes reproducibly with complete provenance
and no expansion of its verified capability set.

**Work:**

- Implement one source-specific adapter behind only its verified capabilities.
- Preserve raw/canonical hashes, identity, timestamp provenance, units, and
  normalization version; quarantine conflicts and unmapped records.
- Prove idempotency, raw-to-canonical and canonical-to-raw traceability, offline
  imports, absent live registry entries, and dependency boundaries.
- Produce coverage, capability, normalization, and provenance reports.

**Required assertions:** `ADP-001`, `ADP-002`, `SAFE-001`, and `SAFE-002` pass;
the adapter emits no capability absent from the approved Phase 0A manifest.

### Phase 4: Runtime quality and supported book state

**Outcome:** replay maintains only the market state supported by the verified
source and exposes scoped quality observations that can fail closed.

**Work:**

- Implement scoped quality dimensions, transitions, recovery, and consumer
  eligibility policies.
- Reconstruct BBO, MBP-N, or MBO state only if its corresponding capability is
  verified; reject unsupported upgrades in fidelity.
- Test sequence gaps, duplicates, staleness, time regression, crossed markets,
  corrections, snapshots/updates, and session/reference failures.
- Run the real pinned fixture twice in a network-denied environment.

**Required assertions:** `TC-001`, `TC-003`, `DET-001`, and `SAFE-003` pass;
corruption fixtures produce expected scoped states and block affected consumers.

### Phase 5: Capability-supported feature parity

**Outcome:** only source-supported, versioned features exist in the core, with
documented parity or intentional divergence from selected prototype oracles.

**Work:**

- Implement only feature rows whose Section 12.2 capability requirements pass.
- Compare selected formulas with frozen prototype or mathematical fixtures under
  the accepted extract/adapt/reimplement decision.
- Produce per-feature documentation and parity fixtures.
- Explain every intentional difference, including units, reset rules, missingness,
  quality gating, and numeric rounding.

**Required assertions:** `SC-001` passes for every enabled feature; `SC-002`
passes for prohibited bar-only substitutions; parity verifier reports exact
matches or approved, versioned differences.

### Phase 6: Preregistered strategy behavior

**Outcome:** one capability-supported hypothesis emits a directional signal or a
structured abstention, then produces a distinct intent when appropriate.

**Work:**

- Select liquidity-sweep reversal only if verified multi-level depth semantics
  pass; select CVD divergence only if its trade/direction requirements pass.
- Preregister hypothesis, source capabilities, features, thresholds, horizon,
  invalidation, evaluation labels, and abstention reasons before final evaluation.
- Keep probability and expected return null before calibration.
- Record score, signal, abstention, and intent as separate contracts.
- Create positive, negative, boundary, and abstention fixtures.

**Required assertions:** `SC-001` and `SC-002` pass for the selected and rejected
candidates; import-boundary tests prove no broker, execution, or risk bypass.

### Phase 7: Risk, execution, and accounting

**Outcome:** approved intents can be conservatively simulated and reconciled.

**Work:**

- Implement independent risk policies and kill switch.
- Implement activation, order lifecycle, eligible-volume allocation, latency,
  fill, fee, commission, multiplier, units, and slippage models supported by the
  source capability manifest.
- Define conservative baseline and sensitivity scenarios.
- Reconcile orders, fills, lots, realized P&L, cash, and positions exactly.
- Attribute rejection and transaction-cost reasons.

**Required assertions:** `EXE-001`, `EXE-002`, `EXE-003`, and `SAFE-003` pass;
queue fidelity remains disabled unless `MBO` is verified.

### Phase 8: Acceptance evidence

**Outcome:** one historical ES session runs end to end.

**Work:**

- Generate and independently verify the terminal acceptance bundle.
- Repeat in a clean, network-denied environment from the pinned offline lock.
- Record capability, coverage, quality, score/signal/abstention/intent, risk,
  execution, accounting, attribution, metrics, and limitations.
- Audit implementation against this specification and record any design change
  as a new ADR/spec version rather than an acceptance exception.

**Required assertions:** all mandatory Section 17.5 assertions and `AE-001` pass.

### Conditional horizons outside the foundation sequence

The following are independent horizons, not Phases 9+ and not an automatic
serial roadmap. Each requires a separate sponsor, scope, design/spec revision,
data/provider/legal review, safety analysis, acceptance assertions, and explicit
authorization. Approval of one does not approve any other:

| Conditional horizon | Minimum new approval evidence |
|---|---|
| Broader futures/order-flow research | Multiple lawful sessions, temporal evaluation design, cost/data-gap stress, and preregistered hypotheses |
| Short-squeeze evidence engine | Accepted `ADR-TIME-001`, authoritative point-in-time sources, structural-pressure/ignition/confirmation separation, and explicit unknownness |
| Equities order flow and research UI | Entitled venue coverage, inference labeling, coverage-bias study, and UI-to-canonical lineage |
| Options foundation | Historical chain availability, quote/trade/analytics capability review, liquidity and Greek-risk contracts, and structure abstention |
| News, social, economic, or alternative data | Publication/revision availability, licensing, identity/deduplication, manipulation and provenance controls, and domain-specific quality policy |
| Regime, calibration, meta, portfolio, or trade-expression layers | Defined outcomes/horizons, temporal calibration evidence, uncertainty/cost model, correlation constraints, and rejection of unrelated score averaging |
| Shadow or paper operation | New live-data design, operational security, reconnect/incident controls, sustained reconciliation criteria, and explicit authorization; no live broker route is implied |
| Controlled live trading | Separate legal/licensing/security review, funded-account authorization, hard capital limits, tested kill switch, incident response, broker reconciliation, rollback, and purpose-built live acceptance evidence |

## 21. Cross-cutting workstreams

### 21.1 Security and credentials

- No committed secrets or account identifiers.
- Private configuration and safe examples are distinct.
- Logs redact tokens, credentials, and sensitive payloads.
- Credentials use least privilege and are rotated after plausible exposure.
- The foundation offline lock and default installation exclude broker SDKs,
  network clients not required for local file access, and any live extras.
- The foundation adapter registry is a closed allowlist of offline readers and
  the simulator. A live market-data or execution adapter is absent, not disabled
  by a Boolean.
- Static boundary rules prohibit `contracts`, `reference_data`, `normalization`,
  `data_quality`, `storage`, `replay`, `features`, `strategies`, `risk`, and the
  simulator from importing broker modules.
- Foundation entry points expose no live-order route, broker credential schema,
  dynamic adapter import, plugin discovery, or arbitrary module path that could
  make such a route reachable.
- Installation and replay must succeed with network access denied. Any attempted
  socket/DNS/HTTP use fails the run and is acceptance evidence.
- Future live capability belongs in a separately approved distribution/registry
  and cannot be activated by environment variable or configuration alone.

### 21.2 Observability and operations

- Structured logs with run, adapter, instrument, and component identifiers.
- Health, readiness, and quality are distinct concepts.
- Metrics for lag, gaps, rejects, reconnects, queue depth, and run failures.
- Failure artifacts preserve enough evidence to reproduce a defect.
- Backups and restore tests precede meaningful collected-data reliance.

### 21.3 Documentation governance

- Every canonical document has owner/status/date and supersession links.
- Implemented, planned, experimental, and deprecated states are explicit.
- Formula documentation includes version, units, parameters, and quality needs.
- Provider claims are dated and linked to primary documentation when maintained.
- Architecture decisions record rejected alternatives and consequences.

### 21.4 Data and model governance

- Dataset and feature versions are immutable.
- Experiments record hypotheses before final evaluation.
- Training, validation, and test boundaries are stored with the run.
- Multiple comparisons and manual interventions are recorded.
- Model or threshold changes never rewrite past outputs.

## 22. Major risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Attempting all domains at once | No trustworthy end-to-end capability | Keep ES slice as the gating milestone |
| Provider entitlements change | Broken system or misleading coverage | Capability adapters, dated matrix, coverage tests |
| Timestamp ambiguity | Look-ahead and invalid replay | Event/publish/live-receive/historical-ingestion/availability contract and fail-closed checks |
| Incomplete depth | False microstructure claims | Quality states, capability metadata, supported-feature gates |
| Prototype semantic drift | Quietly changed formulas | Versioned features and parity fixtures |
| Unrealistic fills | Inflated research performance | Conservative latency/fill model and sensitivity reporting |
| Score/probability confusion | Invalid portfolio comparison | Null uncalibrated fields and semantic contract tests |
| Overfitting | Fragile apparent edge | Temporal splits, walk-forward, parameter-region stability |
| Premature infrastructure | High cost and slow learning | Modular monolith and local analytical storage |
| Credential or licensing exposure | Security/legal harm | Secret audit, redaction, explicit licensing boundary |
| Accidental live trading | Financial harm | No first-slice live path; separate future approval and controls |
| Root lacks Git governance | Weak change traceability | Decide repository ownership before implementation migration |

## 23. Foundational ADR and blocker register

`SPEC-RESOLVED` means this specification fixes the invariant; Phase 1 still
records the decision, alternatives, consequences, and conformance fixtures in an
ADR. `BLOCKING` means no dependent implementation may begin until an owner
accepts an ADR supported by the listed evidence. Suggested owners are roles
because named project maintainers have not been assigned.

| ADR | Decision | Status and specification constraint | Suggested owner | Evidence required for acceptance |
|---|---|---|---|---|
| `ADR-NUM-001` | Exact price/numeric representation | `SPEC-RESOLVED`: integer increment/minor units plus exact rational scale; no authoritative binary float | Architecture lead + execution/accounting owner | ES tick/multiplier examples, fee/currency cases, overflow and rounding vectors |
| `ADR-TSP-001` | Timestamp precision | `SPEC-RESOLVED`: UTC epoch nanoseconds with preserved source precision and derivation; no invented precision | Data-contract owner | Source metadata/records, DST/local-time and coarse-precision fixtures |
| `ADR-ID-001` | Event identity and idempotency | `SPEC-RESOLVED`: deterministic normalized identity, identical replay no-op, conflicts quarantined | Data-contract owner | Duplicate/conflict fixtures and stable UUID vectors |
| `ADR-ID-002` | Source-record versus normalized-event identity | `SPEC-RESOLVED`: distinct fully qualified source and immutable normalized identities | Data-contract owner | Provider native-ID semantics or raw-boundary derivation proof; correction examples |
| `ADR-SEQ-001` | Sequence-number scope | `SPEC-RESOLVED`: explicit provider/venue/publisher/channel/source-instance/reset scope | Market-data owner | Usable fixture sequence/reconnect/reset characterization |
| `ADR-SRC-001` | Venue, publisher, channel, source-instance identity | `SPEC-RESOLVED`: all four are separate envelope dimensions | Market-data owner | Source documentation and sample mappings; unknown/aggregate cases |
| `ADR-ORD-001` | Ordering and deterministic tie-break | `SPEC-RESOLVED`: Section 7.2 tuple; ranks/precedence versioned | Replay owner | Adversarial equal-time, missing-sequence, reconnect, correction, and late fixtures |
| `ADR-SCH-001` | Schema compatibility and migrations | `SPEC-RESOLVED`: semantic versions, major break rules, pure hashed migrations, no in-place rewrite | Architecture lead | Forward/backward compatibility matrix and migration golden files |
| `ADR-REF-001` | Reference-data bitemporality | `SPEC-RESOLVED`: market-valid and knowledge-valid intervals required | Reference-data owner | Contract/tick/session/symbol correction fixtures and as-of query results |
| `ADR-STORE-001` | Storage layout and physical engine | `BLOCKING` before Phase 2 production storage: logical layout is fixed; DuckDB/SQLite split is not | Storage owner | Usable fixture size, query benchmark, atomic publish/failure test, offline packaging constraints |
| `ADR-RUN-001` | Atomic run lifecycle | `SPEC-RESOLVED`: staged state machine and terminal marker; completed runs immutable | Replay/storage owner | Crash-at-each-transition tests, terminal manifest/hash verifier |
| `ADR-DET-001` | Determinism and artifact hashing | `SPEC-RESOLVED`: canonical encoding and ordered SHA-256 manifests | Replay/release owner | Cross-process clean reruns, locale/path/thread variation, canonical encoding vectors |
| `ADR-OFF-001` | Offline dependency boundary | `SPEC-RESOLVED`: broker SDKs and live registry/routes absent; denied-network replay required | Security/release owner | Lock scan, import graph, registry snapshot, network-denied install/replay, reachability report |
| `ADR-TIME-001` | Short Squeeze `effective_timestamp` versus canonical `available_time` | `BLOCKING` before any Short Squeeze reuse | Data-contract owner + Short Squeeze maintainer | Contract/ADR review, historical/live/date-only/correction mappings, replay parity and counterexamples |
| `ADR-PROT-001` | Extract, adapt, or reimplement Short Squeeze primitives | `BLOCKING` before code reuse; prototype working tree remains untouched | Architecture lead + Short Squeeze maintainer | Component inventory, dependency/import graph, license/provenance review, parity fixtures, maintenance-cost analysis |
| `ADR-DATA-001` | Pinned ES fixture and capability manifest | `BLOCKING`: no usable event-level ES object is verified locally | Market-data owner + research lead | Non-pointer lawful object, SHA-256, schema/record inspection, coverage/defect/capability report |
| `ADR-STRAT-001` | First strategy selection and thresholds | `BLOCKING` until `ADR-DATA-001`; sweep and CVD requirements are fixed by Section 12.2 | Research lead + market-microstructure reviewer | Passing capability join, usable fixture characterization, preregistration; no threshold selected from final P&L |
| `ADR-REPO-001` | Repository-root ownership and prototype path policy | `BLOCKING` before code migration; current collection root is not Git | Project owner + release owner | Chosen ownership/remote, preservation plan for nested repo and current local changes |

Library selection and performance budgets are implementation-plan decisions only
after the offline runtime and usable fixture are known. They may not weaken these
contracts. No data-dependent threshold may be invented to make a gate pass.

## 24. Definition of the first milestone complete

The foundation milestone is complete only when all of the following are true:

1. Phases 0 through 8 have machine-readable gate results and no mandatory
   assertion is `FAIL` or `BLOCKED`.
2. `DF-001` and `DF-002` prove one immutable, lawful, non-pointer ES session and
   its actual capabilities.
3. Foundational ADRs are accepted and their conformance evidence resolves.
4. Canonical contracts, timestamp requirement states, bitemporal reference data,
   scoped quality observations, and schema migrations are versioned and enforced.
5. The adapter is idempotent, capability honest, and bidirectionally traceable to
   immutable raw evidence.
6. Only capability-supported features are enabled and their parity or intentional
   divergence is approved.
7. One preregistered strategy separates score, signal/abstention, intent, risk,
   order, fill, and position action; probability and expected return remain null
   unless calibrated.
8. Risk independently approves, rejects, or resizes intent and strategy cannot
   bypass it.
9. Execution respects activation and eligible observed-volume limits, makes no
   queue claim without MBO, and records exact ticks, units, multiplier, fees, and
   commissions.
10. Independent recomputation exactly reconciles orders, fills, positions, lots,
    cash, fees, realized P&L, and terminal equity.
11. Two clean network-denied runs produce the same canonical run-root hash.
12. Every result and assertion resolves to inputs, versions, configuration,
    decisions, and evidence hashes.
13. The terminal report describes limitations and makes no unsupported data,
    queue, execution, calibration, or edge claim.
14. Broker SDKs, live adapters, broker imports, live routes, and network
    dependencies are structurally absent from the milestone runtime.

## 25. Success beyond the first milestone

The overall integration succeeds when additional domains reuse the same contracts,
quality controls, replay clock, risk boundary, execution semantics, and
attribution model without reintroducing vendor coupling or arbitrary score
comparison. New providers should be adapters; new features should be versioned
measurements; new strategies should be falsifiable hypotheses; and new product
views should remain projections over canonical evidence.

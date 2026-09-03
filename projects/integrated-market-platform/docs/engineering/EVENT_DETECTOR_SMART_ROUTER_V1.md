# Event Detector & Smart Router V1 (BUILD 09)

> BUILD 09 deterministically recognizes meaningful state transitions from canonical point-in-time intelligence and converts those detections into capability-aware specialist routing intents.

Cross-links: [Quality & Capability Engine V1](./QUALITY_CAPABILITY_ENGINE_V1.md), [Feature & Fast Signal Layer V1](./FEATURE_FAST_SIGNAL_LAYER_V1.md), [Replay Runtime V1](./REPLAY_RUNTIME_V1.md), [Baseline Prediction System V1](./BASELINE_PREDICTION_SYSTEM_V1.md), [Intelligence Persistence Architecture V1](./INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md).

## Semantic boundary

```text
EventV1              = normalized provider/source event
DetectionV1          = derived deterministic trigger
RoutingDecisionV1    = logical specialist-domain intent
```

A semantic detection is not a probability, `ForecastV1`, expert `EvidenceV1`, or `HypothesisV1`. Detection severity is a coarse deterministic magnitude/importance bucket; it is not confidence. A route is not a scheduled job, model selection, expert invocation, or execution instruction.

BUILD 09 consumes only an explicit `DetectionFrame`:

```text
SnapshotV1
  + current snapshot-derived SignalV1[]
  + current snapshot-resolved EventV1[]
  + BUILD 04 QualityDecision
  + optional caller-supplied RegimeContext
  + optional same-snapshot ForecastV1[] (validated, unused in v1)
        ↓
EventDetectorEngine
        ↓
DetectionV1[]
        ↓
SmartRouter
        ↓
RoutingDecisionV1[]
```

No detector queries providers, MongoDB, or repository “latest” state. Inputs are canonicalized so tuple order does not alter output.

## Contract and identity design

`EventV1` remains source-event-specific. BUILD 09 adds separate immutable V1 contracts:

- `DetectionV1`: source snapshot, exact signal/event references, detector lineage, scope, severity, reason codes, source-derived quality, identity context, and audit metadata.
- `RoutingDecisionV1`: detection reference, expert domain, action, priority, capability requirements, deterministic deadline/expiration/TTL, quality, router lineage, and reason codes.

Detection identity is `semantic-detection-sha256-v1`. It hashes detector/policy identity, semantic type, source snapshot, source signal/event references, and trigger identity context. Computed severity and narrative output are excluded, so a changed output for identical inputs becomes an immutable persistence conflict.

Route identity is `routing-decision-sha256-v1`. It hashes detection ID, full routing-policy fingerprint, expert domain, required capabilities, and the BUILD 04 routing context. Computed priority and timestamps are policy outputs and are excluded directly; their configuration is covered by the policy fingerprint. Neither identity uses wall clock, random UUIDs, backend, or machine state.

## Detector support matrix

| Semantic event | Required canonical input | Status | Implementation | Limitation |
|---|---|---|---|---|
| `ORDER_FLOW_REVERSAL` | exact `net_signed_share@300s`, `cvd-calculator` v1 | `IMPLEMENTED` | material-sign transition | Initial threshold is heuristic, not empirically optimized. |
| `UNUSUAL_OPTIONS_ACTIVITY` | canonical option volume/OI/IV signals | `INACTIVE_INPUT_UNAVAILABLE` | inactive | Standard snapshots/signals have no canonical option-chain state. |
| `BORROW_CHANGE` | sequential canonical `SHORT_INTEREST` events | `IMPLEMENTED` | relative short-interest change | Detects positioning change; canonical live borrow-rate/availability normalization remains absent. |
| `LIQUIDITY_EVENT` | point `spread_bps`, `spread-calculator` v1 | `IMPLEMENTED` | spread-stress crossing with hysteresis | Initial thresholds are heuristic, not empirically optimized. |
| `NEWS_EVENT` | canonical normalized `NEWS` event lane | `INACTIVE_INPUT_UNAVAILABLE` | inactive | No canonical news normalizer/snapshot lane exists; SEC filings are not relabeled as generic news. |
| `REGIME_SHIFT` | caller-supplied previous/current regime keys | `IMPLEMENTED_WITH_EXTERNAL_CONTEXT` | exact key transition | BUILD 09 does not calculate regimes. |

The router defines mappings for all six semantic types independently of detector availability.

## Detector-visible state and anti-lookahead

`EventDetectorEngine` owns explicit bounded state for at most 1,024 scope keys. Each scope retains only:

- the last material NSS signal;
- the last spread signal and liquidity-stress flag;
- the last processed short-interest event;
- the last supplied regime key.

State updates only when frames are actually processed. Persisted historical `SignalV1` rows are not preloaded merely because `as_of_time_ns <= decision_time_ns`; an old as-of timestamp does not prove the detector had operationally seen the derived artifact. This distinction prevents derived-state lookahead in live and replay operation.

`reset()` clears detector runtime state only. It never clears source repositories or canonical artifacts. Every `ReplayRuntime.run` creates a fresh detector engine, so runs cannot contaminate one another.

## Order-flow reversal

Selector:

```text
signal_type = net_signed_share
window      = 300 seconds
calculator  = cvd-calculator v1
```

Policy v1 uses `threshold = 0.15`:

```text
previous <= -0.15 and current >= +0.15 → NSS_NEGATIVE_TO_POSITIVE
previous >= +0.15 and current <= -0.15 → NSS_POSITIVE_TO_NEGATIVE
```

The `±0.15` default follows the existing P6 NSS convention as a deterministic initial heuristic; it is not an empirically optimized reversal threshold. Values inside the deadband do not trigger and do not erase the last material state. After a reversal, the current material signal becomes prior state, preventing repeated same-direction events. CVD is not recomputed or required.

Severity uses `abs(current_nss - previous_nss)`:

| Magnitude | Severity |
|---:|---|
| `< 0.60` | `LOW` |
| `0.60–<1.00` | `MEDIUM` |
| `1.00–<1.50` | `HIGH` |
| `>=1.50` | `CRITICAL` |

Both previous and current NSS signal references are retained.

## Liquidity event

Policy v1 requires a real spread crossing:

```text
previous spread_bps < 50
current  spread_bps >= 50
→ SPREAD_ENTERED_STRESS
```

While stressed, further high spreads do not repeat. Stress clears only when `spread_bps <= 30`; a later crossing can emit a new event. Depth imbalance is neither required nor interpreted as illiquidity. Invalid/negative or policy-rejected spread values cannot update detector state.

Severity uses current spread divided by the 50 bps entry threshold: `<1.5x LOW`, `1.5–<2x MEDIUM`, `2–<4x HIGH`, `>=4x CRITICAL`.

## Short-interest, news, options, and regime

The positioning detector compares two actually processed canonical `SHORT_INTEREST` events. It requires positive prior quantity and triggers at an absolute relative change of at least 10%. Missing prior state is never treated as zero. Reasons are `SHORT_INTEREST_INCREASE` or `SHORT_INTEREST_DECREASE`; exact prior/current event references are retained.

`NEWS_EVENT` remains inactive. BUILD 09 performs no sentiment analysis, keyword classification, fuzzy filing-to-news conversion, or LLM call. `UNUSUAL_OPTIONS_ACTIVITY` remains inactive because the standard canonical snapshot/signal boundary lacks option-chain measurements.

`REGIME_SHIFT` emits only when valid caller-supplied previous/current keys differ. Repeated current keys are suppressed. Metadata records the source context version and explicitly states that BUILD 09 did not generate the regime.

## Primitive expert domains

```text
MICROSTRUCTURE
DERIVATIVES
POSITIONING_BORROW
CORPORATE_FUNDAMENTAL
INSIDER_OWNERSHIP
NARRATIVE_SENTIMENT
MACRO_POLICY
CRYPTO_ONCHAIN
REGIME_CROSS_ASSET
```

There is deliberately no `SHORT_SQUEEZE` primitive expert. A short squeeze is a later composite hypothesis across microstructure, derivatives, positioning/borrow, and regime evidence (BUILD 13).

## Router policy v1

| Semantic event | Primary expert | Required capabilities | Optional capabilities | Base priority | Deadline | TTL |
|---|---|---|---|---|---:|---:|
| `ORDER_FLOW_REVERSAL` | `MICROSTRUCTURE` | `QUOTES`, `TRADES` | `DEPTH` | `HIGH` | 5 s | 30 s |
| `LIQUIDITY_EVENT` | `MICROSTRUCTURE` | `QUOTES` | `DEPTH` | `HIGH` | 5 s | 30 s |
| `UNUSUAL_OPTIONS_ACTIVITY` | `DERIVATIVES` | `OPTIONS_CHAIN` | — | `HIGH` | 30 s | 5 min |
| `BORROW_CHANGE` | `POSITIONING_BORROW` | `SHORT_INTEREST` | `BORROW` | `NORMAL` | 15 min | 4 h |
| `NEWS_EVENT` | `NARRATIVE_SENTIMENT` | `NEWS` | `FILINGS` | `NORMAL` | 2 min | 30 min |
| `REGIME_SHIFT` | `REGIME_CROSS_ASSET` | `MACRO` | `QUOTES` | `HIGH` | 5 min | 60 min |

These conservative defaults are explicit and versioned, not empirically optimal and not learned. `HIGH` or `CRITICAL` detection severity promotes base priority by one stable enum level, capped at `CRITICAL`. No historical route success or forecast accuracy is used.

## BUILD 04 quality and capability gating

`SmartRouter` consumes the canonical `QualityDecision` for the same decision time:

| BUILD 04 action/context | Router behavior |
|---|---|
| `USE` + required capabilities | executable `ROUTE` |
| required capability missing | non-executable `SUPPRESS` |
| optional capability missing | policy-allowed route with `DEGRADED` quality |
| `DEGRADE` | route only when routing policy permits; quality stays `DEGRADED` |
| `ABSTAIN` | non-executable `ABSTAIN` |
| `FAIL_CLOSED` | non-executable `ABSTAIN`; router cannot override |

An executable route can never claim better quality than its detection or BUILD 04 context.

## Deadline, expiration, and TTL

For executable routes:

```text
decision_time_ns = detection.detected_at_ns
deadline_time_ns = decision_time_ns + policy deadline offset
expires_at_ns    = decision_time_ns + policy TTL
ttl_ns           = expires_at_ns - decision_time_ns
```

The deadline is the preferred latest useful specialist completion. Expiration is the hard relevance boundary that BUILD 10 can use for stale-job cancellation. Invariants require positive offsets and `decision < deadline <= expiration`. No wall clock is called. Non-executable decisions carry no deadline/expiration/TTL.

TTL is logical intelligence semantics, not database deletion TTL.

## Persistence

BUILD 04.5 repository parity is extended with:

```text
put/get_detection
get_detections_by_snapshot
put/get_routing_decision
get_routes_by_detection
```

Normal Mongo collections are `detections` and `routing_decisions`; neither is time-series. Indexes support snapshot/event-time queries, detection lookup, domain/time lookup, and logical `expires_at_ns` lookup. No `expireAfterSeconds` index exists. Writes use immutable insert semantics: identical content is `ALREADY_PRESENT`; same ID with changed content raises `RepositoryConflictError`.

The detector/router core imports no PyMongo and works with no Mongo server.

## Replay and baseline context

BUILD 07 can enable BUILD 09 in `ReplayPipelineConfig`. Each decision passes only the snapshot, signals, events, and exact-time BUILD 04 decision visible then. Observed replay and live-like paths call the same engine/router. Counterfactual delivery changes may legitimately remove a trigger, but repeated identical scenarios reproduce identical detection and route IDs.

Optional baseline forecasts are validated for same-snapshot lineage and decision time, then ignored by v1 routing. There is no averaging, voting, calibration, probability generation, forecast evaluation, or fusion.

## Handoffs and exclusions

BUILD 10 can consume executable `RoutingDecisionV1` records for central priority queueing, CPU/GPU capacity checks, batching, model/adapter selection, deadline enforcement, stale cancellation, and fallback behavior without changing BUILD 09 semantics.

BUILD 11 receives the exact source snapshot, detection, route, required capabilities, and logical time bounds, then may emit `EvidenceV1`. BUILD 09 itself does not invoke a specialist. BUILD 13 later composes independent evidence into hypotheses.

BUILD 09 adds no queue, worker, async/thread framework, GPU inspection, model loading, LLM call, `ForecastV1`, `EvidenceV1`, `HypothesisV1`, outcome adjudication, trade execution, or live-order authority.

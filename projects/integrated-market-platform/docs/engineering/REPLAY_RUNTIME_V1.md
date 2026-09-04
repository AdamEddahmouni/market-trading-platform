# Replay Runtime V1 (BUILD 07)

> Replay is deterministic re-execution of canonical information arrival and decision-state evolution under an explicit virtual clock and explicit delivery scenario.

BUILD 07 establishes a **deterministic experimental time machine** for the intelligence platform. It reproduces the same point-in-time intelligence path used by live operation (BUILD 02–06) with a different clock and event source.

## Related Documents

- [TEMPORAL_INTEGRITY_V1.md](./TEMPORAL_INTEGRITY_V1.md) — BUILD 02 temporal authority
- [IMMUTABLE_SNAPSHOT_ENGINE_V1.md](./IMMUTABLE_SNAPSHOT_ENGINE_V1.md) — BUILD 05 snapshot engine
- [FEATURE_FAST_SIGNAL_LAYER_V1.md](./FEATURE_FAST_SIGNAL_LAYER_V1.md) — BUILD 06 signals
- [INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md](./INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md) — BUILD 04.5 repositories
- [EVENT_DETECTOR_SMART_ROUTER_V1.md](./EVENT_DETECTOR_SMART_ROUTER_V1.md) — BUILD 09 stateful detection and routing parity

## Architecture

```text
Historical Source Repository (read-only)
        │
        ▼
Replay Delivery Schedule (fault engine)
        │
        ▼
ReplayVisibilityIndex / ReplayVisibleRepository
        │
        ▼
ReplayClock (virtual deterministic time)
        │
        ▼
BUILD 02 temporal rules (on visible canonical events)
        │
        ▼
BUILD 04 quality assessment
        │
        ▼
BUILD 05 SnapshotBuilder
        │
        ▼
BUILD 06 FastSignalEngine
        │
        ▼
Isolated Output Repository
```

## Observed vs Counterfactual

### Observed Replay (`OBSERVED_REPLAY`)

Faithful replay of recorded availability:

```text
effective_delivery_time_ns = record.available_time_ns
```

No artificial fault transformation. Output should match live-like sequential delivery for identical source data.

### Counterfactual Replay (`COUNTERFACTUAL`)

Recorded canonical data plus explicit deterministic fault rules:

```text
effective_delivery_time_ns may differ from record.available_time_ns
```

Counterfactual runs are **not** actual live evidence. `RunManifestV1.metadata.replay_classification` is set to `COUNTERFACTUAL`.

Configuration rejects `OBSERVED_REPLAY` mode when fault rules are present.

## Time Semantics

| Field | Meaning |
|-------|---------|
| `event_time_ns` | Economic/provider event time on canonical `EventV1` (immutable) |
| `available_time_ns` | Recorded knowability time on canonical `EventV1` (immutable) |
| `effective_delivery_time_ns` | Replay visibility time under the scenario overlay |
| `decision_time_ns` | Virtual clock time when snapshot/signal decisions execute |

Replay visibility requires:

```text
effective_delivery_time_ns <= decision_time_ns
```

BUILD 02 still enforces on visible events:

```text
available_time_ns <= decision_time_ns
```

## Source Immutability

Fault injection never mutates canonical source `EventV1` timestamps, payloads, IDs, or provenance. Fault simulation operates through `ReplayDeliveryEnvelope` metadata only.

## Replay Visibility

The full historical source repository **must not** be used directly as replay decision state when counterfactual delays/drops exist.

**Post-run recomposition example:**

- Source `available_time = T`
- Counterfactual delay → `effective_delivery = T+5`
- After full replay completes, recomposing at decision `T+2` must **still exclude** the event because the delivery overlay records it was not yet visible at `T+2`.

`ReplayVisibilityIndex` preserves this history independently of final repository contents.

## Same-Timestamp Ordering

At equal nanoseconds:

1. Provider/fault state transitions (disconnect windows)
2. Event deliveries (`DELIVERY`)
3. Decision points (`DECISION`)
4. Checkpoint/observer notifications

Under observed semantics, an event effective exactly at decision time `T` is visible to a decision at `T`.

## Clocks

- **`LiveClock`** — isolated wall-clock boundary (`time.time_ns()`)
- **`ReplayClock`** — deterministic virtual clock; cannot move backward; no sleeps

Replay advances virtual time immediately. No real-time pacing in core.

## Fault Catalog

### Delay

- **Selectors:** `provider_id`, `event_type`, `instrument_id`, `event_ids`
- **Semantics:** `effective_delivery = max(current, recorded + delay_ns)`
- **Source mutation:** none
- **Trace:** `DELAY`, matched rule IDs

### Drop

- **Selectors:** same as delay
- **Semantics:** event never becomes replay-visible
- **Source:** canonical record remains in source repository

### Disconnect

- **Interval:** `[start, end)` — start inclusive, end exclusive
- **DROP:** events with recorded availability in window are `DISCONNECT_DROP`
- **BUFFER:** release at `max(recorded, reconnect_time)` with canonical ordering

### Throttle

- **Window:** fixed deterministic window per provider
- **Quota:** `max_deliveries` per window
- **Overflow:** `DROP` or `BUFFER` (release at window end)

### Out-of-Order

Emerges deterministically from delay rules — no random shuffle.

## Source / Output Isolation

```text
Historical Source → read only
Replay Runtime → isolated output repository (default InMemoryIntelligenceRepository)
```

`ReplayRuntime` rejects aliased source/output repository objects.

## Run Manifest

`RunManifestV1` is reused with:

- `data_mode`: `HISTORICAL_CAPTURE` (observed) or `FIXTURE_REPLAY` (counterfactual)
- `config_identity`: scenario fingerprint
- `metadata`: replay classification, scenario fingerprint, source/decision ranges, decision schedule

## Snapshot/Signal Parity

BUILD 07 uses BUILD 05 `SnapshotBuilder` and BUILD 06 `FastSignalEngine` unchanged. Observed replay reproduces identical snapshot IDs and signal IDs as live-like sequential delivery for identical information state.

## What Replay Does Not Do

```text
Replay ≠ forecasting (BUILD 08)
Replay ≠ outcome adjudication (BUILD 15+)
Replay ≠ strategy PnL
Replay ≠ model training
Replay ≠ execution
```

## BUILD 08 Handoff

At each replay/live decision point:

1. Event delivery establishes replay-visible state
2. `SnapshotBuilder` produces deterministic `SnapshotV1`
3. `FastSignalEngine` produces deterministic `SignalV1`
4. BUILD 08 attaches baseline `ForecastV1` generation to the same signals
5. Live vs replay forecast comparison avoids feature skew
6. Replay remains model-neutral

## Public API

```python
from market_platform_foundation.intelligence.replay import (
    Clock,
    LiveClock,
    ReplayClock,
    ReplayScenario,
    ReplayRuntime,
    ReplayDecisionSchedule,
    ReplayFaultProfile,
    ReplayRunResult,
    observed_replay_scenario,
    counterfactual_replay_scenario,
)
```

## Component Identity

- `replay-runtime` v1 via `ComponentLineage` on `RunManifestV1`
- Scenario fingerprint: `replay-scenario-sha256-v1`

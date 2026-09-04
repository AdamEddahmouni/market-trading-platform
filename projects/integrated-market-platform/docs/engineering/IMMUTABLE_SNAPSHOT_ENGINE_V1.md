# Immutable Snapshot Engine V1

BUILD 05 establishes the immutable, deterministic, point-in-time information
boundary for the intelligence plane.

> A snapshot is the immutable, deterministic, point-in-time information state
> that a downstream intelligence process was legitimately permitted to consume
> at a specific decision time.

See also: [INTELLIGENCE_CONTRACTS_V1.md](INTELLIGENCE_CONTRACTS_V1.md),
[TEMPORAL_INTEGRITY_V1.md](TEMPORAL_INTEGRITY_V1.md),
[QUALITY_CAPABILITY_ENGINE_V1.md](QUALITY_CAPABILITY_ENGINE_V1.md),
[INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md](INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md).

## What a snapshot is not

```text
Snapshot ≠ database view
Snapshot ≠ latest market state
Snapshot ≠ feature calculation
Snapshot ≠ prediction
Snapshot ≠ provider response dump
Snapshot ≠ replay runtime
```

## Core law

```text
available_time_ns <= decision_time_ns
```

Delayed-information example:

```text
event_time      = 09:59:59
available_time  = 10:00:05
decision_time   = 10:00:00
→ excluded permanently from that snapshot

decision_time   = 10:00:10
→ may be included in a new snapshot
```

## Pipeline

```text
SnapshotBuildRequest
      │
      ▼
IntelligenceRepository candidate retrieval
      │
      ▼
BUILD 02 temporal eligibility
      │
      ▼
BUILD 04 quality/capability decision
      │
      ▼
Deterministic reference selection
      │
      ▼
compose_snapshot (pure)
      │
      ▼
Deterministic content fingerprint + SNAP-<sha256> id
      │
      ▼
BUILD 02 snapshot temporal validation
      │
      ▼
IntelligenceRepository.put_snapshot
```

## Snapshot semantics (`SnapshotV1`)

| Field | Meaning |
|-------|---------|
| `snapshot_id` | Content-derived `SNAP-<SHA256>` identity |
| `decision_time_ns` | Explicit decision boundary — never wall clock |
| `scope` | Instrument/context boundary for selection |
| `source_event_refs` | Canonical event references only |
| `source_signal_refs` | Pre-existing signal references only (no calculation) |
| `component_refs` | Builder lineage (`snapshot-builder` v1) |
| `quality` | BUILD 01 `QualitySummary` from BUILD 04 assessment |
| `metadata` | Fingerprint + composition policy receipt (not hashed identity inputs) |

Snapshots store references, not duplicated market histories.

## Quality gating

| BUILD 04 action | BUILD 05 behavior |
|-----------------|-------------------|
| `USE` | Build full permitted snapshot |
| `DEGRADE` | Build when `allow_degraded` policy permits |
| `ABSTAIN` | No operational snapshot (`SnapshotQualityError`) |
| `FAIL_CLOSED` | No snapshot (`SnapshotQualityError`) |

BUILD 05 consumes BUILD 04 decisions; it does not re-run quote validation or provider health logic independently.

## Content identity

- **Algorithm:** SHA-256 over canonical JSON (`canonical_bytes`)
- **Version:** `snapshot-content-sha256-v1`
- **Snapshot ID:** `SNAP-` + uppercase hex digest (Strategy A)

### Included in fingerprint

- fingerprint version, schema version
- `decision_time_ns`, `scope`, `quality`
- sorted `source_event_refs`, `source_signal_refs`, `component_refs`
- composition policy semantics (`policy_id`, limits, lookback, flags)
- builder component identity

### Excluded from fingerprint

- `snapshot_id`, `created_at_ns`, metadata receipt fields
- Mongo `_id`, backend name, insertion order
- wall clock, host state, credentials

Event references are ordered by BUILD 02 `event_sort_key` (chronological semantics).
Signal references are ordered by `(as_of_time_ns, signal_id)`.

## Reconstruction vs recomposition

| Operation | Input | Behavior |
|-----------|-------|----------|
| **Reconstruction** | Existing `SnapshotV1` | Resolve exact stored reference IDs |
| **Recomposition** | `SnapshotBuildRequest` + repository state | Build what a new snapshot would be |

Reconstruction never queries “latest” records.

## Persistence

```text
SnapshotBuilder → IntelligenceRepository → InMemory or Mongo
```

Core snapshot code imports only `IntelligenceRepository`, never PyMongo.

## BUILD 06 handoff

BUILD 06 can:

1. load/resolve a `SnapshotV1`
2. fetch exactly referenced `EventV1` / `SignalV1` records
3. compute deterministic features
4. emit new `SignalV1` with snapshot lineage
5. persist signals through `IntelligenceRepository`

BUILD 05 does not calculate CVD, momentum, volatility, or any feature.

## BUILD 07 handoff

The same snapshot engine operates under explicit replay decision times injected
by a future replay runtime. No replay-specific logic lives in BUILD 05.

## Public API

```python
from market_platform_foundation.intelligence.snapshots import (
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
    SnapshotBuilder,
    build_snapshot,
    compose_snapshot,
    inspect_snapshot_build,
    resolve_snapshot,
    verify_snapshot_integrity,
    verify_snapshot_reproducibility,
)
```

## Module layout

```text
intelligence/snapshots/
  policy.py      # request + composition policy
  canonical.py   # fingerprint + snapshot id
  builder.py     # orchestration + pure compose
  resolver.py    # reconstruction + integrity
  errors.py      # snapshot-domain errors
```

# Temporal Integrity V1 (BUILD 02)

BUILD 02 answers:

> **At a given decision time, what information was legitimately knowable and usable?**

It provides reusable, deterministic, clock-injected temporal primitives for the
intelligence architecture introduced in BUILD 01.

## Public API

```python
from market_platform_foundation.intelligence.temporal import (
    TemporalIntegrityPolicy,
    TemporalIntegrityReport,
    TemporalIntegrityError,
    inspect_temporal_integrity,
    require_temporally_usable,
    eligible_as_of,
    usable_as_of,
    select_events_as_of,
    validate_snapshot_temporal_integrity,
    require_snapshot_temporally_valid,
)
```

Module path: `src/market_platform_foundation/intelligence/temporal/`.

## Timestamp definitions

| Field | Meaning |
|-------|---------|
| `event_time_ns` | When the underlying economic/market event occurred or is attributed. **Not** the primary anti-lookahead gate. |
| `provider_time_ns` | When the source/provider timestamps the record (optional). May differ from event/received due to latency, aggregation, or clock skew. |
| `received_time_ns` | When this platform observed/received the information (optional). Local observational timing. |
| `available_time_ns` | Earliest time the intelligence system could legitimately use the information. **Authoritative anti-lookahead eligibility timestamp.** |
| `decision_time_ns` | Point-in-time cutoff for a snapshot, forecast, or selection query. Always supplied explicitly by the caller — core logic never reads wall clock. |
| `as_of_time_ns` | On `SignalV1`, the measurement time the signal claims to represent. Must be `<= snapshot.decision_time_ns` when included in a snapshot. |

Freshness/expiration: BUILD 02 uses policy-driven `max_age_ns` (and optional per-`event_type` overrides). BUILD 01 contracts do not carry universal `expires_at_ns` fields; explicit expiration enforcement can be added later without weakening availability rules.

## The anti-lookahead law

```text
available_time_ns <= decision_time_ns
```

Information with `available_time_ns > decision_time_ns` must not influence that
decision — not by one nanosecond.

`event_time_ns <= decision_time_ns` alone is **insufficient**. An economic event
may have occurred before a decision while still being unknowable because
distribution/receipt happened later.

### Example — delayed data

```text
10:00:00.000  event occurred           (event_time)
10:00:02.000  provider timestamp       (provider_time)
10:00:02.200  platform received        (received_time)
10:00:02.200  available for use        (available_time)

10:00:01.000  decision → NOT ELIGIBLE
10:00:03.000  decision → ELIGIBLE
```

## Eligibility vs usability

| Concept | Meaning |
|---------|---------|
| **eligible** | Information could legitimately have been known: `available_time_ns <= decision_time_ns`. |
| **usable** | Eligible **and** satisfies freshness/validity policy (e.g. `decision_time_ns - available_time_ns <= max_age_ns`). |

Future information is never classified as merely stale — it is `FUTURE_INFORMATION` (hard fail).

### Example A — immediately available trade

```text
event_time     = 100
received_time  = 102
available_time = 102
decision       = 102
→ eligible, usable
```

### Example B — delayed data

```text
event_time     = 100
available_time = 110
decision       = 105
→ NOT ELIGIBLE (FUTURE_INFORMATION)
```

### Example C — stale but legitimate

```text
available_time = 100
decision       = 1000
max_age        = 100
→ eligible, NOT usable (STALE_INFORMATION)
```

### Example D — late event does not rewrite history

Snapshot created at `decision = 500` cannot retroactively incorporate an event
with `event_time = 490` if `available_time = 510`. Immutable snapshots are
validated against resolved source records at creation time; late arrivals affect
**future** decisions only.

## Late arrival principle

A late record does not retroactively alter a prior immutable snapshot, even when
its economic `event_time_ns` predates that snapshot's `decision_time_ns`.
Availability — not event time — governs knowability.

## Replay parity

Historical replay uses the **same** `available_time_ns <= decision_time_ns` rule
as live operation. There is no historical lookahead exception and no
`if replay:` branch in BUILD 02 primitives.

## Temporal violation taxonomy

| Code | Default severity | Typical meaning |
|------|------------------|-----------------|
| `FUTURE_INFORMATION` | ERROR | `available_time_ns > decision_time_ns` (or optional `event_time` policy) |
| `STALE_INFORMATION` | WARNING | Age exceeds configured `max_age_ns` |
| `EXPIRED_INFORMATION` | WARNING/ERROR | Reserved for explicit expiration fields (future) |
| `CLOCK_SKEW` | WARNING (configurable ERROR) | Provider/received clock delta outside tolerance |
| `OUT_OF_ORDER` | WARNING | Stream arrival regression (does not auto-invalidate if eligible) |
| `EXACT_DUPLICATE` | INFO | Same `event_id` and semantic content |
| `CONFLICTING_DUPLICATE` | WARNING | Same `event_id`, different content |
| `SIGNAL_AS_OF_AFTER_DECISION` | ERROR | Signal measurement time after snapshot decision |
| `MISSING_REFERENCE` | ERROR | Snapshot audit could not resolve a referenced record |
| `INVALID_TEMPORAL_RELATION` | WARNING | Diagnostic cross-field anomaly (e.g. `available < received`) |

BUILD 04 maps violations such as `CLOCK_SKEW` into provider quality
flags (e.g. `CLOCK_DRIFT`) — see `docs/engineering/QUALITY_CAPABILITY_ENGINE_V1.md`.
BUILD 02 does not propagate quality decisions.

## Shadow P6 relationship

Shadow Run 1 predictor eligibility (`shadow/predictor.py`) already requires:

```text
event_time_ns <= decision_time_ns
AND
available_time_ns <= decision_time_ns
```

BUILD 02 enforces the universal availability gate for all intelligence-plane
records. Optional policy `require_event_time_before_decision=True` aligns with
stricter domain rules such as P6 without weakening them.

## APIs

### Diagnostic (non-throwing)

```python
report = inspect_temporal_integrity(event, decision_time_ns=T)
report.eligible
report.usable
report.violations
report.hard_failures
```

### Fail-closed

```python
require_temporally_usable(event, decision_time_ns=T, policy=policy)
require_snapshot_temporally_valid(snapshot, resolver=resolver, policy=policy)
```

There is **no** `allow_future=True` production bypass.

### Point-in-time selection

```python
eligible_as_of(events, decision_time_ns=T)          # availability only
usable_as_of(events, decision_time_ns=T, policy=p)  # + freshness
select_events_as_of(events, T, require_usable=True)
```

Selection sorts deterministically by
`(available_time_ns, received_time_ns, event_time_ns, event_id)`.

### Snapshot audit

```python
validate_snapshot_temporal_integrity(snapshot, resolver=resolver)
```

Resolves `source_event_refs` and `source_signal_refs` (and signal upstream
events when resolvable). Every incorporated event must satisfy
`available_time_ns <= snapshot.decision_time_ns`.

## Design constraints

- Pure functions: no network, database, broker, filesystem, or wall-clock reads.
- Integer nanosecond timestamps only — no float seconds in comparisons.
- No timezone conversion in core logic.
- No silent timestamp repair/clamping.
- `TemporalStreamState` is optional, bounded, and deterministic for duplicate/out-of-order observation.

## Build boundaries

BUILD 02 does **not** implement:

| Build | Scope |
|-------|-------|
| BUILD 03 | Provider normalization / provenance expansion — see `PROVIDER_NORMALIZATION_V1.md` |
| BUILD 04 | Quality/capability engine |
| BUILD 05 | Snapshot persistence engine |
| BUILD 06 | Feature calculations |
| BUILD 07 | Replay runtime |

## BUILD 03 handoff

Provider adapters should emit `EventV1` records with trustworthy:

```text
event_time_ns
provider_time_ns
received_time_ns
available_time_ns
source provenance
```

BUILD 02 validates those records deterministically at any explicit
`decision_time_ns` without provider-specific branching.

## Related documents

- [INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md](INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md) — BUILD 04.5 applies BUILD 02 semantics at the persistence query boundary

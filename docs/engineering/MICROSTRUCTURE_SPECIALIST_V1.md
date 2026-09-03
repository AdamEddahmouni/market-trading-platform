# Microstructure Specialist V1 (BUILD 11)

> BUILD 11 introduces the platform's first real specialist: a deterministic CPU-native MICROSTRUCTURE expert that converts scheduler-dispatched, snapshot-bound routed market state into immutable source-grounded EvidenceV1.

## Heterogeneous specialist principle

Specialist intelligence is heterogeneous. A domain should use the simplest model class that performs the task correctly. Microstructure v1 is deterministic/quantitative rather than an LLM.

## Pipeline

```
SnapshotV1 → SignalV1 → DetectionV1 → RoutingDecisionV1 → InferenceJobV1
  → BUILD 10 Scheduler → InferenceDispatchBatch → MicrostructureSpecialist
  → EvidenceV1 → IntelligenceRepository
```

See also:

- [Event Detector & Smart Router V1](./EVENT_DETECTOR_SMART_ROUTER_V1.md)
- [Inference Scheduler V1](./INFERENCE_SCHEDULER_V1.md)
- [Feature Fast Signal Layer V1](./FEATURE_FAST_SIGNAL_LAYER_V1.md)
- [Immutable Snapshot Engine V1](./IMMUTABLE_SNAPSHOT_ENGINE_V1.md)

## Blind first pass

The microstructure specialist receives:

- `InferenceJobV1`, `RoutingDecisionV1`, `DetectionV1`, `SnapshotV1`
- Exact frozen `SignalV1` refs from `DetectionV1`
- Permitted `EventV1` refs when explicitly frozen

It does **not** receive:

- Other specialist `EvidenceV1`
- `HypothesisV1`
- Baseline `ForecastV1` by default
- Blackboard or council state

## Input boundary and derived-signal temporal safety

SignalV1 must be explicitly frozen in the route/detection/job context; later repository signals for the same SnapshotV1 are not automatically admissible.

Example:

1. Snapshot T exists.
2. Signal S1 was available to the route at T.
3. Signal S2 referencing the same snapshot is computed later.

Specialist execution for the original routed job may use S1. It must not silently discover S2 merely because S2 now exists in persistence.

Cross-snapshot frozen refs from BUILD 09 order-flow detections (previous/current NSS) are allowed because they are explicit detection inputs, not repository expansion.

## Supported semantic events

| Semantic event | Evidence kind | Notes |
|----------------|---------------|-------|
| `ORDER_FLOW_REVERSAL` | `ORDER_FLOW_TRANSITION` | NSS transition evidence |
| `LIQUIDITY_EVENT` | `LIQUIDITY_STRESS` | Spread stress transition evidence |

Other domains/events are rejected with `UNSUPPORTED_DOMAIN` or `UNSUPPORTED_SEMANTIC_EVENT`.

## Order-flow analysis

For `ORDER_FLOW_REVERSAL`:

- Source signals: frozen `net_signed_share` refs from detection
- Transition: `NEGATIVE_TO_POSITIVE` or `POSITIVE_TO_NEGATIVE`
- Outputs: `previous_nss`, `current_nss`, `delta_nss`
- Polarity semantics: observed microstructure pressure, not future-price probability
- Strength: derived from BUILD 09 detection severity (not probability)

## Liquidity analysis

For `LIQUIDITY_EVENT`:

- Source signals: frozen `spread_bps` refs from detection
- Outputs: `previous_spread_bps`, `current_spread_bps`, `spread_delta_bps`, optional `spread_ratio`
- Stress transition from detection identity context

## Evidence ≠ forecast

Observed directional pressure ≠ future price probability. The specialist emits `EvidenceV1` only — never `ForecastV1`, `HypothesisV1`, or `OpportunityV1`.

## Evidence identity

Identity version: `microstructure-evidence-sha256-v1`

Inputs: job ID, route ID, detection ID, snapshot ID, semantic event, evidence kind, frozen source signal refs, specialist component/version, policy identity.

Excluded from identity: computed prose, deltas, strength outputs (conflicts expose nondeterminism via `RepositoryConflictError`).

## Execution profile

| Field | Value |
|-------|-------|
| Profile ID | `microstructure-cpu-v1` |
| Resource class | CPU |
| VRAM | 0 |
| Residency | `microstructure-cpu` (no model load) |
| Adapter | none |

This proves heterogeneous scheduling: not every specialist requires GPU/LLM residency.

## Scheduler integration

1. BUILD 09 routes microstructure detections
2. BUILD 10 admits `InferenceJobV1` and dispatches batches
3. `MicrostructureInferenceExecutor.submit()` accepts dispatch receipts
4. Specialist produces per-job outcomes; valid evidence persists via `put_evidence`
5. Scheduler marks jobs `COMPLETED` after successful execution

## Staleness

- `execution_start_time_ns >= expires_at_ns` → `STALE_INFERENCE`, no evidence persisted
- `completion_time_ns >= expires_at_ns` → `STALE_INFERENCE`, no evidence persisted
- Deadline missed but completion before expiration → evidence allowed with `DEADLINE_MISSED` diagnostic

## Batch independence

Jobs may be physically batched but remain epistemically independent. One job's source data or evidence may not influence another job.

## Abstention and failure

- **ABSTAINED**: policy declines degraded optional context
- **FAILED**: integrity errors (missing refs, wrong signal type, route/detection mismatch)
- **STALE**: expiration boundary crossed

## BUILD 12 handoff

BUILD 12 can add more specialists behind the same boundary, dispatch through BUILD 10, preserve blind first-pass execution, collect immutable EvidenceV1, and introduce an Evidence Blackboard only after blind execution completes.

## BUILD 13 handoff

EvidenceV1 from multiple primitive domains can later contribute to composite hypotheses (for example short-squeeze thesis formation) without allowing the microstructure specialist itself to emit that hypothesis.

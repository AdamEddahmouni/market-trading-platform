# Inference Scheduler V1 (BUILD 10)

> BUILD 10 converts deterministic routing intents into deterministic, resource-aware, deadline-aware inference work plans and dispatches them through an abstract executor boundary without performing specialist inference itself.

## BUILD 09 / BUILD 10 / BUILD 11 boundary

| Build | Responsibility |
|-------|----------------|
| BUILD 09 | **Who** should reason — expert domain, priority, capabilities, deadline/TTL |
| BUILD 10 | **When/how** that work should run — queue, resources, batching, residency plan, dispatch |
| BUILD 11 | **Actual** specialist reasoning — model execution, EvidenceV1 output |

## InferenceJobV1 contract

Immutable work specification (`InferenceJobV1`) derived from an executable `RoutingDecisionV1`.

| Field | Semantics |
|-------|-----------|
| `job_id` | Deterministic SHA-256 identity (`inference-job-sha256-v1`) |
| `routing_decision_ref` | Source route |
| `detection_ref` | Upstream detection |
| `source_snapshot_ref` | Optional snapshot context |
| `expert_domain` | Specialist lane from route |
| `priority` | Routing priority preserved |
| `decision_time_ns` | Route decision time |
| `submitted_at_ns` | Scheduler admission time (injected clock) |
| `deadline_time_ns` | Soft usefulness target |
| `expires_at_ns` | Hard no-dispatch boundary |
| `execution_profile_id` | Scheduler resource profile |
| `batch_key` / `residency_key` / `adapter_key` | Batching and residency planning |
| `scheduler_policy_identity` | Policy fingerprint |

Job identity inputs: `routing_decision_id`, `scheduler_policy_identity`, `execution_profile_id`. Runtime outputs (dispatch time, queue position, batch ID) are excluded.

## Queue ordering

Deterministic min-heap ordering (lower tuple value dispatches first):

1. Higher routing priority (`CRITICAL` > `HIGH` > `NORMAL` > `LOW`)
2. Earlier `deadline_time_ns`
3. Earlier `expires_at_ns`
4. Earlier submission sequence (FIFO)
5. Residency affinity rank (tie-break only when policy enabled)
6. `job_id` lexicographic tie-break

## Deadline vs expiration

- **Deadline** = soft usefulness target. After `deadline_time_ns`, job remains runnable until expiration; diagnostic `DEADLINE_MISSED` is recorded.
- **Expiration** = hard boundary. At `now_ns >= expires_at_ns`, job transitions to `EXPIRED` and is never dispatched.

## Resource model

- `ResourceSnapshot` is injected via `ResourceProvider` — scheduler does not probe hardware.
- Logical CPU slots, GPU slots, and VRAM estimates gate admission.
- `BLOCKED_RESOURCE` for temporary unavailability; `REJECTED` for permanently unsupported profiles.
- Cloud tests use synthetic snapshots; physical GPU is not required.

## Execution profiles

`InferenceExecutionProfile` describes specialist runtime requirements. This is **not** BUILD 23 Model Registry governance — profiles are scheduler configuration placeholders until BUILD 11 provides real specialist descriptors.

## Residency / adapter planning

Scheduler emits plans only:

| Action | Meaning |
|--------|---------|
| `KEEP_CURRENT` | Current residency matches |
| `LOAD_RESIDENCY` | Base model load required |
| `SWITCH_ADAPTER` | Adapter switch sufficient |

**Residency affinity never overrides materially higher routing priority or expiration safety.**

## Batching

Compatible jobs share: execution profile, batch key, residency key, adapter key, expert domain. `max_batch_size` from profile. No waiting between ticks for fuller batches.

## Supersession

When enabled, newer route with same supersession key (`expert_domain`, `instrument_id`, `semantic_event_type`, `execution_profile_id`) supersedes older `QUEUED`/`BLOCKED` jobs. Running jobs are not retroactively superseded in v1.

## State machine

States: `QUEUED`, `BLOCKED_RESOURCE`, `READY`, `DISPATCHED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED`, `SUPERSEDED`, `REJECTED`.

Terminal: `COMPLETED`, `FAILED`, `CANCELLED`, `EXPIRED`, `SUPERSEDED`, `REJECTED`.

Runtime state is separate from immutable `InferenceJobV1`.

## Persistence

| Artifact | Classification |
|----------|----------------|
| `InferenceJobV1` | Durable immutable audit/spec (`inference_jobs` collection) |
| Scheduler runtime queue | Ephemeral in-process |
| Scheduler observer trace | Telemetry, bounded |
| Attempt records | Not persisted in v1 |

No Mongo TTL index on `expires_at_ns` — logical expiration ≠ database deletion.

## Replay parity

Identical route sequences, resource snapshots, policy, and executor acknowledgements produce identical job IDs, queue order, batch IDs, and residency plans under `ReplayClock` and live-like clocks.

## BUILD 11 handoff

BUILD 11 implements `InferenceExecutor` for one domain:

1. Define concrete execution profile
2. Implement executor receiving `InferenceDispatchBatch`
3. Consume SnapshotV1 + DetectionV1 + RoutingDecisionV1
4. Obey deadline/expiry from job contract
5. Apply residency plan from dispatch batch
6. Execute specialist, emit EvidenceV1
7. Acknowledge completion/failure via scheduler callbacks

BUILD 10 scheduler semantics remain unchanged.

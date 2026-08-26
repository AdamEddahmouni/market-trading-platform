# BUILD 32 — Operational Reliability, SLOs & Disaster Recovery

> **BUILD 32 makes supervised live operations observable and recoverable. It does not expand live execution authority or reduce human controls.**

## Core Principle

Operational uncertainty must reduce authority, never increase it. If the platform cannot reliably observe, reconcile, persist, or recover its live state, new live submissions must fail closed.

## Separation of Concerns

| Concept | Is NOT |
| --- | --- |
| metrics | canonical state |
| alert | trade instruction |
| SLO success | trading permission |
| healthy status | authorization |
| recovery complete | resume approval |

## Health Semantics

- **Liveness**: process/component is running
- **Readiness**: component can safely perform its responsibility
- **Health**: quality/state within policy
- **Stale**: `now >= last_heartbeat + stale_after`
- **Unknown**: telemetry/evaluation failed — must not display as healthy for execution-critical dependencies

## Heartbeats

Critical components emit heartbeats with:

- `observed_at_ns`
- `expected_interval_ns` (default 30s)
- `stale_after_ns` (default 90s)

Never-observed execution-critical components are not healthy and block live readiness.

## SLO Framework

`OperationalSLOPolicyV1` defines conservative qualification objectives:

| Objective | Safety-critical | Missing data |
| --- | --- | --- |
| provider connection availability | yes | INSUFFICIENT_DATA |
| broker status freshness | yes | INSUFFICIENT_DATA |
| reconciliation freshness | yes | INSUFFICIENT_DATA |
| persistence write success | yes | INSUFFICIENT_DATA |
| operator API availability | no | INSUFFICIENT_DATA |
| critical alert delivery success | yes | INSUFFICIENT_DATA |

Missing data never produces 100% success.

## Alerting

- Alerts are distinct from `LiveExecutionIncidentV1` canonical incidents
- Alert acknowledgement does not resolve incidents
- Dedup prevents storms; critical severity escalation is never silently deduped
- Delivery failures produce `ALERT_DELIVERY_FAILED` evidence
- Default channel: console/local operator (external channels optional)

## Persistence

Canonical persistence failure blocks new live submissions (`PERSISTENCE_UNHEALTHY`).

Required durable records must be known before broker transport (persist-before-side-effect).

## Backup & Recovery

- `BackupManifestV1` with content hashes; secrets excluded
- Backup success requires restore verification in qualification
- Corrupt backup checksum → do not restore as trusted
- Recovered runtime starts `BLOCKED_PENDING_RECONCILIATION`
- Broker remains external truth for live order state after stale restore
- Unknown/corrupt kill-switch state defaults to BLOCK

## Disaster Recovery Drills

DR01–DR15 run with fixtures only:

- real submit = 0
- real cancel = 0
- real replace = 0

## Soak Qualification

- Deterministic virtual endurance in CI (`run_virtual_soak_endurance`)
- Wall-clock soak reported separately when actually executed
- Soak success does not widen live authority

## Operator Control Plane Integration

`GET /canary/reliability` exposes read-only:

- health matrix with as-of/freshness
- SLO summary
- persistence health
- backup integrity status
- observability degraded state

## BUILD 33 Boundary

Future work: long-duration supervised production pilot, provider redundancy, broker failover analysis — not removal of human authorization or per-order confirmation.

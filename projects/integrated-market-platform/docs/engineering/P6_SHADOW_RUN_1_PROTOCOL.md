# P6 Shadow Run 1 — Preregistered Forward Validation Protocol

**Status:** Authoritative preregistered protocol (outcome-independent)  
**Protocol version:** `SHADOW_RUN_1_BIYA_FROZEN/1.0.0`  
**Preregistered:** 2026-09-01T15:33:00Z  
**Machine-readable:** [`artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json`](../../artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json)

## Purpose

Execute a prospective, no-lookahead shadow validation of IMP's observational forward-validation machinery on BIYA using the frozen NSS-direction predictor. This protocol proves operational integrity and evidence capture — not trading alpha.

## Scope

| Dimension | Binding value |
|-----------|---------------|
| Instrument | BIYA (Nasdaq) |
| Provider | Moomoo observational (`IMP_LIVE_OBSERVATIONAL=1`, `IMP_MOOMOO_LIVE=1`) |
| Execution | **NONE** — no orders, no Live production execution |
| Predictor | `nss-direction-v1` (frozen constants in protocol JSON) |
| Sessions | Up to 8 regular ET sessions from preregistered `first_session` |
| Cadence | 60-second decision buckets; 30-minute label horizon |

## Time semantics

| Term | Definition |
|------|------------|
| `source_time` | Provider `event_time_ns` on admitted trade |
| Ingestion time | `live_received_time` / envelope receive clock |
| Decision time | First qualifying admitted trade `event_time_ns` in bucket |
| Persistence time | Append-only `created_at_ns` on ledger rows |
| Evaluation time | After `target_time + horizon_tolerance`; labeling only |

**Anti-lookahead law:** `available_time_ns <= decision_time_ns`. Late-arriving trades are excluded even when `event_time` precedes the decision.

## Admissibility

At decision time the system may use only admitted trades and quotes available at or before decision time, plus frozen predictor constants from the immutable manifest.

Forbidden: outcome labels, P30 prices, post-horizon captures, execution/portfolio mutation authority.

## Stopping rule (frozen)

```text
STOP when (complete_sessions >= 5 AND scheduled_grid_opportunities >= 65)
     OR elapsed_regular_sessions >= 8
```

Scheduled grid opportunities are outcome-independent.

## Acceptance

See [`artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json`](../../artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json) (generated after run initialization). P6 closes only when every criterion has evidence.

## Operator workflow

See [FORWARD_SHADOW_VALIDATION SOP](sops/FORWARD_SHADOW_VALIDATION.md).

## Related

- Design spec: [2026-08-23-platform-p6-shadow-run-1-design.md](../superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md)
- BUILD 26 forward qualification: [FORWARD_SHADOW_QUALIFICATION_V1.md](FORWARD_SHADOW_QUALIFICATION_V1.md)
- Source audit: [SOURCE_AVAILABILITY_AUDIT.json](../../artifacts/shadow-run-1/SOURCE_AVAILABILITY_AUDIT.json)

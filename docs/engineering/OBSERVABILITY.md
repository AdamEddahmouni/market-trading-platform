# Observability

**Status:** Logging and trace guidance.

## Business audit vs technical logs

| Type | Examples | Storage |
|------|----------|---------|
| **Business audit** | Intents, ledger events, `decision_source_snapshot`, `correlation_id` | Paper ledger / events |
| **Technical logs** | API errors, provider health, startup recovery | `.local/platform-*.log`, console |

Do not conflate `source_time` (audit context) with log timestamps.

## Frontend error visibility

- Query errors surface in observability panels where applicable
- Startup recovery banner for crash recovery / corrupt DB
- Mode mismatch shown in `ModeEnvironmentBar`

## Correlation IDs

End-to-end Paper decision linkage — display in Portfolio and Execution Trace. See [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md).

## Execution trace

`ExecutionTracePanel` — intent → order → fill chain with provenance and source snapshot.

## Provider health

`/diagnostics/provider` — channel health, generation, quota.

## Canary / reconciliation

`/live-canary` — Live operational control plane; `canary-snapshot` and `canary-reconciliation` queries.

## Backend logs

Launcher captures API output to `.local/platform-backend.log`. Redact secrets manually if sharing logs.

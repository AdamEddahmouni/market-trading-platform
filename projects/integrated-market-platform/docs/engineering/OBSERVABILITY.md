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

## Strategy Paper runtime diagnostics

The backend-only `StrategyPaperRuntime` returns a bounded, ephemeral receipt
for each entry, close, reconstruction, or settlement/learning operation.
Persisted IntelligenceRepository records, Paper ledger events, and portfolio
projections remain authoritative. Each stage diagnostic contains a stage,
status, sorted reason codes, and non-secret identifiers; it does not include
credentials, raw provider payloads, or a second decision record.

The receipt joins these identifiers when they exist: scan, StrategyMatch,
ForecastV1, prediction-ledger entry, opportunity, economic assessment, thesis
cluster, comparison, allocation decision/set, trade proposal, risk decision,
Paper order, fill, and cumulative attribution. Quantity facts are reported
separately as allocation desired, proposal requested, risk approved,
submitted, and filled quantities.

Terminal and stop statuses are explicit and machine-readable:
`SCREENED_OUT`, `STRATEGY_REJECTED`, `FORECAST_UNAVAILABLE`,
`OPPORTUNITY_SUPPRESSED`, `NOT_ACTIONABLE`, `NOT_ALLOCATED`,
`RISK_REJECTED`, `EXECUTION_FAILED`, `FILLED`, and `CLOSED`. These statuses
describe the bounded runtime attempt; they do not authorize execution.
Failures for account/mode, point-in-time, expiry, authority, or lineage
guards stop before downstream Paper mutation and retain only the evidence
already persisted by the relevant authority.

Attribution diagnostics must be interpreted using cumulative fill-set
semantics. A later snapshot covers the complete persisted fill set through
that materialization and is selected as the latest complete result; snapshots
must never be added together. Prediction quality and trading quality are
separate learning outputs, and a closed trade can legitimately have a
`NOT_DUE` prediction outcome until its availability cutoff.

## Provider health

`/diagnostics/provider` — channel health, generation, quota.

## Canary / reconciliation

`/live-canary` — Live operational control plane; `canary-snapshot` and `canary-reconciliation` queries.

## Backend logs

Launcher captures API output to `.local/platform-backend.log`. Redact secrets manually if sharing logs.

## Developer workflow telemetry

`python tools/imp.py` records one JSON object per command in
`.local/developer-workflow/telemetry.jsonl` (or `IMP_TELEMETRY_PATH`). Events
contain a schema version, command identity, exit status, and wall time only;
environment values, credentials, test output, and market data are excluded.
This is intentionally a local, lightweight measurement surface rather than a
remote analytics system.

Aggregate the events when needed to measure validation runtime, CI/local
runtime, repeated command fingerprints, agent iterations, or command adoption.
`artifacts/developer-workflow/closure-report.json` records the telemetry path
used for a closure run.

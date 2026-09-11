# P7 Telemetry Architecture

## Validation receipt extension

Every executed validation receipt may include `performance_telemetry`:

- Wall timing, mode, suite/test counts
- Worker and scheduler metadata
- Environment fingerprint (OS, Python, CPU, git SHA, dirty state)
- Suite-level timing summary and wave summary
- Budget classification with explain payload

Schema version: `1.0` (`telemetry_schema_version`).

## Ephemeral storage

Per-run summaries append to
`.local/developer-workflow/performance-telemetry.jsonl` (gitignored).
Disable with `IMP_PERF_TELEMETRY=0`.

## Committed evidence

Deliberate benchmark series and closure receipts live under
`docs/audits/performance-engineering-p7/` and `evidence/performance/` per
manifest `GENERATED_PERFORMANCE_EVIDENCE` patterns.

## CI integration

`imp-python.yml` writes `ci-performance-summary.json` with
`remote_status: REMOTE_UNMEASURED`. No timing gates.

## Developer interface

`python tools/imp.py env` exposes `performance` block: budget version, gating
policy, scheduler/selector versions, canonical workloads. No validation launch.

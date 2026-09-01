# Operations Runbook

**Status:** Lightweight local operations guide.

## UI fails to start

1. Check `ui/node_modules` — run `npm install`
2. Check port 5173 not in use
3. Read `.local/platform-ui.log`
4. `cd ui && npm run dev` manually for errors

## Backend fails to start

1. Use CPython 3.11 `.venv`
2. `PYTHONPATH=src`
3. Check port 8766 — kill stale: `tools/ui1/restart_ui_api.ps1`
4. Read `.local/platform-backend.log`

## Provider unhealthy

1. `/diagnostics/provider` or provider panel
2. Verify credentials in env (not committed)
3. Moomoo: OpenD on `127.0.0.1:11111`
4. Live tests only when debugging: `validate.py live <provider>`

## Paper execution unavailable

1. Check `IMP_PAPER_EXECUTION=1` and related gates
2. Verify operating context: `execution_mode=INTERNAL_SIMULATION`, `execution_authority=PAPER_ONLY`
3. UI: `ModeEnvironmentBar` mismatch warning
4. See [MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md)

## Canary degraded

1. `/live-canary` — snapshot and reliability panels
2. Check `canary-snapshot` query errors in network tab
3. Live mode only — Demo/Paper use different data paths

## Reconciliation failure

1. Canary reconciliation panel
2. Backend reconciliation events (P4-4B) — mismatches are explicit events
3. Never silently fix mismatches in UI

## API schema validation failure

1. Compare `ui/src/api/schemas.ts` with API response
2. Check `manifests/ui1/schemas/`
3. Run targeted vitest + backend suite

## Full validation failure

```powershell
.venv\Scripts\python.exe tools\validate.py changed --explain
```

Identify failing suite from output; run targeted unittest module.

## Bundle budget failure

```powershell
cd ui && npm run build
```

Inspect largest chunk in script output; lazy-load or split imports.

## Provider-specific

See [docs/providers/](../providers/).

## Escalation

Document incident in WORK_LOG if significant; use [templates/BUG_REPORT.md](../engineering/templates/BUG_REPORT.md).

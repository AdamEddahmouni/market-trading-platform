# RT-01 Runbook

## Inspect tracing status

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m market_platform_foundation.rt01 status --json
```

## Run measured baseline

```powershell
.venv\Scripts\python.exe -m market_platform_foundation.rt01 baseline --profile receive_to_canonical_state --json
```

## Export in-memory spans

```powershell
.venv\Scripts\python.exe -m market_platform_foundation.rt01 export artifacts/imp-rebase/RT01/trace_export.json --json
```

## Measure tracing overhead

```powershell
.venv\Scripts\python.exe -m market_platform_foundation.rt01 overhead --json
```

## Investigate partial traces

Use `RT01.OP.SHOW_TRACE` and verify `completeness` in the response. Partial
context loss is expected when sampling is active or context carriers are dropped
at queue boundaries.

## Safe real-provider observational tracing

Only exercise live provider callbacks when OpenD is reachable and observational
mode is enabled. Fixture replay is not live provider evidence.

# P3.1 Live Internal Execution & Operator Closure

**Date:** 2026-08-21  
**Status:** Operator-owned closure of live observational Moomoo data + internal paper simulation. Not P4. No external brokers, OMS, or strategy automation.

## Root cause

Live MARKET fills previously failed for three independent reasons:

1. **Intent time vs latest quote.** Using `latest_quote - 1` as `created_time` made the last L1 snapshot look post-intent. Intent time is wall-clock `T`. Preview is `WAITING_FOR_ELIGIBLE_LIVE_EVENT` until a later `EXECUTION_ADMITTED` L1 exists. Submit waits a bounded interval for that event (`IMP_LIVE_EXECUTION_WAIT_MS`).
2. **INTERNAL_PAPER gated on fill eligibility.** Capability `INTERNAL_PAPER` was `UNAVAILABLE` / `INTERNAL_PAPER_GATED` until the simulation gate was `AUTHORIZED`. Env flags `IMP_PAPER_EXECUTION=1` and `IMP_LIVE_INTERNAL_SIMULATION=1` make internal paper **reachable** (`AVAILABLE`, reason `AWAITING_ELIGIBLE_LIVE_EVENT` until a fresh admitted L1 exists). `IMP_MOOMOO_LIVE` authorizes observational market data only; it does not authorize broker execution.
3. **Active instrument leaked BIYA.** Fixture identity (`store.instrument_id`) was used as a silent live default. Canonical resolver: ticket → workspace → explore pref → session pref → first `scope_symbols` → none. Live mode never falls back to BIYA.

## Active instrument

`resolve_active_operator_instrument` is the only identity resolver for tickets, context SCOPE, health quotes, and paper session preferred instrument. Live `/workspace` with no selection shows **SELECT AN INSTRUMENT**. Replay still routes empty `/workspace` to the admitted fixture.

## Live evidence path

Moomoo L1 → runtime admission (`EXECUTION_ADMITTED`) → `LiveExecutionEventBuffer` → `LIVE_L1_SNAPSHOT` bars (`SIMULATION_POLICY` volume) → `BarConservativeSimulator`. Fill uses the first post-intent eligible bar, never the latest quote shortcut. Display-admitted tape is not executable.

Every live paper API envelope stamps `data_provider=MOOMOO`, `execution_provider=INTERNAL`. Traces set `broker_order_submitted=False`.

## Restart semantics

SQLite restores the open paper session, orders, fills, idempotency, and workspace instrument. Execution authority stays deferred until fresh live health (`RESTORED_SESSION_AWAITING_FRESH_LIVE_HEALTH`). Last known mark restores as quality `RESTORED` (not `PASS`) until a fresh Moomoo quote is applied. Same idempotency key returns the same order; fill count is unchanged. Provider generation change clears the execution buffer.

## Browser acceptance

Restart API from current source (`tools/ui1/restart_ui_api.ps1`, SDK venv). Env: `IMP_LIVE_OBSERVATIONAL=1 IMP_MOOMOO_LIVE=1 IMP_PAPER_EXECUTION=1 IMP_LIVE_INTERNAL_SIMULATION=1 IMP_PERSIST_STATE=1`. Explore AAPL → capabilities → subscribe → Workspace (quote/tape/CVD/L2) → ContextBar DATA LIVE OBSERVATIONAL · MOOMOO / EXECUTION INTERNAL SIMULATION · PAPER ONLY → Portfolio BUY 1 MARKET Preview/Submit FILLED → trace Moomoo/Internal/PAPER ONLY/Broker NO → restart without wiping SQLite → restore + stale mark then PASS after fresh data.

Live AAPL MARKET fill (2026-08-21): session `1FB1AF68…637A3`, order `0917CCD3…07E4`, fill `6E865C8D…BB16`, fill_price_minor `30969` (309.69), idempotency `p31-live-20260821212708`. Screenshots: `evidence/ui1/p31/01-context-bar-live.png` … `05-execution-trace.png`. Cursor IDE browser MCP tabs were not stable; operator path was confirmed with agent-browser on `http://localhost:5173/`.

## Validation (2026-08-21)

- `pytest tests/platform/test_paper_p31.py`: 26 tests covering PIT, instrument, restart, Moomoo trade-API AST, capture vertical slice.
- `python tools/validate.py changed --workers 2`: **PASSED** 843 tests, 7 skipped, 0 failures (239.987s); `full_suite_required=true`.
- `python tools/validate.py full --workers 2`: **FAILED** 1323 tests, 7 skipped, **1 failure** in suite `phase1` (6 tests). Classified as pre-existing dirty-tree `tests/phase1/.out/*` ADR hash mismatch; those artifacts were not regenerated as a P3.1 fix.

## Limitations

- Regular-hours / thin tape can delay post-intent L1 (`WAITING_FOR_ELIGIBLE_LIVE_EVENT` / UI copy `WAITING_FOR_EXECUTABLE_LIVE_DATA`). Do not rename `NO_EXECUTABLE_BAR` for fixture replay.
- Moomoo depth is MBP, not MBO.
- Vite `/workspace` proxy can steal full page loads; client-side routing from `/` works.
- OpenD stop/start reconnect-generation was covered in unit tests (`previous_generation`, `reconnect_cached`); a live OpenD bounce without resetting the paper session was not executed in this sprint.
- Unrelated dirty-tree `tests/phase1/test_adr_verifier.py` hash mismatch is not this milestone.

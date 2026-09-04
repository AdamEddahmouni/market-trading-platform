# PLATFORM-STATE-001 — Durable Local State & Operator Workflow

**Status:** COMPLETE_WITH_LIMITATIONS (Platformization P3)  
**Authority:** Extends [PLATFORM-PAPER-001](./2026-08-21-platform-paper-001-design.md) and [PLATFORM-DATA-001](./2026-08-21-platform-data-001-design.md)  
**Date:** 2026-08-21

This is a **local, single-owner** market intelligence and paper-trading workstation.
P3 does **not** add authentication, hosted persistence, multi-user roles, or broker execution.

## Storage

Default engine: **SQLite** (stdlib `sqlite3`) with WAL, `BEGIN IMMEDIATE` transactions, and `PRAGMA integrity_check`.

| Path | Rule |
|---|---|
| Default | `integrated-market-platform/.local/imp-state.sqlite3` (gitignored) |
| Override | `IMP_STATE_DIR` |
| Enable | `IMP_PERSIST_STATE=1` or any `IMP_STATE_DIR` (API `--serve` sets persist on) |
| Captures | File-backed JSONL + manifests. Catalog indexes paths only |

Ticks / L2 / high-volume tape **must not** enter SQLite.

## Event-sourced paper truth

Append-only `paper_events` is the ledger. Positions, cash, orders, fills, and P&L are **projections**.
`paper_snapshots` is an optional **cache** keyed by `last_event_sequence`, `schema_version`, and `projection_hash`.

`FillRecorded` + `PositionChanged` append inside one `atomic_append()` / SQLite transaction.

Idempotency keys live in `paper_idempotency` and survive restart. Duplicate key → same `order_id`, no second fill.

Unknown `schema_version` newer than this binary **fail closed**. Corrupt DB: fail safe, **do not overwrite** the file.

## Restart recovery

1. Open DB, migrate, integrity-check.
2. If an `OPEN` paper session exists and `data_mode` / providers / starting cash match, restore events.
3. Reconnect Moomoo independently. Do **not** persist `provider.health=HEALTHY`. Last quote is historical, not a live mark.
4. Re-enable `INTERNAL_SIMULATION` only after env flags (`IMP_PAPER_EXECUTION`, `IMP_LIVE_OBSERVATIONAL`, `IMP_LIVE_INTERNAL_SIMULATION`) still authorize **and** fresh observational evidence is healthy.
5. Persisted session cannot override safety env.

Same paper session ≠ new provider connection.

## Operator state

Watchlists, bounded MRU recents, saved workspace (`layout_schema_version`), non-secret provider prefs.
Unknown workspace fields ignored. Secrets (`api_key`, `password`, `token`, `unlock`, …) rejected.

Capture catalog statuses: `AVAILABLE` / `MISSING` / `CORRUPT` / `INCOMPATIBLE`.
Replay launch provenance: `REPLAY · MOOMOO CAPTURE` (`CAPTURE_REPLAY`), never `LIVE`.

## Tools

```text
python tools/state/check.py
python tools/state/backup.py
python tools/state/export_state.py --output .local/export.json
python tools/state/rebuild_projections.py
```

Backup uses SQLite's backup API. `tools/moomoo/check_live_environment.py` is imported in-process (no shell-out) from `local_state/opend.py`.

## Known limitations (P3)

- Cursor IDE browser MCP could not attach a tab (`No browser tab available` / `view not found`). Live preflight used HTTP against OpenD-backed API instead of click-through Explore UI.
- Live internal fills remain `NO_EXECUTABLE_BAR` / `SIM_NO_POST_SIGNAL_BAR` when the execution buffer has no `EXECUTION_ADMITTED` L1 quotes (display-admitted tape is not enough). Fixture-bar fills persist and replay correctly.
- `GET /instruments/{id}/capabilities` previously dropped the HTTP connection; the handler now fails closed with JSON. Restart the API process to load that fix.
- Research-run history UI is deferred (table exists; no productized experiment browser).
- Workspace persistence stores selected instrument and panel ids, not a full drag-layout engine.

## Out of scope (P4+)

Tradier/Moomoo paper adapters, external broker orders, live-money execution, hosted auth, strategy automation.

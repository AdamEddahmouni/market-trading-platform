# Paper Backend — Agent Instructions

Parent: [AGENTS.md](../../../AGENTS.md)

## Invariants

- **Fail closed** — reject mutations without `PAPER_ONLY` authority
- **Append-only** ledger events — no silent mutation of history
- **Optional fields** on intents/projections for backward compatibility
- Epoch **nanoseconds** for new timestamps
- Bounded `decision_source_snapshot` on write

## Flow

Preview → submit → `UserOrderIntent` → ledger → `project_orders()` / trace.

See [PAPER_DECISION_LIFECYCLE.md](../../../docs/architecture/PAPER_DECISION_LIFECYCLE.md).

## Changes

Complete [PAPER_EXECUTION_CHANGE.md](../../../docs/engineering/sops/PAPER_EXECUTION_CHANGE.md).

Run `validate.py full` for execution-path changes.

## Key modules

- `decision_source.py` — snapshot validation
- `execution.py`, `ledger.py` — events
- `ui_api/` projections — JSON shapes for UI

## Tests

Manifest-owned suites under `tests/` — run via
`python tools/imp.py test affected`; use
`python tools/imp.py validate full` for the required execution-path checkpoint.

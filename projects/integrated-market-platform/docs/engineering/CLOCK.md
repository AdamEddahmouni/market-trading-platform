# Shared wall-clock primitive: `monotonic_wall_ns`

**Module:** `src/market_platform_foundation/clock.py` (neutral, top-level — imported as `from ..clock import monotonic_wall_ns`).

## Problem

`time.time_ns()` (the wall clock) can freeze for whole ticks in virtualized
environments or return coarse-grained values. In this VM the same value was
observed returned 30× across seconds. That produced real defects:

- two `open_session` calls in the same tick → byte-identical session bodies → **identical session ids** (P3 flake, fixed in P4-4B);
- successive ledger appends → identical `event_time` / `available_time` values;
- `conversation_id` / `message_id` content hashes colliding for back-to-back identical writes (assistant audit store);
- a busy-wait **deadline** computed from a frozen wall clock that never expired;
- staleness checks (capability registry) reporting a capability as perpetually fresh.

## The primitive

`monotonic_wall_ns()` returns the wall clock when it advances and `last + 1`
when it does not, so successive calls within **one process** are strictly
increasing while still tracking wall time whenever it moves. `reset_clock_for_tests()`
resets the per-process guard for test isolation.

```python
from ..clock import monotonic_wall_ns

now_ns = monotonic_wall_ns()
```

## Adoption policy

Use `monotonic_wall_ns()` wherever a wall-clock value feeds:

1. **identity hashes** (session ids, conversation ids, message ids, event ids);
2. **event / observation timestamps** on the same ledger or store (no ties);
3. **point-in-time defaults** (`as_of` when a caller supplies none);
4. **staleness / deadline decisions** where a wall timestamp is the only available anchor.

Adopted sites (from the repo-wide audit, 2026-08-22):

| Site | Role |
|---|---|
| `paper/ledger.py` | session `opened_at_ns` (hashed into session id) + all event timestamps |
| `ui_api/paper_projections.py` | live observation times |
| `local_state/repository.py` | SQLite session/preference timestamps |
| `assistant/audit_store.py` | `conversation_id` / `message_id` hash inputs |
| `donor_bridge/projections.py` | default as-of for `mode == "current"` |
| `market_data/live_admission.py` | `received_time_ns` fallback when no injected clock |
| `market_data/live_runtime.py` | ingest `received_time_ns` / `effective_wall` fallbacks |
| `market_data/observational_state.py` | `received_time_ns` / freshness fallbacks |
| `market_data/capability_registry.py` | capability staleness (`_age_seconds`) |
| `providers/projections.py` | RTH/EXTENDED session classification fallback |

## Deliberately NOT adopted

Sites that only write **informational metadata** (never a decision, hash, or
deadline) stay on the raw clock: `observed` / `tested_at` / `retrieved_at`
strings, capture `received_ns`/`available_ns` on data records, migration
`applied_at` bookkeeping. `time.monotonic()` remains the correct primitive for
**elapsed-time waits** (e.g. the post-intent bar wait deadline in
`paper_projections.py`) — a wall clock, however guarded, cannot measure elapsed
time while frozen.

## Residual limitations

- **Elapsed time during a freeze is still understated.** While the wall clock
  is frozen, `monotonic_wall_ns()` advances only per-call, so a staleness/age
  computation during a long freeze understates true elapsed time. For
  hard deadlines prefer `time.monotonic()`-based elapsed tracking; for
  persisted cross-process timestamps the freeze window is bounded by the clock
  stall.
- **Cross-process uniqueness is NOT covered.** The clock guarantees
  strictly-increasing values only within one process. Identity bodies that need
  global uniqueness carry an explicit `uuid4` nonce (paper session ids); the
  audit store predates this and relies on timestamped hashes, so two processes
  could in principle still collide — add a nonce there if multi-process writes
  ever land.

## Tests

Frozen-clock regression tests patch `market_platform_foundation.clock.time.time_ns`
(the module-level `time` reference inside the clock, not `time` itself):

- `tests/platform/test_paper_p3.py` — unique session ids + strictly increasing
  event times under a frozen clock;
- `tests/assistant/test_audit_store.py` — unique conversation/message ids under
  a frozen clock.

### Clock flake guard

`tools/platform/run_clock_flake_guard.py` replays the platform persistence test
modules (default `tests/platform/test_paper_p3.py`) for N iterations per
scenario under the same adversarial clock patches, and asserts the guarded
clock invariant directly. Two scenarios:

- **frozen** — `time.time_ns()` returns a constant;
- **jump** — the wall clock freezes, jumps backward, jumps forward, and
  freezes again (an `itertools.cycle` script).

After each iteration the guard samples `monotonic_wall_ns()` 64 times under the
active patch and requires strictly increasing values; any suite failure or
invariant violation fails the run. Suites are rebuilt fresh per iteration (in
this interpreter a `unittest.TestSuite` object can only be executed once).

Invocation:

```bash
python tools/platform/run_clock_flake_guard.py                  # frozen,jump x3 over the default module
python tools/platform/run_clock_flake_guard.py --iterations 5   # more iterations per scenario
python tools/platform/run_clock_flake_guard.py --scenarios frozen
python tools/platform/run_clock_flake_guard.py --module tests/assistant/test_audit_store.py
```

Flags: `--iterations N` (default 3), `--scenarios frozen,jump`
(comma-separated), `--module <path>` (repeatable). The run writes
`evidence/platform/clock-flake-guard-report.json` and exits 0 on pass / 1 on
any failure, so CI can gate on the exit code. The guard is deliberately
standalone — it is not wired into `tools/validation_manifest.json` (a governed
manifest edit).

# P5 — Production / Body Runtime Profiling & Optimization

**Status:** Preserved locally on `perf/p5-runtime-profile` at P5 checkpoint
**Base checkpoint:** `efc9219ea4d1a79511278a4a8c0ea0d0d5e8e2fd` (P6 clean)

## Scope

Profile-first reduction of measured production/body runtime hotspots while preserving
exact product semantics, P3 selector behavior, P4 fixture/cache contracts, and P6
environment/bootstrap behavior.

## Primary finding

Unified workstation, UI1 pipeline aggregate, and donor-bridge cross-lane bodies were
dominated by **repeated donor HTTP availability probes** (`is_available` /
`fetch_health`) against offline localhost bridges. Each probe blocked ~2s on Windows
TCP connect when donors were not running — not projection math or fixture I/O.

## Implemented optimizations

1. **Donor availability probe timeout + bounded cache** (`squeeze_client.py`,
   `futures_client.py`) — 0.5s probe timeout; 2s TTL cache keyed by `base_url`.
2. **ReplayStore-scoped `build_capabilities` memoization** (`projections.py`,
   `store.py`) — keyed by instrument, cursor, prediction cutoff; invalidated on
   load/hydrate/refresh.

## Evidence files

| File | Purpose |
|------|---------|
| `P5_BEFORE_BASELINE.json` | Controlled pre-change suite timings |
| `P5_AFTER_BASELINE.json` | Post-change suite timings |
| `HOTSPOT_PROFILE.json` | cProfile attribution summary |
| `OPTIMIZATION_LEDGER.json` | Hotspot ledger with status |
| `FULL_COST_ATTRIBUTION.json` | Suite share table |
| `P5_CLOSURE.json` | Closure receipt |

## Profiling tooling

Opt-in harness: `python tools/p5_profile_harness.py <mode> --output <path>`

Modes: `import-decomposition`, `workspace-evidence`, `short-intelligence`, `build-evidence`

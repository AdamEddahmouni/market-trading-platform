# Documentation and governance audit

**Lane:** J | **Date:** 2026-09-12  
**Excluded:** `WORK_LOG.md` (no-touch)

## Authority map (healthy)

- `docs/README.md` routes to architecture, engineering, platform truth.
- `docs/platform/PROGRAM_STATUS.md` — current accepted state (v1.10, verified 2026-09-10).
- Preimplementation closure on main: `PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md`.
- FTEP governance on main: `FTEP_ACTIVATION_GATES.md`, `FTEP_CORE_V1.md`, capability + calibration contracts.

## Gaps

1. Foreground branch carries Wave A artifacts not on `origin/main` — risk of **split-brain** until merged or cherry-picked.
2. `PROJECT_STATUS.md` vs `PROGRAM_STATUS.md` — agents must prefer PROGRAM_STATUS per AGENTS.md.
3. Overnight deliverables are **candidate truth** until merged; label as `OVERNIGHT_SYNTHESIS`.

## Verdict

**RESEARCH_COMPLETE** — governance on main is coherent; merge foreground FTEP docs when activation lane stabilizes.

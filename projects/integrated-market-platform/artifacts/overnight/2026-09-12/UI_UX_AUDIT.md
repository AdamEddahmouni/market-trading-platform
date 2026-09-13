# UI / UX audit (read-only)

**Lane:** D | **Date:** 2026-09-12  
**Source:** `artifacts/wave-a-findings/ux-hooks-audit.json` (foreground, read-only)

## Surfaces

| Operator term | IMP surface | APIs | UI reach |
|---|---|---|---|
| Screener / radar | DISCOVER | `/discover/mixed` | Strong |
| Command center | NOW | `/context`, `/attention` | Moderate |
| Cross-lane opportunity | SHARED P4 fusion | Workspace options snapshot | Options block only |
| Provider health | Live diagnostics | `/provider/health`, Finviz health | Strong |
| Operator readiness | Preflight | `/operator/readiness` | Moderate |

## Gaps (no code changes overnight)

1. **`capability_states`** projected but largely unused in React components — operators see health strips, not lane capability matrix.
2. **Three parallel type systems** — lane capabilities, provider health, operator readiness; increases hook/query duplication risk.
3. **FTEP / forward-test UX** — persistence env-gated; preflight messaging when `PERSISTENCE_DISABLED`.
4. **Discover vs Opportunity contract** — no single “opportunity card” component enforcing `OPPORTUNITY_CONTRACT.md` fields in UI.

## Recommendations

| Priority | Action | Class |
|---|---|---|
| P1 | Consume `capability_states` in DISCOVER observability panel | IMPLEMENT_IN_ISOLATED_WORKTREE |
| P2 | Unify operator readiness + provider health strip | DEFER_TO_FOREGROUND_LANE |
| P3 | Opportunity summary component from contract | SPEC_READY_FOR_LATER |

## Foreground overlap

Any change to `ui_api/projections.py` or campaign-readiness hooks → **DEFER_TO_FOREGROUND_LANE**.

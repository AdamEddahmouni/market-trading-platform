# Foreground conflict map

**Foreground:** `work/ftep-v1-activation` @ `099388f`  
**Overnight base:** `origin/main` @ `588ada8`

## Divergence

Foreground is **ahead** of main with FTEP activation, Wave A findings, Wave B tooling, and readiness fixes. Overnight branch is **clean main + deliverables only**.

## High-conflict paths (do not cherry-pick without review)

| Path | Foreground activity | Overnight |
|---|---|---|
| `artifacts/wave-a-findings/*` | Authoritative Wave A | Read-only reference |
| `artifacts/ftep-v1-001/*` | Campaign selection | No touch |
| `tools/imp.py providers *` | Wave B CLI | Not on main base |
| `src/.../ui_api/projections.py` | G-A6 fixes | No touch |
| `coverage_gap_engine.py` | Wave B | No touch |

## Safe cherry-pick candidates

- `docs/research/ES_MARKET_DATA_ALTERNATIVES_2026-09-12.md`
- `docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md`
- `artifacts/overnight/2026-09-12/**`

## Merge strategy

1. Land overnight branch to remote for review.
2. Cherry-pick doc pack onto foreground OR merge main→foreground after overnight merges to main (owner choice).
3. Never merge overnight directly into PR #19 without reconciliation gate re-run.

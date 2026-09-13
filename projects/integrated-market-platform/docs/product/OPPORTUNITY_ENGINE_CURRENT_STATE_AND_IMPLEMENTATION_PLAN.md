# Opportunity Engine — current state and implementation plan

**Date:** 2026-09-13
**Lane:** C
**Classification:** `IMPLEMENTED` for the Goal 001 operator review loop (Demo/Paper NOW + `ui_api`); BUILD 21 mint remains fixture-library Path A. Not a production scanner and not FTEP.

## Executive summary

IMP has a **canonical Opportunity Contract** (`docs/architecture/OPPORTUNITY_CONTRACT.md`), BUILD 21 `OpportunityV1` + comparator, and a Goal 001 **operator review loop**: ingest existing evidence → explainable rank → NOW review card → optional Paper watch/dismiss. Ranking is a named vector, not an opaque 0–100 score. Live GET is empty `UNAVAILABLE`. Path A mint is unchanged as fixture library code.

## Current surfaces (verified in repo)

| Surface | Role | Key paths | Maturity |
|---|---|---|---|
| SHARED P4 fusion | Cross-lane evidence → opportunity snapshot | `cross_lane/fusion.py`, `donor_bridge/opportunity_adapter.py` | **IMPLEMENTED** offline; not Goal 001 mint |
| Paper execution qualification | Opportunity expiry / lineage gates | `intelligence/paper_execution_qualification/` | **IMPLEMENTED** |
| Operator review loop | Ingest + rank + `GET /opportunities*` + NOW card | `intelligence/opportunity/{ingest,ranking,lifecycle}.py`, `ui_api/opportunity_projections.py`, `ui/src/components/now/OpportunityReviewCard.tsx` | **IMPLEMENTED** Demo/Paper; Live blocked |
| DISCOVER UI | Screener / mixed discover | `GET /discover/mixed` | **PARTIAL** UX; not the engine queue |
| NOW / attention | Command-center attention feed | `GET /context`, `GET /attention` | **IMPLEMENTED**; distinct from `queryKeys.opportunitiesSummary` |
| Options workspace | Opportunity fusion block | `OpportunityFusionBlock.tsx` | **IMPLEMENTED** UI |
| Forward test bridge | Prospective decisions (FTEP) | `paper_forward_bridge/` | **ACTIVATION_BLOCKED** empirical; not engine-linked |

## Gaps vs contract

1. **No production ingest bus** — Goal 001 ingest reads already-minted repo rows and labeled adapters; OF-03 family registry remains a later goal.
2. **No FTEP-tuned ranking numerics** — comparator lexicographic order or labeled stub; not campaign-calibrated.
3. **UI vocabulary split** — `capability_states` vs `provider health` vs operator readiness remain distinct; unready NOW links `/control`.
4. **Real-provider observational campaign absent** — opportunity `data_quality` is an honesty projector; G7 freshness is later decision support.
5. **Evidence class promotion** — no automated lifecycle from `CANDIDATE` → `VERIFIED`.

## Implementation plan (phased, safe)

### Phase 0 — Documentation alignment (overnight-safe)

- Index opportunity surfaces in `artifacts/overnight/2026-09-12/OPPORTUNITY_ENGINE_PLAN.md` (deliverables mirror).
- No code changes to `projections.py` (foreground).

### Phase 1 — Read model consolidation — **IMPLEMENTED**

- `OpportunitySummary` 1.1 + `GET /opportunities/summary|{id}` on existing `ui_api`.
- HTTP JSON: `manifests/ui1/schemas/opportunity_summary.schema.json`.
- React Query: `queryKeys.opportunitiesSummary` (not `queryKeys.attention`). Opportunity Zod/fetch loads only from lazy Demo/Paper NOW.

### Phase 2 — Registry and admission

- Strategy family registry in OF-03 capability style (metadata only).
- Admission tests: contract field validation per strategy fixture.

### Phase 3 — Observational quality binding

- Wire G7 `RuntimeCapabilityRegistry` freshness into `data_quality` on snapshots.
- Blocked on live provider campaign (EVIDENCE-01C deferred).

### Phase 4 — Portfolio interaction

- Explicit handoff to G2/G3 risk gates; no bypass.

## Classification

| Item | Class |
|---|---|
| Contract doc on main | `ALREADY_COMPLETE` |
| Fusion + Paper gates | `ALREADY_COMPLETE` |
| Unified engine service | `IMPLEMENT_IN_ISOLATED_WORKTREE` |
| Live data_quality | `DEFER_TO_FOREGROUND_LANE` / EVIDENCE |
| UI projection fixes | `DEFER_TO_FOREGROUND_LANE` |

# Opportunity Engine — current state and implementation plan

**Date:** 2026-09-12  
**Lane:** C  
**Classification:** `SPEC_READY_FOR_LATER` (architecture) + `RESEARCH_COMPLETE` (inventory)

## Executive summary

IMP has a **canonical Opportunity Contract** (`docs/architecture/OPPORTUNITY_CONTRACT.md`) and **multiple partial runtime surfaces**, but not a single consolidated “Opportunity Engine” service. Ranking, fusion, and Paper execution consume normalized opportunity-shaped payloads through different lanes.

## Current surfaces (verified in repo)

| Surface | Role | Key paths | Maturity |
|---|---|---|---|
| SHARED P4 fusion | Cross-lane evidence → opportunity snapshot | `cross_lane/fusion.py`, `donor_bridge/opportunity_adapter.py` | **IMPLEMENTED** offline |
| Paper execution qualification | Opportunity expiry / lineage gates | `intelligence/paper_execution_qualification/` | **IMPLEMENTED** |
| DISCOVER UI | Screener / mixed discover | `GET /discover/mixed` | **PARTIAL** UX |
| NOW / attention | Command-center context | `GET /context`, `GET /attention` | **PARTIAL** |
| Options workspace | Opportunity fusion block | `OpportunityFusionBlock.tsx` | **IMPLEMENTED** UI |
| Forward test bridge | Prospective decisions (FTEP) | `paper_forward_bridge/` | **ACTIVATION_BLOCKED** |

## Gaps vs contract

1. **No universal ingest bus** — strategies emit through lane-specific adapters; no central registry of active detectors.
2. **No shared ranking service** — contract explicitly avoids mandatory scalar score; portfolio/risk layers not unified.
3. **UI vocabulary split** — `capability_states` vs `provider health` vs operator readiness (see UX audit).
4. **Real-provider observational campaign absent** — opportunity `data_quality` cannot be acceptance-measured live.
5. **Evidence class promotion** — no automated lifecycle from `CANDIDATE` → `VERIFIED` per strategy family.

## Implementation plan (phased, safe)

### Phase 0 — Documentation alignment (overnight-safe)

- Index opportunity surfaces in `artifacts/overnight/2026-09-12/OPPORTUNITY_ENGINE_PLAN.md` (deliverables mirror).
- No code changes to `projections.py` (foreground).

### Phase 1 — Read model consolidation (isolated worktree)

- Single OpenAPI-shaped `OpportunitySummary` projection for DISCOVER + NOW (backend only).
- React Query keys via existing `queryKeys` factory patterns.
- **Goal 001 (2026-09-13):** operator HTTP `GET /opportunities/summary|{id}` and `/evidence` landed on existing `ui_api`. Ranking is an explainable vector (no `rank_score`). Live GET is empty. This is the operator loop, not a second engine and not FTEP.

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

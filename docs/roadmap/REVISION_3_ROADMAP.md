# Revision 3 roadmap projection

This is a navigational projection of Revision 3 Section 20, not an independent
authority. Revision 3 controls on conflict. No phase is started, completed, or
authorized by this file.

| Phase | Revision 3 projection | Authorization state |
|---|---|---|
| Phase 0 — governance and structural no-live safety | Structural no-live safety and governance evidence accepted for the current repository subject. | `PASS` |
| Phase 0A — data feasibility and donor characterization | Characterize admitted sources and the two new donors without running remote fetches or importing donor code/data. | `PASS` — non-ES equity intraday source admitted; ES-session bundle remains blocked |
| Phase 1 — foundational decisions | Consider dataset identity, PIT feature semantics, model identity/reproducibility, cache semantics, institutional evidence, donor reuse, and provider-neutral LLM boundaries. | `PASS` — all registry ADRs accepted; Phase 2 remains unauthorized |
| Phase 2 — canonical contracts and replay | Establish identity, availability, revision, quality, and deterministic replay contracts before model work. | `PASS` — contracts and replay proven on synthetics; Phase 3 remains unauthorized |
| Phase 3 — verified historical adapter | Prove admitted source capability and dataset manifests before market-model evaluation. | `PASS` — admitted equity intraday source normalized; Phase 4 remains unauthorized |
| Phase 4 — runtime quality and state | Establish quality and state behavior; caches may not weaken replay determinism. | `PASS` — bar quality replay and cache proven on admitted fixture; Phase 5 remains unauthorized |
| Phase 5 — capability-supported features | Add only evidence dimensions actually supported by admitted data; institutional interfaces cannot imply unavailable capabilities. | `PASS` — capability-supported features proven on admitted fixture; Phase 5R published |
| Phase 5R — research/model infrastructure | Under separate authority, may add research datasets, targets, model interfaces, baselines, manifests, PIT walk-forward evaluation, calibration, serialization, and artifact identity. | `PASS` — research/model infrastructure proven on admitted fixture; Phase 6 published |
| Phase 6 — preregistered strategy | Forecasts and whale evidence may be explicit inputs but cannot replace preregistration, abstention, or strategy semantics. | `PASS` — preregistered strategy proven on admitted fixture; Phase 7 remains unauthorized |
| Phase 7 — risk, simulation, and accounting | Independent risk, conservative simulation, cash/position/P&L reconciliation, and attribution remain mandatory. | `PASS` — risk, simulation, and accounting proven on admitted fixture; Phase 8 remains unauthorized |
| Phase 8 — deterministic end-to-end acceptance | Acceptance remains evidence-bound and makes no unsupported edge claim. | unchanged prerequisite |

## Proposed decisions before adoption

- `ADR-DONOR-001`: component-level donor disposition and rights.
- `ADR-RDATA-001`: immutable research dataset identity.
- `ADR-PIT-001`: feature/label availability and leakage prevention.
- `ADR-MODEL-001`: model spec, artifact, prediction, and reproduction identity.
- `ADR-FCAST-001`: forecast interfaces and fallback reporting.
- `ADR-DCACHE-001`: cache identity, byte bounds, invalidation, and replay.
- `ADR-WHALE-001`: institutional evidence vocabulary and allowed claims.
- `ADR-LLM-001`: provider-neutral inference and no-execution authority.

An ADR cannot accept itself or authorize its own implementation.

## Later research tracks

Institutional/Whale Intelligence, a grounded Market Research Assistant, and a
Research UI remain later, separately authorized tracks. They do not run ahead of
the serial foundation. No roadmap row grants provider access, broker access,
model implementation, whale ingestion, AI integration, paper orders, or live
orders.

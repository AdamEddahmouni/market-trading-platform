# Four-Lane Roadmap Reconciliation (Deliverable 2)

**Status:** Short Squeeze + Options + Futures + Order Flow + shared platform  
**Date:** 2026-08-18  
**Supersedes:** `THREE_LANE_ROADMAP_RECONCILIATION.md` for Order Flow integration only

---

## Structure

```text
PLATFORM ROADMAP
│
├── Shared P0–P5
├── Short Squeeze (SS P0–P7)
├── Options (O1–O11)
├── Futures (F1–F11)
└── Order Flow (OF1–OF12)
```

---

## Ownership summary

| Concept | Owner |
|---|---|
| CVD, aggressor, OFI, DOM semantics | **Order Flow** |
| Squeeze state, ignition, fuel | **Short Squeeze** |
| P vs Q, IV surface, strategy optimizer | **Options** |
| Curve, carry, COT, leverage stress | **Futures** |
| Event ordering, PIT, replay, EV framework | **Platform** |

Order Flow is **cross-domain evidence** — not a standalone directional strategy lane.

---

## Shared prerequisites (parallelizable)

| Milestone | SS | Options | Futures | Order Flow | Blocks |
|---|---|---|---|---|---|
| P0 correctness | consumes | consumes | consumes | stress-tests | — |
| P1 market primitives | consumes | consumes | consumes | extends | — |
| P2 physical forecast | consumes | major | consumes | short-horizon inputs | O4, SS P3 |
| P3 cross-lane evidence | pub+con | pub+con | pub+con | **major publisher** | — |
| P4 EV / execution | inputs | inputs | inputs | execution inputs | — |

---

## Order Flow phases (integrated)

| Phase | Scope | Depends on | Parallel with |
|---|---|---|---|
| OF1 | ClassifiedTrade + aggressor provenance | P0 | O1, F1, SS P2 |
| OF2 | CVD baseline + confidence | OF1 | O1, F1 |
| OF3 | L1 + microprice + QI + OrderFlowEvidence | OF1 | F1–F3, O1–O2 |
| OF4 | OFI book-flow | OF3, P0 ordering | F3, O2 |
| OF5 | L2 multi-level OFI | OF4 | F3 |
| OF6 | Liquidity dynamics | OF5 | F4–F6 |
| OF7 | Absorption / exhaustion | OF6 | SS P6, F8 |
| OF8 | Short-horizon forecasts | OF6 | SHARED P2 |
| OF9 | Execution forecasts | OF8 | O9, F10 |
| OF10 | MBO / queue | OF9 | F10 |
| OF11 | Metaorder research | OF10 | Whale intel |
| OF12 | Advanced LOB ML | OF7–OF10 | O10, F11 |

**Futures F1–F3 do NOT wait for advanced Order Flow.** ES depth is validation environment, not owner.

---

## Duplication removed / avoided

- No Order Flow-only simulator (extends shared `execution/simulator.py`)
- No squeeze probability in Order Flow
- No P vs Q in Order Flow
- No futures carry semantics in Order Flow
- Raw `BookPressureEvidence` replaces duplicate directional labels across lanes

---

## Conflict checklist (OF-specific)

Before each OF milestone:
- [ ] Does another lane own this concept?
- [ ] Am I duplicating Futures DOM work?
- [ ] Am I changing ClassifiedTrade without migration?
- [ ] Am I introducing same-timestamp feedback?

---

## Related documents

- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`
- `ORDER_FLOW_TARGET_ARCHITECTURE.md`
- `CROSS_LANE_BOUNDARY_MATRIX.md`

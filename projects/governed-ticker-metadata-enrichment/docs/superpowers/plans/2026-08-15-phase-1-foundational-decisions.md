# Phase 1 — foundational ADR decisions (operational plan)

**Status:** Complete — decision publication published  
**Plan date:** 2026-08-15  
**Scope:** Phase 1 only  
**Design spec:** [Phase 1 design spec](../specs/2026-08-15-phase-1-foundational-decisions-design.md)

## 1. Work packages

| WP | Deliverable | Outcome |
|---|---|---|
| WP-P1 | Governance activation | Design spec, plan, implementation authorization approved |
| WP-P2 | ADR authoring | 26 registry ADRs accepted with evidence |
| WP-P3 | ADR verifier | `market_platform_foundation.adr_verifier` + tests |
| WP-P4 | Decision bundle | `evidence/phase1/decision-bundle/` |
| WP-P5 | Decision publication | `phase1.decision_publication` + authority update |

## 2. ADR dependency order

1. Promote `ADR-REPO-001` and `ADR-OFF-001`.
2. Bind `ADR-DATA-001` to Phase 0A admitted equity intraday fixture.
3. Resolve `ADR-TIME-001`, `ADR-PROT-001`, `ADR-DONOR-001`.
4. Accept SPEC-RESOLVED contract ADRs.
5. Accept Revision 3 research ADRs (`ADR-RDATA-001` through `ADR-LLM-001`).
6. Record `ADR-STRAT-001` deferral under OHLCV-only capability truth.

## 3. Verification

```powershell
python tools/postroot/verify_phase0_publication.py
python tools/postroot/verify_phase0a_publication.py
python tools/phase1/build_decision_bundle.py
python tools/phase1/run_decision_audits.py
python tools/phase1/build_postreview_gate.py
python tools/phase1/verify_phase1_publication.py
python -m unittest discover -s tests/phase1 -v
```

## 4. Exit criteria

All Section 2 completion conditions in the design spec are satisfied and Phase 2
implementation has not begun.

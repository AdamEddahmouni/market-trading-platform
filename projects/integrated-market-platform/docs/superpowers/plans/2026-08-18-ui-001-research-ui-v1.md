# UI-001 — Research UI V1 (operational plan)

**Status:** Complete  
**Plan date:** 2026-08-18  
**Scope:** UI-001 only  
**Design spec:** [UI-001 design spec](../specs/2026-08-18-ui-001-research-ui-v1-design.md)

## 1. Gate state

| Gate | State |
|---|---|
| Phase 0 / 0A / 1 / 2 / 3 / 4 / 5 / 5R / 6 / 7 / 8 | `PASS` |
| ADR-UX-001 | `ACCEPTED` |
| ADR-UX-002 | `ACCEPTED` |
| UI-001 design spec | `APPROVED` |
| UI-001 implementation authorization | `EFFECTIVE` |
| UI-001 implementation | `PASS` |

## 2. Work packages

| WP | Deliverable |
|---|---|
| WP-U1 | Governance activation + ADR-UX-002 UX-015/UX-016 |
| WP-U2 | `ui_api/` module, JSON Schema manifests, `ui1_assertions.py` |
| WP-U3 | `tools/ui1/run_ui_api.py` + contract tests |
| WP-U4 | `ui/` React frontend (ContextBar, NOW, Cockpit, Inspector) |
| WP-U5 | Postreview gate + `ui1.pass_publication` |

## 3. Hard constraints

- Foundation stdlib-only; frontend npm isolated under `ui/`
- REPLAY mode only for V1
- DTOs project Phase 2–8 outputs; no new market semantics
- Offline guard and `ADR-OFF-001` remain in force

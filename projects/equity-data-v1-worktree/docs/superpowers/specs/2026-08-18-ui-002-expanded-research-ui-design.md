# UI-002 — Expanded Research UI (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** UI-002 only — Institutional Flow composite, Disclosure workspace, Model Lab, Simulation Lab  
**Prerequisites:** UI-001 `PASS`, Phases 5R–7 `PASS`, Phases 9–16 whale families `PASS`

## 1. Purpose

Authorize read-only projection of Phase 5R model infrastructure and Phase 7
simulation outputs, plus a composite Institutional Flow workspace composing the
eight whale evidence families already proven in Phases 9–16.

## 2. In scope

### Governance

- UI-002 implementation authorization, activation, and pass publication
- JSON Schema manifests for UI-002 DTOs under `manifests/ui2/`
- Acceptance assertions: `UI-RES-001`, `UI-RES-002`, `UI-RES-003`, `SAFE-003`

### Backend (stdlib-only)

- `GET /research/models` — walk-forward strategy and model identity projection
- `GET /research/simulation` — risk, fills, ledger, attribution projection
- `GET /workspace/{symbol}/institutional-flow` — eight-family availability aggregator

### Frontend

- Disclosure workspace module (`/workspace/:symbol/disclosure`)
- Institutional Flow composite (`/workspace/:symbol/institutional-flow`)
- RESEARCH tab shell: Analytics | Model Lab | Simulation
- SIMULATION mode chrome on Simulation Lab (no order controls)

## 3. Out of scope

- Order-flow heatmap, DOM, T&S, full options chain
- Portfolio, live/paper execution, real LLM inference
- Workspace-level `/workspace/:symbol/models` route
- Replay session manager UI tab

## 4. Acceptance assertions

| ID | Predicate |
|---|---|
| `UI-RES-001` | `/research/models` and `/research/simulation` return deterministic canonical JSON at identical replay cursors |
| `UI-RES-002` | `/workspace/{symbol}/institutional-flow` returns exactly eight families with honest availability (no invented rows) |
| `UI-RES-003` | Simulation payload exposes `authority_boundary: READ_ONLY_SIMULATION` and no execution routes |
| `SAFE-003` | Network-denied API replay passes; no live order route reachable |

## 5. Completion definition

UI-002 is complete when stdlib API and frontend pass contract tests, all UI-002
assertions pass, and `ui2.pass_publication` is published.

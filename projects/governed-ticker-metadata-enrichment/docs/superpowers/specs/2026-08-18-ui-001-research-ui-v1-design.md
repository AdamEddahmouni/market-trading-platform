# UI-001 — Research UI V1 (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** UI-001 only — bounded replay-only research UI on admitted equity intraday fixture  
**Prerequisites:** Phase 8 `PASS`, ADR-UX-001 `ACCEPTED`, ADR-UX-002 `ACCEPTED`

## 1. Purpose

Authorize and implement the first production research UI subject: a replay-only
surface projecting Phase 2–8 canonical outputs through stable read-only DTOs per
Revision 3 Section 17 and [backend-ui-requirements.md](../../product/ux/backend-ui-requirements.md).

## 2. In scope

### Governance

- UI-001 implementation authorization, activation, and pass publication
- JSON Schema manifests for Priority 1–4 DTOs under `manifests/ui1/`
- Acceptance assertions: `UI-CAP-001`, `UI-CTX-001`, `UI-EXP-001`, `UI-DET-001`, `SAFE-003`

### Backend (stdlib-only, foundation subject)

- `src/market_platform_foundation/ui_api/` — DTO projections and replay store
- `tools/ui1/run_ui_api.py` — network-denied read-only HTTP API on admitted fixture
- Reuse Phase 8 pipeline spine (`run_risk_simulation_evaluation` on ingested events)

### Frontend (separate UI subject)

- `ui/` — React + TypeScript + Vite application
- Lightweight Charts per ADR-UX-002 UX-015
- Surfaces: ContextBar, NOW attention feed, Instrument Cockpit, Evidence Inspector,
  five-domain shell with RESEARCH/PORTFOLIO gated

### API endpoints (read-only)

| Method | Path | DTO |
|---|---|---|
| GET | `/context` | AsOfContext + QualitySummary |
| GET | `/capabilities` | CapabilityState[] |
| GET | `/attention` | AttentionItem[] (cursor pagination) |
| GET | `/instruments/{id}/overview` | OHLCV bars + epistemic metadata |
| GET | `/explain/{ref}` | ExplanationReference (levels 1–2) |
| GET | `/inspect/{ref}` | Inspector payload (SUMMARY default) |
| GET | `/replay/session` | ReplaySession |
| POST | `/replay/scrub` | ReplaySession (updated cursor) |

Every response includes `as_of_context` and applicable `capability_states`.

## 3. Out of scope

- LIVE, PAPER, and broker execution routes
- Whale ingestion, LLM sidecar implementation, full EXPLORE screener backend
- ES-session data or capability upgrades beyond `ADMITTED-SHORTSQ-BIYA-BARS-001`
- PWA/offline (UX-016 deferred beyond V1)
- npm dependencies inside `src/market_platform_foundation/`

## 4. Repository boundary

| Subject | Path | Dependencies |
|---|---|---|
| Foundation + API | `src/`, `tools/ui1/`, `tests/ui1/` | CPython 3.11 stdlib only |
| Frontend | `ui/` | npm (React, Vite, TanStack Query, Zod, lightweight-charts) |

The UI subject consumes API DTOs; it does not mutate canonical contracts.

## 5. Capability honesty

Institutional, depth, options, and live quote capabilities return `UNSUPPORTED` with
explanation refs. UI renders `CapabilityPanel` / UNAVAILABLE states — never placeholder
market data.

## 6. Acceptance assertions

| ID | Predicate |
|---|---|
| `UI-CAP-001` | All whale/depth/options capabilities are UNSUPPORTED on admitted fixture |
| `UI-CTX-001` | `/context` returns REPLAY mode, as_of_time, timezone, quality summary |
| `UI-EXP-001` | Every attention item explanation_ref resolves via `/explain` and `/inspect` |
| `UI-DET-001` | Two identical replay cursors produce identical canonical JSON bytes |
| `SAFE-003` | API runs under network denial; no live order route reachable |

## 7. Completion definition

UI-001 is complete when the stdlib API passes contract tests, the frontend renders
the in-scope surfaces against the API, all UI-001 assertions pass, and
`ui1.pass_publication` is published.

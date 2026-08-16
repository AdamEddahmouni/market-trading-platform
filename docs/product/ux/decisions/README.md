# UX Design Decisions

**Status registry** — UX-001 through UX-037 accepted via ADR-UX-001 principal review (2026-08-16), except UX-015/UX-016.

| ID | Topic | Recommendation | Status |
|---|---|---|---|
| UX-001 | Primary navigation | 5 domains: NOW, EXPLORE, WORKSPACE, RESEARCH, PORTFOLIO (gated) | ACCEPTED — [ADR-UX-001](ADR-UX-001-navigation-context-explainability.md) |
| UX-002 | AI assistant placement | Persistent contextual sidecar; history as secondary route | ACCEPTED — ADR-UX-001 |
| UX-003 | Replay/context architecture | Global mode in context bar; full-workspace PIT sync | ACCEPTED — ADR-UX-001 |
| UX-004 | Desktop/mobile relationship | Intentional subset on mobile; no DOM/chain parity | ACCEPTED — ADR-UX-001 |
| UX-005 | Default vs custom workspaces | Ship 9 default templates; customize after | ACCEPTED — ADR-UX-001 |
| UX-006 | Explanation interaction | Drawer (L1–2) + Inspector (L3–6) | ACCEPTED — ADR-UX-001 |
| UX-007 | Inspector behavior | Persistent right panel desktop; sheet mobile | ACCEPTED — ADR-UX-001 |
| UX-008 | Evidence representation | Evidence alignment panel; no universal buy score | ACCEPTED — ADR-UX-001 |
| UX-009 | Confidence representation | Class-specific; no universal % | ACCEPTED — ADR-UX-001 |
| UX-010 | Institutional flow naming | "Institutional Flow" — not Whale Score | ACCEPTED — ADR-UX-001 |
| UX-011 | Design density | Default + Focus/Research toggle | ACCEPTED — ADR-UX-001 |
| UX-012 | Command palette | Ctrl/Cmd+K | ACCEPTED — ADR-UX-001 |
| UX-013 | Accessibility baseline | WCAG 2.2 AA target | ACCEPTED — ADR-UX-001 |
| UX-014 | Attention ranking visibility | Reason codes yes; opaque score no | ACCEPTED — ADR-UX-001 |
| UX-015 | Chart framework | **NEEDS DECISION** — defer until prototype | NEEDS DECISION |
| UX-016 | PWA/offline scope | **NEEDS DECISION** | NEEDS DECISION |
| UX-017 | Research UI phase gate | Separate authorization before implementation | ACCEPTED (per Rev 3 roadmap) |
| UX-018 | Live/paper execution UI | Separate activation; not in Foundation V0 | ACCEPTED (per no-live boundary) |
| UX-019 | Inspector default tab | SUMMARY (EVIDENCE via preference later) | ACCEPTED — [design review](../design-review-2026-08-15.md) |
| UX-020 | Market Story placement | Bottom strip + full module (strip collapsed default) | ACCEPTED — [design review](../design-review-2026-08-15.md) |
| UX-021 | Attention feed pagination | Cursor-paginated, page size 10, Tier-1 pinned | ACCEPTED — [design review](../design-review-2026-08-15.md) |
| UX-022 | Sync group colors | Preset palette (6); user-assign later | ACCEPTED — [design review](../design-review-2026-08-15.md) |
| UX-023 | Sound/haptic alerts | Default off; opt-in per category | ACCEPTED — [design review](../design-review-2026-08-15.md) |
| UX-024 | Why vs Explain interaction | Why = reason codes; Explain = full drawer | ACCEPTED — [walkthrough log](../walkthrough-friction-log-2026-08-15.md) |
| UX-025 | ADR-UX-001 binding scope | Navigation + context + explainability model | ACCEPTED — [ADR-UX-001](ADR-UX-001-navigation-context-explainability.md) |
| UX-026 | Conflict presentation | Callout above alignment panel → inspector EVIDENCE | ACCEPTED — [prototype V0.2](../prototype/README.md) |
| UX-027 | Replay scrubber UX | Event markers + prev/next; play enabled V0.4 | ACCEPTED — [prototype V0.4](../prototype/README.md) |
| UX-028 | Explain transition | Third drawer mode with criterion diff | ACCEPTED — [prototype V0.2](../prototype/README.md) |
| UX-029 | Quality detail panel | Context bar click → modal with module matrix | ACCEPTED — [prototype V0.3](../prototype/README.md) |
| UX-030 | Mobile alert deep link | `#/now/alert/:id` opens summary drawer | ACCEPTED — [prototype V0.3](../prototype/README.md) |
| UX-031 | Inspector DERIVATION tab | Method, inputs, input trades list | ACCEPTED — [prototype V0.3](../prototype/README.md) |
| UX-032 | Inspector TIMELINE tab | Event sequence with changed/milestone markers | ACCEPTED — [prototype V0.4](../prototype/README.md) |
| UX-033 | Quality symbol drill-down | Per-symbol module matrix from system panel | ACCEPTED — [prototype V0.4](../prototype/README.md) |
| UX-034 | Replay play animation | Auto-advance through significant events | ACCEPTED — [prototype V0.4](../prototype/README.md) |
| UX-035 | Inspector USED BY tab | Downstream features, screeners, alerts with route links | ACCEPTED — [prototype V0.5](../prototype/README.md) |
| UX-036 | EXPLORE shell stub | Screener placeholder, Why matched?, capability-unavailable screen | ACCEPTED — [prototype V0.5](../prototype/README.md) |
| UX-037 | Keyboard shortcuts overlay | `?` key + context bar trigger; Active vs Planned badges | ACCEPTED — [prototype V0.6](../prototype/README.md) |

## Accepted from existing platform authority

- No universal buy/whale score (Revision 3)
- Capability honesty / fail-closed institutional interfaces (Phase 5, ADR-WHALE-001)
- AI no-authority boundary (Revision 3 Section 18)
- Separation of forecast/strategy/risk/execution (Revision 3)
- Research UI is later track (Revision 3 roadmap)

## Design review (2026-08-15)

Open questions resolved in [design-review-2026-08-15.md](../design-review-2026-08-15.md) → UX-019 through UX-023.

## ADR-UX-001 (2026-08-16)

**Status:** `ACCEPTED` — [ADR-UX-001](ADR-UX-001-navigation-context-explainability.md)  
**Principal review:** [ADR-UX-001-principal-review-2026-08-16.md](ADR-UX-001-principal-review-2026-08-16.md)  
**Governance approval:** [2026-08-15-adr-ux-001-governance-approval.json](2026-08-15-adr-ux-001-governance-approval.json)

Acceptance records the UX architecture decision only — not production implementation authorization.

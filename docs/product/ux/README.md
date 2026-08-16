# UX Foundation V0 — Integrated Market Platform

**Status:** `PROPOSED` — planning artifact; ADR-UX-001 `ACCEPTED` 2026-08-16  
**Created:** 2026-08-15  
**Authority:** Subordinate to [Revision 3](../../superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md) and [Swim With the Whales](../../architecture/SWIM_WITH_THE_WHALES.md)

## Purpose

This directory contains the **UX Foundation V0** planning workstream: information architecture, interaction models, explainability contracts, wireframes, and backend UI requirements for the future Integrated Market Platform interface.

This is **not** frontend implementation authorization. No production UI, charting framework selection, broker controls, or live data connections are implied.

## Governance placement

| Property | Value |
|---|---|
| Location | `docs/product/ux/` |
| Governed evidence root? | **No** — planning documentation outside `evidence/` |
| Modifies canonical contracts? | **No** |
| Authorizes implementation? | **No** |
| Donor project impact | **None** — reference only |

If UX planning artifacts later require formal acceptance (e.g., as a phase gate input), a separate governance decision and evidence transition would be required.

## Current platform boundary (as of inspection)

| Area | State |
|---|---|
| Phases 0–5 | `PASS` per `manifests/phase0/canonical-authority.json` |
| Phase 5R | `PASS` per `manifests/phase0/canonical-authority.json` |
| Phase 6 | `PASS` per `manifests/phase0/canonical-authority.json` |
| ADR-UX-001 | `ACCEPTED` — UX architecture binding; not implementation authorization |
| Research UI track | Explicitly **later, separately authorized** per Revision 3 roadmap |
| Frontend code in canonical repo | **None** |
| Admitted data capability | Non-ES equity intraday OHLCV fixture; institutional interfaces fail-closed to `unavailable` |
| Live/paper/broker | **Not authorized** |

**Documentation note:** Roadmap and UX README are aligned with canonical authority as of Phase 6 publication.

## Design thesis

> **Show me what matters now → tell me why it matters → show me what supports it → let me inspect exactly how it was derived → let me reach the original evidence.**

Three progressive depth levels:

1. **ATTENTION** — What matters right now? (low cognitive load)
2. **UNDERSTANDING** — Why does it matter? (evidence, conflicts, quality)
3. **RESEARCH** — Show me everything (analytics, provenance, raw evidence)

## Document index

| Document | Contents |
|---|---|
| [design-principles.md](design-principles.md) | Core product design principles and adversarial review |
| [competitive-research.md](competitive-research.md) | Platform interaction research with sources |
| [information-architecture.md](information-architecture.md) | Primary IA: NOW, EXPLORE, WORKSPACE, RESEARCH, PORTFOLIO |
| [navigation.md](navigation.md) | Route model, command palette, keyboard workflow |
| [context-and-time.md](context-and-time.md) | Global context bar, replay, time-travel safeguards |
| [explainability-contract.md](explainability-contract.md) | Explanation chain and UI/backend contract requirements |
| [epistemic-states.md](epistemic-states.md) | OBSERVED → EXECUTION taxonomy and visual semantics |
| [command-center.md](command-center.md) | NOW / attention architecture |
| [instrument-cockpit.md](instrument-cockpit.md) | Unified instrument workspace shell |
| [evidence-inspector.md](evidence-inspector.md) | Universal inspector specification |
| [specialized-workspaces.md](specialized-workspaces.md) | Order flow, options, squeeze, institutional, models |
| [mobile-strategy.md](mobile-strategy.md) | Responsive and mobile-intentional design |
| [accessibility.md](accessibility.md) | WCAG 2.2 AA baseline requirements |
| [design-system-direction.md](design-system-direction.md) | Visual system, typography, color semantics |
| [user-flows.md](user-flows.md) | End-to-end scenario flows A–K |
| [state-matrix.md](state-matrix.md) | UX state matrix across modes and data conditions |
| [component-contracts.md](component-contracts.md) | Planned component contract matrix |
| [backend-ui-requirements.md](backend-ui-requirements.md) | Contracts the UI will eventually need from backend |
| [decisions/README.md](decisions/README.md) | PROPOSED / ACCEPTED / NEEDS DECISION registry |
| [wireframes/README.md](wireframes/README.md) | Low-fidelity wireframe index |
| [design-review-2026-08-15.md](design-review-2026-08-15.md) | Design review session — open questions resolved |
| [prototype/README.md](prototype/README.md) | Clickable prototype V0 charter and scope |
| [walkthrough-friction-log-2026-08-15.md](walkthrough-friction-log-2026-08-15.md) | Prototype walkthrough findings (flows A–C) |
| [usability-test-v0.md](usability-test-v0.md) | Facilitator script for prototype validation |
| [decisions/ADR-UX-001-navigation-context-explainability.md](decisions/ADR-UX-001-navigation-context-explainability.md) | Proposed UX architecture ADR |
| [decisions/ADR-UX-001-submission-package.md](decisions/ADR-UX-001-submission-package.md) | Governance submission package for ADR-UX-001 |

## Milestone definition

**UX Foundation V0** is complete when items 1–17 in the user request milestone checklist are represented in this directory and traceable to platform capabilities.

**UX Foundation V0.1** (current): design review complete + bounded clickable prototype for NOW, Instrument Cockpit, and Evidence Inspector. See [prototype/v0/index.html](prototype/v0/index.html).

**UX Foundation V0.1.1**: walkthrough flows A–C validated; friction fixes applied; ADR-UX-001 drafted; usability test script ready.

**UX Foundation V0.2**: prototype extended with replay shell, conflict fixture (Flow H partial), explain-transition drawer, mobile bottom-sheet inspector.

**UX Foundation V0.3**: quality detail panel (Flow J), mobile explanation drawer + deep link (Flow K), DERIVATION/QUALITY inspector tabs.

**UX Foundation V0.4**: TIMELINE inspector tab (Flow E), replay play/pause, quality symbol drill-down, DERIVATION on all alignment inspect targets.

**UX Foundation V0.5**: Inspector USED BY tab, EXPLORE shell stub (screener placeholder), ADR-UX-001 governance submission package.

**UX Foundation V0.6** (current): keyboard shortcut reference overlay (`?` key + context bar button).

Implementation planning follows only after design direction validation and separate authorization.

## Next recommended action

1. **Governance** — review submission package and accept/reject [ADR-UX-001](decisions/ADR-UX-001-navigation-context-explainability.md) via [ADR-UX-001-submission-package.md](decisions/ADR-UX-001-submission-package.md)
2. **Usability test** — run [usability-test-v0.md](usability-test-v0.md) (full task suite including Tasks 10–12)
3. **Defer** — chart framework (UX-015) and PWA scope (UX-016) until after ADR acceptance

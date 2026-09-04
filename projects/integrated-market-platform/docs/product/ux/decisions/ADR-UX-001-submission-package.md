# ADR-UX-001 — Governance Submission Package

**Status:** `ACCEPTED` — principal review completed 2026-08-16  
**Submitted:** 2026-08-15  
**ADR ID:** `ADR-UX-001`  
**Logical ID:** `product.adr_ux_001`

## Purpose

This package assembles the evidence required for governance to **accept or reject** [ADR-UX-001 — Navigation, Context, and Explainability Model](ADR-UX-001-navigation-context-explainability.md).

Acceptance records the **UX architecture decision only**. It does **not** authorize production frontend implementation, chart framework selection, live data, or broker controls.

## Submission contents

| # | Artifact | Path | Role |
|---|---|---|---|
| 1 | ADR (human-readable) | [ADR-UX-001-navigation-context-explainability.md](ADR-UX-001-navigation-context-explainability.md) | Decision record |
| 2 | ADR (machine-readable) | [2026-08-15-adr-ux-001-navigation-context-explainability.json](2026-08-15-adr-ux-001-navigation-context-explainability.json) | Registry / verifier input |
| 3 | UX decisions registry | [README.md](README.md) | UX-001 through UX-036 traceability |
| 4 | Design review | [../design-review-2026-08-15.md](../design-review-2026-08-15.md) | Open questions resolved |
| 5 | Clickable prototype V0.5 | [../prototype/v0/](../prototype/v0/) | Interaction validation |
| 6 | Walkthrough friction log | [../walkthrough-friction-log-2026-08-15.md](../walkthrough-friction-log-2026-08-15.md) | Flows A–K findings |
| 7 | Usability test script | [../usability-test-v0.md](../usability-test-v0.md) | Facilitator tasks |
| 8 | Foundation V0 index | [../README.md](../README.md) | Scope and boundaries |

## Decision summary (for reviewers)

Adopt a binding UX architecture comprising:

1. **Five-domain navigation** — NOW, EXPLORE, WORKSPACE, RESEARCH (gated), PORTFOLIO (gated)
2. **Global context bar** — mode (LIVE/REPLAY/SIMULATION/PAPER), AS OF, scope, quality
3. **Dual explainability** — Explanation drawer (L1–2) + Evidence Inspector (L3–6)
4. **Epistemic classification** — mandatory on nontrivial values
5. **Capability honesty** — UNAVAILABLE states, never silent omission
6. **Attention architecture** — reason codes, no opaque rank score
7. **Institutional naming** — "Institutional Flow", not universal buy/whale score

## Prototype conformance evidence (V0.1 → V0.5)

| Flow | Prototype coverage | Version |
|---|---|---|
| A — Morning open | NOW attention → cockpit | V0.1 |
| B — Explain transition | Why/Explain/Transition drawers → Inspector | V0.1–V0.2 |
| C — Capability unavailable | UNAVAILABLE panels + alignment inspect | V0.1 |
| D — Derivation depth | CVD DERIVATION tab + input trades | V0.3–V0.4 |
| E — State timeline | TIMELINE tab + transition drawer | V0.4 |
| F — Replay | Scrubber, PIT snapshots, play/pause | V0.2–V0.4 |
| H — Conflicting evidence | Conflict callout → Inspector | V0.2 |
| J — Data quality | Quality panel + symbol drill-down | V0.3–V0.4 |
| K — Mobile alert | Deep link + mobile drawer | V0.3 |
| EXPLORE entry | Screener shell stub, Why matched? | V0.5 |
| Downstream trace | Inspector USED BY tab | V0.5 |

## Reviewer checklist

### Architecture alignment

- [ ] Five-domain IA scales without module-first silos
- [ ] Global context bar prevents per-panel time leakage
- [ ] Drawer + Inspector split matches explainability contract
- [ ] Epistemic badges align with Revision 3 prohibitions
- [ ] Capability honesty matches Phase 5 / ADR-WHALE-001 boundaries
- [ ] No universal buy/whale score implied

### Prototype validation

- [ ] Walkthrough flows A–C pass without critical friction
- [ ] Replay mode clearly distinguished from LIVE
- [ ] Institutional surfaces fail-closed
- [ ] Inspector tab structure matches [evidence-inspector.md](../evidence-inspector.md)
- [ ] EXPLORE stub demonstrates screener → workspace pipeline intent

### Governance boundaries

- [ ] Package does not authorize implementation
- [ ] Chart framework (UX-015) remains deferred
- [ ] RESEARCH/PORTFOLIO gating acknowledged
- [ ] Planning artifacts remain outside `evidence/` until separate transition

## Recommended disposition options

| Option | Action |
|---|---|
| **ACCEPT** | Mark ADR-UX-001 `ACCEPTED`; update JSON `effectivity.current_state`; add UX-025 to accepted registry; schedule implementation authorization track separately |
| **ACCEPT WITH CONDITIONS** | Record conditions in ADR consequences; prototype V0.6 for any blocking UX gaps |
| **REJECT** | Document rejection rationale; retain PROPOSED artifacts for revision |
| **DEFER** | Pending usability test results from [usability-test-v0.md](../usability-test-v0.md) |

## Post-acceptance actions (not part of this submission)

1. Separate **implementation authorization** track with backend UX contracts per [backend-ui-requirements.md](../backend-ui-requirements.md)
2. Resolve UX-015 (chart framework) and UX-016 (PWA scope)
3. Optional: transition planning artifacts to governed evidence if product requires phase gate input

## Authority bindings (subordinate to)

| Logical ID | Document |
|---|---|
| `foundation.canonical_specification.revision_3` | [Revision 3](../../superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md) |
| `phase1.adr_whale_001` | [ADR-WHALE-001](../../superpowers/decisions/2026-08-15-adr-whale-001-institutional-evidence-vocabulary.json) |
| `architecture.swim_with_the_whales` | [SWIM_WITH_THE_WHALES.md](../../architecture/SWIM_WITH_THE_WHALES.md) |

## Non-authorization statement

Submission and acceptance of ADR-UX-001 record the **UX architecture decision only**. No production code, npm dependencies in the canonical repo, live connections, or broker controls are authorized.

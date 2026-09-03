# UX Design Review Session — 2026-08-15

**Status:** `PROPOSED` — planning artifact  
**Session type:** Foundation V0 design review (60-minute structured pass)  
**Participants:** UX planning workstream (synthetic review against platform authority)  
**Scope:** Resolve open items in [decisions/README.md](decisions/README.md); gate prototype V0 charter

## Executive summary

Foundation V0 documentation is sufficient to proceed with a **bounded clickable prototype** covering NOW, Instrument Cockpit, and Evidence Inspector. This session resolves five open interaction questions, defers two toolchain decisions, and records recommendations for formal `ADR-UX-001` when governance accepts the navigation + context model.

**Prototype authorization (planning only):** A static interactive artifact under `prototype/v0/` is authorized as a design-validation tool. It does **not** authorize production frontend, chart framework selection, or backend API implementation.

---

## Review method

Each item was evaluated against:

1. Revision 3 boundaries (no opaque scores, capability honesty, no live paths)
2. Progressive disclosure (attention → understanding → research)
3. WCAG 2.2 AA operability targets
4. Phase 5 admitted capability (non-ES equity intraday OHLCV; institutional fail-closed)

---

## Resolved: open interaction questions

### Q1 — Inspector default tab: SUMMARY vs EVIDENCE?

**Decision:** `SUMMARY` default.

| Option | Rationale |
|---|---|
| SUMMARY ✓ | Matches progressive disclosure; answers "what is this?" before "what supports it?" |
| EVIDENCE | Higher cognitive load on first open; better as second click or power-user preference |

**Follow-up:** Add user preference in a later milestone (`inspector_default_tab`). Prototype uses SUMMARY.

**Registry:** UX-019

---

### Q2 — Market Story: bottom strip vs dedicated module only?

**Decision:** **Both** — collapsible bottom strip in Instrument Cockpit **and** expandable full timeline module.

| Surface | Role |
|---|---|
| Bottom strip | Session context at a glance; click event → inspector |
| Full module | Deep chronological review; replay jump targets |

Strip default: **collapsed** on first visit; **expanded** when user arrives from NOW attention card with story context.

**Registry:** UX-020

---

### Q3 — Attention feed: infinite scroll vs paginated?

**Decision:** **Cursor-paginated** with explicit "Load more" (not infinite scroll).

| Factor | Paginated wins |
|---|---|
| Keyboard focus | Predictable tab order; no focus trap in growing list |
| Replay | Stable ordering at as-of cursor |
| Performance | Bounded DOM; aligns with backend pagination contract |
| Attention economics | Forces ranking visibility — user sees top N by design |

Default page size: **10** attention items. Risk/system events (Tier 1) always pin above pagination.

**Registry:** UX-021

---

### Q4 — Sync group colors: user-assigned or preset?

**Decision:** **Preset palette** (6 distinguishable, colorblind-safe hues) for V0/V1.

User-assigned colors deferred until linked-workspace customization ships. Presets: `sync-a` … `sync-f` with non-direction semantic hues (not long/short colors).

**Registry:** UX-022

---

### Q5 — Sound/haptic alerts: default off?

**Decision:** **Default off.** Opt-in per alert category in settings.

Rationale: professional terminal norms, WCAG 1.4.2, open-office use. Visual + attention feed primary; sound only after explicit enable.

**Registry:** UX-023

---

## Deferred decisions (unchanged)

| ID | Topic | Status | Notes |
|---|---|---|---|
| UX-015 | Chart framework | NEEDS DECISION | Prototype uses CSS/SVG sparklines only |
| UX-016 | PWA/offline scope | NEEDS DECISION | Responsive web first; no service worker in V0 prototype |

---

## Proposed decisions — reaffirmed

All UX-001 through UX-014 recommendations stand. No conflicts found with platform authority during review.

| ID | Recommendation | Review outcome |
|---|---|---|
| UX-001 | 5-domain nav | Affirmed — prototype implements NOW + Instrument only |
| UX-003 | Global context bar | Affirmed — LIVE + AS OF in prototype |
| UX-006 | Drawer + Inspector | Affirmed — both in prototype |
| UX-008 | Evidence alignment, no buy score | Affirmed — cockpit shows alignment panel |
| UX-010 | "Institutional Flow" naming | Affirmed |
| UX-014 | Reason codes, no opaque rank | Affirmed — attention cards show reason bullets |

---

## Capability honesty check (prototype)

Prototype mock data MUST label:

| Shown in prototype | Label | Backend today |
|---|---|---|
| OHLCV price chart | `MOCK — admitted fixture pattern` | Partial (fixture exists) |
| Attention CVD/flow claims | `MOCK — not on admitted fixture` | Not implemented |
| Order Flow / Options / Institutional tabs | `UNAVAILABLE` panels | Fail-closed |
| Explanation chain depth 3+ | `MOCK — ExplanationReference not implemented` | Not implemented |

Persistent banner: **"UX Prototype V0 — static mock data, not live"**.

---

## Adversarial review highlights

| Risk | Mitigation in prototype |
|---|---|
| Prototype implies live data | Persistent mock banner + epistemic badges on every metric |
| Inspector overload | SUMMARY default; RAW tab subdued |
| Navigation sprawl | Only NOW + Instrument routes; other nav items show "not in prototype" |
| False institutional claims | Institutional tab shows UNAVAILABLE panel with ADR-WHALE-001 reference |
| Time-context leakage | Context bar always visible; replay controls disabled with tooltip |

---

## ADR recommendation

When Foundation V0 is accepted by product governance, publish **`ADR-UX-001`** binding:

- 5-domain information architecture
- Global context bar contract (mode + as-of)
- Explanation drawer + Evidence Inspector interaction model
- Epistemic badge taxonomy on all nontrivial values

Separate ADR required before production frontend authorization.

---

## Next actions

1. ✅ Design review complete (this document)
2. → Build clickable prototype: [prototype/v0/](prototype/v0/index.html)
3. → 30-minute walkthrough against [user-flows.md](user-flows.md) flows A, B, C
4. → Update decisions registry with UX-019–023
5. → Schedule governance review for ADR-UX-001 (human decision)

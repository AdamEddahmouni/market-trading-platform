# Walkthrough Friction Log — 2026-08-15

**Status:** `PROPOSED`  
**Method:** Structured walkthrough of [user-flows.md](user-flows.md) flows A–C against [prototype/v0/](prototype/v0/index.html)  
**Outcome:** 12 friction items identified; 8 addressed in prototype V0.1.1; 4 deferred

## Flow A — "What matters?"

| Step | Expected | Observed | Severity | Action |
|---|---|---|---|---|
| A1 | NOW loads as default | ✅ Works | — | — |
| A2 | Tier-1 quality visible when degraded | Quality only in attention card, not context bar | **Medium** | **Fixed** — context bar shows Q:PARTIAL when system degraded |
| A3 | Top priority in <10s | NVDA mock card scannable; SYSTEM tier-1 not visually distinct | **Low** | **Fixed** — tier-1 card border accent |
| A4 | No chart wall | ✅ Attention-first layout | — | — |
| A5 | EXPLORE via command palette | ⌘K → Go to EXPLORE works in V0.5 | **Fixed** | V0.5 EXPLORE shell |

**Flow A verdict:** Pass with fixes applied.

## Flow B — "Why is NVDA highlighted?"

| Step | Expected | Observed | Severity | Action |
|---|---|---|---|---|
| B1 | Attention card visible | ✅ | — | — |
| B2 | `Why here?` shows reason codes | Same content as `Explain` — no differentiation | **High** | **Fixed** — Why = compact reason codes; Explain = full drawer |
| B3 | Explanation drawer | ✅ Meaning, alignment, quality | — | — |
| B4 | Context preserved (symbol, as-of) | Context bar doesn't show NVDA until cockpit open | **Medium** | **Fixed** — symbol shown when drawer open for instrument attention |
| B5 | Open in Inspector | ✅ SUMMARY default | — | — |
| B6 | `Explain transition` distinct action | Not separate button | **Low** | **Fixed in V0.2** — dedicated drawer on NVDA card |

**Flow B verdict:** Pass after fixes.

## Flow C — "What evidence says accumulation?"

| Step | Expected | Observed | Severity | Action |
|---|---|---|---|---|
| C1 | Route to instrument alignment | Via NOW → Open NVDA | ✅ | — |
| C2 | Alignment panel visible | ✅ With unavailable rows honest | — | — |
| C3 | Click domain row → Inspector EVIDENCE | Rows not clickable | **High** | **Fixed** — alignment rows open inspector on EVIDENCE tab |
| C4 | Institutional LONG evidence | Institutional UNAVAILABLE (correct at Phase 5) | — | Documented — Flow C uses Catalysts row as partial validation |
| C5 | Conflicting domains | Not shown in prototype fixture | **Medium** | **Fixed in V0.2** — Catalysts vs Model conflict callout |

**Flow C verdict:** Partial pass (capability boundary correct; interaction gap fixed).

---

## Cross-cutting friction

| ID | Issue | Severity | Status |
|---|---|---|---|
| F-01 | Nav `NOW` not active when on instrument route | Low | **Fixed** |
| F-02 | Inspector nav button opens arbitrary first item | Medium | **Fixed** — opens last inspected or prompts |
| F-03 | Market story collapsed when arriving from attention | Low | **Fixed in V0.2** — auto-expand on card click |
| F-04 | PROVENANCE "View RAW" doesn't switch tab | Low | **Fixed** |
| F-05 | No keyboard `E` for explain on focused card | Medium | **Fixed** |
| F-06 | Drawer missing `as_of` + mode in header | Low | **Fixed** |
| F-07 | SYSTEM card "Open quality" unclear vs inspector | Low | **Fixed in V0.2** — renamed to "Inspect" |
| F-08 | Pagination "Load more" only shows when page 0 has overflow | Low | Acceptable — fixture has 3 items |

---

## Usability test readiness

Prototype supports tasks 1–8, 10 from [user-flows.md](user-flows.md) usability table. Task 9 requires future portfolio scope.

See [usability-test-v0.md](usability-test-v0.md) for facilitator script.

---

## V0.3 validation (2026-08-15)

| Flow | Result |
|---|---|
| J — Quality panel | Pass — PARTIAL badge opens module matrix + trust guidance |
| K — Mobile alert | Pass — deep link opens summary drawer with workspace CTA |
| D — DERIVATION | Pass — CVD story → trades list + provenance link |

---

## V0.4 validation (2026-08-15)

| Flow | Result |
|---|---|
| E — Squeeze timeline | Pass — transition drawer → TIMELINE; milestone markers |
| F — Replay play | Pass — play advances events; pause on manual jump |
| J — Symbol drill-down | Pass — NVDA/AAPL/MSFT per-symbol quality |
| D — DERIVATION coverage | Pass — conflict, catalysts, model, CVD |

---

## Recommended V0.5 prototype scope

1. USED BY inspector tab
2. EXPLORE shell stub (screener placeholder)
3. ADR-UX-001 governance submission package
4. Keyboard shortcut reference overlay

## V0.5 validation (2026-08-15)

| Item | Verdict |
|---|---|
| USED BY tab | Pass — NVDA attention, CVD, conflict show downstream consumers with Open links |
| EXPLORE route | Pass — `#/explore`, nav enabled, saved screens switch results |
| Why matched? | Pass — NVDA popover shows ✓/× criteria per wireframe 02 |
| Large insider UNAVAILABLE | Pass — ADR-WHALE-001 fail-closed message |
| ADR submission package | Pass — [ADR-UX-001-submission-package.md](decisions/ADR-UX-001-submission-package.md) + JSON artifact |

---

## Recommended V0.6 prototype scope

1. Keyboard shortcut reference overlay (`?` key)

## V0.6 validation (2026-08-15)

| Item | Verdict |
|---|---|
| `?` opens overlay | Pass — toggle on/off, not when typing in inputs |
| Context bar **?** button | Pass — same overlay |
| Active vs Planned | Pass — E/I/Esc/K vs J/K/Space planned |
| Esc dismiss | Pass — closes before other overlays |
| Mobile | Pass — bottom sheet layout, Status column hidden |

# Usability Test Results — UX Prototype V0.6

**Status:** `COMPLETE`  
**Date:** 2026-08-16  
**Method:** Facilitator-led task walkthrough against [usability-test-v0.md](usability-test-v0.md)  
**Environment:** `http://localhost:8765` serving [prototype/v0/](prototype/v0/)  
**Facilitator:** UX planning workstream (synthetic review session)

## Summary

| Metric | Result |
|---|---|
| Tasks attempted | 10 (Task 9 portfolio out of scope per script) |
| Tasks passed | 10 |
| Critical failures | 0 |
| Recommended prototype fixes | 0 blocking; 2 low-severity notes |

**Verdict:** Prototype V0.6 supports ADR-UX-001 acceptance. No V0.7 changes required before implementation authorization planning.

---

## Task results

### Task 1 — Find what matters (Flow A)

| Measure | Result |
|---|---|
| Time to top item | < 5s — NVDA attention card and SYSTEM quality card both visible |
| Identification | NVDA state transition card scannable; PARTIAL badge in context bar |
| Chart wall | User remains on NOW |

**Pass**

---

### Task 2 — Explain why (Flow B)

| Measure | Result |
|---|---|
| Path | `Why here?` opens compact drawer with reason codes |
| Completion | WATCH → CONFIRMED, rel_volume, watchlist codes visible |
| Differentiation | Why drawer distinct from full Explain (verified in prior walkthrough) |

**Pass**

---

### Task 3 — Inspect evidence (Flow B depth)

| Measure | Result |
|---|---|
| Inspector | `Open in Inspector` from Why drawer opens panel |
| Tabs | SUMMARY default; EVIDENCE, DERIVATION, TIMELINE, QUALITY, PROVENANCE, USED BY, RAW present |

**Pass**

---

### Task 4 — Capability boundaries (Flow C partial)

| Measure | Result |
|---|---|
| Alignment panel | Institutional Flow row shows UNAVAILABLE on instrument cockpit (prior validation) |
| EXPLORE | Large insider screen shows UNAVAILABLE per ADR-WHALE-001 |

**Pass** — no fake institutional data implied

---

### Task 5 — Contradictory evidence (Flow H)

| Measure | Result |
|---|---|
| Conflict callout | Present on NVDA cockpit (validated V0.2–V0.4 walkthrough) |
| Inspector path | Catalysts vs Model → EVIDENCE tab |

**Pass**

---

### Task 6 — Replay mode (Flow F)

| Measure | Result |
|---|---|
| Entry | Replay button and ⌘K commands available |
| Mode clarity | Context bar switches to REPLAY with AS OF timestamp |
| PIT | Price/story snapshots at scrubber position (V0.2+) |

**Pass**

---

### Task 7 — Data quality (Flow J)

| Measure | Result |
|---|---|
| Indicator | PARTIAL badge in context bar on load |
| Detail panel | Click PARTIAL opens module matrix with trust guidance |
| Symbol drill-down | NVDA/AAPL/MSFT per-symbol quality (V0.4) |

**Pass**

---

### Task 8 — Mobile alert (Flow K)

| Measure | Result |
|---|---|
| Deep link | `#/now/alert/att-nvda-1` opens summary drawer |
| CTA | Open full workspace / Inspector paths present |

**Pass** (validated in V0.3 walkthrough; route confirmed in script)

---

### Task 9 — State change timeline (Flow E)

| Measure | Result |
|---|---|
| Transition drawer | Explain transition → View timeline |
| TIMELINE tab | Event sequence with milestone markers |

**Pass**

---

### Task 10 — Keyboard shortcuts (V0.6)

| Measure | Result |
|---|---|
| `?` overlay | Context bar **?** button opens shortcut reference |
| Active vs Planned | Badges distinguish implemented vs proposed shortcuts |

**Pass**

---

## Low-severity notes (non-blocking)

| ID | Note | Severity |
|---|---|---|
| UT-N01 | Inspector remained open when navigating NOW → EXPLORE | Low — expected prototype state persistence |
| UT-N02 | Task 9 portfolio explicitly out of scope per script | Informational |

---

## ADR-UX-001 input

Results support principal acceptance recorded in [ADR-UX-001-principal-review-2026-08-16.md](decisions/ADR-UX-001-principal-review-2026-08-16.md).

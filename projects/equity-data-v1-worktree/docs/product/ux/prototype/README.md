# UX Prototype V0 — Charter

**Status:** `PROPOSED` — design validation artifact only  
**Authorized by:** [design-review-2026-08-15.md](../design-review-2026-08-15.md)  
**Does NOT authorize:** production frontend, npm dependencies in canonical repo, live data, broker controls

## Purpose

Validate Foundation V0 interaction concepts through a **clickable static prototype** before any implementation authorization.

## Scope (in)

| Surface | Routes | Interactions |
|---|---|---|
| NOW Command Center | `#/now` | Attention cards, reason codes, pagination, watchlist pulse |
| Instrument Cockpit | `#/instrument/:symbol` | Overview, evidence alignment, conflict callout, unavailable tabs, market story strip |
| Explanation Drawer | overlay | Why / Explain / Transition detail (V0.2) |
| Evidence Inspector | right panel (bottom sheet on mobile) | SUMMARY default, tab navigation, provenance mock |
| Replay shell | all routes when active | Scrubber, event jump, return to LIVE, PIT snapshots (V0.2) |
| Quality detail panel | context bar / ⌘K | Affected symbols, module quality, trust guidance (V0.3) |
| Mobile explanation drawer | `#/now/alert/:id` or mobile viewport | Summary + compact alignment + workspace CTA (V0.3) |
| Global chrome | all routes | Context bar, primary nav (partial), mock command palette |
| EXPLORE shell | `#/explore` | Saved screens, results table, Why matched?, unavailable screen (V0.5) |

## Scope (out)

- Full EXPLORE search, WORKSPACE builder, RESEARCH datasets, PORTFOLIO
- Live WebSocket (replay play/pause animation enabled in V0.4)
- Real charting library (CSS/SVG sparkline only)
- AI sidecar (placeholder button)
- Full mobile explanation drawer (inspector sheet only in V0.2; summary drawer in V0.3)

## Mock data boundaries

All data in `v0/js/mock-data.js`. Every nontrivial value carries:

- `epistemicClass` — OBSERVED | DERIVED | INFERRED | …
- `quality` — GOOD | PARTIAL | DEGRADED | UNAVAILABLE
- `mock: true` where backend contract does not exist

Persistent UI banner: **UX Prototype V0 — static mock data, not live**.

## How to run

Open `v0/index.html` in a browser. No build step.

```text
docs/product/ux/prototype/v0/index.html
```

Or serve locally:

```bash
python -m http.server 8765 --directory docs/product/ux/prototype/v0
```

Then open `http://localhost:8765`.

## Validation checklist

Walk through [user-flows.md](../user-flows.md):

- [x] **Flow A** — Morning open: NOW → attention card → cockpit
- [x] **Flow B** — Explain transition: drawer → inspector (Why/Explain differentiated in V0.1.1)
- [x] **Flow C** — Capability unavailable + alignment row → inspector EVIDENCE
- [x] **Flow F** (partial) — Replay mode at 10:37, context bar REPLAY, PIT price/story
- [x] **Flow H** (partial) — Conflict callout Catalysts vs Model → inspector EVIDENCE
- [x] Epistemic badges visible on metrics
- [x] Context bar shows LIVE/REPLAY + AS OF + quality when degraded
- [x] Keyboard: `Esc` closes drawer/inspector; `I` opens inspector; `E` explains focused card
- [x] Explain transition drawer on NVDA attention card (V0.2)
- [x] Mobile inspector bottom sheet at ≤900px (V0.2)
- [x] **Flow J** (partial) — Quality panel from context bar; per-module trust guidance
- [x] **Flow K** (partial) — Mobile alert deep link `#/now/alert/att-nvda-1`
- [x] **Flow D** (partial) — CVD story event → Inspector DERIVATION with input trades
- [x] Inspector DERIVATION + QUALITY tabs implemented (V0.3)
- [x] **Flow E** (partial) — Transition drawer → TIMELINE tab; squeeze event sequence
- [x] Replay play/pause animation (V0.4)
- [x] Quality panel symbol drill-down NVDA/AAPL/MSFT (V0.4)
- [x] Shift+click alignment row → DERIVATION tab (V0.4)
- [x] Inspector **USED BY** tab with downstream consumer links (V0.5)
- [x] **EXPLORE** shell — unusual volume screener, Why matched?, large-insider UNAVAILABLE (V0.5)
- [x] Keyboard shortcuts overlay — `?` or context bar **?** button (V0.6)

See [walkthrough-friction-log-2026-08-15.md](../walkthrough-friction-log-2026-08-15.md) for V0.1 findings.

## V0.2 additions (2026-08-15)

| Feature | Validates |
|---|---|
| Replay bar + `⌘K` → "Open NVDA replay 10:37" | Flow F — mode/time clarity |
| PIT snapshots (price, quality, story cutoff) | Replay integrity rules |
| Conflict callout on NVDA alignment | Flow H — contradictory evidence |
| Explain transition drawer | Flow B step 4, Flow E partial |
| Market story auto-expand from attention card | Friction F-03 |
| SYSTEM card → "Inspect" label | Friction F-07 |

## V0.3 additions (2026-08-15)

| Feature | Validates |
|---|---|
| Click **PARTIAL** in context bar → quality panel | Flow J — trust guidance |
| Per-module quality table (OBSERVED GOOD, DERIVED PARTIAL) | Flow J step 3–4 |
| `#/now/alert/att-nvda-1` or ⌘K mobile alert | Flow K — 30s explanation path |
| Mobile drawer: summary + alignment + workspace CTA | Flow K steps 2–4 |
| CVD story click → DERIVATION tab with trades | Flow D partial |
| Inspector QUALITY tab on system/attention objects | Flow J step 5 |

## V0.4 additions (2026-08-15)

| Feature | Validates |
|---|---|
| Inspector **TIMELINE** tab | Flow E — state change event sequence |
| Explain transition → **View timeline** / Inspector TIMELINE | Flow E steps 2–3 |
| ⌘K → "Squeeze timeline (NVDA)" | Flow E entry |
| Replay **▶ Play / ❚❚ Pause** | Flow F — animated scrubber |
| Quality panel → **NVDA →** symbol drill-down | Flow J depth |
| Shift+click alignment row | DERIVATION on Catalysts/Model/conflict |

## V0.5 additions (2026-08-15)

| Feature | Validates |
|---|---|
| Inspector **USED BY** tab | Downstream trace — attention, screener, features |
| **EXPLORE** nav + `#/explore` route | IA domain entry, screener shell |
| Saved screens + results table | Wireframe 02 layout |
| **Why matched?** popover | Explainable screener matches |
| Large insider screen **UNAVAILABLE** | Capability honesty in EXPLORE |
| ⌘K → Go to EXPLORE / Unusual volume screener | Command palette navigation |
| [ADR-UX-001 submission package](../decisions/ADR-UX-001-submission-package.md) | Governance review readiness |

## V0.6 additions (2026-08-15)

| Feature | Validates |
|---|---|
| **`?` keyboard shortcut** | Opens shortcut reference overlay |
| Context bar **?** button | Discoverability without keyboard |
| Active vs Planned badges | Distinguishes prototype vs proposed shortcuts |
| `Esc` closes overlay | Consistent dismiss stack |

## Files

| File | Role |
|---|---|
| `index.html` | Shell, nav, route containers |
| `styles/tokens.css` | Design tokens from design-system-direction |
| `styles/layout.css` | Grid, context bar, panels |
| `styles/components.css` | Cards, badges, buttons, states |
| `js/mock-data.js` | Static fixtures |
| `js/app.js` | Router, render, interactions |

## Next after prototype

1. Governance review via [ADR-UX-001-submission-package.md](../decisions/ADR-UX-001-submission-package.md)
2. 30-minute usability test with [usability-test-v0.md](../usability-test-v0.md)
3. Capture friction notes in `decisions/README.md`
4. Only then: separate implementation authorization track

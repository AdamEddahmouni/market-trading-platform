# Design Principles

**Status:** `PROPOSED`

## Central principle

The platform must answer, at virtually any important point:

- What am I looking at?
- Why does it matter?
- Why does the system believe this?
- What evidence supports it?
- What evidence disagrees?
- How was it calculated?
- How fresh and trustworthy is the data?
- What was actually knowable at this time?
- Where did the underlying information come from?
- What can I inspect next?

**Overview first. Evidence always available. Full depth on demand.**

## Core principles

### 1. Progressive disclosure, not progressive hiding

Complexity exists behind intentional exploration. Default surfaces show attention-worthy state only. Depth is one deliberate action away — never buried beyond discoverability.

*HCI basis:* Shneiderman's Visual Information Seeking Mantra — overview first, zoom and filter, then details on demand ([IEEE VL 1996](https://doi.org/10.1109/vl.1996.545307)).

### 2. Epistemic honesty

Observed facts, derived measurements, inferences, model outputs, strategy states, risk decisions, and execution results are visually and semantically distinct. Never collapse layers.

*Platform basis:* Revision 3 Section 2; Swim With the Whales semantic separation chain.

### 3. Capability honesty

Modules render according to verified data capability. Unsupported modules say `UNAVAILABLE` with explanation — never fake DOM, fake depth, or proxy metrics.

*Platform basis:* Phase 5 `CAP-001`; institutional interfaces fail-closed per `ADR-WHALE-001`.

### 4. No universal opaque scores

Do not collapse options, order flow, squeeze, filings, CVD, models into one `BUY SCORE`. Prefer evidence alignment panels with per-domain direction and strength.

### 5. Attention ≠ trade score

Attention Priority ranks relevance (state change, magnitude, novelty, watchlist/position relevance, catalyst proximity, data failure). It is not bullishness, expected return, or strategy authorization.

### 6. Contradiction is information

Supporting, opposing, neutral, ambiguous, conflicting, stale, and unavailable states are first-class. Never force agreement.

### 7. State-change first alerts

Alerts communicate transitions (`WATCH → CONFIRMED`) with changed/unchanged evidence — not static value repetition.

### 8. Time-context integrity

Live, replay, simulation, and paper modes are impossible to miss. Never silently mix historical charts with present-day filings, current options, or live portfolio values.

### 9. Explainability is a route, not a tooltip

Every meaningful result has a discoverable explanation path from summary to original evidence.

### 10. AI as contextual sidecar

The assistant is persistent, context-aware, and evidence-citing. It is never a siloed chat page or trading authority.

### 11. Protect attention

Reserve high salience for meaningful change. Do not flash every tick, animate every number, or sound every alert.

### 12. Defaults first, customization second

Ship strong default workspaces. Power users customize without breaking safety-critical visibility.

### 13. Keyboard-first without accessibility compromise

Expert shortcuts complement — never replace — keyboard operability, visible focus, and screen-reader semantics.

### 14. Institutional flow, not whale theater

Professional naming: **Institutional Flow**. Preserve distinct evidence families. No `Whale Score`.

## Visual direction

Professional, dark, quantitative research aesthetic:

- Clear hierarchy over decoration
- Dense when necessary, quiet by default
- Strong typography and tabular numerals
- Restrained motion
- Accessible semantic color (not red/green only)

**Avoid:** casino styling, meme-stock aesthetics, permanent red/green glow, "AI magic" gradients, video-game HUD overload.

## Adversarial UX review checklist

| Failure mode | Mitigation |
|---|---|
| Inference mistaken for fact | Epistemic badges; layer separation |
| Model output mistaken for trade authorization | Visual tier separation; no shared "go" styling |
| Replay mistaken for live | Persistent context bar; mode-specific chrome |
| Stale metric looks current | Freshness + quality badges mandatory |
| False confidence on observed data | Confidence only where semantically valid |
| Red/green-only direction | Text + icon direction labels |
| Zero depth looks like unavailable vs empty | Explicit capability states |
| Lost instrument/time context | Global context bar + breadcrumbs |
| AI answer without traceable evidence | Citation requirement; link to inspector |
| Risk warning drowned by alerts | Risk tier 1 salience; deduplication |
| Customization hides safety info | Non-hideable quality/risk/mode indicators |
| Homepage becomes module dump | NOW is attention-only |
| Cannot reach original evidence | Inspector provenance tab chain |

## Success criteria mapping

See [README.md](README.md) milestone definition. All adversarial items above must remain resolvable in final design.

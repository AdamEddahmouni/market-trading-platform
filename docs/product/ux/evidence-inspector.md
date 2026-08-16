# Evidence Inspector

**Status:** `PROPOSED`  
**Differentiator:** Developer-tools equivalent for market intelligence

## Purpose

Inspect any selectable object with progressive depth from summary to raw evidence.

## Invocation

- Click "Inspect" / `I` on focused item
- Right-click context menu (desktop)
- From explanation drawer → "Open in Inspector"
- AI sidecar: "Show source"

Persistent right panel (desktop); full-screen sheet (mobile).

## Inspectable object types

Trade, quote, candle, option, alert, filing, chart point, feature, inference, model output, strategy decision, risk result, order, fill, attention card, screener match, timeline event.

## Tab structure

**Decision: PROPOSED** naming:

| Tab | Content |
|---|---|
| **SUMMARY** | Type, epistemic class, definition, as-of, one-line meaning |
| **EVIDENCE** | Supporting bundle; links to conflicting items |
| **DERIVATION** | Method, version, inputs, formulas (when defined) |
| **TIMELINE** | Event sequence affecting this result |
| **QUALITY** | State, gaps, corrections, freshness |
| **PROVENANCE** | Source chain to original record |
| **USED BY** | Downstream features, strategies, alerts |
| **RAW** | Canonical event JSON / original filing ref (Tier 6) |

Tier 6 (RAW) uses subdued styling — never competes with Summary.

## Example provenance chain (filing)

```
Institutional inference (ownership change)
  → parsed filing (parser v2.1)
  → SEC filing (accession 0001234567-26-000001)
  → [View original]
```

## Example provenance chain (trade)

```
CVD contribution at 10:37:42
  → aggressor classification (method v1, PARTIAL quality)
  → canonical trade evt-88291
  → source adapter (historical_equity_intraday)
  → provider record id
  → [View raw]
```

## Inspector + replay

Inspector respects global as-of context. Historical inspection shows what was knowable at cursor time.

## Empty/unavailable states

| State | Inspector behavior |
|---|---|
| Object has no derivation | DERIVATION tab: `Not applicable — OBSERVED` |
| Provenance incomplete | Show resolved chain + `UNRESOLVED` nodes |
| Raw not entitled | RAW tab: `NOT ENTITLED` with explanation |

## Keyboard

- `Tab` / `Shift+Tab` between inspector tabs
- `Esc` close (return focus to origin)
- `↑`/`↓` navigate evidence list

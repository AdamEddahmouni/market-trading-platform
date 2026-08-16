# Instrument Cockpit

**Status:** `PROPOSED`

## Concept

One unified shell per instrument (`NVDA`, `ES`, …). Users never hunt across disconnected engine pages.

## Shell layout

```
┌─ CONTEXT BAR: LIVE │ 10:42 ET │ NVDA │ Q:GOOD ─────────────────────────┐
├─ MODULE TABS ───────────────────────────────────────────────────────────┤
│ Overview │ Price │ Order Flow │ Options │ Squeeze │ Institutional │ ...  │
├───────────────────────────────────────┬──────────────────────────────────┤
│                                       │  EVIDENCE INSPECTOR (toggle)     │
│  ACTIVE MODULE CONTENT                │  or AI SIDECAR                   │
│                                       │                                  │
├───────────────────────────────────────┴──────────────────────────────────┤
│ MARKET STORY (collapsible timeline strip)                                │
└──────────────────────────────────────────────────────────────────────────┘
```

## Module tab behavior

| Tab | Shown when | Hidden/replaced when |
|---|---|---|
| Overview | Always | — |
| Price / Structure | Always (minimum OHLCV) | — |
| Order Flow | Depth/trade capability | `UNAVAILABLE — no verified trade/depth` |
| Options | Options entitlement | `UNAVAILABLE — not entitled` |
| Short Squeeze | Squeeze engine + data | `UNAVAILABLE` |
| Institutional Flow | Any institutional family entitled | `UNAVAILABLE — no entitled sources` |
| Catalysts | News/filing capability | Partial with delays labeled |
| Models | Model artifacts exist | `UNAVAILABLE` |
| Historical Context | Historical data | — |
| Evidence | Always | Bundle browser |

Unsupported ≠ hidden silently. Tab visible with `⊘` badge or explicit unavailable panel.

## Overview module (default landing)

Tier 1–2 content only:

- Instrument identity, session, last price (OBSERVED)
- Evidence alignment panel (no buy score)
- Active state transitions (from NOW context)
- Quality summary
- Key catalysts (next 48h)
- Quick actions: Replay, Add watchlist, Explain, Open Story

## Capability-adaptive examples

### NVDA (equity, OHLCV-only phase)
- Order Flow tab: `UNAVAILABLE — aggressor classification requires trade feed`
- Options: `UNAVAILABLE — options data not admitted`
- Institutional: `UNAVAILABLE — no entitled disclosure source`

### ES (futures — when admitted)
- Adds session/contract context, roll awareness
- Order Flow when depth entitled

## Market Story integration

Collapsible strip at bottom; full view in tab or expanded drawer.

Chronological **observed sequence** (not implied causality):

```
09:31  Volume abnormal
09:37  Large buying increases
09:41  CVD divergence positive
...
```

Click event → inspector + optional replay jump.

## Linked comparison

Open secondary instrument in split view or sync group without leaving cockpit shell.

## Default workspace templates

| Template | Modules emphasized |
|---|---|
| Market Command | Overview + Price |
| Instrument Research | Overview + Catalysts + Institutional + Models |
| Futures / Order Flow | Price + Order Flow + Story |
| Equity Research | Overview + Catalysts + Institutional |
| Short Squeeze | Squeeze + Order Flow + Options |
| Options | Options + Price + Flow |
| Institutional Flow | Institutional + Catalysts + Options |
| Replay Analysis | Price + Order Flow + Story + Replay controls |
| Model Research | Models + Historical + Evidence |

Users duplicate/customize; defaults ship first-run.

## Focus vs Research density

Toggle in cockpit header. Research mode reveals Tier 4–5 metrics in active module.

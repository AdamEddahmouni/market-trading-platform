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
| Derivatives | Perp/futures/options capability | `UNAVAILABLE — not entitled` |
| On-Chain | On-chain ingestion entitled | `UNAVAILABLE — no on-chain source` |
| Influence | Social/influence events entitled | `UNAVAILABLE — no influence source` |
| Probability | Prediction market entitled | `UNAVAILABLE — no prediction source` |
| Resolution | Prediction market rules entitled | `UNAVAILABLE — no resolution source` |
| Whales (prediction) | Public participant data entitled | `UNAVAILABLE — participant data not exposed` |
| Related Markets | Cross-mapped prediction events | Partial when mapping incomplete |
| Narrative | Narrative engine + social data | `UNAVAILABLE` |
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

### DOGE (crypto — when admitted)
- Adds 24/7 session context, venue identity, stablecoin quote awareness
- Derivatives tab when perp/options entitled; funding/OI/liquidations labeled DERIVED
- On-Chain tab when entitled; entity labels show confidence and source
- Influence tab when entitled; first_observed_at and engagement snapshots in inspector
- Order Flow when trade/depth entitled; aggressor provenance explicit

### NVDA (equity, OHLCV-only phase)
- Order Flow tab: `UNAVAILABLE — aggressor classification requires trade feed`
- Options: `UNAVAILABLE — options data not admitted`
- Institutional: `UNAVAILABLE — no entitled disclosure source`

### ES (futures — when admitted)
- Adds session/contract context, roll awareness
- Order Flow when depth entitled

### FED CUT BY SEPTEMBER (prediction market — when admitted)
- Probability tab: executable bid/ask vs midpoint vs model fair — labeled separately
- Order Book and Trades when entitled; spread and liquidity quality explicit
- Whales tab when public participant data entitled; identity only where legitimately public
- Our Model tab: calibration, resolution risk, after-cost edge — not "guaranteed edge"
- Resolution tab: full rules, version history, semantic risk, amendment alerts
- Related Markets: cross-venue mapped contracts with `settlement_equivalent` flag
- Underlying Data / News/Influence: macro feeds and influence events linked PIT
- Cross-asset Market Story: prediction repricing → treasuries → ES/NQ → BTC when entitled

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
| Prediction Market Research | Probability + Our Model + Resolution + Whales + Related Markets |
| Cross-Asset Event | Probability + Related Markets + Story (multi-asset sync) |

Users duplicate/customize; defaults ship first-run.

## Focus vs Research density

Toggle in cockpit header. Research mode reveals Tier 4–5 metrics in active module.

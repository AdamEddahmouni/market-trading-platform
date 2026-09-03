# Global Context & Time Model

**Status:** `PROPOSED`

## Context bar (mandatory)

Persistent, high-contrast bar. User must never wonder: *Am I looking at live or historical data?*

```
┌────────────────────────────────────────────────────────────────────────────┐
│ ● LIVE  │  AS OF 10:42:18.328 ET  │  NVDA  │  Sync: Group A  │  Q: GOOD  │
└────────────────────────────────────────────────────────────────────────────┘
```

### Mode indicator

| Mode | Visual treatment | Behavior |
|---|---|---|
| `LIVE` | Green dot + label | Real-time entitled streams |
| `REPLAY` | Amber dot + label + scrubber | All components use knowable-at-time state |
| `SIMULATION` | Purple dot + label | Simulated fills/positions; no live data |
| `PAPER` | Blue dot + label | Paper execution boundary (future) |

**Decision: PROPOSED** — mode affects entire workspace, not per-panel exceptions without explicit "out-of-band comparison" label.

### As-of timestamp

- **Live:** `AS OF` shows current receipt/observation time with freshness indicator.
- **Replay:** `AS OF` shows replay cursor; frozen relative to live wall clock.
- **Simulation:** `AS OF` shows simulation clock.

Sub-second precision available on inspection; default display to ms where meaningful.

## Time-travel controls (replay)

```
09:30 ───────────●──────────── 16:00
                 10:37:42
    [◀◀] [◀] [▶/❚❚] [▶] [▶▶]   Speed: 1x ▼
    
    [◀ Prev significant event]  [Next significant event ▶]
    [Return to LIVE]
```

### Controls
- Play / pause / step / speed
- Jump to timestamp (command palette or scrubber)
- Event navigation (significant state changes only)
- Return to live (prominent, keyboard-accessible)

### Replay integrity rules

When `mode=REPLAY` at time T:

| Data type | Rule |
|---|---|
| Price/trades/bars | State knowable at T |
| Features derived from above | Computed with PIT cutoff at T |
| Filings/disclosures | Only if `available_time ≤ T` |
| Options chain | As-of T snapshot or `UNAVAILABLE` |
| Current portfolio | `UNAVAILABLE` in replay unless historical positions exist |
| News | Publication time ≤ T |
| Model outputs | Only if model run cutoff ≤ T |

**Out-of-band comparison:** If showing present-day data alongside replay, panel must carry explicit `COMPARISON — NOT KNOWABLE AT REPLAY TIME` banner.

## Visual safeguards against time-context leakage

1. Mode-specific chrome color (subtle border/tint)
2. Disabled live-only actions in replay (grayed with tooltip)
3. Filing/options panels show `REPORTED` vs `AVAILABLE` timestamps
4. AI sidecar inherits mode; cites availability semantics
5. Export artifacts embed `asOfContext` block

## Synchronized time across workspace

In replay, all linked panels share one replay cursor. Independent groups allowed for comparison studies.

## Market session context

Display session boundaries (RTH, ETH, futures session) relative to as-of time. ES vs equity session differences must be explicit when comparing instruments.

## Freshness semantics

| Label | Meaning |
|---|---|
| `LIVE` | Streaming within SLA |
| `FRESH` | Within expected delay |
| `DELAYED` | Known reporting delay (e.g., filings) |
| `STALE` | Beyond threshold; still shown with warning |
| `UNKNOWN` | Freshness not computable |

Freshness is separate from quality (partial, degraded, etc.).

## Backend contract needs

See [backend-ui-requirements.md](backend-ui-requirements.md): `AsOfContext`, `ReplaySession`, `AvailabilityBoundary`, `ModeState`.

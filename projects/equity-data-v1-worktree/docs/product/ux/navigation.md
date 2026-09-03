# Navigation & Route Model

**Status:** `PROPOSED`

## Primary navigation

Persistent left rail (desktop) or bottom tab bar (mobile subset):

```
NOW | EXPLORE | WORKSPACE | RESEARCH | PORTFOLIO*
```
*PORTFOLIO hidden or locked until separately authorized.

### Decision: PROPOSED
- Fixed 4–5 top-level items maximum
- No per-module top-level entries (Options, Squeeze, etc. live under WORKSPACE)

## Route structure (conceptual)

```
/now
/explore
  /explore/screeners
  /explore/screeners/:screenId
  /explore/watchlists/:listId
/workspace/:symbol
  /workspace/:symbol/overview
  /workspace/:symbol/order-flow
  /workspace/:symbol/options
  /workspace/:symbol/squeeze
  /workspace/:symbol/institutional
  /workspace/:symbol/models
  /workspace/:symbol/catalysts
  /workspace/:symbol/story
/research
  /research/replay
  /research/replay/:sessionId
  /research/models
  /research/datasets
  /research/simulation
/portfolio          (future, gated)
/assistant/history   (secondary — not primary nav)
```

Routes preserve global context query params: `?mode=replay&asOf=...&group=...`

## Global chrome (always visible)

1. **Context bar** — mode, as-of time, sync group indicator
2. **Instrument breadcrumb** — when in WORKSPACE
3. **Quality summary** — when degraded/partial (non-dismissible)
4. **Command trigger** — `⌘K` / `Ctrl+K`

## Command palette

**Decision: PROPOSED** — `Ctrl/Cmd+K` as primary expert entry.

### Example commands
```
NVDA                          → open instrument cockpit
ES                            → open futures cockpit
AAPL options                  → workspace options module
13D filings today             → explore filtered view
highest CVD divergence        → screener result (if entitled)
active squeeze confirmations  → explore (if entitled)
open NVDA replay 10:15        → research replay at timestamp
why did ES reverse?           → AI sidecar with context
compare NVDA vs QQQ           → linked workspace group
show conflicting evidence     → inspector/evidence view
```

### Command categories
- Navigate (domains, modules)
- Instrument (switch symbol)
- Time (jump replay, return live)
- Inspect (open inspector on selection)
- Explain (trigger explanation drawer)
- Watchlist actions
- Workspace layout (switch default template)

Commands complement navigation; they do not replace visible mode/time context.

## Keyboard workflow (desktop)

| Action | Shortcut (proposed) |
|---|---|
| Command palette | `Ctrl/Cmd+K` |
| Toggle inspector | `I` |
| Toggle AI sidecar | `A` |
| Explain selection | `E` |
| Next/previous attention item | `J` / `K` |
| Replay play/pause | `Space` (when replay focused) |
| Step replay | `,` / `.` |
| Switch workspace module | `1`–`9` (module tabs) |
| Focus chart | `C` |
| Return to live | `Esc` (from replay) |

All shortcuts require visible focus indicators and must not be the only path (WCAG).

## Linked workspace groups

Color-coded sync groups (inspired by TradingView tab linking):

| Sync dimension | Default |
|---|---|
| Symbol | Independent per chart unless linked |
| Time / as-of | Linked in replay mode |
| Crosshair | Optional link |
| Date range | Optional link |
| Selected event | Optional link |

Example: `ES / NQ / SPY / VIX` at synchronized replay timestamp.

## Focus mode vs Research mode

User-controlled density toggle (WORKSPACE-level):

| Mode | Shows |
|---|---|
| **Focus** | Essential state, key evidence, summary chart, alerts |
| **Research** | Full metrics, extra panels, diagnostics |

Safety-critical: quality warnings, mode indicator, risk rejections — **never hidden** in Focus mode.

## Mobile navigation

See [mobile-strategy.md](mobile-strategy.md). Primary tabs: NOW, Watchlists, Instrument, Alerts, Assistant.

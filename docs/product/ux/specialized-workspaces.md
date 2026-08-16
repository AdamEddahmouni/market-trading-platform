# Specialized Workspaces

**Status:** `PROPOSED`

Progressive disclosure does not mean avoiding density. Deep tasks get dedicated sub-workspaces within WORKSPACE modules or RESEARCH — with maximize/fullscreen.

## Order Flow / Microstructure

**Module:** WORKSPACE → Order Flow  
**Capability required:** Trades and/or depth (not OHLCV-only)

| Component | Tier | Notes |
|---|---|---|
| Price chart | 2 | Session markers, replay crosshair |
| Liquidity heatmap | 3 | Bookmap-inspired; capability-gated |
| Volume bubbles/dots | 3 | Size-encoded |
| DOM / depth ladder | 3 | No fake DOM when absent |
| Time & Sales | 4 | Virtualized |
| CVD / OFI | 3 | DERIVED badges + quality |
| Large trades table | 3 | Link to inspector |
| Quality state banner | 1 | Non-hideable |

**Interactions:** Toggle layers (Bookmap pattern), fullscreen, link sync group, jump to Story event.

**Current phase:** Render `UNAVAILABLE` with capability detail — do not mock.

## Options

**Module:** WORKSPACE → Options

| Component | Notes |
|---|---|
| Chain (strikes × expirations) | Virtualized grid |
| Greeks, IV, skew | DERIVED; model version |
| Flow feed | Unusual Whales-inspired table; explainable filters |
| Unusual activity | INFERRED with evidence |
| Term structure | Chart |
| Historical comparison | Replay-aware |

Side determination shown as heuristic with explanation path (bid/ask proximity).

## Short Squeeze

**Module:** WORKSPACE → Short Squeeze  
**Donor reference:** short-squeeze-project (CONCEPT_ONLY / PORT_ADAPT patterns)

| Component | Notes |
|---|---|
| Ignition state machine | State-transition display |
| Float / SI evidence | OBSERVED + delays |
| Borrow (if entitled) | |
| Options + flow cross-ref | Evidence alignment |
| Historical squeeze context | |

No `Whale Score` or opaque squeeze probability without calibrated model.

## Institutional Flow

**Module:** WORKSPACE → Institutional Flow  
**Naming:** Professional — not "Whales"

Eight evidence families per Swim With the Whales doctrine:

1. Regulatory/disclosure (Form 4, 13D/G, 13F)
2. Large transactions
3. Order book behavior
4. Order flow
5. Options
6. Futures positioning
7. Fund/ETF/cross-asset
8. Public catalyst

Each family: separate sub-panel, own freshness/availability, explainable inferences.

## Models

**Module:** WORKSPACE → Models / RESEARCH → Model Lab

| Component | Notes |
|---|---|
| Forecast + uncertainty | Calibrated intervals only |
| Feature contribution | When supportable |
| Regime / coverage | |
| Evaluation metrics | Walk-forward, PIT |
| Model identity | Version, artifact hash |
| Training manifest link | |

Phase 5R provides backend patterns; UI remains unauthorized until Research UI track.

## Replay Analysis

**Domain:** RESEARCH + WORKSPACE overlay

- Session manager: select date, instrument, start time
- Full cockpit in REPLAY mode
- Event markers on scrubber
- Compare before/after at selected event

## Simulation Lab

**Domain:** RESEARCH (Phase 7+ — not authorized)

- Deterministic simulation runs
- Clear SIMULATION mode chrome
- No ambiguous order buttons

## Layout defaults

Each specialized workspace ships as a **saved template** under WORKSPACE. User can maximize, duplicate, export layout JSON (future).

# Information Architecture

**Status:** `PROPOSED`

## Top-level domains

Five primary domains. Each answers a distinct user question. None grows unbounded into a module dump.

```
┌─────────────────────────────────────────────────────────────────┐
│  CONTEXT BAR: MODE | AS-OF TIME | INSTRUMENT | QUALITY SUMMARY  │
├──────────┬──────────┬──────────────┬───────────┬────────────────┤
│   NOW    │  EXPLORE │  WORKSPACE   │ RESEARCH  │   PORTFOLIO    │
│          │          │ (Instrument  │           │   (future)     │
│          │          │  Cockpit)    │           │                │
└──────────┴──────────┴──────────────┴───────────┴────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │ Evidence Inspector │  (persistent side panel)
                    │ AI Research Sidecar│  (persistent, contextual)
                    └───────────────────┘
```

| Domain | User question | Cognitive load target |
|---|---|---|
| **NOW** | What deserves my attention? | Lowest |
| **EXPLORE** | What should I investigate? | Low–medium |
| **WORKSPACE** | What is happening with this instrument/event? | Medium (module-dependent) |
| **RESEARCH** | Can I validate, reproduce, and inspect deeply? | High (intentional) |
| **PORTFOLIO** | What do I own and what risk exists? | Medium (future; gated) |

## NOW — Market Command Center

**Purpose:** Scarce attention resource. Not a dashboard of every module.

### Contains (when capability exists)
- Attention-ranked state changes and alerts
- Significant unusual activity (magnitude-normalized)
- Watchlist-relevant transitions
- Active-position risk proximity (future)
- Catalyst changes
- Institutional-flow evidence changes (when entitled)
- Squeeze state transitions (when entitled)
- Market regime summary
- System/data-quality problems (Tier 1 — never hidden)

### Does not contain
- Full option chains, DOM, model dashboards, raw tables
- Every market metric
- Universal buy/sentiment score

### Key artifact: Attention Priority Card
See [command-center.md](command-center.md).

## EXPLORE — Discovery

**Purpose:** Find something worth investigating.

### Capabilities (progressive by authorization)
- Universal search / command palette entry
- Screeners and scanners (explainable matches)
- Watchlists (persistent, lightweight)
- Saved screens
- Domain entry points: squeeze candidates, unusual volume, options activity, filings, model anomalies

### Output contract
Every result links to WORKSPACE or opens inspector with "Why matched?" path.

## WORKSPACE — Instrument Cockpit

**Purpose:** Unified shell for understanding one instrument, event, or market context.

Single conceptual shell for `NVDA`, `ES`, etc. Modules appear based on **verified capability** — unsupported modules render explicit `UNAVAILABLE` states.

### Default modules (capability-gated)

| Module | Typical content |
|---|---|
| Overview | Summary state, evidence alignment, quality, catalysts |
| Price / Structure | Chart, levels, session context |
| Order Flow | CVD, OFI, large trades, microstructure (if entitled) |
| Options | Chain, flow, Greeks, IV (if entitled) |
| Short Squeeze | Ignition state, SI evidence (if entitled) |
| Institutional Flow | Disclosures, large transactions (if entitled) |
| Catalysts | News, filings, events |
| Models | Forecasts, uncertainty (if entitled) |
| Historical Context | Regime, seasonality, prior events |
| Evidence | Market Story timeline, bundle browser |

See [instrument-cockpit.md](instrument-cockpit.md).

## RESEARCH — Deep validation

**Purpose:** Reproduce, validate, inspect methodology.

### Tools (future, separately authorized)
- Replay Session Manager
- Model Lab
- Dataset Explorer / Feature Explorer
- Simulation Lab
- Backtest/evaluation results
- Experiment registry
- Research notebook (context-attached notes)
- Provenance / raw event explorer

## PORTFOLIO — Future

**Purpose:** Positions, P&L, exposure, attribution, orders, fills, risk.

**Not authorized.** UI concepts documented for continuity. No live controls until separately authorized.

## Cross-cutting surfaces

| Surface | Role |
|---|---|
| Evidence Inspector | Universal inspect-anything side panel |
| AI Research Sidecar | Contextual explain/compare; never trading authority |
| Command Palette | `Ctrl/Cmd+K` expert navigation |
| Market Story | Chronological evidence timeline (observed sequence, not implied causality) |

## Depth model

| Level | Name | Surfaces |
|---|---|---|
| 1 | ATTENTION | NOW, alert cards, context bar |
| 2 | UNDERSTANDING | Overview modules, explanation drawer, evidence alignment |
| 3 | RESEARCH | Specialized workspaces, inspector RAW tab, replay, Model Lab |

## IA anti-patterns (explicitly rejected)

- One page per engine per instrument (fragmentation)
- Top-level "AI Chat" as primary nav item
- "Dashboard" as homepage with 20 widgets
- Adding primary nav item per new capability (modules live inside WORKSPACE/RESEARCH)

## Scalability rule

New capabilities attach as **WORKSPACE modules** or **RESEARCH tools**, not new top-level navigation — unless they represent a genuinely new user intent (rare).

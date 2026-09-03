# Mode-Specific UI Surfaces — Completion Record

> **Current architecture:** [ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) · [FRONTEND_GUIDE.md](../../engineering/FRONTEND_GUIDE.md)

**Date:** 2026-08-31  
**Status:** Complete (historical delivery record)  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Goal

Extend the mode-specific **Now** dashboard pattern to **Portfolio**, **Workspace**, **Explore**, **Research**, and **Discover** so Demo, Paper, and Live each get dedicated read-only or authority-appropriate surfaces instead of one shared page with inline gating.

## Architecture pattern

Each route family follows the same structure:

```
App.tsx
  └── Mode*Route (switches on session mode)
        ├── Demo*Page   — read-only, exploration copy, mode accent CSS
        ├── Paper*Page  — full controls when canUsePaperActions passes
        └── Live*Page   — broker-observed / observational, link to live canary
```

Shared observability components avoid duplicating tables and metrics:

| Route | Shared component | Data source |
|-------|------------------|-------------|
| `/` (Now) | Per-mode panels + `AttentionFeed` | Context, attention, replay, portfolio, canary |
| `/portfolio` | `PaperPortfolioObservability` | `/paper/portfolio` (Demo/Paper); canary APIs (Live) |
| `/workspace/:symbol` | `WorkspaceObservability` | Instrument, evidence, squeeze, replay chart |
| `/workspace/:symbol/*` | `*WorkspaceObservability` + `WorkspaceModuleModeShell` | Per-lane APIs (squeeze, order-flow, options, etc.) |
| `/explore` | `ExploreObservability` | Donor screener, scanner, futures, catalyst bridges |
| `/research` | `ResearchObservability` | Analytics, Model Lab, Simulation Lab APIs |
| `/discover` | `DiscoverObservability` | Mixed live screener, single-screen diagnostics |

## Completed deliverables

### Portfolio (`ModePortfolioRoute`)

- **Demo:** `DemoPortfolioPage` — simulated portfolio, no order/session controls
- **Paper:** `PaperPortfolioPage` — order ticket, session management, trace panel
- **Live:** `LivePortfolioPage` — positions, open orders, program caps, reconciliation from canary snapshot

Removed: `PortfolioPage.tsx`

### Workspace (`ModeWorkspacePage` via `WorkspaceRoute`)

- **Demo:** `DemoWorkspacePage` — lane evidence and replay, read-only
- **Paper:** `PaperWorkspacePage` — **decision cockpit** (lane handoff, decision snapshot, risk context, preview status) + order ticket + trace when authorized; accepts lane/Paper Now draft via router state
- **Live:** `LiveWorkspacePage` — observational workspace, link to `/live-canary`

Removed: `WorkspacePage.tsx`

### Workspace sub-modules (`Mode*WorkspaceRoute`)

All ten lane modules follow `WorkspaceModuleModeShell` + `*WorkspaceObservability` + **`ModeAwareWorkspaceLane` product content**:

- **Squeeze, Order Flow, Order Book, Futures, Catalyst, Fund/ETF, Options, Large Transactions, Disclosure, Institutional Flow**
- Demo/Live: read-only restriction notes; Paper: simulation context note, overview/portfolio links, per-module Paper/Live description hints via `workspaceModuleModeDescription`
- **Product depth (2026-08-31):** each lane renders mode-specific context panels (`buildLaneModeContent`) with Demo learning/replay framing, Paper decision readiness + draft workflow copy, and Live observational/operational context (`LiveLaneOperationalStrip` reuses `canary-snapshot` cache)
- Removed legacy monolithic `*WorkspacePage.tsx` files

See [Lane content completion record](2026-08-31-mode-specific-lane-content-completion.md) and [Paper workspace decision cockpit](2026-08-31-paper-workspace-decision-cockpit-completion.md).

### Explore (`ModeExploreRoute`)

- **Demo:** `DemoExplorePage` — frozen research bridges, read-only restriction note
- **Paper:** `PaperExplorePage` — candidate discovery framing, link to paper portfolio
- **Live:** `LiveExplorePage` — live observational panel, canary link, read-only note

Removed: `ExplorePage.tsx`

### Research (`ModeResearchRoute`)

- **Demo:** `DemoResearchPage` — replay-bound research, read-only note
- **Paper:** `PaperResearchPage` — research-to-simulation framing, defaults to Simulation tab
- **Live:** `LiveResearchPage` — read-only with canary link

Removed: `ResearchPage.tsx`

### Discover (`ModeDiscoverRoute`)

- **Demo:** `DemoDiscoverPage` — observational queue, GET-only polling, workspace links without promote
- **Paper:** `PaperDiscoverPage` — full discovery desk with refresh, promote, and auto-refresh on mount
- **Live:** `LiveDiscoverPage` — read-only monitor with canary link, no refresh or promote mutations

Removed: `DiscoverPage.tsx`

### Navigation (`NavShell`)

- Accepts session `mode` and renders per-link mode hints plus accessible `aria-label` descriptions for Discover, Explore, Workspace, Research, Portfolio, and Live Canary.

### Integration tests

`App.test.tsx` navigates to all primary routes, every workspace lane (`/workspace/BIYA/*` plus `/workspace/GME/squeeze` via Explore), secondary routes (`/settings`, `/live-canary`, `/diagnostics/provider`, `/assistant/history`), and Paper lane draft handoff in each mode where applicable.

### Operator settings (`/settings`)

- **Demo / Live:** read-only restriction note; watchlist, capture reindex, and replay controls hidden
- **Paper:** full operator housekeeping mutations enabled

### Workspace lane drafts (Paper)

- **All lane modules:** `Draft paper order from lane` navigates to workspace overview with a version-1 `PaperOrderDraft` (`sourceAttentionId: lane:<moduleId>`)

### Route unit tests

`ModeWorkspaceRoutes.test.tsx` table-drives Demo/Paper/Live chrome assertions for all 10 `Mode*WorkspaceRoute` components.

## Mode behavior matrix

| Surface | Demo | Paper | Live |
|---------|------|-------|------|
| Now (`/`) | Replay + inspect | Decision canvas + preview | Provider + safety + attention |
| Portfolio (`/portfolio`) | Read-only simulated | Sessions + orders | Broker-observed |
| Workspace (`/workspace/:symbol`) | Read-only research | Order ticket when authorized | Read-only + canary link |
| Workspace modules (`/workspace/:symbol/*`) | Read-only lane evidence + replay/learn context | Simulation context + decision hints + lane draft + overview link | Read-only + operational strip + canary links |
| Explore (`/explore`) | Frozen bridges | Candidate discovery | Live scanner + observational panel |
| Research (`/research`) | Replay-bound read-only | Simulation default tab | Read-only + canary link |
| Discover (`/discover`) | Observational queue | Full discovery desk | Read-only monitor |
| Settings (`/settings`) | Read-only operator | Mutations enabled | Read-only operator |

Authority rules unchanged: `modeAuthority.ts` / `canUsePaperActions` fail closed.

## Validation

```text
cd ui
npm test          # 298 tests passed (2026-08-31, incl. lane product content)
npm run build     # pass
```

## Not in scope (deferred)

- Master-account login (user idea only)
- Backend API changes for lane-specific Live broker snapshots (UI uses best-effort existing payloads; see lane content completion follow-ups)

## Related plans

- [2026-08-30 Demo Now dashboard](2026-08-30-demo-now-dashboard.md)
- [2026-08-31 Paper Now dashboard](2026-08-31-paper-now-dashboard.md)
- [2026-08-30 Mode-aware workstation](2026-08-30-mode-aware-workstation.md)

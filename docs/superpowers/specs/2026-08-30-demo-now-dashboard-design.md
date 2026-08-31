# Demo Now Dashboard Design

## Summary

The Demo launcher mode will open a purpose-built **Now** dashboard instead of the shared Command Center. The dashboard will make the admitted BIYA replay immediately understandable through a guided replay overview, observational portfolio summary, attention feed, and deterministic “Inspect next” path.

This increment is UI-only. It composes the existing context, replay-session, attention, and paper-portfolio APIs without adding or changing backend endpoints, schemas, execution authority, or persistence.

Paper and Live continue to render the existing Command Center until each mode receives its own approved dashboard design.

## Goals

1. Make Demo useful immediately after launcher entry.
2. Give the current replay position and next safe action the strongest visual priority.
3. Preserve the existing attention feed’s reason codes, explanations, inspection, and workspace navigation.
4. Show simulated portfolio state as read-only observational context.
5. Keep scenario identity truthful despite the absence of a scenario catalog or switch endpoint.
6. Let individual data failures degrade locally instead of replacing the whole dashboard.
7. Establish an information hierarchy that can later be adapted to Paper and Live without transferring capabilities between modes.

## Non-goals

- Adding a backend dashboard endpoint or aggregate view model.
- Adding a scenario catalog or scenario-switch action.
- Adding autoplay, pause, playback speed, or a playback lifecycle.
- Adding Demo order, paper-session, or other execution controls.
- Redesigning Paper or Live Now pages in this increment.
- Performing a global workstation visual redesign outside the Demo landing surface.

## Experience

### Page hierarchy

The Demo page uses a balanced command layout:

1. **Page introduction** — “See the market unfold” explains that the user is moving through a known historical sequence without execution risk.
2. **Replay overview** — the current BIYA scenario, cursor progress, Previous and Next event controls, and a link to the full workspace timeline.
3. **Simulated portfolio summary** — observational cash, total P&L, gross exposure, and open-order count.
4. **What matters now** — the current attention feed with tier identity, reason codes, and existing explain, inspect, and workspace actions.
5. **Inspect next** — a short deterministic path that begins with the highest-priority attention item and ends by advancing the replay.

On wide screens, the replay overview sits beside the portfolio summary, and the attention feed sits beside the guided path. On narrow screens, those regions reflow in the same reading order without hiding content.

### Visual direction

The dashboard keeps the workstation’s dark operational character while improving hierarchy and restraint:

- Cyan identifies replay state, current progress, and the primary replay action.
- Existing tier colors retain their semantic attention meaning.
- Human-readable headings pair with monospaced timestamps, evidence codes, state labels, and numeric values.
- A single strong replay surface anchors the page; supporting panels use quieter borders and backgrounds.
- Controls use consistent spacing, visible focus, and a minimum 44px interaction target.
- Environment, historical, read-only, and progress states remain understandable without color.

The visual changes apply to the Demo landing experience and its dashboard components. Future cross-workstation polish remains separate work.

## Architecture

### Mode routing

The root route will render a focused routing component:

```text
WorkstationShell
      |
      v
ModeNowRoute
  |-- DEMO  -> DemoNowPage
  |-- PAPER -> existing NowPage
  `-- LIVE  -> existing NowPage
```

`WorkstationShell` remains the owner of shared queries, drawer state, inspector state, replay cursor state, and navigation callbacks. It passes the already-loaded data and callbacks needed by the root route. This avoids duplicate context, attention, and replay-session queries.

The Demo dashboard may load the existing paper-portfolio query within its route branch because that data is not currently loaded by `WorkstationShell`. The query is observational; the dashboard does not import or render order tickets, session actions, or mutation hooks.

### Components

The implementation introduces a `demo-now` component group with focused responsibilities:

- `ModeNowRoute` selects the correct root page for the frontend mode and keeps Paper and Live behavior stable.
- `DemoNowPage` owns the Demo page layout and composes its child panels.
- `DemoReplayOverview` renders truthful scenario identity, replay position, progress, boundary state, and scrub/navigation actions.
- `DemoPortfolioSummary` transforms the existing portfolio response into four observational metrics and renders an unavailable fallback when necessary.
- `DemoInspectNext` derives safe, deterministic next steps from the top attention item and replay availability.
- The existing attention card behavior remains available through a shared feed presentation rather than being reimplemented with different semantics.

Each component receives explicit data and callbacks. No child component obtains execution capability from the selected frontend mode.

## Data flow

```text
/context ----------> authority, as-of time, scope symbol
/replay/session ---> cursor index, event count
/attention --------> tiered attention items and reason codes
/paper/portfolio --> observational account and exposure summary
                            |
                            v
                       DemoNowPage
                            |
             render-only data and safe callbacks
```

The scenario region identifies the existing admitted replay as **BIYA admitted replay**. It is a status card, not a select element, dropdown, or disabled fake control. The UI does not invent a catalog, alternate scenarios, or backend-supported scenario metadata.

The replay progress value is derived from `cursor_index` and `event_count`. With a non-empty replay, the displayed ordinal is `cursor_index + 1` out of `event_count`. Progress remains clamped to the valid range.

The portfolio panel uses the existing response fields:

- Cash: `account.cash_display`
- Total P&L: `pnl.total_display`, falling back to `account.realized_pnl_display`
- Gross exposure: `exposure.gross_shares`, falling back to zero
- Open orders: `risk.open_order_count`

The panel explicitly labels these values as a simulated, observational snapshot. It never treats portfolio execution authority as permission for the Demo frontend.

## Interactions

### Replay controls

- **Previous** scrubs to `cursor_index - 1`.
- **Next event** scrubs to `cursor_index + 1`.
- Previous is disabled at cursor zero.
- Next event is disabled at the final event.
- Both controls are disabled while a scrub request is pending.
- **Open full timeline** navigates to `/workspace/BIYA`.

The current `api.scrubReplay` call is used. Successful scrubs continue to refresh context, attention, and instrument queries. Autoplay is excluded because the current API supports deterministic cursor changes but exposes no playback lifecycle.

### Attention and guided path

Attention items preserve the existing actions:

- Why here?
- Explain
- Inspect
- Open workspace when `instrument_id` exists

The first guided action explains the top attention item. The second opens that item’s workspace when it has an instrument; otherwise it invites inspection. The final action advances one replay event when a next event exists.

When there is no attention item, the guided panel explains that no item requires inspection at the current event and keeps the replay-advance action available when possible.

## Loading, empty, and error behavior

Each region handles its own state:

- Replay loading shows a polite replay-status message and disables replay controls.
- Missing or invalid replay data shows “Replay status unavailable” without blocking attention or portfolio content.
- An empty replay session shows zero events and no scrub actions.
- Attention loading shows a polite feed-status message.
- An empty attention response explains that nothing requires attention at the current event.
- Attention failure leaves replay and portfolio panels available.
- Portfolio loading uses a compact summary placeholder.
- Portfolio failure shows “Simulated portfolio unavailable” and renders no fabricated values.
- Context failure continues to be surfaced by the persistent environment bar and does not independently replace the dashboard.

A scrub failure leaves the last confirmed cursor visible and announces that the replay could not move. The UI does not optimistically claim a new cursor before the backend confirms the scrub.

## Safety and authority

The dashboard does not alter the mode-authority model.

- Demo remains compatible only with replay/historical data and non-executing or blocked execution.
- Selected frontend mode never becomes execution authority.
- Portfolio data is observational and cannot reveal or invoke mutation controls.
- Direct navigation does not bypass the existing authority checks elsewhere in the workstation.
- Missing or incompatible backend authority continues to fail closed in the environment bar and restricted pages.

## Accessibility

- The page uses one level-one heading and named regions for replay, portfolio summary, attention, and guided steps.
- Native buttons provide keyboard activation and disabled semantics.
- Replay changes and scrub failures use polite status announcements.
- Tier, historical, read-only, disabled, and progress states use text in addition to color.
- Focus indicators remain visible in standard and forced-colors modes.
- Interactive targets are at least 44px in both dimensions.
- The responsive reading order matches the desktop information hierarchy.
- Motion is not required to understand progress or state.

## Testing

### Component coverage

- Scenario copy identifies BIYA without presenting a working selector.
- Replay ordinal and progress calculations handle first, middle, final, empty, and invalid states.
- Previous and Next event controls enforce replay bounds and pending state.
- Timeline navigation targets `/workspace/BIYA`.
- Portfolio metrics use the specified fields and fallbacks.
- No order, session, kill-switch, authorization-mutation, or execution controls render in Demo.
- Guided actions use the top attention item and degrade correctly without one.
- Replay, attention, and portfolio loading, empty, and failure states render independently.
- Attention actions preserve the existing callback behavior.

### Integration coverage

- Demo entry renders the Demo dashboard.
- Paper and Live entry retain the existing Command Center.
- Switching mode resets the route and a new Demo entry returns to the Demo dashboard.
- Replay scrubbing refreshes the existing query set and does not claim an unconfirmed cursor.
- Semantic regions, headings, button names, disabled states, and status announcements are queryable by accessible role and name.

### Repository validation

Implementation follows the repository validation ladder:

1. Run changed-files validation after each edit.
2. Run the UI domain validation at the feature milestone.
3. Run the full offline repository validation once at the final checkpoint.
4. Run the complete UI test suite.
5. Run TypeScript with `tsc --noEmit`.
6. Run the production build and bundle budget.
7. Run `git diff --check`.

Existing React Router future-flag warnings may remain warnings; new errors or warnings introduced by this work are not accepted.

## Acceptance criteria

1. Entering Demo at `/` displays the new mode-specific dashboard.
2. The dashboard shows truthful BIYA replay identity and confirmed cursor progress from the existing replay-session response.
3. Previous and Next event perform bounded, confirmed replay scrubs.
4. The full timeline action opens the BIYA workspace.
5. Simulated portfolio state is visible only as an observational summary.
6. No Demo execution or session mutation control is rendered.
7. Attention reason codes and explanation, inspection, and workspace actions remain available.
8. A clear guided path tells the user what to inspect next.
9. Replay, attention, and portfolio failures degrade locally.
10. Paper and Live root-route behavior is unchanged.
11. Responsive, keyboard, screen-reader, and forced-colors behavior meets the accessibility requirements.
12. Required UI and repository validation passes.

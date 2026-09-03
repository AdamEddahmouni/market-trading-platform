# Paper Now Dashboard Design

## Summary

Paper mode will receive a purpose-built **Paper Command** dashboard at `/`. The page will combine a persistent portfolio-and-risk frame with a clear trade-review path: select the highest-priority attention candidate, enter side and quantity, request a real backend risk preview, then continue to the instrument workspace for a fresh preview and final simulated submission.

The selected layout is the **Decision Canvas**. A compact risk ribbon spans the page. Below it, the attention queue, preview composer, and exception feed form a three-column operational canvas. The dashboard accelerates paper decisions without becoming a second portfolio ledger or allowing submission from the landing page.

This increment is UI-only. It uses the existing context, attention, paper portfolio, and paper order-preview APIs. It does not add backend endpoints, change execution authority, or alter Demo and Live behavior.

## Product decisions

The design uses the recommended choices approved during brainstorming:

1. Risk and portfolio state establish the page frame; the trade workflow is the main action path.
2. The dashboard can request an actual paper order preview, but cannot submit an order.
3. The highest-priority attention item with an instrument is selected by default; the user can choose another candidate.
4. Side and quantity are explicit user inputs. The existing `MARKET` order type remains fixed and visible.
5. Continuing to the workspace carries the draft, not the dashboard preview decision.
6. The workspace automatically re-runs the preview against current state before submission can be enabled.
7. Portfolio detail is limited to headline risk metrics and actionable exceptions; complete positions, orders, fills, traces, and session history remain on `/portfolio`.

## Goals

1. Make Paper mode immediately useful as a risk-aware decision surface.
2. Keep portfolio health and execution authority visible before the user sizes a trade.
3. Turn the attention feed into an explicit candidate-selection workflow without changing its reason-code semantics.
4. Produce truthful backend order previews from deliberate symbol, side, and quantity inputs.
5. Keep final simulated submission inside the evidence-rich instrument workspace.
6. Revalidate the draft after navigation so stale preview state never authorizes submission.
7. Surface operational exceptions without duplicating the full Portfolio page.
8. Preserve local loading and failure boundaries so one unavailable region does not replace the dashboard.

## Non-goals

- Submitting, cancelling, or modifying an order from the Paper dashboard.
- Opening, closing, archiving, or replacing paper sessions from the Paper dashboard.
- Replacing the full Portfolio page or its execution trace.
- Adding limit orders, advanced order types, bracket orders, sizing recommendations, or automated side/quantity selection.
- Treating an attention item as trading advice or execution authorization.
- Persisting drafts across browser restarts or URLs.
- Adding or changing backend paper, risk, attention, or workspace contracts.
- Redesigning Demo or Live Now pages.
- A global workstation visual redesign.

## Experience

### Page hierarchy

The Paper dashboard uses this reading and keyboard order:

1. **Page introduction** — “Paper Command” with Paper-only simulation language, session identity when present, execution mode, authority, and data-health status.
2. **Risk ribbon** — total P&L, buying power, gross exposure, largest-position limit utilization, and open-order limit utilization.
3. **Attention queue** — candidates sorted by `priority_rank`, preserving tier, headline, instrument, reason codes, and existing explain/inspect actions.
4. **Review and preview** — selected candidate context, explicit Buy/Sell choice, quantity, fixed Market order type, preview action, preview result, and workspace handoff.
5. **Exceptions** — compact, actionable portfolio, risk, reconciliation, order, and mark-quality problems.
6. **Portfolio link** — a secondary route to full positions, orders, fills, traces, data health, and session controls.

On wide screens, the decision area uses three columns: candidate queue, preview composer, and exceptions. The preview composer is the visual anchor. On narrower screens, the regions stack in the same order: risk ribbon, queue, preview, exceptions.

### Visual direction

The page extends the workstation’s dark operational language while distinguishing Paper from Demo:

- Paper teal identifies simulation state and the main safe-forward action.
- Existing attention tier colors retain their current semantic meaning.
- Positive, warning, and blocked preview states use text, iconography, and border treatment in addition to color.
- The risk ribbon is compact and always precedes the trade composer in reading order.
- The preview composer has the strongest surface treatment; the queue and exception feed are quieter supporting panels.
- Monospaced text is reserved for symbols, quantities, limits, authority, state codes, and timestamps.
- All interactive targets are at least 44 by 44 CSS pixels with visible focus.

## Architecture

### Mode routing

`ModeNowRoute` will become a three-branch route selector:

```text
ModeNowRoute
  |-- DEMO  -> DemoNowRoute -> DemoNowPage
  |-- PAPER -> PaperNowRoute -> PaperNowPage
  `-- LIVE  -> existing NowPage
```

`WorkstationShell` remains the owner of shared context, attention, explanation, inspection, and navigation callbacks. `PaperNowRoute` loads the existing paper portfolio query because that query is Paper-specific. It owns ephemeral candidate selection and preview state through the Paper page component group.

Live continues to render the existing Command Center. Demo continues to render the completed Demo dashboard.

### Components

The implementation introduces a `paper-now` component group:

- `PaperNowPage` composes the page and owns selected attention ID, draft side, draft quantity, and the currently confirmed dashboard preview.
- `PaperRiskRibbon` derives and renders the five headline metrics.
- `PaperCandidateQueue` sorts eligible attention items, manages accessible selection, and preserves explanation and inspection actions.
- `PaperPreviewComposer` validates the draft, calls the existing preview mutation, renders the preview result, and offers the workspace handoff only when appropriate.
- `PaperExceptionsPanel` derives a bounded list of explicit operational exceptions from the portfolio response.
- `paperDashboardViewModel.ts` contains pure metric, utilization, exception, candidate, and draft-request helpers.
- `paperOrderDraft.ts` defines the route-state draft contract shared by the Paper dashboard, `WorkspaceRoute`, `WorkspacePage`, and `OrderTicket`.

`OrderTicket` gains an optional initial draft and one-shot revalidation behavior. It remains the only component that exposes final submission. Preview request construction and draft validation move to shared pure helpers so the dashboard and workspace cannot silently diverge.

### Draft handoff contract

The in-memory React Router state uses this shape:

```ts
type PaperOrderDraft = {
  version: 1;
  instrumentId: string;
  side: "BUY" | "SELL";
  quantity: number;
  orderType: "MARKET";
  sourceAttentionId?: string;
};
```

The dashboard navigates to `/workspace/:symbol` with this draft after the user chooses to continue. It does not pass a `risk_status`, decision, idempotency key, or other preview output as authority.

`WorkspaceRoute` accepts only a structurally valid version-1 draft whose instrument matches the route symbol. Invalid or mismatched state is ignored. `WorkspacePage` passes a valid draft to `OrderTicket`. Once current portfolio authority is available, `OrderTicket` initializes the fields and requests one new preview. Submit remains disabled until that workspace preview returns `PASS`.

The draft is ephemeral. Reloading the workspace discards it and returns the ticket to its existing defaults.

## Data and derived state

### Inputs

```text
/context ----------------> data mode, execution mode, execution authority
/attention --------------> ranked candidates and reason codes
/paper/portfolio --------> account, P&L, exposure, positions, orders, risk, health
/paper/orders/preview ---> draft-specific risk and execution preview
```

### Risk ribbon

- **Total P&L:** `pnl.total_display`, falling back to `account.realized_pnl_display`.
- **Buying power:** `account.buying_power_minor`, formatted with `account.currency`; if formatting cannot be performed, show a labeled unavailable state rather than cash.
- **Gross exposure:** `exposure.gross_shares`, falling back to zero shares.
- **Largest-position utilization:** maximum absolute position quantity divided by `risk.limits.max_position_shares`, clamped for display but accompanied by the raw quantity and limit. If the limit is zero or invalid, show unavailable.
- **Open-order utilization:** `risk.open_order_count` divided by `risk.limits.max_open_orders`, with the raw count and limit always visible.

The UI does not convert share limits into notional risk or invent dollar exposure.

### Candidate selection

Eligible candidates have a non-empty `instrument_id`. They are sorted by ascending `priority_rank` without mutating the API array. The first eligible item is selected initially.

Selection remains stable by `attention_id` when the feed refreshes and the item still exists. If it disappears, selection moves to the new highest-priority eligible item. Items without an instrument remain visible for explanation and inspection but cannot become an order-preview candidate.

Changing the candidate, side, or quantity clears the previous preview immediately. Preview is enabled only when:

- Paper mode is active.
- Context and portfolio authority are compatible with internal simulation.
- A candidate instrument is selected.
- Quantity is an integer from 1 through `risk.limits.max_order_shares`.
- No preview request is pending.

The dashboard sends the same request fields as the existing ticket: side, quantity, `MARKET`, instrument ID/symbol, and a new idempotency key scoped to the specific preview attempt.

### Preview result

The preview region renders backend-provided fields only:

- Risk status and decision.
- Reason codes.
- Current and projected position.
- Current and estimated gross/net exposure when present.
- Risk limits and utilization when present.
- Quality state and fill-preview availability.
- Execution model/version when present.

A `PASS` permits the safe-forward action **Open workspace and revalidate**. A non-PASS result remains inspectable but does not offer a submission shortcut. Because the workspace always revalidates, dashboard PASS is never described as approval to execute.

### Exceptions

The exception panel shows a maximum of five items, ordered by severity and then stable source order. It reports only explicit states available in the portfolio response:

1. Active kill switch.
2. Unhealthy or unavailable `data_health.state`.
3. Non-healthy `reconciliation_status`.
4. A non-PASS last risk decision with its explicit reason or decision code.
5. Open-order states that explicitly indicate blocked, rejected, waiting, or failed behavior.
6. Position marks whose explicit quality is not current/healthy.

Unknown records are not guessed into exceptions. When no explicit exception exists, the panel says “No active exceptions” while still showing the portfolio link.

## Interactions and authority

### Candidate review

- Selecting a candidate updates the preview composer and clears any previous preview.
- Why, Explain, and Inspect retain their existing callbacks.
- “Open workspace” remains available as a direct research action independent of the order draft.
- The selected state is conveyed with `aria-selected` and text, not color alone.

### Preview

- Buy/Sell and quantity are always user-controlled; the dashboard never recommends or preselects a direction based on an attention item. The neutral initial state requires an explicit side choice before Preview is enabled.
- Quantity begins empty rather than using a suggested or maximum size.
- Preview responses are tied to the current draft fingerprint. A late response for an earlier draft cannot replace the current state.
- Changing any draft field invalidates the preview.
- Preview failures retain the draft and show a local error with Retry.

### Workspace continuation

- The continuation action is available after a successful, current dashboard preview.
- Navigation passes only the validated draft and source-attention reference.
- The workspace re-runs preview automatically once current Paper authority and account limits are known.
- The workspace clearly labels the result “Revalidated in workspace.”
- Final Submit remains an explicit click in the existing `OrderTicket` and is enabled only by the fresh workspace PASS result and existing authority checks.

### Session lifecycle

The dashboard displays session identity and authority but does not open, close, archive, or replace sessions. When Paper authority is unavailable, the preview composer fails closed and directs the user to `/portfolio`, where existing session controls remain. This keeps session mutations in one established surface.

## Loading, empty, and error behavior

Each region degrades independently:

- **Context unavailable:** authority status shows unavailable; preview is disabled; attention and portfolio regions may still render their own confirmed data.
- **Attention loading:** queue shows a polite loading status; risk and exceptions remain usable.
- **Attention error:** queue shows an alert; no preview candidate is inferred from portfolio state.
- **No eligible attention candidate:** queue explains that no instrument-backed candidate is available; preview fields remain disabled; Portfolio remains reachable.
- **Portfolio loading:** risk ribbon uses compact skeleton/status treatment; preview and exceptions are disabled without fabricated limits.
- **Portfolio error:** risk ribbon and exceptions show unavailable states; attention research actions remain available; order preview is disabled.
- **Preview pending:** draft inputs remain visible, Preview is disabled, and a polite status message announces validation.
- **Preview error:** the draft remains editable, an error is announced, and Retry is available.
- **Stale response:** ignored when its draft fingerprint no longer matches current inputs.
- **Workspace revalidation failure:** draft fields remain populated, Submit remains disabled, and the user can retry preview.

No page-level error replaces independently available regions.

## Accessibility and responsive behavior

- One level-one heading and named regions for risk summary, candidate queue, order preview, and exceptions.
- Native form controls and buttons with explicit labels, descriptions, errors, and disabled reasons.
- Candidate selection uses a single-selection listbox or radio-group pattern; implementation chooses the simpler pattern that preserves full card content and correct keyboard behavior.
- Preview status uses polite announcements; request failure uses an alert.
- Risk and limit meters expose numeric text and accessible names in addition to visual bars.
- Focus moves to the preview result heading after a user-initiated preview resolves, without stealing focus on background query refreshes.
- Minimum 44px interaction targets and visible `:focus-visible` treatment.
- At widths below the existing workstation breakpoint, columns stack in DOM order without hiding actions or data.
- Reduced-motion removes nonessential meter and result transitions.
- Forced-colors mode preserves selection, focus, preview result, and exception boundaries.

## Testing

### Pure view-model coverage

- Candidate sorting and non-mutating selection.
- Selection stability and fallback after feed refresh.
- Money formatting and unavailable buying-power behavior.
- Position and open-order utilization, including zero/invalid limits and over-limit raw values.
- Exception derivation, ordering, five-item cap, and no-guess behavior for unknown records.
- Draft validation, request construction, fingerprinting, and route-state validation.

### Component coverage

- Paper page exposes one heading and four named operational regions.
- Highest-priority eligible candidate is selected by default.
- Instrument-less attention items remain researchable but cannot drive preview.
- Side starts neutral and quantity starts empty.
- Preview is disabled until authority, candidate, side, and valid quantity are present.
- Draft changes clear prior preview.
- PASS and non-PASS results render backend fields truthfully.
- Only current PASS exposes workspace continuation.
- The dashboard renders no Submit, Cancel order, Open session, Close session, Archive session, or New session control.
- Risk and exception failures do not hide attention content.
- Attention failure does not hide confirmed portfolio state.

### Integration coverage

- Demo entry remains the Demo dashboard.
- Paper entry renders Paper Command.
- Live entry retains the existing Command Center.
- Paper preview calls the existing endpoint with the explicit draft.
- Out-of-order preview responses cannot replace current draft state.
- Workspace navigation carries only the versioned draft.
- Invalid or symbol-mismatched route state is ignored.
- Valid route state populates the workspace ticket and triggers one new preview.
- Submit stays disabled until the workspace preview returns PASS under current authority.
- Reloading the workspace discards ephemeral route state safely.

### Repository validation

Implementation follows `AGENTS.md`:

1. Run `.venv\Scripts\python.exe tools\validate.py changed` after each edit group.
2. Run the UI domain validation at the feature milestone.
3. Run the complete Vitest suite.
4. Run TypeScript with `tsc --noEmit`.
5. Run the production build and bundle budget.
6. Run the full offline repository validation once at the final checkpoint.
7. Run `git diff --check`.

## Acceptance criteria

1. Paper mode at `/` renders Paper Command in the selected Decision Canvas layout.
2. The risk ribbon shows truthful portfolio values and explicit limit denominators.
3. The highest-priority instrument-backed attention item is selected by default and can be changed.
4. Existing attention reason codes and research actions remain available.
5. Side and quantity require explicit user input; order type is visibly fixed to Market.
6. The dashboard uses the existing backend to preview the current draft.
7. Any draft change invalidates the previous preview.
8. The dashboard cannot submit, cancel, or modify orders or paper sessions.
9. Current PASS previews can continue to the matching instrument workspace.
10. The workspace receives only the draft, revalidates it, and keeps Submit disabled until the fresh preview passes.
11. Compact exceptions expose explicit operational problems without duplicating full portfolio tables.
12. Region-level loading and failures degrade independently.
13. Demo and Live root-route behavior remains unchanged.
14. Responsive, keyboard, screen-reader, reduced-motion, and forced-colors behavior meets the stated requirements.
15. Required UI and repository validation passes.

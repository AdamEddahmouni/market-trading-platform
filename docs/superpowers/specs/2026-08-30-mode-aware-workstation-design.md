# Mode-Aware Workstation Design

**Date:** 2026-08-30
**Status:** Approved design, pending written-spec review
**Scope:** Replace the Demo, Paper, and Live placeholder destinations with the existing workstation, add persistent mode identity and context warnings, and enforce mode-specific UI authority boundaries

## Purpose

The mode launcher currently ends at static placeholder cards even though the application already contains a complete research and market-analysis workstation. This change connects each launcher choice to that workstation while preserving the launcher’s safety model.

Mode selection remains frontend session context. It changes which workstation controls are presented; it does not change backend data, execution authority, broker connectivity, or account state. The backend `/context` response and action-specific API payloads remain the source of truth.

## Product decisions

- Demo, Paper, and Live all open the existing full workstation instead of a placeholder.
- A persistent environment bar identifies the selected mode, summarizes its safety boundary, and provides **Switch mode**.
- The existing primary navigation, routes, research surfaces, and market-analysis tools remain available in every mode.
- Demo is an exploration environment. It exposes research, replay, and observability surfaces but no order, paper-session, authorization-preview, or execution-control actions.
- Paper is the only mode that may expose simulated-order and paper-session actions.
- Paper actions appear only when both `/context` and the relevant action-specific backend payload confirm `execution_mode: INTERNAL_SIMULATION` and `execution_authority: PAPER_ONLY`.
- Live is a read-only data and observability environment. It never exposes order, paper-session, authorization-preview, kill-switch, or other execution-control actions.
- Selecting a mode never rewrites backend context or implies that provider readiness or execution authority changed.
- The selected mode remains in memory only. A reload returns to the launcher, and entering Live always requires the existing confirmation.

## Experience

### Entering a mode

After the existing startup and launcher flow completes, the operator lands on the workstation’s **Now** route. The placeholder card is removed. The persistent environment bar appears above the existing workstation navigation and context bar.

The bar contains:

- an explicit `DEMO`, `PAPER`, or `LIVE` text label;
- a concise boundary statement;
- a backend-context status, when available;
- a **Switch mode** button.

Mode identity cannot rely on color alone. Demo uses the established neutral blue treatment, Paper uses green, and Live uses amber, consistent with the approved Signal at Open launcher.

### Demo

Demo opens the complete research workstation. Historical and replay content remains available according to backend capabilities. Paper account, order, fill, and session data may still be displayed as read-only observability when returned by the backend, but action controls are replaced with an explanatory message: **Demo is exploration only. Order and session controls are unavailable.**

### Paper

Paper opens the complete workstation. Simulated-order tickets and paper-session controls are shown only when both the global `/context` response and the action-specific account payload confirm internal simulation and paper-only authority. If either source is loading, unavailable, absent, contradictory, or different, the data remains visible but the actions are replaced by a blocked-state explanation using the actual returned execution labels.

This is fail-closed: loading, errors, missing fields, and ambiguous values never render a mutating control.

### Live

Live opens the complete workstation after the existing explicit Live confirmation. Current market information is shown only when supplied by the backend. All pages remain read-only.

The Portfolio and instrument workspaces omit order and session controls. The Live Canary route may display its snapshot, safety state, incidents, and reliability information, but it omits mutating kill-switch and authorization-preview controls. Its banner identifies the page as read-only within this selected environment and continues to display backend-reported safety state.

### Switching

**Switch mode** clears the in-memory selection and returns to the launcher from any route. A later selection starts at the workstation’s **Now** route so a route from the previous mode cannot carry over. Selecting Live again repeats confirmation.

## Mode and backend-context relationship

The selected UI mode and backend context are deliberately separate:

- selected mode answers: “Which user experience did the operator choose for this session?”
- `/context` answers: “What data and execution environment is the backend actually reporting?”
- action-specific responses answer: “Is this particular action eligible?”

The environment bar derives a compatibility status from `/context`:

| Selected mode | Compatible backend context |
| --- | --- |
| Demo | `data_mode` is `FIXTURE_REPLAY` or `HISTORICAL_CAPTURE`, `execution_mode` is `NONE`, and `execution_authority` is `BLOCKED` |
| Paper | `execution_mode` is `INTERNAL_SIMULATION` and `execution_authority` is `PAPER_ONLY`; supported backend data modes may be used |
| Live | `data_mode` is `LIVE_OBSERVATIONAL` or `BROKER_DELAYED`, `execution_mode` is `NONE`, and `execution_authority` is `BLOCKED` |

While `/context` is loading, the bar says that backend context is being verified and no warning is announced. If the query fails, it shows a non-blocking **Context unavailable** warning; all mutating controls remain fail-closed.

If returned values do not satisfy the selected mode, the bar renders a `role="alert"` mismatch warning. The warning states both the selected mode and the backend-reported data/execution labels and clarifies that changing the UI mode did not change backend authority. The workstation remains available for observation, but all restricted controls remain hidden. A mismatch never grants additional capability.

## Component architecture

### `WorkstationShell`

Accepts the selected `Mode` and `onSwitchMode` callback. It renders the complete route tree, evaluates global mode compatibility, and passes mode plus a fail-closed `paperActionsPermitted` value to pages that contain restricted controls. It navigates to `/` before clearing the mode during switching.

### `ModeEnvironmentBar`

Renders persistent mode identity, safety copy, actual context status, mismatch/error states, and **Switch mode**. A pure compatibility helper converts `Mode` plus `AsOfContext` into `checking`, `compatible`, `mismatch`, or `unavailable` presentation state. `paperActionsPermitted` is true only for a compatible Paper result. These rules can be unit tested without rendering the entire application.

### `NavShell`

Remains the primary navigation. It receives mode only where needed for accurate accessible descriptions or read-only labeling. Restricted behavior is not enforced solely by hiding a link.

### Restricted pages

`PortfolioPage`, `WorkspacePage`, and `LiveCanaryControlPlanePage` receive the selected mode explicitly.

- `PortfolioPage` renders order and session mutations only when global Paper compatibility is confirmed and its account payload independently confirms the same authority.
- `WorkspacePage` renders its embedded order ticket only when global Paper compatibility is confirmed and its portfolio payload independently confirms the same authority.
- `LiveCanaryControlPlanePage` renders observability in all modes but exposes no mutating controls as part of this feature.

The restriction is enforced at the component that owns each mutation. Deep links therefore receive the same boundary as normal navigation.

### Removed component

`ModePlaceholderDashboard` is removed after all launcher destinations render `WorkstationShell`. Its placeholder-specific tests and styles are removed or migrated to the new environment bar.

## Data flow

The new entry path is:

`ApplicationBootstrap → ModeLauncher → optional LiveModeConfirmation → ModeTransition → WorkstationShell`

Within the shell:

1. `ApplicationBootstrap` supplies the in-memory selected mode.
2. `WorkstationShell` obtains the existing `/context` query result.
3. `ModeEnvironmentBar` displays selected-mode identity and the result of the backend-context comparison.
4. Restricted pages receive selected mode and the fail-closed global Paper permission as props.
5. Paper pages combine that global permission with action-specific backend authority before rendering mutations.

No new backend endpoint, mode mutation, persistence mechanism, or broker connection is introduced.

## Error and safety behavior

- Missing or failed context never enables actions.
- Paper mutation eligibility requires exact allowlisted values from both global and action-specific contexts; unknown future enum values and contradictory responses fail closed.
- Demo and Live never render order or paper-session controls, regardless of backend-reported authority.
- The Live Canary page does not issue POST requests unless a future separately designed authorization feature explicitly restores those controls.
- A selected/backend mismatch is visible and announced but does not block read-only research work.
- Existing page-level loading and unavailable states remain intact.
- Switching mode clears mode context without reloading the browser or mutating backend state.
- Backend authorization continues to be required even when a Paper control is visible; UI gating is defense in depth, not an authorization mechanism.

## Accessibility and responsive behavior

- The environment bar is a labeled region placed before primary navigation in reading order.
- Mode and boundary are expressed in text, not color alone.
- Mismatch and context-error messages use concise alert semantics and do not repeatedly announce query refreshes.
- **Switch mode** is a native button with a visible focus state and a target size consistent with the launcher controls.
- Restricted-control explanations are associated with their page section and readable by assistive technology.
- Narrow layouts wrap the mode metadata and keep the switch control reachable without horizontal scrolling.
- Motion remains minimal and honors the existing reduced-motion rules.
- Existing heading order and landmark structure remain valid after the bar is inserted.

## Testing strategy

Implementation follows test-driven development with focused red-green cycles.

Tests cover:

- Demo, Paper, and Live entering the workstation instead of a placeholder;
- the persistent environment label, boundary copy, and **Switch mode** control;
- switching from a nested route returning to the launcher and resetting the next entry to **Now**;
- Live still requiring confirmation after a switch;
- compatible, loading, failed, and mismatched `/context` states;
- mismatch copy containing selected and actual backend labels;
- Demo and Live hiding Portfolio and workspace order/session controls even when backend payloads claim authority;
- Paper showing controls only for exact `INTERNAL_SIMULATION` plus `PAPER_ONLY` payloads;
- Paper failing closed for loading, errors, missing fields, and any other authority combination;
- deep links receiving the same restrictions as navigation;
- Live Canary observability remaining visible while mutating controls are absent;
- keyboard focus, alert semantics, text-based mode identity, responsive wrapping, and reduced-motion behavior.

Repository validation follows `AGENTS.md`:

1. Run focused UI tests during red-green cycles.
2. Run `.venv\Scripts\python.exe tools\validate.py changed` after implementation edits.
3. Run the UI/domain milestone validation required by the manifest.
4. Run `.venv\Scripts\python.exe tools\validate.py full` at the final checkpoint when required by changed-file validation.
5. Run the UI production build and TypeScript no-emit check before completion.

## Out of scope

- Changing backend data mode or execution authority from the launcher
- Persisting a default or last-used mode
- Enabling live order entry, live session authorization, or broker commands
- Adding new Paper trading capabilities beyond the existing simulated controls
- Redesigning individual research pages or primary navigation
- Provider setup, authentication, or health remediation
- Converting mode selection into a security boundary; backend authorization remains authoritative

## Acceptance criteria

1. Every launcher choice opens the full existing workstation and no placeholder dashboard remains.
2. The selected mode and its safety boundary remain visible on every workstation route.
3. **Switch mode** works from every route, returns to the launcher, and does not persist a selection.
4. The environment bar clearly distinguishes selected UI mode from backend-reported context and warns on mismatches.
5. Demo exposes research and observability only, with no mutating order, session, or execution controls.
6. Paper exposes simulated-order and session controls only when exact backend action authority is confirmed.
7. Live exposes current-data and operational observability only, with all execution-related actions locked and absent.
8. Direct navigation cannot bypass mode restrictions.
9. Tests cover mode entry, switching, authority combinations, mismatch behavior, keyboard semantics, and responsive behavior.
10. Required repository validation, UI tests, type checking, and production build pass.

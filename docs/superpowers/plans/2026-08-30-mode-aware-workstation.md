# Mode-Aware Workstation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all three static launcher destinations with the existing workstation while keeping Demo and Live read-only and allowing Paper mutations only under exact, independently confirmed simulation authority.

**Architecture:** A pure mode-authority module compares the frontend session selection with backend context and produces a fail-closed permission. `WorkstationShell` owns the persistent environment bar and passes that permission to the specific pages that own restricted controls; those pages independently verify their action payloads before rendering mutations.

**Tech Stack:** React 18, TypeScript 5.6, React Router 6, TanStack Query 5, Vitest, Testing Library, CSS

## Global Constraints

- Mode selection remains frontend session context and never mutates backend data mode, execution authority, broker connectivity, or account state.
- Demo and Live never render order, paper-session, authorization-preview, kill-switch, or execution-control actions.
- Paper actions require `execution_mode: INTERNAL_SIMULATION` and `execution_authority: PAPER_ONLY` from both `/context` and the action-specific payload.
- Missing, loading, failed, contradictory, and unknown authority values fail closed.
- The selected mode remains in memory only; switching and re-entry start at **Now**, and Live always repeats confirmation.
- Mode identity uses text in addition to the established Demo blue, Paper green, and Live amber colors.
- Mismatch alerts report selected and backend context without blocking read-only work.
- No new dependencies, backend endpoints, or persistent mode storage.

---

## File structure

- Create `ui/src/components/mode-session/modeAuthority.ts`: pure compatibility and Paper-action predicates.
- Create `ui/src/components/mode-session/modeAuthority.test.ts`: enum combinations and fail-closed unit coverage.
- Create `ui/src/components/mode-session/ModeEnvironmentBar.tsx`: persistent environment identity, context status, mismatch alert, and switch control.
- Create `ui/src/components/mode-session/ModeEnvironmentBar.test.tsx`: accessible rendering and context-state tests.
- Modify `ui/src/App.tsx`: render `WorkstationShell` after mode selection, own global compatibility, reset routes on switch, and pass permissions to restricted pages.
- Modify `ui/src/App.test.tsx`: launcher-to-workstation integration and route-reset coverage.
- Modify `ui/src/components/mode-session/ModeSession.test.tsx`: retain bootstrap/confirmation tests using a small test destination instead of the deleted placeholder.
- Delete `ui/src/components/mode-session/ModePlaceholderDashboard.tsx`: remove the temporary destination.
- Modify `ui/src/components/PortfolioPage.tsx` and `ui/src/components/PortfolioPage.test.tsx`: fail-closed order/session gating.
- Modify `ui/src/components/WorkspaceRoute.tsx` and `ui/src/components/WorkspacePage.tsx`: carry the Paper permission to the embedded order ticket.
- Create `ui/src/components/WorkspacePage.test.tsx`: verify embedded ticket restrictions.
- Modify `ui/src/components/live/LiveCanaryControlPlanePage.tsx` and its test: retain observability and remove mutations.
- Modify `ui/src/styles/mode-session.css` and `ui/src/styles/layout.css`: replace placeholder rules with responsive, accessible environment-bar rules.

---

### Task 1: Pure mode authority and persistent environment bar

**Files:**
- Create: `ui/src/components/mode-session/modeAuthority.ts`
- Create: `ui/src/components/mode-session/modeAuthority.test.ts`
- Create: `ui/src/components/mode-session/ModeEnvironmentBar.tsx`
- Create: `ui/src/components/mode-session/ModeEnvironmentBar.test.tsx`
- Modify: `ui/src/styles/mode-session.css`

**Interfaces:**
- Consumes: `Mode` from `./types` and `AsOfContext` from `../../api/client`.
- Produces: `evaluateModeContext(mode, context)`, `hasPaperAuthority(context)`, `canUsePaperActions(mode, globalPaperPermission, actionContext)`, and `ModeEnvironmentBar`.

- [ ] **Step 1: Write failing authority tests**

Create table-driven tests with these exact expectations:

```ts
import { describe, expect, it } from "vitest";
import { canUsePaperActions, evaluateModeContext } from "./modeAuthority";

const base = {
  mode: "REPLAY" as const,
  as_of_time: "2026-08-30T12:00:00Z",
  timezone: "America/New_York",
};

describe("mode authority", () => {
  it.each([
    ["DEMO", { ...base, data_mode: "FIXTURE_REPLAY", execution_mode: "NONE", execution_authority: "BLOCKED" }],
    ["PAPER", { ...base, data_mode: "LIVE_OBSERVATIONAL", execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY" }],
    ["LIVE", { ...base, data_mode: "LIVE_OBSERVATIONAL", execution_mode: "NONE", execution_authority: "BLOCKED" }],
  ] as const)("accepts compatible %s context", (mode, context) => {
    expect(evaluateModeContext(mode, context)).toMatchObject({
      status: "compatible",
      paperActionsPermitted: mode === "PAPER",
    });
  });

  it("fails closed when selected Paper disagrees with backend context", () => {
    expect(evaluateModeContext("PAPER", { ...base, data_mode: "FIXTURE_REPLAY", execution_mode: "NONE", execution_authority: "BLOCKED" }))
      .toMatchObject({ status: "mismatch", paperActionsPermitted: false });
  });

  it("requires global and action-specific Paper authority", () => {
    const paper = { execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY" };
    expect(canUsePaperActions("PAPER", true, paper)).toBe(true);
    expect(canUsePaperActions("PAPER", false, paper)).toBe(false);
    expect(canUsePaperActions("DEMO", true, paper)).toBe(false);
    expect(canUsePaperActions("PAPER", true, { execution_mode: "NONE", execution_authority: "BLOCKED" })).toBe(false);
    expect(canUsePaperActions("PAPER", true, undefined)).toBe(false);
  });
});
```

- [ ] **Step 2: Run the authority tests and verify red**

Run from `ui`:

```powershell
npm run test -- src/components/mode-session/modeAuthority.test.ts
```

Expected: FAIL because `./modeAuthority` does not exist.

- [ ] **Step 3: Implement the minimal authority module**

Create the module with exact allowlists and no truthy/substring checks:

```ts
import type { AsOfContext } from "../../api/client";
import type { Mode } from "./types";

type ExecutionContext = Pick<AsOfContext, "data_mode" | "execution_mode" | "execution_authority">;

export type ModeContextEvaluation = {
  status: "compatible" | "mismatch" | "unavailable";
  paperActionsPermitted: boolean;
  actualSummary: string;
};

export function hasPaperAuthority(context: Partial<ExecutionContext> | undefined): boolean {
  return context?.execution_mode === "INTERNAL_SIMULATION" && context.execution_authority === "PAPER_ONLY";
}

export function evaluateModeContext(mode: Mode, context: AsOfContext | undefined): ModeContextEvaluation {
  if (!context) return { status: "unavailable", paperActionsPermitted: false, actualSummary: "Unavailable" };
  const noExecution = context.execution_mode === "NONE" && context.execution_authority === "BLOCKED";
  const compatible = mode === "DEMO"
    ? (["FIXTURE_REPLAY", "HISTORICAL_CAPTURE"] as const).includes(context.data_mode as "FIXTURE_REPLAY" | "HISTORICAL_CAPTURE") && noExecution
    : mode === "PAPER"
      ? hasPaperAuthority(context)
      : (["LIVE_OBSERVATIONAL", "BROKER_DELAYED"] as const).includes(context.data_mode as "LIVE_OBSERVATIONAL" | "BROKER_DELAYED") && noExecution;
  return {
    status: compatible ? "compatible" : "mismatch",
    paperActionsPermitted: mode === "PAPER" && compatible,
    actualSummary: `DATA ${context.data_mode ?? context.mode} · EXEC ${context.execution_mode ?? "UNKNOWN"} · AUTH ${context.execution_authority ?? "UNKNOWN"}`,
  };
}

export function canUsePaperActions(
  mode: Mode,
  globalPaperPermission: boolean,
  actionContext: Partial<ExecutionContext> | undefined,
): boolean {
  return mode === "PAPER" && globalPaperPermission && hasPaperAuthority(actionContext);
}
```

- [ ] **Step 4: Run the authority tests and verify green**

Run the Step 2 command. Expected: all tests PASS.

- [ ] **Step 5: Write failing environment-bar tests**

Cover a text label and native Switch button for every mode, a polite checking state, a non-blocking unavailable alert, and a mismatch `role="alert"` containing `PAPER` plus `EXEC NONE` and `AUTH BLOCKED`. Use a complete `AsOfContext` fixture and assert the region has accessible name `Session environment`.

- [ ] **Step 6: Run the component test and verify red**

```powershell
npm run test -- src/components/mode-session/ModeEnvironmentBar.test.tsx
```

Expected: FAIL because `ModeEnvironmentBar.tsx` does not exist.

- [ ] **Step 7: Implement `ModeEnvironmentBar` and its focused styles**

The component accepts:

```ts
type Props = {
  mode: Mode;
  context?: AsOfContext;
  contextState: "loading" | "ready" | "error";
  onSwitchMode: () => void;
};
```

Use these boundary strings exactly:

```ts
const boundaries: Record<Mode, string> = {
  DEMO: "Historical research · No execution",
  PAPER: "Internal simulation · Paper authority only",
  LIVE: "Current market observation · Execution locked",
};
```

Render `<section className="mode-environment-bar" data-mode={mode} aria-label="Session environment">`, visible mode text, boundary text, actual compatible summary, a polite `Verifying backend context…` status while loading, and an alert for error or mismatch. The mismatch copy must be `Selected ${mode}; backend reports ${evaluation.actualSummary}. UI mode selection does not change backend authority.` Add a native **Switch mode** button.

Replace the placeholder CSS rules with a compact three-column bar that uses `border-left` as the semantic color, wraps below `720px`, keeps the button at least `44px` high, has a visible `:focus-visible` outline, honors forced colors, and introduces no animation.

- [ ] **Step 8: Run both Task 1 test files and commit**

```powershell
npm run test -- src/components/mode-session/modeAuthority.test.ts src/components/mode-session/ModeEnvironmentBar.test.tsx
git add ui/src/components/mode-session/modeAuthority.ts ui/src/components/mode-session/modeAuthority.test.ts ui/src/components/mode-session/ModeEnvironmentBar.tsx ui/src/components/mode-session/ModeEnvironmentBar.test.tsx ui/src/styles/mode-session.css
git commit -m "feat(ui): add mode authority environment bar"
```

Expected: tests PASS and commit succeeds without skipped hooks.

---

### Task 2: Replace placeholders with the real workstation

**Files:**
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/App.test.tsx`
- Modify: `ui/src/components/mode-session/ModeSession.test.tsx`
- Delete: `ui/src/components/mode-session/ModePlaceholderDashboard.tsx`
- Modify: `ui/src/styles/layout.css`

**Interfaces:**
- Consumes: `evaluateModeContext` and `ModeEnvironmentBar` from Task 1.
- Produces: `WorkstationShell({ mode, onSwitchMode })` and the launcher-to-workstation route. Task 3 adds the global Paper permission when its consumers are ready.

- [ ] **Step 1: Convert mode-session tests away from the placeholder**

Replace the `ModePlaceholderDashboard` import and test-only usage with:

```tsx
function TestModeDestination({ mode, onSwitchMode }: { mode: Mode; onSwitchMode: () => void }) {
  return (
    <main>
      <h1>{mode} workstation</h1>
      <button type="button" onClick={onSwitchMode}>Switch mode</button>
    </main>
  );
}
```

Update placeholder heading expectations to `${mode} workstation` while retaining all startup, retry, focus trap, repeated Live confirmation, switch, and fresh-mount assertions.

- [ ] **Step 2: Write failing App integration tests**

Change the hook mock so `useContextQuery` returns a compatible Demo context and assert:

```tsx
fireEvent.click(await screen.findByRole("button", { name: /Demo/i }));
expect(await screen.findByRole("region", { name: "Session environment" })).toHaveTextContent("DEMO");
expect(screen.getByRole("navigation", { name: "Primary" })).toBeInTheDocument();
expect(screen.getByRole("heading", { name: "Command Center" })).toBeInTheDocument();
expect(screen.queryByText(/environment ready/i)).not.toBeInTheDocument();
```

Add an `it.each` proving Demo, Paper, and confirmed Live all reach the same primary navigation. Add a route reset test: enter Demo, click **WORKSPACE**, click **Switch mode**, enter Demo again, and assert **Command Center** is rendered and the **NOW** link is active.

- [ ] **Step 3: Run integration tests and verify red**

```powershell
npm run test -- src/App.test.tsx src/components/mode-session/ModeSession.test.tsx
```

Expected: App integration FAILS because it still renders `ModePlaceholderDashboard`; updated isolated bootstrap tests PASS.

- [ ] **Step 4: Integrate the workstation**

In `App.tsx`:

- import `Mode`, `ModeEnvironmentBar`, and `evaluateModeContext`;
- change the shell signature to `export function WorkstationShell({ mode, onSwitchMode }: { mode: Mode; onSwitchMode: () => void })`;
- remove the early returns for context loading/error so research navigation remains usable;
- compute `contextState` as `loading`, `ready`, or `error` and pass it with the optional backend context to `ModeEnvironmentBar`;
- render `ModeEnvironmentBar` before `NavShell`; render `ContextBar` when data exists and otherwise render a same-height `.context-bar.context-bar-unavailable` row saying `Backend context is not available.` so grid ordering stays stable;
- implement switch as `navigate("/", { replace: true }); onSwitchMode();`;
- replace the App child with `<WorkstationShell mode={mode} onSwitchMode={switchMode} />`.

Change `.app-shell` to `grid-template-rows: auto auto auto 1fr;` so the environment bar, navigation, context bar, and body occupy stable rows even when the context bar is absent.

- [ ] **Step 5: Delete the placeholder and run integration tests**

Delete `ModePlaceholderDashboard.tsx`, remove all imports and remaining `.mode-dashboard*` CSS, then run the Step 3 command. Expected: all tests PASS.

- [ ] **Step 6: Commit workstation integration**

```powershell
git add ui/src/App.tsx ui/src/App.test.tsx ui/src/components/mode-session/ModeSession.test.tsx ui/src/components/mode-session/ModePlaceholderDashboard.tsx ui/src/styles/layout.css ui/src/styles/mode-session.css
git commit -m "feat(ui): open workstation from mode launcher"
```

---

### Task 3: Gate Portfolio and embedded workspace actions

**Files:**
- Modify: `ui/src/components/PortfolioPage.tsx`
- Modify: `ui/src/components/PortfolioPage.test.tsx`
- Modify: `ui/src/components/WorkspaceRoute.tsx`
- Modify: `ui/src/components/WorkspacePage.tsx`
- Create: `ui/src/components/WorkspacePage.test.tsx`
- Modify: `ui/src/App.tsx`

**Interfaces:**
- Consumes: `Mode`, global `paperActionsPermitted`, and `canUsePaperActions`.
- Produces: read-only restricted states and Paper-only action surfaces.

- [ ] **Step 1: Write failing Portfolio tests**

Make the mocked portfolio payload mutable and render `PortfolioPage` with explicit props. Add these assertions:

```tsx
it.each(["DEMO", "LIVE"] as const)("keeps %s read-only despite a Paper-authorized payload", (mode) => {
  portfolio.account.execution_mode = "INTERNAL_SIMULATION";
  portfolio.account.execution_authority = "PAPER_ONLY";
  renderPage(mode, true);
  expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "New Paper Session" })).not.toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent(/controls are unavailable/i);
});

it("fails closed when global Paper context is incompatible", () => {
  portfolio.account.execution_mode = "INTERNAL_SIMULATION";
  portfolio.account.execution_authority = "PAPER_ONLY";
  renderPage("PAPER", false);
  expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
});

it("shows Paper actions only when both authority checks pass", () => {
  portfolio.account.execution_mode = "INTERNAL_SIMULATION";
  portfolio.account.execution_authority = "PAPER_ONLY";
  renderPage("PAPER", true);
  expect(screen.getByText("Order ticket")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "New Paper Session" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run Portfolio tests and verify red**

```powershell
npm run test -- src/components/PortfolioPage.test.tsx
```

Expected: FAIL because `PortfolioPage` does not accept mode permission props and always renders controls.

- [ ] **Step 3: Implement Portfolio gating**

Add props `{ mode: Mode; paperActionsPermitted: boolean }`, calculate:

```ts
const actionEligible = canUsePaperActions(mode, paperActionsPermitted, account);
```

Render the two session buttons and `OrderTicket` only when `actionEligible`. Otherwise render:

```tsx
<aside className="panel mode-restriction-note" role="note">
  <strong>{mode} is read-only here.</strong>
  <p>Order and paper-session controls are unavailable for this context.</p>
</aside>
```

Keep account, positions, orders, fills, traces, health, and session history visible.

- [ ] **Step 4: Run Portfolio tests and verify green**

Run the Step 2 command. Expected: all tests PASS.

- [ ] **Step 5: Write failing WorkspacePage tests**

Create a focused test that mocks chart-heavy and evidence children, returns an exact Paper-authorized portfolio payload from `usePaperPortfolioQuery`, sets `replayChartAvailable={false}`, and asserts:

- Demo plus global true has no `Order ticket`.
- Live plus global true has no `Order ticket`.
- Paper plus global false has no `Order ticket`.
- Paper plus global true renders `Order ticket`.

- [ ] **Step 6: Run WorkspacePage tests and verify red**

```powershell
npm run test -- src/components/WorkspacePage.test.tsx
```

Expected: FAIL because `WorkspacePage` always renders the ticket for a returned portfolio.

- [ ] **Step 7: Carry and enforce the workspace permission**

In `WorkstationShell`, calculate `const evaluation = evaluateModeContext(mode, contextQuery.data?.as_of_context)` and `const paperActionsPermitted = contextState === "ready" && evaluation.paperActionsPermitted`. Pass `mode` and this value to `PortfolioPage`.

Add `mode: Mode` and `paperActionsPermitted: boolean` to both `WorkspaceRoute` and `WorkspacePage` props. Pass them from the `/workspace/:symbol` route in `App.tsx`, then from `WorkspaceRoute` into `WorkspacePage`. Render the ticket row only when:

```ts
const paperActionsAvailable = canUsePaperActions(
  mode,
  paperActionsPermitted,
  portfolio?.account,
);
```

When a portfolio exists but actions are unavailable, render the same `role="note"` restriction copy instead of `OrderTicket`; never render an `ExecutionTracePanel` without a ticket-generated trace selection.

- [ ] **Step 8: Run restricted-page tests and commit**

```powershell
npm run test -- src/components/PortfolioPage.test.tsx src/components/WorkspacePage.test.tsx src/App.test.tsx
git add ui/src/App.tsx ui/src/components/PortfolioPage.tsx ui/src/components/PortfolioPage.test.tsx ui/src/components/WorkspaceRoute.tsx ui/src/components/WorkspacePage.tsx ui/src/components/WorkspacePage.test.tsx
git commit -m "feat(ui): enforce mode-specific paper controls"
```

Expected: all tests PASS.

---

### Task 4: Make Live Canary observational and complete verification

**Files:**
- Modify: `ui/src/components/live/LiveCanaryControlPlanePage.tsx`
- Modify: `ui/src/components/live/LiveCanaryControlPlanePage.test.tsx`
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/styles/mode-session.css`
- Modify: `ui/src/styles/layout.css`

**Interfaces:**
- Consumes: selected `Mode` from `WorkstationShell`.
- Produces: read-only Live Canary observability with no mutation paths.

- [ ] **Step 1: Write failing read-only Canary tests**

Render the page for each mode and assert the snapshot, safety state, incidents, and reliability section remain visible. Assert both mutation buttons are absent:

```tsx
expect(screen.queryByRole("button", { name: "Activate program kill switch" })).not.toBeInTheDocument();
expect(screen.queryByRole("button", { name: "Prepare session authorization preview" })).not.toBeInTheDocument();
expect(screen.getByText(new RegExp(`${mode} workstation.*read-only`, "i"))).toBeInTheDocument();
```

Inspect every fetch call and assert no request has a second argument with `method: "POST"`.

- [ ] **Step 2: Run Canary tests and verify red**

```powershell
npm run test -- src/components/live/LiveCanaryControlPlanePage.test.tsx
```

Expected: FAIL because both mutation buttons are still rendered.

- [ ] **Step 3: Remove Canary mutation paths**

Add `{ mode: Mode }` props and pass mode from the `/live-canary` route in `App.tsx`. Remove `postJson`, `activateKillSwitch`, `loadAuthorizationPreview`, `commandStatus`, `authPreview`, and their buttons/panels. Keep the global/program/session kill-switch values, authorization status, action queue, incident list, and reliability matrix as read-only data. Add the visible line `${mode} workstation · Read-only operational observability` beneath the safety header.

- [ ] **Step 4: Run Canary tests and all UI tests**

```powershell
npm run test -- src/components/live/LiveCanaryControlPlanePage.test.tsx
npm run test
```

Expected: both commands PASS with no unhandled promise rejections.

- [ ] **Step 5: Run accessibility-oriented static and responsive checks**

Confirm the final CSS contains a `44px` minimum target for the switch button, a `:focus-visible` outline, a `max-width: 720px` wrapping rule, and forced-colors support. Confirm tests assert a labeled environment region, textual mode identity, native button, polite checking status, and mismatch/error alerts. Run:

```powershell
rg -n "mode-environment-bar|44px|focus-visible|max-width: 720px|forced-colors" src/styles src/components/mode-session
```

Expected: every required behavior has a matching implementation or test location.

- [ ] **Step 6: Run repository and production verification**

From `ui`:

```powershell
.\node_modules\.bin\tsc.cmd --noEmit
npm run build
```

From the repository root:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py domain ui
```

Run `tools\validate.py full` only if `changed` reports that the full suite is required. Expected: zero type errors, successful production build and bundle budget, and zero validation failures.

- [ ] **Step 7: Review, commit, and push**

```powershell
git diff --check
git status --short
git diff --stat
git add ui/src/App.tsx ui/src/components/live/LiveCanaryControlPlanePage.tsx ui/src/components/live/LiveCanaryControlPlanePage.test.tsx ui/src/styles/mode-session.css ui/src/styles/layout.css
git commit -m "feat(ui): keep live canary controls read-only"
git push origin HEAD
git status --short --branch
```

Expected: no whitespace errors, the final commit succeeds, push advances the configured upstream branch, and the worktree is clean and synchronized.

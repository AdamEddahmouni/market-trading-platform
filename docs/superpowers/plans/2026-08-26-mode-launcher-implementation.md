# Mode Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an every-launch Demo, Paper, or confirmed read-only Live entry flow with honest readiness feedback, accessible interactions, temporary mode dashboards, and mode switching.

**Architecture:** A focused `mode-session` component group owns transient mode state and the launch state machine. `App` keeps the existing query/router shell intact but places it behind `ApplicationBootstrap`; the selected placeholder is intentionally isolated so later dashboard design can replace it without changing the safety gate. Readiness is supplied as injectable async work for deterministic tests and never changes backend execution authority.

**Tech Stack:** React 18, TypeScript 5.6, React Testing Library, Vitest, CSS custom properties, existing Vite application.

## Global Constraints

- Show the launcher on every fresh application mount; do not persist a mode in storage, cookies, URLs, or backend state.
- Live means read-only current data and always requires confirmation; execution authority remains `LOCKED`.
- Do not connect a broker, mutate backend mode, preview or stage orders, or add live-trading controls.
- Use only real async readiness boundaries: indeterminate progress while work is unmeasured and completed/active/pending steps for known stages; never add artificial delays.
- Preserve the approved “Signal at Open” direction and exclude the heartbeat/ticker line.
- Maintain keyboard operation, dialog focus trapping/restoration, mobile stacking, polite status announcements, and `prefers-reduced-motion` behavior.
- After every implementation edit run `.venv\Scripts\python.exe tools\validate.py changed`; at the final checkpoint run `.venv\Scripts\python.exe tools\validate.py full` if required.

## File map

- Create `ui/src/components/mode-session/types.ts`: public mode, readiness, and adapter contracts.
- Create `ui/src/components/mode-session/ApplicationBootstrap.tsx`: startup state machine, progress/error UI, and the in-memory session gate.
- Create `ui/src/components/mode-session/ModeLauncher.tsx`: Signal at Open launch deck and Live-confirmation ownership.
- Create `ui/src/components/mode-session/LiveModeConfirmation.tsx`: accessible modal, focus trap, Escape, and restoration.
- Create `ui/src/components/mode-session/ModeTransition.tsx`: selected-mode readiness state and retry/return actions.
- Create `ui/src/components/mode-session/ModePlaceholderDashboard.tsx`: minimal mode-specific destination and Switch mode control.
- Create `ui/src/components/mode-session/ModeSession.test.tsx`: behavior, error, focus, remount, and accessibility coverage.
- Create `ui/src/styles/mode-session.css`: approved visuals, responsive layout, loading motion, and reduced-motion rules.
- Modify `ui/src/App.tsx`: wrap the existing `Shell` with the launch gate and import its stylesheet.

---

### Task 1: Session contracts and startup gate

**Files:**
- Create: `ui/src/components/mode-session/types.ts`
- Create: `ui/src/components/mode-session/ApplicationBootstrap.tsx`
- Test: `ui/src/components/mode-session/ModeSession.test.tsx`

**Interfaces:**
- Produces: `type Mode = "DEMO" | "PAPER" | "LIVE"`, `type ReadinessTask = () => Promise<void>`, and `ApplicationBootstrap({ children, readinessTask?, modeReadinessTask? })`.
- Consumes: a render prop `children(mode: Mode, switchMode: () => void): ReactNode` for the selected dashboard/workstation destination.

- [ ] **Step 1: Write the failing startup tests**

```tsx
it("shows startup readiness before the launcher", async () => {
  const readiness = deferred<void>();
  render(<TestApplication readinessTask={() => readiness.promise} />);
  expect(screen.getByRole("status")).toHaveTextContent("Connecting to platform");
  expect(screen.queryByRole("heading", { name: /choose how you enter/i })).not.toBeInTheDocument();
  readiness.resolve();
  expect(await screen.findByRole("heading", { name: /choose how you enter/i })).toBeInTheDocument();
});

it("retries a failed startup check without reloading", async () => {
  const readinessTask = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(undefined);
  render(<TestApplication readinessTask={readinessTask} />);
  expect(await screen.findByText(/could not connect to the platform/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("heading", { name: /choose how you enter/i })).toBeInTheDocument();
  expect(readinessTask).toHaveBeenCalledTimes(2);
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL because `ApplicationBootstrap` and the mode-session contracts do not exist.

- [ ] **Step 3: Implement the minimal startup state machine**

```ts
export type Mode = "DEMO" | "PAPER" | "LIVE";
export type ReadinessTask = () => Promise<void>;
export const defaultReadinessTask: ReadinessTask = async () => {
  const response = await fetch("/context", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Platform readiness check failed");
};
```

`ApplicationBootstrap` starts in `STARTING`, invokes the readiness task from an effect, displays `Connecting to platform` with an indeterminate `role="progressbar"`, advances to the launcher only on resolution, and keeps a named failed-stage surface with `Retry` on rejection. It owns `Mode | null` only in component state, so remounting resets selection.

- [ ] **Step 4: Run the focused test and repository changed validation**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Expected: PASS for both startup cases.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS, or an explicit unrelated baseline failure recorded before continuing.

- [ ] **Step 5: Commit the startup gate**

```powershell
git add ui/src/components/mode-session/types.ts ui/src/components/mode-session/ApplicationBootstrap.tsx ui/src/components/mode-session/ModeSession.test.tsx
git commit -m "feat(ui): add application readiness gate"
```

### Task 2: Mode launcher and mandatory Live confirmation

**Files:**
- Create: `ui/src/components/mode-session/ModeLauncher.tsx`
- Create: `ui/src/components/mode-session/LiveModeConfirmation.tsx`
- Modify: `ui/src/components/mode-session/ApplicationBootstrap.tsx`
- Modify: `ui/src/components/mode-session/ModeSession.test.tsx`

**Interfaces:**
- Consumes: `Mode` from `types.ts` and `onSelect(mode: Mode): void` from the bootstrap.
- Produces: `ModeLauncher({ onSelect })` and `LiveModeConfirmation({ open, onCancel, onConfirm, triggerRef })`.

- [ ] **Step 1: Add failing selection and dialog tests**

```tsx
it.each(["Demo", "Paper"])("enters the %s transition directly", async (label) => {
  render(<ReadyTestApplication />);
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(label, "i") }));
  expect(await screen.findByRole("status")).toHaveTextContent(new RegExp(`Preparing ${label}`, "i"));
});

it("requires explicit confirmation for read-only Live and restores focus on cancel", async () => {
  render(<ReadyTestApplication />);
  const live = await screen.findByRole("button", { name: /Live/i });
  fireEvent.click(live);
  const dialog = screen.getByRole("dialog", { name: "Enter the live-data environment?" });
  expect(within(dialog).getByText(/Execution authority: LOCKED/i)).toBeInTheDocument();
  expect(screen.queryByText("Live environment ready")).not.toBeInTheDocument();
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(live).toHaveFocus();
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL because the launcher and dialog are not implemented.

- [ ] **Step 3: Implement the launch deck and focus-safe dialog**

`ModeLauncher` renders native buttons in DOM order Demo, Paper, Live with the exact approved copy. Demo and Paper call `onSelect` immediately; Live opens the dialog instead. `LiveModeConfirmation` uses `role="dialog"`, `aria-modal="true"`, a labelled heading, initial focus on **Go back**, Tab/Shift+Tab wrapping between its two buttons, Escape cancellation, body-scroll locking while mounted, and focus restoration to `triggerRef` on close. Confirmation alone calls `onSelect("LIVE")`.

- [ ] **Step 4: Run tests and changed validation**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Expected: PASS for direct selection, Live blocking, Escape, and focus restoration.

Run: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS.

- [ ] **Step 5: Commit the launcher safety flow**

```powershell
git add ui/src/components/mode-session
git commit -m "feat(ui): add safe mode launcher flow"
```

### Task 3: Honest transitions and temporary mode dashboards

**Files:**
- Create: `ui/src/components/mode-session/ModeTransition.tsx`
- Create: `ui/src/components/mode-session/ModePlaceholderDashboard.tsx`
- Modify: `ui/src/components/mode-session/ApplicationBootstrap.tsx`
- Modify: `ui/src/components/mode-session/ModeSession.test.tsx`

**Interfaces:**
- Consumes: `Mode`, injectable `modeReadinessTask(mode: Mode): Promise<void>`, `onReady`, `onRetry`, and `onReturn`.
- Produces: `ModePlaceholderDashboard({ mode, onSwitchMode })` with no execution mutation and a stable `data-mode` attribute for styling.

- [ ] **Step 1: Add failing transition, dashboard, retry, and remount tests**

```tsx
it.each(["DEMO", "PAPER", "LIVE"] as const)("shows the %s placeholder and switches mode", async (mode) => {
  render(<ReadyTestApplication />);
  await selectMode(mode);
  expect(await screen.findByRole("heading", { name: `${modeTitle(mode)} environment ready` })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
  expect(await screen.findByRole("heading", { name: /choose how you enter/i })).toBeInTheDocument();
});

it("keeps a failed mode visible and supports retry or return", async () => {
  const modeTask = vi.fn().mockRejectedValueOnce(new Error("unavailable")).mockResolvedValueOnce(undefined);
  render(<ReadyTestApplication modeReadinessTask={modeTask} />);
  fireEvent.click(await screen.findByRole("button", { name: /Paper/i }));
  expect(await screen.findByText(/could not prepare Paper/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("heading", { name: "Paper environment ready" })).toBeInTheDocument();
});

it("does not remember a mode across mounts", async () => {
  const first = render(<ReadyTestApplication />);
  await selectMode("DEMO");
  first.unmount();
  render(<ReadyTestApplication />);
  expect(await screen.findByRole("heading", { name: /choose how you enter/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL because transition and placeholder destinations do not exist.

- [ ] **Step 3: Implement transition and placeholders**

`ModeTransition` runs only the supplied task, marks `Preparing environment` active while unresolved, and changes the active stage to a safe error message on rejection. It offers **Retry** and **Return to mode selection** without reloading. `ModePlaceholderDashboard` uses exact authority copy: Demo `Historical replay · No execution`, Paper `Simulated orders · No live execution`, Live `Current market data · Execution authority locked`; all expose **Switch mode** and Live never claims provider health.

- [ ] **Step 4: Run focused and complete UI tests plus changed validation**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Run: `cd ui; npm test`

Run: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: all PASS.

- [ ] **Step 5: Commit mode destinations**

```powershell
git add ui/src/components/mode-session
git commit -m "feat(ui): add mode transitions and placeholders"
```

### Task 4: Signal at Open styling and App integration

**Files:**
- Create: `ui/src/styles/mode-session.css`
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/components/mode-session/ModeSession.test.tsx`

**Interfaces:**
- Consumes: `ApplicationBootstrap` and `ModePlaceholderDashboard` from the component group.
- Produces: the existing application entry point gated by launch selection, plus responsive and reduced-motion presentation.

- [ ] **Step 1: Add failing integration and style-contract tests**

```tsx
it("renders mode cards with explicit non-color labels", async () => {
  render(<ReadyTestApplication />);
  expect(await screen.findByRole("button", { name: /Demo.*Historical replay/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Paper.*Simulated/i })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Live.*Read-only/i })).toBeInTheDocument();
});

it("announces transition changes politely", async () => {
  render(<ReadyTestApplication />);
  fireEvent.click(await screen.findByRole("button", { name: /Demo/i }));
  expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run: `cd ui; npm test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL until accessible labels and status semantics match the contract.

- [ ] **Step 3: Integrate the gate and approved visual system**

In `App.tsx`, import `ApplicationBootstrap`, `ModePlaceholderDashboard`, and `./styles/mode-session.css`; replace `<Shell />` with:

```tsx
<ApplicationBootstrap>
  {(mode, switchMode) => (
    <ModePlaceholderDashboard mode={mode} onSwitchMode={switchMode}>
      <Shell />
    </ModePlaceholderDashboard>
  )}
</ApplicationBootstrap>
```

The dashboard component must keep the existing `Shell` mounted only if its placeholder explicitly renders children; for this approved placeholder phase, omit children from the visual destination so existing data-heavy workstation requests do not begin before later dashboard design. Add deep exchange-blue layers, a subtle CSS grid, static upper-right amber horizon glow, semantic card edges, visible focus rings, stacked layout below `720px`, an indeterminate bar driven by transform, and a media query that disables nonessential animation under `prefers-reduced-motion: reduce`. Do not add a centered ticker, ECG, or heartbeat line.

- [ ] **Step 4: Validate behavior, types, build, and CSS requirements**

Run: `cd ui; npm test`

Run: `cd ui; npm run build`

Run: `rg -n "heartbeat|ticker|localStorage|sessionStorage" ui/src/components/mode-session ui/src/styles/mode-session.css`

Expected: tests and build PASS; search returns no matches.

Run: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS and note whether `full_suite_required=true`.

- [ ] **Step 5: Perform browser verification**

Start the existing local UI/backend environment, inspect at desktop and narrow viewport widths, and verify startup, all three destinations, Live dialog keyboard behavior, Switch mode, failure/retry using controlled tests, and reduced motion. Confirm no horizontal overflow and no heartbeat/ticker line.

- [ ] **Step 6: Run the final offline checkpoint**

Run when required by changed validation: `.venv\Scripts\python.exe tools\validate.py full`

Expected: PASS. Do not run live-provider validation because no provider boundary changed.

- [ ] **Step 7: Commit the integrated experience**

```powershell
git add ui/src/App.tsx ui/src/styles/mode-session.css ui/src/components/mode-session/ModeSession.test.tsx
git commit -m "feat(ui): integrate signal at open launcher"
```


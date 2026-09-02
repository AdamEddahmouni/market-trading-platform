# Research Workstation Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first fixture-backed Research workstation milestone with a Research / Demo / Live launcher, a fast graphite-and-frosted-glass command surface, traceable opportunity analysis, meaningful charts, and no paper, broker, or live-order authority in Research.

**Architecture:** A transient mode-session gate selects one of three environment destinations without persisting or granting authority. Research renders a standalone workstation whose typed adapter boundary initially serves deterministic fixtures; small presentation components consume presentation-ready state, while `ResearchPage` owns only navigation, selection, drawer, and reviewed-command state. Existing API-backed workstation code remains exported as `LegacyShell` for later mode-specific integration but is not rendered by the new Research destination.

**Tech Stack:** React 18.3, TypeScript 5.6 strict mode, React Router 6.27, Recharts 2.15, Zod 3.23, CSS custom properties, Vitest 2.1, React Testing Library 16.3, Vite 5.4, repository CPython 3.11 validation runner.

## Global Constraints

- The startup launcher is **Research / Demo / Live**; the earlier Demo historical-exploration responsibility belongs to Research, and the earlier Paper destination is named Demo.
- Research creates no paper or live orders and holds no broker authority.
- Demo is identified as the paper-trading proving ground, but this milestone provides only an honest unavailable placeholder and no simulated order controls.
- Entering Live does not connect a broker, authorize a session, enable a strategy, or permit an order; Live requires explicit confirmation and remains `Execution authority: LOCKED`.
- Mode selection is React memory only. Do not write it to local storage, session storage, cookies, URL parameters, or backend state.
- The prototype uses deterministic representative fixtures behind a typed adapter and visibly labels fixture content; unsupported capabilities never display invented values, rows, charts, or progress.
- Preserve `OBSERVED_FACT`, `REPORTED_CLAIM`, `MODEL_OUTPUT`, and reference metadata as distinct epistemic labels; missing, insufficient, stale, and conflicting evidence are not zero.
- Use cyan-to-purple only for intelligence, selection, model activity, regime context, and automated workflow state; neon green only for favorable outcomes; neon red only for adverse outcomes; amber for caution, incomplete validation, and authority boundaries.
- Every graph must state the decision question it answers and provide a textual summary, period, key result, and primary risk.
- Preserve existing XA-01 through XA-05 semantics, OF/RT authority boundaries, EVIDENCE isolation, prediction authority, settlement, risk, execution, and broker transport.
- Do not add dependencies. Use the repository's existing Recharts package and CSS system.
- All navigation and actions are keyboard operable with visible focus; drawers restore focus; color is never the only state carrier; reduced motion removes nonessential transforms and ambient effects.
- Follow TDD. During red-green cycles run the focused Vitest file, then `npm.cmd test`; after implementation edits run `.venv\Scripts\python.exe tools\validate.py changed`; run `.venv\Scripts\python.exe tools\validate.py full` only at the final major checkpoint when required.

## File map

- Create `ui/src/components/mode-session/types.ts`: transient mode and readiness contracts.
- Create `ui/src/components/mode-session/ApplicationBootstrap.tsx`: startup, mode selection, transition, retry, and reset state machine.
- Create `ui/src/components/mode-session/ModeLauncher.tsx`: approved Research / Demo / Live launch deck.
- Create `ui/src/components/mode-session/LiveModeConfirmation.tsx`: focus-safe mandatory Live confirmation.
- Create `ui/src/components/mode-session/ModeTransition.tsx`: honest indeterminate environment preparation.
- Create `ui/src/components/mode-session/ModePlaceholderDashboard.tsx`: non-mutating Demo and Live placeholders.
- Create `ui/src/components/mode-session/ModeSession.test.tsx`: launcher, confirmation, transition, reset, and authority tests.
- Create `ui/src/components/research/contracts.ts`: canonical prototype DTOs and adapter interface.
- Create `ui/src/components/research/fixtures.ts`: deterministic ready and degraded snapshots.
- Create `ui/src/components/research/researchAdapter.ts`: fixture adapter and deterministic command parser.
- Create `ui/src/components/research/useResearchWorkstation.ts`: adapter loading, retry, and immutable selection state.
- Create `ui/src/components/research/ResearchShell.tsx`: workstation layout and responsive drawer ownership.
- Create `ui/src/components/research/ResearchSidebar.tsx`: workflow navigation, recents, watchlist, jobs, and Switch mode.
- Create `ui/src/components/research/GlobalCommandBar.tsx`: search and reviewed research-command flow.
- Create `ui/src/components/research/MarketContextBar.tsx`: compact as-of and cross-asset context.
- Create `ui/src/components/research/PriorityBriefing.tsx`: first-viewport most-important-now summary.
- Create `ui/src/components/research/OpportunityQueue.tsx`: ranked selectable investigations.
- Create `ui/src/components/research/ResearchJobActivity.tsx`: actual fixture-run progress and failures.
- Create `ui/src/components/research/QualificationGatePanel.tsx`: policy-owned gate status and package preview.
- Create `ui/src/components/research/DemoPackagePreview.tsx`: immutable, non-mutating package preview with blocking-gate truth.
- Create `ui/src/components/research/ResearchCommandHome.tsx`: first-viewport composition.
- Create `ui/src/components/research/MeaningfulCharts.tsx`: instrument-context and baseline-comparison charts with summaries and data tables.
- Create `ui/src/components/research/EvidenceRail.tsx`: evidence classes, gaps, risks, invalidation, and next action.
- Create `ui/src/components/research/ResearchWorkspace.tsx`: unified selected-investigation detail surface.
- Create `ui/src/components/research/ResearchDrawers.tsx`: explanation and provenance drawers with focus restoration.
- Create `ui/src/components/research/ResearchStateNotice.tsx`: loading, empty, error, and unsupported states.
- Create `ui/src/components/research/ResearchPage.test.tsx`: priority, selection, state, authority, keyboard, drawer, and chart acceptance tests.
- Create `ui/src/components/research/GlobalCommandBar.test.tsx`: parsing preview and safe launch tests.
- Create `ui/src/components/research/ResearchWorkspace.test.tsx`: epistemic, chart, gate, and provenance tests.
- Create `ui/src/styles/mode-session.css`: launcher, transition, confirmation, and placeholder presentation.
- Create `ui/src/styles/research-workstation.css`: graphite/frosted Research layout, density, semantic states, responsive rules, and reduced motion.
- Modify `ui/src/styles/tokens.css`: semantic theme tokens shared by the new surfaces.
- Modify `ui/src/components/ResearchPage.tsx`: replace the three-tab page with the adapter-backed workstation orchestrator.
- Modify `ui/src/App.tsx`: retain the old shell as an exported legacy surface and route mode destinations through the new gate.

---

### Task 1: Restore the launcher as Research / Demo / Live

**Files:**
- Create: `ui/src/components/mode-session/types.ts`
- Create: `ui/src/components/mode-session/ModeLauncher.tsx`
- Create: `ui/src/components/mode-session/LiveModeConfirmation.tsx`
- Test: `ui/src/components/mode-session/ModeSession.test.tsx`

**Interfaces:**
- Produces: `Mode = "RESEARCH" | "DEMO" | "LIVE"`, `ReadinessTask`, `ModeReadinessTask`, `ModeLauncher({ onSelect })`, and `LiveModeConfirmation({ onCancel, onConfirm, triggerRef })`.
- Consumes: no backend authority and no persisted state.

- [ ] **Step 1: Write the failing launcher and confirmation tests**

```tsx
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModeLauncher } from "./ModeLauncher";

describe("ModeLauncher", () => {
  it("orders Research, Demo, and Live with truthful responsibilities", () => {
    render(<ModeLauncher onSelect={vi.fn()} />);
    const cards = screen.getAllByRole("button");
    expect(cards.map((card) => card.textContent)).toEqual([
      expect.stringContaining("Research"),
      expect.stringContaining("Demo"),
      expect.stringContaining("Live"),
    ]);
    expect(cards[0]).toHaveTextContent(/investigate, build, test, and qualify/i);
    expect(cards[1]).toHaveTextContent(/paper-trading proving ground/i);
  });

  it("enters Research and Demo directly", () => {
    const onSelect = vi.fn();
    render(<ModeLauncher onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /Research/i }));
    fireEvent.click(screen.getByRole("button", { name: /Demo/i }));
    expect(onSelect.mock.calls).toEqual([["RESEARCH"], ["DEMO"]]);
  });

  it("requires Live confirmation and restores focus after Escape", () => {
    const onSelect = vi.fn();
    render(<ModeLauncher onSelect={onSelect} />);
    const live = screen.getByRole("button", { name: /Live/i });
    fireEvent.click(live);
    const dialog = screen.getByRole("dialog", { name: "Enter the live-data environment?" });
    expect(within(dialog).getByText("Execution authority: LOCKED")).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(live).toHaveFocus();
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL because `ModeLauncher` and the mode-session contracts do not exist on this branch.

- [ ] **Step 3: Add the exact mode contracts**

```ts
export type Mode = "RESEARCH" | "DEMO" | "LIVE";
export type ReadinessTask = () => Promise<void>;
export type ModeReadinessTask = (mode: Mode) => Promise<void>;
```

- [ ] **Step 4: Implement the launch deck**

```tsx
import { useRef, useState } from "react";
import { LiveModeConfirmation } from "./LiveModeConfirmation";
import type { Mode } from "./types";

type Props = { onSelect: (mode: Mode) => void };

const modes = [
  {
    mode: "RESEARCH",
    label: "Research",
    status: "Investigation laboratory",
    description: "Investigate markets, build and test candidates, and qualify immutable versions for Demo.",
  },
  {
    mode: "DEMO",
    label: "Demo",
    status: "Paper-trading proving ground",
    description: "Forward-test Research-qualified strategies with simulated execution before risking money.",
  },
] as const;

export function ModeLauncher({ onSelect }: Props) {
  const [confirmLive, setConfirmLive] = useState(false);
  const liveTriggerRef = useRef<HTMLButtonElement>(null);
  return (
    <main className="mode-session-surface">
      <section className="mode-launcher" aria-labelledby="mode-launcher-title">
        <header className="mode-launcher-header">
          <p className="mode-eyebrow">Initialize session</p>
          <h1 id="mode-launcher-title">Choose how you enter the market.</h1>
          <p>Set the environment for this session. You can switch modes later without leaving the workstation.</p>
        </header>
        <div className="mode-card-grid">
          {modes.map((item) => (
            <button
              key={item.mode}
              type="button"
              className={`mode-card mode-card-${item.mode.toLowerCase()}`}
              onClick={() => onSelect(item.mode)}
            >
              <span className="mode-card-status">{item.status}</span>
              <strong>{item.label}</strong>
              <span>{item.description}</span>
            </button>
          ))}
          <button
            ref={liveTriggerRef}
            type="button"
            className="mode-card mode-card-live"
            onClick={() => setConfirmLive(true)}
          >
            <span className="mode-card-status">Guarded real-capital environment</span>
            <strong>Live</strong>
            <span>Inspect current state. Entry never grants broker or order authority.</span>
          </button>
        </div>
      </section>
      {confirmLive ? (
        <LiveModeConfirmation
          triggerRef={liveTriggerRef}
          onCancel={() => setConfirmLive(false)}
          onConfirm={() => onSelect("LIVE")}
        />
      ) : null}
    </main>
  );
}
```

- [ ] **Step 5: Implement the focus-safe Live confirmation**

```tsx
import { useEffect, useRef, type RefObject } from "react";

type Props = {
  onCancel: () => void;
  onConfirm: () => void;
  triggerRef: RefObject<HTMLButtonElement>;
};

export function LiveModeConfirmation({ onCancel, onConfirm, triggerRef }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    cancelRef.current?.focus();
    return () => {
      document.body.style.overflow = overflow;
      triggerRef.current?.focus();
    };
  }, [triggerRef]);

  return (
    <div className="live-confirmation-backdrop">
      <div
        ref={dialogRef}
        className="live-confirmation"
        role="dialog"
        aria-modal="true"
        aria-labelledby="live-confirmation-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onCancel();
          }
          if (event.key === "Tab") {
            const buttons = Array.from(dialogRef.current?.querySelectorAll("button") ?? []);
            const first = buttons[0];
            const last = buttons.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <p className="mode-eyebrow">Authority boundary</p>
        <h2 id="live-confirmation-title">Enter the live-data environment?</h2>
        <p>Current provider data may be displayed. This does not connect a broker, enable a strategy, place an order, or grant execution authority.</p>
        <div className="live-authority-summary" aria-label="Live authority summary">
          <p>Data environment: LIVE</p>
          <p>Execution authority: LOCKED</p>
        </div>
        <div className="live-confirmation-actions">
          <button ref={cancelRef} type="button" onClick={onCancel}>Go back</button>
          <button type="button" onClick={onConfirm}>Enter live data</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run tests, changed validation, and commit**

Run from `ui`: `npm.cmd test -- src/components/mode-session/ModeSession.test.tsx`

Expected: PASS, 3 tests.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS with no UI test substitution implied; Vitest remains an explicit boundary.

```powershell
git add ui/src/components/mode-session/types.ts ui/src/components/mode-session/ModeLauncher.tsx ui/src/components/mode-session/LiveModeConfirmation.tsx ui/src/components/mode-session/ModeSession.test.tsx
git commit -m "feat(ui): revise launcher modes for research workflow"
```

### Task 2: Add honest startup, transitions, and inactive mode destinations

**Files:**
- Create: `ui/src/components/mode-session/ApplicationBootstrap.tsx`
- Create: `ui/src/components/mode-session/ModeTransition.tsx`
- Create: `ui/src/components/mode-session/ModePlaceholderDashboard.tsx`
- Modify: `ui/src/components/mode-session/ModeSession.test.tsx`

**Interfaces:**
- Consumes: `Mode`, `ReadinessTask`, `ModeReadinessTask`, and `ModeLauncher` from Task 1.
- Produces: `ApplicationBootstrap({ children, readinessTask?, modeReadinessTask? })` render-prop gate and `ModePlaceholderDashboard({ mode, onSwitchMode })` for `DEMO | LIVE`.

- [ ] **Step 1: Add failing startup, retry, reset, and placeholder tests**

```tsx
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApplicationBootstrap } from "./ApplicationBootstrap";
import { ModePlaceholderDashboard } from "./ModePlaceholderDashboard";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, reject, resolve };
}

it("shows real startup work before mode selection", async () => {
  const readiness = deferred<void>();
  render(<ApplicationBootstrap readinessTask={() => readiness.promise}>{() => <div>destination</div>}</ApplicationBootstrap>);
  expect(screen.getByRole("status")).toHaveTextContent("Connecting to platform");
  await act(async () => readiness.resolve());
  expect(await screen.findByRole("heading", { name: /Choose how you enter/i })).toBeInTheDocument();
});

it("retries a failed environment without browser reload", async () => {
  const modeTask = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(undefined);
  render(
    <ApplicationBootstrap readinessTask={() => Promise.resolve()} modeReadinessTask={modeTask}>
      {(mode) => <div>{mode} destination</div>}
    </ApplicationBootstrap>,
  );
  fireEvent.click(await screen.findByRole("button", { name: /Demo/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not prepare Demo");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("DEMO destination")).toBeInTheDocument();
});

it.each(["DEMO", "LIVE"] as const)("keeps %s non-mutating and returns to selection", async (mode) => {
  const onSwitchMode = vi.fn();
  render(<ModePlaceholderDashboard mode={mode} onSwitchMode={onSwitchMode} />);
  expect(screen.getByText("Execution authority: LOCKED")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /order|broker|trade/i })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
  expect(onSwitchMode).toHaveBeenCalledOnce();
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL because the bootstrap, transition, and placeholder components do not exist.

- [ ] **Step 3: Implement `ApplicationBootstrap`**

```tsx
import { useEffect, useState, type ReactNode } from "react";
import { ModeLauncher } from "./ModeLauncher";
import { ModeTransition } from "./ModeTransition";
import type { Mode, ModeReadinessTask, ReadinessTask } from "./types";

type Props = {
  children: (mode: Mode, switchMode: () => void) => ReactNode;
  readinessTask?: ReadinessTask;
  modeReadinessTask?: ModeReadinessTask;
};
type Startup = "CONNECTING" | "ERROR" | "READY";

export const defaultReadinessTask: ReadinessTask = async () => {
  const response = await fetch("/context", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Platform readiness check failed");
};

export function ApplicationBootstrap({
  children,
  readinessTask = defaultReadinessTask,
  modeReadinessTask = () => Promise.resolve(),
}: Props) {
  const [attempt, setAttempt] = useState(0);
  const [startup, setStartup] = useState<Startup>("CONNECTING");
  const [mode, setMode] = useState<Mode | null>(null);
  useEffect(() => {
    let active = true;
    setStartup("CONNECTING");
    void readinessTask().then(
      () => active && setStartup("READY"),
      () => active && setStartup("ERROR"),
    );
    return () => { active = false; };
  }, [attempt, readinessTask]);

  if (startup === "CONNECTING") return (
    <main className="mode-session-surface">
      <section className="startup-progress" role="status" aria-live="polite">
        <p className="mode-eyebrow">Application launch</p>
        <h1>Opening market workstation</h1>
        <ol className="mode-transition-steps" aria-label="Application startup stages">
          <li data-state="complete">Starting interface</li>
          <li data-state="active">Connecting to platform</li>
          <li data-state="pending">Checking environment readiness</li>
          <li data-state="pending">Ready</li>
        </ol>
        <div role="progressbar" aria-label="Application startup" />
      </section>
    </main>
  );
  if (startup === "ERROR") return (
    <main className="mode-session-surface">
      <section className="startup-progress" role="alert">
        <p className="mode-eyebrow">Startup blocked</p>
        <h1>Could not connect to the platform.</h1>
        <p>The platform readiness check failed. Existing data and authority state were not changed.</p>
        <button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button>
      </section>
    </main>
  );
  if (!mode) return <ModeLauncher onSelect={setMode} />;
  return (
    <ModeTransition mode={mode} readinessTask={modeReadinessTask} onReturn={() => setMode(null)}>
      {children(mode, () => setMode(null))}
    </ModeTransition>
  );
}
```

- [ ] **Step 4: Implement `ModeTransition` and the honest placeholders**

```tsx
import { useEffect, useState, type ReactNode } from "react";
import type { Mode, ModeReadinessTask } from "./types";

type Props = { children: ReactNode; mode: Mode; onReturn: () => void; readinessTask: ModeReadinessTask };
const label = (mode: Mode) => mode[0] + mode.slice(1).toLowerCase();

export function ModeTransition({ children, mode, onReturn, readinessTask }: Props) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<"LOADING" | "ERROR" | "READY">("LOADING");
  useEffect(() => {
    let active = true;
    setState("LOADING");
    void readinessTask(mode).then(
      () => active && setState("READY"),
      () => active && setState("ERROR"),
    );
    return () => { active = false; };
  }, [attempt, mode, readinessTask]);
  if (state === "READY") return children;
  if (state === "ERROR") return (
    <main className="mode-session-surface">
      <section className="mode-transition" role="alert">
        <p className="mode-eyebrow">{label(mode)} environment</p>
        <h1>Could not prepare {label(mode)}</h1>
        <p>The environment readiness check failed. No authority or platform state changed.</p>
        <div className="mode-transition-actions">
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry</button>
          <button type="button" onClick={onReturn}>Return to mode selection</button>
        </div>
      </section>
    </main>
  );
  return (
    <main className="mode-session-surface">
      <section className="mode-transition" role="status" aria-live="polite">
        <p className="mode-eyebrow">Preparing environment</p>
        <h1>Preparing {label(mode)}</h1>
        <ol className="mode-transition-steps">
          <li data-state="complete">Session selected</li>
          <li data-state="active">Checking environment readiness</li>
          <li data-state="pending">Opening workstation</li>
        </ol>
        <div role="progressbar" aria-label={`${label(mode)} environment readiness`} />
      </section>
    </main>
  );
}
```

```tsx
import type { Mode } from "./types";

type Props = { mode: Exclude<Mode, "RESEARCH">; onSwitchMode: () => void };
const copy = {
  DEMO: {
    title: "Demo proving ground",
    description: "Paper execution for Research-qualified packages is not connected in this frontend milestone.",
  },
  LIVE: {
    title: "Live environment guarded",
    description: "Live strategy, broker, risk-session, and per-order authority remain independently unavailable here.",
  },
} as const;

export function ModePlaceholderDashboard({ mode, onSwitchMode }: Props) {
  return (
    <main className="mode-session-surface mode-dashboard" data-mode={mode.toLowerCase()}>
      <header className="mode-dashboard-bar">
        <strong>{mode} session</strong>
        <button type="button" onClick={onSwitchMode}>Switch mode</button>
      </header>
      <section className="mode-dashboard-placeholder">
        <p className="mode-eyebrow">Environment boundary</p>
        <h1>{copy[mode].title}</h1>
        <p>Execution authority: LOCKED</p>
        <p>{copy[mode].description}</p>
        <div className="mode-dashboard-empty" role="status">Capability unavailable in this milestone</div>
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Run tests, changed validation, and commit**

Run from `ui`: `npm.cmd test -- src/components/mode-session/ModeSession.test.tsx`

Expected: PASS for startup, retry, transition, authority, and reset behavior.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS.

```powershell
git add ui/src/components/mode-session
git commit -m "feat(ui): add honest mode session boundaries"
```

### Task 3: Define typed Research fixtures and adapter behavior

**Files:**
- Create: `ui/src/components/research/contracts.ts`
- Create: `ui/src/components/research/fixtures.ts`
- Create: `ui/src/components/research/researchAdapter.ts`
- Create: `ui/src/components/research/useResearchWorkstation.ts`
- Test: `ui/src/components/research/researchAdapter.test.ts`

**Interfaces:**
- Produces: `ResearchSnapshot`, `ResearchOpportunity`, `ResearchDataAdapter`, `CommandPreview`, `createFixtureResearchAdapter(variant)`, `parseResearchCommand(input)`, and `useResearchWorkstation(adapter)`.
- Consumes: deterministic frontend-only data. No component reads raw records or makes authority decisions.

- [ ] **Step 1: Write failing adapter tests**

```ts
import { describe, expect, it } from "vitest";
import { createFixtureResearchAdapter, parseResearchCommand } from "./researchAdapter";

describe("research adapter", () => {
  it("returns stable ranked fixture data with explicit context", async () => {
    const adapter = createFixtureResearchAdapter("READY");
    const first = await adapter.loadCommand();
    const second = await adapter.loadCommand();
    expect(second).toEqual(first);
    expect(first.context.fixture).toBe(true);
    expect(first.opportunities.map((item) => item.id)).toEqual(["inq-nvda-ignition", "inq-es-liquidity"]);
  });

  it("parses read-only searches separately from reviewed tests", () => {
    expect(parseResearchCommand("NVDA")).toMatchObject({ action: "SEARCH", reviewRequired: false });
    expect(parseResearchCommand("Compare NVDA ignition models during stressed liquidity")).toMatchObject({
      action: "COMPARE",
      instrument: "NVDA",
      reviewRequired: true,
      cutoff: "2026-08-30T14:30:00Z",
    });
  });

  it("exposes unsupported and conflicting variants without replacing them with zero", async () => {
    const unsupported = await createFixtureResearchAdapter("UNSUPPORTED").loadCommand();
    const conflicting = await createFixtureResearchAdapter("CONFLICTING").loadCommand();
    expect(unsupported.capability.state).toBe("UNSUPPORTED");
    expect(conflicting.evidence.some((item) => item.state === "CONFLICTING")).toBe(true);
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/research/researchAdapter.test.ts`

Expected: FAIL because contracts and adapters do not exist.

- [ ] **Step 3: Add exact contracts**

```ts
export type ResearchSection = "COMMAND" | "EXPLORE" | "BUILD" | "TEST" | "EVALUATE" | "PROMOTE";
export type EpistemicClass = "OBSERVED_FACT" | "REPORTED_CLAIM" | "MODEL_OUTPUT" | "REFERENCE_METADATA";
export type EvidenceState = "AVAILABLE" | "MISSING" | "INSUFFICIENT" | "STALE" | "CONFLICTING";
export type GateState = "PASS" | "BLOCKED" | "PENDING";
export type AdapterVariant = "READY" | "EMPTY" | "STALE" | "CONFLICTING" | "UNSUPPORTED" | "FAILED";

export type ResearchContext = {
  asOf: string;
  cutoff: string;
  dataMode: "FIXTURE";
  fixture: true;
  freshness: "CURRENT_AT_CUTOFF" | "STALE";
  regime: string;
  rates: string;
  volatility: string;
};
export type ResearchOpportunity = {
  id: string;
  rank: number;
  symbol: string;
  investigatedDirection: "LONG" | "SHORT" | "NEUTRAL";
  state: "INQUIRY" | "HYPOTHESIS" | "CANDIDATE";
  title: string;
  whyNow: string;
  timingWindow: string;
  evidenceStrength: "HIGH" | "MEDIUM" | "LOW";
  estimatedAdvantageBps: number | null;
  baseline: string;
  primaryRisk: string;
  invalidation: string;
  uncertainty: string;
  lastPrice: number;
  priceChangePct: number;
};
export type ResearchJob = {
  id: string;
  label: string;
  status: "RUNNING" | "COMPLETE" | "FAILED";
  progress: number | null;
  detail: string;
  traceRef: string;
  trigger: string;
  cutoff: string;
  inputs: string[];
  candidateVersion: string | null;
  baseline: string;
  result: string;
  warnings: string[];
  permittedNextActions: string[];
};
export type QualificationGate = {
  id: string;
  label: string;
  state: GateState;
  policyRef: string;
  explanation: string;
};
export type EvidenceItem = {
  id: string;
  label: string;
  epistemicClass: EpistemicClass;
  state: EvidenceState;
  summary: string;
  source: string;
  availableTime: string | null;
};
export type PricePoint = { time: string; price: number; volume: number; marker?: "ENTRY" | "EXIT" | "INVALIDATION" };
export type ComparisonPoint = { cohort: string; candidate: number; baseline: number };
export type ResearchSnapshot = {
  context: ResearchContext;
  capability: { state: "AVAILABLE" | "UNSUPPORTED"; detail: string };
  briefing: { headline: string; summary: string; mainRisk: string; nextAction: string };
  opportunities: ResearchOpportunity[];
  jobs: ResearchJob[];
  gates: QualificationGate[];
  evidence: EvidenceItem[];
  prices: Record<string, PricePoint[]>;
  comparison: ComparisonPoint[];
};
export type CommandPreview = {
  input: string;
  action: "SEARCH" | "COMPARE" | "BACKTEST" | "STRESS_TEST";
  instrument: string | null;
  cutoff: string;
  baseline: string;
  inputs: string[];
  reviewRequired: boolean;
};
export interface ResearchDataAdapter {
  loadCommand(): Promise<ResearchSnapshot>;
  previewCommand(input: string): CommandPreview;
  launchReviewedTest(preview: CommandPreview): Promise<ResearchJob>;
}
```

- [ ] **Step 4: Add deterministic fixtures and adapter**

```ts
import type { AdapterVariant, ResearchSnapshot } from "./contracts";

export const readyResearchSnapshot: ResearchSnapshot = {
  context: {
    asOf: "2026-08-30T14:30:00Z",
    cutoff: "2026-08-30T14:30:00Z",
    dataMode: "FIXTURE",
    fixture: true,
    freshness: "CURRENT_AT_CUTOFF",
    regime: "RISK_ON · LIQUIDITY THINNING",
    rates: "2Y +4 bp",
    volatility: "VIX 17.8",
  },
  capability: { state: "AVAILABLE", detail: "Deterministic Research prototype fixture" },
  briefing: {
    headline: "NVDA ignition inquiry has the highest decision value",
    summary: "Price expansion and relative volume align, but stressed-liquidity cohorts remain under-tested.",
    mainRisk: "The apparent edge falls below baseline after adverse slippage.",
    nextAction: "Compare candidate v0.7.3 with the declared baseline in stressed-liquidity cohorts.",
  },
  opportunities: [
    {
      id: "inq-nvda-ignition", rank: 1, symbol: "NVDA", investigatedDirection: "LONG", state: "CANDIDATE",
      title: "Opening-range ignition after volume confirmation", whyNow: "Relative volume crossed 2.8× while breadth remained constructive.",
      timingWindow: "First 45 minutes", evidenceStrength: "HIGH", estimatedAdvantageBps: 38, baseline: "BUY_AND_HOLD_30M_V2",
      primaryRisk: "Liquidity stress erases the advantage", invalidation: "Close below the opening range low with spread above 28 bp",
      uncertainty: "Stressed-liquidity cohort has 41 observations", lastPrice: 131.42, priceChangePct: 2.7,
    },
    {
      id: "inq-es-liquidity", rank: 2, symbol: "ES", investigatedDirection: "NEUTRAL", state: "INQUIRY",
      title: "Index liquidity compression before macro release", whyNow: "Depth declined while cross-asset rates pressure increased.",
      timingWindow: "Next 90 minutes", evidenceStrength: "MEDIUM", estimatedAdvantageBps: null, baseline: "NO_POSITION",
      primaryRisk: "Reported depth does not predict executable liquidity", invalidation: "Depth normalizes before the event window",
      uncertainty: "Causal direction is unresolved", lastPrice: 5612.25, priceChangePct: -0.2,
    },
  ],
  jobs: [
    { id: "job-173", label: "NVDA stressed-liquidity comparison", status: "RUNNING", progress: 64, detail: "Cohort 7 of 11", traceRef: "fixture:trace:job-173", trigger: "Candidate v0.7.3 failed regime robustness", cutoff: "2026-08-30T14:30:00Z", inputs: ["fixture:market-bars", "fixture:liquidity-cohorts"], candidateVersion: "v0.7.3", baseline: "BUY_AND_HOLD_30M_V2", result: "Pending", warnings: ["Stressed-liquidity sample remains small"], permittedNextActions: ["Inspect progress", "Cancel fixture run"] },
    { id: "job-168", label: "ES macro-window replay", status: "FAILED", progress: null, detail: "Missing admitted depth snapshots", traceRef: "fixture:trace:job-168", trigger: "Scheduled replay coverage check", cutoff: "2026-08-30T14:30:00Z", inputs: ["fixture:es-bars", "fixture:depth-snapshots"], candidateVersion: null, baseline: "NO_POSITION", result: "Failed before evaluation", warnings: ["Depth snapshots unavailable"], permittedNextActions: ["Revise admitted inputs", "Retry after evidence repair"] },
  ],
  gates: [
    { id: "pit", label: "Point-in-time integrity", state: "PASS", policyRef: "policy:research-qualification:v3", explanation: "All admitted inputs were available at or before cutoff." },
    { id: "costs", label: "Profitability after costs", state: "PASS", policyRef: "policy:research-qualification:v3", explanation: "Candidate remains above declared baseline after configured costs." },
    { id: "regime", label: "Regime robustness", state: "BLOCKED", policyRef: "policy:research-qualification:v3", explanation: "Stressed-liquidity sample is below the owning policy requirement." },
  ],
  evidence: [
    { id: "ev-price", label: "Price and volume", epistemicClass: "OBSERVED_FACT", state: "AVAILABLE", summary: "Observed expansion above the opening range on 2.8× relative volume.", source: "fixture:market-bars:nvda", availableTime: "2026-08-30T14:29:58Z" },
    { id: "ev-catalyst", label: "Catalyst report", epistemicClass: "REPORTED_CLAIM", state: "CONFLICTING", summary: "Two admitted reports disagree on timing and materiality.", source: "fixture:reported-catalysts:nvda", availableTime: "2026-08-30T14:22:00Z" },
    { id: "ev-model", label: "Ignition model", epistemicClass: "MODEL_OUTPUT", state: "AVAILABLE", summary: "Candidate v0.7.3 estimates 38 bp advantage over the declared baseline.", source: "fixture:model-run:nvda-v073", availableTime: "2026-08-30T14:30:00Z" },
    { id: "ev-alt-catalyst", label: "Independent catalyst confirmation", epistemicClass: "REPORTED_CLAIM", state: "MISSING", summary: "No second admitted source confirmed the reported catalyst before cutoff.", source: "fixture:reported-catalysts:independent", availableTime: null },
  ],
  prices: {
    NVDA: [
      { time: "09:30", price: 128.2, volume: 810000 },
      { time: "09:40", price: 129.1, volume: 940000, marker: "ENTRY" },
      { time: "09:50", price: 130.8, volume: 1210000 },
      { time: "10:00", price: 131.42, volume: 1080000 },
      { time: "10:10", price: 130.1, volume: 890000, marker: "INVALIDATION" },
    ],
    ES: [
      { time: "09:30", price: 5620.5, volume: 54000 },
      { time: "10:00", price: 5612.25, volume: 71000 },
    ],
  },
  comparison: [
    { cohort: "Normal", candidate: 62, baseline: 31 },
    { cohort: "Thin liquidity", candidate: 18, baseline: 21 },
    { cohort: "High volatility", candidate: 44, baseline: 27 },
  ],
};

export function snapshotForVariant(variant: AdapterVariant): ResearchSnapshot {
  const copy = structuredClone(readyResearchSnapshot);
  if (variant === "EMPTY") copy.opportunities = [];
  if (variant === "STALE") copy.context.freshness = "STALE";
  if (variant === "CONFLICTING") copy.evidence[0].state = "CONFLICTING";
  if (variant === "UNSUPPORTED") copy.capability = { state: "UNSUPPORTED", detail: "Research fixture capability disabled" };
  return copy;
}
```

```ts
import type { AdapterVariant, CommandPreview, ResearchDataAdapter, ResearchJob } from "./contracts";
import { snapshotForVariant } from "./fixtures";

const CUTOFF = "2026-08-30T14:30:00Z";
export function parseResearchCommand(input: string): CommandPreview {
  const normalized = input.trim();
  const instrument = normalized.match(/\b[A-Z]{1,5}\b/)?.[0] ?? null;
  const lower = normalized.toLowerCase();
  const action = lower.startsWith("compare") ? "COMPARE" : lower.includes("stress") ? "STRESS_TEST" : lower.includes("backtest") ? "BACKTEST" : "SEARCH";
  return {
    input: normalized,
    action,
    instrument,
    cutoff: CUTOFF,
    baseline: "BUY_AND_HOLD_30M_V2",
    inputs: ["fixture:market-bars", "fixture:regime-state", "fixture:cost-policy:v2"],
    reviewRequired: action !== "SEARCH",
  };
}

export function createFixtureResearchAdapter(variant: AdapterVariant = "READY"): ResearchDataAdapter {
  return {
    async loadCommand() {
      if (variant === "FAILED") throw new Error("Deterministic fixture load failed");
      return snapshotForVariant(variant);
    },
    previewCommand: parseResearchCommand,
    async launchReviewedTest(preview): Promise<ResearchJob> {
      return {
        id: "job-reviewed-001",
        label: `${preview.instrument ?? "Market"} ${preview.action.toLowerCase()} review`,
        status: "RUNNING",
        progress: null,
        detail: "Fixture run accepted; duration is not measurable.",
        traceRef: "fixture:trace:job-reviewed-001",
        trigger: preview.input,
        cutoff: preview.cutoff,
        inputs: preview.inputs,
        candidateVersion: "v0.7.3",
        baseline: preview.baseline,
        result: "Pending",
        warnings: [],
        permittedNextActions: ["Inspect fixture run"],
      };
    },
  };
}
```

- [ ] **Step 5: Add the loading and retry hook**

```ts
import { useCallback, useEffect, useState } from "react";
import type { ResearchDataAdapter, ResearchSnapshot } from "./contracts";

export function useResearchWorkstation(adapter: ResearchDataAdapter) {
  const [attempt, setAttempt] = useState(0);
  const [snapshot, setSnapshot] = useState<ResearchSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    void adapter.loadCommand().then(
      (value) => { if (active) { setSnapshot(value); setLoading(false); } },
      () => { if (active) { setError("Research data could not be loaded."); setLoading(false); } },
    );
    return () => { active = false; };
  }, [adapter, attempt]);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { error, loading, retry, snapshot };
}
```

- [ ] **Step 6: Run adapter tests, build, changed validation, and commit**

Run from `ui`: `npm.cmd test -- src/components/research/researchAdapter.test.ts`

Expected: PASS, 3 tests.

Run from `ui`: `npm.cmd run build`

Expected: PASS with no TypeScript diagnostics.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS.

```powershell
git add ui/src/components/research/contracts.ts ui/src/components/research/fixtures.ts ui/src/components/research/researchAdapter.ts ui/src/components/research/useResearchWorkstation.ts ui/src/components/research/researchAdapter.test.ts
git commit -m "feat(ui): add typed research prototype adapter"
```

### Task 4: Build the Research shell, sidebar, and navigation model

**Files:**
- Create: `ui/src/components/research/ResearchShell.tsx`
- Create: `ui/src/components/research/ResearchSidebar.tsx`
- Create: `ui/src/components/research/ResearchStateNotice.tsx`
- Modify: `ui/src/components/ResearchPage.tsx`
- Test: `ui/src/components/research/ResearchPage.test.tsx`

**Interfaces:**
- Consumes: `ResearchDataAdapter`, `ResearchSection`, and `useResearchWorkstation` from Task 3.
- Produces: `ResearchPage({ adapter?, onSwitchMode? })`, a persistent desktop sidebar, a narrow-layout drawer, and stable section selection.

- [ ] **Step 1: Write failing shell tests**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResearchPage } from "../ResearchPage";
import { createFixtureResearchAdapter } from "./researchAdapter";

describe("ResearchPage shell", () => {
  it("shows Command first with all workflow destinations in order", async () => {
    render(<ResearchPage adapter={createFixtureResearchAdapter()} />);
    expect(await screen.findByRole("heading", { name: "Research Command" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Command|Explore|Build|Test|Evaluate|Promote/ }).map((node) => node.textContent)).toEqual([
      "Command", "Explore", "Build", "Test", "Evaluate", "Promote",
    ]);
  });

  it("keeps recent inquiries, watchlist, jobs, and Switch mode in the sidebar", async () => {
    const onSwitchMode = vi.fn();
    render(<ResearchPage adapter={createFixtureResearchAdapter()} onSwitchMode={onSwitchMode} />);
    await screen.findAllByText(/NVDA/);
    expect(screen.getByRole("heading", { name: "Recent inquiries" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Watchlist" })).toBeInTheDocument();
    expect(screen.getByText("1 active · 1 needs attention")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Switch mode" }));
    expect(onSwitchMode).toHaveBeenCalledOnce();
  });

  it("labels fixture mode and contains no execution actions", async () => {
    render(<ResearchPage adapter={createFixtureResearchAdapter()} />);
    expect(await screen.findByText(/FIXTURE · 2026-08-30 14:30 UTC/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /buy|sell|place order|connect broker/i })).not.toBeInTheDocument();
  });

  it("keeps unimplemented workflow destinations honest", async () => {
    render(<ResearchPage adapter={createFixtureResearchAdapter()} />);
    await screen.findByRole("heading", { name: "Research Command" });
    fireEvent.click(screen.getByRole("button", { name: "Explore" }));
    expect(screen.getByRole("heading", { name: "Explore workspace not connected" })).toBeInTheDocument();
    expect(screen.getByText(/scheduled for the workflow-workspaces milestone/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/research/ResearchPage.test.tsx`

Expected: FAIL because the new shell and sidebar do not exist.

- [ ] **Step 3: Implement the state notice and sidebar**

```tsx
type Props = { kind: "LOADING" | "EMPTY" | "ERROR" | "UNSUPPORTED"; onRetry?: () => void };
const copy = {
  LOADING: ["Loading Research", "Reading the deterministic workstation snapshot."],
  EMPTY: ["No investigations matched", "The current cutoff has no ranked opportunities. Missing results are not zero."],
  ERROR: ["Research unavailable", "The snapshot failed to load. Completed evidence was not changed."],
  UNSUPPORTED: ["Capability unavailable", "This Research capability is not supported by the selected adapter."],
} as const;

export function ResearchStateNotice({ kind, onRetry }: Props) {
  const role = kind === "ERROR" ? "alert" : "status";
  return (
    <section className={`research-state research-state-${kind.toLowerCase()}`} role={role} aria-live="polite">
      <h2>{copy[kind][0]}</h2><p>{copy[kind][1]}</p>
      {kind === "ERROR" && onRetry ? <button type="button" onClick={onRetry}>Retry Research load</button> : null}
    </section>
  );
}
```

```tsx
import type { ResearchOpportunity, ResearchSection } from "./contracts";

type Props = {
  active: ResearchSection;
  opportunities: ResearchOpportunity[];
  drawerOpen: boolean;
  onCloseDrawer: () => void;
  onSelectOpportunity: (id: string) => void;
  onSectionChange: (section: ResearchSection) => void;
  onSwitchMode?: () => void;
};
const sections: ResearchSection[] = ["COMMAND", "EXPLORE", "BUILD", "TEST", "EVALUATE", "PROMOTE"];

export function ResearchSidebar({ active, opportunities, drawerOpen, onCloseDrawer, onSelectOpportunity, onSectionChange, onSwitchMode }: Props) {
  return (
    <aside className={`research-sidebar ${drawerOpen ? "open" : ""}`} aria-label="Research navigation">
      <div className="research-brand"><span>IMP</span><strong>Research</strong><small>EXECUTION NONE</small></div>
      <nav aria-label="Research workflow">
        {sections.map((section) => (
          <button key={section} type="button" aria-current={active === section ? "page" : undefined} onClick={() => { onSectionChange(section); onCloseDrawer(); }}>
            {section[0] + section.slice(1).toLowerCase()}
          </button>
        ))}
      </nav>
      <section><h2>Recent inquiries</h2>{opportunities.slice(0, 2).map((item) => <button key={item.id} type="button" onClick={() => { onSelectOpportunity(item.id); onCloseDrawer(); }}>{item.symbol} · {item.state}</button>)}</section>
      <section><h2>Pinned work</h2><button type="button" onClick={() => onSelectOpportunity("inq-nvda-ignition")}>NVDA candidate v0.7.3</button></section>
      <section><h2>Watchlist</h2><p>NVDA <span>+2.7%</span></p><p>ES <span>-0.2%</span></p></section>
      <section><h2>Research jobs</h2><p>1 active · 1 needs attention</p></section>
      {onSwitchMode ? <button type="button" className="switch-mode" onClick={onSwitchMode}>Switch mode</button> : null}
    </aside>
  );
}
```

- [ ] **Step 4: Implement the shell and initial page orchestrator**

```tsx
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { ResearchSection, ResearchSnapshot } from "./contracts";
import { ResearchSidebar } from "./ResearchSidebar";

type Props = {
  children: ReactNode;
  section: ResearchSection;
  snapshot: ResearchSnapshot;
  onSelectOpportunity: (id: string) => void;
  onSectionChange: (section: ResearchSection) => void;
  onSwitchMode?: () => void;
};

export function ResearchShell({ children, section, snapshot, onSelectOpportunity, onSectionChange, onSwitchMode }: Props) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const menuRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!drawerOpen) return;
    sidebarRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      menuRef.current?.focus();
    };
  }, [drawerOpen]);
  return (
    <div className="research-workstation">
      <div ref={sidebarRef}><ResearchSidebar active={section} opportunities={snapshot.opportunities} drawerOpen={drawerOpen} onCloseDrawer={() => setDrawerOpen(false)} onSelectOpportunity={onSelectOpportunity} onSectionChange={onSectionChange} onSwitchMode={onSwitchMode} /></div>
      {drawerOpen ? <button type="button" className="research-sidebar-backdrop" aria-label="Close Research navigation" onClick={() => setDrawerOpen(false)} /> : null}
      <div className="research-surface">
        <header className="research-mobile-header"><button ref={menuRef} type="button" aria-label="Open Research navigation" onClick={() => setDrawerOpen(true)}>Menu</button><strong>Research</strong></header>
        <div className="research-fixture-banner" role="status">FIXTURE · {snapshot.context.asOf.slice(0, 16).replace("T", " ")} UTC · RESEARCH ONLY · EXECUTION NONE</div>
        {children}
      </div>
    </div>
  );
}
```

```tsx
import { useMemo, useState } from "react";
import type { ResearchDataAdapter, ResearchSection } from "./research/contracts";
import { createFixtureResearchAdapter } from "./research/researchAdapter";
import { ResearchShell } from "./research/ResearchShell";
import { ResearchStateNotice } from "./research/ResearchStateNotice";
import { useResearchWorkstation } from "./research/useResearchWorkstation";

type Props = { adapter?: ResearchDataAdapter; onSwitchMode?: () => void };
export function ResearchPage({ adapter, onSwitchMode }: Props) {
  const stableAdapter = useMemo(() => adapter ?? createFixtureResearchAdapter(), [adapter]);
  const { error, loading, retry, snapshot } = useResearchWorkstation(stableAdapter);
  const [section, setSection] = useState<ResearchSection>("COMMAND");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  if (loading) return <ResearchStateNotice kind="LOADING" />;
  if (error || !snapshot) return <ResearchStateNotice kind="ERROR" onRetry={retry} />;
  if (snapshot.capability.state === "UNSUPPORTED") return <ResearchStateNotice kind="UNSUPPORTED" />;
  if (!snapshot.opportunities.length) return <ResearchStateNotice kind="EMPTY" />;
  const selected = snapshot.opportunities.find((item) => item.id === selectedId) ?? snapshot.opportunities[0];
  return (
    <ResearchShell section={section} snapshot={snapshot} onSelectOpportunity={setSelectedId} onSectionChange={setSection} onSwitchMode={onSwitchMode}>
      <main className="research-main">
        {section === "COMMAND" ? <><h1>Research Command</h1><p>Highest-value investigations first. Fixture-backed and non-executable.</p><p>Selected inquiry: {selected.symbol}</p></> : <section role="status"><h1>{section[0] + section.slice(1).toLowerCase()} workspace not connected</h1><p>This destination is scheduled for the workflow-workspaces milestone. No result or progress is being simulated.</p></section>}
      </main>
    </ResearchShell>
  );
}
```

- [ ] **Step 5: Run tests, build, changed validation, and commit**

Run from `ui`: `npm.cmd test -- src/components/research/ResearchPage.test.tsx`

Expected: PASS, 4 tests.

Run from `ui`: `npm.cmd run build`

Expected: PASS.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS.

```powershell
git add ui/src/components/ResearchPage.tsx ui/src/components/research/ResearchShell.tsx ui/src/components/research/ResearchSidebar.tsx ui/src/components/research/ResearchStateNotice.tsx ui/src/components/research/ResearchPage.test.tsx
git commit -m "feat(ui): add research workstation shell"
```

### Task 5: Implement the fast command bar and first-viewport Command surface

**Files:**
- Create: `ui/src/components/research/GlobalCommandBar.tsx`
- Create: `ui/src/components/research/MarketContextBar.tsx`
- Create: `ui/src/components/research/PriorityBriefing.tsx`
- Create: `ui/src/components/research/OpportunityQueue.tsx`
- Create: `ui/src/components/research/ResearchJobActivity.tsx`
- Create: `ui/src/components/research/QualificationGatePanel.tsx`
- Create: `ui/src/components/research/DemoPackagePreview.tsx`
- Create: `ui/src/components/research/ResearchCommandHome.tsx`
- Test: `ui/src/components/research/GlobalCommandBar.test.tsx`
- Modify: `ui/src/components/ResearchPage.tsx`

**Interfaces:**
- Consumes: Task 3 contracts, `adapter.previewCommand`, `adapter.launchReviewedTest`, snapshot, and selected opportunity.
- Produces: `GlobalCommandBar`, `ResearchCommandHome`, and callbacks `onSelectOpportunity(id)` and `onOpenWorkspace()`.

- [ ] **Step 1: Write failing command safety tests**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GlobalCommandBar } from "./GlobalCommandBar";
import { createFixtureResearchAdapter } from "./researchAdapter";

it("runs read-only lookup without a review dialog", () => {
  const adapter = createFixtureResearchAdapter();
  render(<GlobalCommandBar adapter={adapter} onJobCreated={vi.fn()} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "NVDA" } });
  fireEvent.submit(screen.getByRole("search"));
  expect(screen.getByText(/SEARCH · NVDA/i)).toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("reviews scope, cutoff, inputs, and baseline before a test launch", async () => {
  const adapter = createFixtureResearchAdapter();
  const onJobCreated = vi.fn();
  render(<GlobalCommandBar adapter={adapter} onJobCreated={onJobCreated} />);
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Compare NVDA ignition models during stressed liquidity" } });
  fireEvent.submit(screen.getByRole("search"));
  const dialog = screen.getByRole("dialog", { name: "Review research test" });
  expect(dialog).toHaveTextContent("2026-08-30T14:30:00Z");
  expect(dialog).toHaveTextContent("BUY_AND_HOLD_30M_V2");
  fireEvent.click(screen.getByRole("button", { name: "Launch reviewed test" }));
  expect(await screen.findByText("Fixture run accepted; duration is not measurable.")).toBeInTheDocument();
  expect(onJobCreated).toHaveBeenCalledOnce();
});
```

Also append this acceptance behavior to `ResearchPage.test.tsx`:

```tsx
it("previews a blocked immutable Demo package without performing a handoff", async () => {
  render(<ResearchPage adapter={createFixtureResearchAdapter()} />);
  fireEvent.click(await screen.findByRole("button", { name: "Preview immutable Demo package" }));
  const dialog = screen.getByRole("dialog", { name: "Immutable Demo package preview" });
  expect(dialog).toHaveTextContent("BLOCKED · Regime robustness");
  expect(dialog).toHaveTextContent(/does not create a package/i);
  expect(screen.queryByRole("button", { name: /promote|hand off/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused command test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/research/GlobalCommandBar.test.tsx`

Expected: FAIL because `GlobalCommandBar` does not exist.

- [ ] **Step 3: Implement the command bar with reviewed launch**

```tsx
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { CommandPreview, ResearchDataAdapter, ResearchJob } from "./contracts";

type Props = { adapter: ResearchDataAdapter; onJobCreated: (job: ResearchJob) => void };
export function GlobalCommandBar({ adapter, onJobCreated }: Props) {
  const [input, setInput] = useState("");
  const [preview, setPreview] = useState<CommandPreview | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const next = adapter.previewCommand(input);
    if (next.reviewRequired) setPreview(next);
    else setResult(`${next.action} · ${next.instrument ?? next.input} · cutoff ${next.cutoff}`);
  };
  return (
    <>
      <form role="search" className="research-command-bar" onSubmit={submit}>
        <label className="sr-only" htmlFor="research-command">Search Research</label>
        <input ref={inputRef} id="research-command" type="search" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Search symbols, objects, or ask a research question" />
        <kbd>Ctrl K</kbd><button type="submit">Run</button>
      </form>
      {result ? <p className="command-result" role="status">{result}</p> : null}
      {preview ? (
        <div className="command-review-backdrop">
          <section className="command-review" role="dialog" aria-modal="true" aria-labelledby="command-review-title">
            <h2 id="command-review-title">Review research test</h2>
            <dl><dt>Action</dt><dd>{preview.action}</dd><dt>Instrument</dt><dd>{preview.instrument ?? "Market"}</dd><dt>Cutoff</dt><dd>{preview.cutoff}</dd><dt>Baseline</dt><dd>{preview.baseline}</dd><dt>Inputs</dt><dd>{preview.inputs.join(" · ")}</dd></dl>
            <button type="button" onClick={() => setPreview(null)}>Cancel</button>
            <button type="button" onClick={async () => { const job = await adapter.launchReviewedTest(preview); onJobCreated(job); setResult(job.detail); setPreview(null); }}>Launch reviewed test</button>
          </section>
        </div>
      ) : null}
    </>
  );
}
```

- [ ] **Step 4: Implement first-viewport presentation components**

```tsx
import type { ResearchContext } from "./contracts";
export function MarketContextBar({ context }: { context: ResearchContext }) {
  return <section className="market-context" aria-label="Market and cross-asset context"><span>{context.regime}</span><span>{context.rates}</span><span>{context.volatility}</span><span>{context.freshness}</span><time dateTime={context.asOf}>{context.asOf.slice(11, 16)} UTC</time></section>;
}
```

```tsx
import type { ResearchSnapshot } from "./contracts";
export function PriorityBriefing({ briefing }: { briefing: ResearchSnapshot["briefing"] }) {
  return <section className="priority-briefing"><p className="panel-eyebrow">Most important now</p><h2>{briefing.headline}</h2><p>{briefing.summary}</p><dl><dt>Main risk</dt><dd>{briefing.mainRisk}</dd><dt>Best next action</dt><dd>{briefing.nextAction}</dd></dl></section>;
}
```

```tsx
import type { ResearchOpportunity } from "./contracts";
export function OpportunityQueue({ items, selectedId, onSelect }: { items: ResearchOpportunity[]; selectedId: string; onSelect: (id: string) => void }) {
  return <section className="opportunity-queue"><header><div><p className="panel-eyebrow">Opportunity queue</p><h2>Ranked by decision value</h2></div><span>Research candidates · not trade instructions</span></header><ol>{items.map((item) => <li key={item.id}><button type="button" aria-pressed={selectedId === item.id} onClick={() => onSelect(item.id)}><span>#{item.rank}</span><strong>{item.symbol}</strong><span>{item.investigatedDirection}</span><span>{item.title}</span><span>{item.estimatedAdvantageBps === null ? "ADVANTAGE UNKNOWN" : `+${item.estimatedAdvantageBps} bp vs baseline`}</span><span>{item.evidenceStrength} evidence</span><small>Risk: {item.primaryRisk}</small></button></li>)}</ol></section>;
}
```

```tsx
import type { ResearchJob } from "./contracts";
export function ResearchJobActivity({ jobs }: { jobs: ResearchJob[] }) {
  return <section className="job-activity"><p className="panel-eyebrow">Automated work</p><h2>Research jobs</h2><ul>{jobs.map((job) => <li key={job.id} data-state={job.status.toLowerCase()}><strong>{job.label}</strong><span>{job.status}</span><p>{job.detail}</p>{job.progress === null ? <span role="progressbar" aria-label={`${job.label} progress`}>Duration unknown</span> : <progress aria-label={`${job.label} progress`} value={job.progress} max={100}>{job.progress}%</progress>}<details><summary>Run inputs and authority</summary><dl><dt>Trigger</dt><dd>{job.trigger}</dd><dt>Cutoff</dt><dd>{job.cutoff}</dd><dt>Inputs</dt><dd>{job.inputs.join(" · ")}</dd><dt>Candidate</dt><dd>{job.candidateVersion ?? "No candidate"}</dd><dt>Baseline</dt><dd>{job.baseline}</dd><dt>Result</dt><dd>{job.result}</dd><dt>Warnings</dt><dd>{job.warnings.length ? job.warnings.join(" · ") : "None"}</dd><dt>Permitted next actions</dt><dd>{job.permittedNextActions.join(" · ")}</dd></dl><code>{job.traceRef}</code></details></li>)}</ul></section>;
}
```

```tsx
import { useEffect, useRef } from "react";
import type { QualificationGate, ResearchOpportunity } from "./contracts";

export function DemoPackagePreview({ candidate, gates, onClose }: { candidate: ResearchOpportunity; gates: QualificationGate[]; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const opener = useRef(document.activeElement as HTMLElement | null);
  const blocked = gates.filter((gate) => gate.state === "BLOCKED");
  useEffect(() => { closeRef.current?.focus(); return () => opener.current?.focus(); }, []);
  return <section className="demo-package-preview" role="dialog" aria-modal="true" aria-labelledby="demo-package-title" onKeyDown={(event) => { if (event.key === "Escape") onClose(); }}><header><h2 id="demo-package-title">Immutable Demo package preview</h2><button ref={closeRef} type="button" onClick={onClose}>Close package preview</button></header><dl><dt>Candidate</dt><dd>{candidate.symbol} · fixture candidate v0.7.3</dd><dt>Entry and exit logic</dt><dd>Frozen by candidate version</dd><dt>Declared baseline</dt><dd>{candidate.baseline}</dd><dt>Evidence bundle</dt><dd>4 admitted fixture references</dd><dt>Qualification</dt><dd>{blocked.length ? `BLOCKED · ${blocked[0].label}` : "QUALIFIED FOR PREVIEW"}</dd></dl><p>This preview does not create a package, mutate a registry, or hand anything to Demo.</p></section>;
}
```

```tsx
import { useState } from "react";
import type { QualificationGate, ResearchOpportunity } from "./contracts";
import { DemoPackagePreview } from "./DemoPackagePreview";

export function QualificationGatePanel({ candidate, gates }: { candidate: ResearchOpportunity; gates: QualificationGate[] }) {
  const [previewOpen, setPreviewOpen] = useState(false);
  const weakest = gates.find((gate) => gate.state === "BLOCKED");
  return <section className="qualification-panel"><p className="panel-eyebrow">Demo qualification</p><h2>{weakest ? "Blocked" : "Ready for package preview"}</h2>{weakest ? <p><strong>Weakest gate: {weakest.label}</strong> — {weakest.explanation}</p> : null}<ul>{gates.map((gate) => <li key={gate.id} data-state={gate.state.toLowerCase()}><span>{gate.state}</span><strong>{gate.label}</strong><small>{gate.policyRef}</small></li>)}</ul><button type="button" onClick={() => setPreviewOpen(true)}>Preview immutable Demo package</button><p>No backend promotion occurs in this milestone.</p>{previewOpen ? <DemoPackagePreview candidate={candidate} gates={gates} onClose={() => setPreviewOpen(false)} /> : null}</section>;
}
```

```tsx
import type { ResearchJob, ResearchSnapshot } from "./contracts";
import { MarketContextBar } from "./MarketContextBar";
import { OpportunityQueue } from "./OpportunityQueue";
import { PriorityBriefing } from "./PriorityBriefing";
import { QualificationGatePanel } from "./QualificationGatePanel";
import { ResearchJobActivity } from "./ResearchJobActivity";

export function ResearchCommandHome({ snapshot, jobs, selectedId, onSelect }: { snapshot: ResearchSnapshot; jobs: ResearchJob[]; selectedId: string; onSelect: (id: string) => void }) {
  const qualificationCandidate = snapshot.opportunities.find((item) => item.state === "CANDIDATE") ?? snapshot.opportunities[0];
  return <><MarketContextBar context={snapshot.context} /><div className="research-command-grid"><PriorityBriefing briefing={snapshot.briefing} /><OpportunityQueue items={snapshot.opportunities} selectedId={selectedId} onSelect={onSelect} /><ResearchJobActivity jobs={jobs} /><QualificationGatePanel candidate={qualificationCandidate} gates={snapshot.gates} /></div></>;
}
```

- [ ] **Step 5: Wire command state and Command home into `ResearchPage`**

Replace `ResearchPage.tsx` with this complete orchestration; loaded-only state stays inside `LoadedResearchPage`, and deferred workflow destinations remain honest:

```tsx
import { useMemo, useState } from "react";
import type { ResearchDataAdapter, ResearchSection, ResearchSnapshot } from "./research/contracts";
import { GlobalCommandBar } from "./research/GlobalCommandBar";
import { ResearchCommandHome } from "./research/ResearchCommandHome";
import { createFixtureResearchAdapter } from "./research/researchAdapter";
import { ResearchShell } from "./research/ResearchShell";
import { ResearchStateNotice } from "./research/ResearchStateNotice";
import { useResearchWorkstation } from "./research/useResearchWorkstation";

type Props = { adapter?: ResearchDataAdapter; onSwitchMode?: () => void };
function LoadedResearchPage({ adapter, snapshot, onSwitchMode }: { adapter: ResearchDataAdapter; snapshot: ResearchSnapshot; onSwitchMode?: () => void }) {
  const [section, setSection] = useState<ResearchSection>("COMMAND");
  const [selectedId, setSelectedId] = useState(snapshot.opportunities[0].id);
  const [jobs, setJobs] = useState(snapshot.jobs);
  const selected = snapshot.opportunities.find((item) => item.id === selectedId) ?? snapshot.opportunities[0];
  return <ResearchShell section={section} snapshot={snapshot} onSelectOpportunity={setSelectedId} onSectionChange={setSection} onSwitchMode={onSwitchMode}><GlobalCommandBar adapter={adapter} onJobCreated={(job) => setJobs((current) => [job, ...current])} /><main className="research-main">{section === "COMMAND" ? <><header className="research-page-header"><div><p className="panel-eyebrow">Research workstation</p><h1>Research Command</h1></div><p>Highest-value investigations first. Every result remains traceable and non-executable.</p></header><ResearchCommandHome snapshot={snapshot} jobs={jobs} selectedId={selected.id} onSelect={setSelectedId} /></> : <section className="research-state" role="status"><h1>{section[0] + section.slice(1).toLowerCase()} workspace not connected</h1><p>This destination is scheduled for the workflow-workspaces milestone. No result or progress is being simulated.</p></section>}</main></ResearchShell>;
}

export function ResearchPage({ adapter, onSwitchMode }: Props) {
  const stableAdapter = useMemo(() => adapter ?? createFixtureResearchAdapter(), [adapter]);
  const { error, loading, retry, snapshot } = useResearchWorkstation(stableAdapter);
  if (loading) return <ResearchStateNotice kind="LOADING" />;
  if (error || !snapshot) return <ResearchStateNotice kind="ERROR" onRetry={retry} />;
  if (snapshot.capability.state === "UNSUPPORTED") return <ResearchStateNotice kind="UNSUPPORTED" />;
  if (!snapshot.opportunities.length) return <ResearchStateNotice kind="EMPTY" />;
  return <LoadedResearchPage adapter={stableAdapter} snapshot={snapshot} onSwitchMode={onSwitchMode} />;
}
```

- [ ] **Step 6: Run command and page tests, changed validation, and commit**

Run from `ui`: `npm.cmd test -- src/components/research/GlobalCommandBar.test.tsx src/components/research/ResearchPage.test.tsx`

Expected: PASS.

Run from `ui`: `npm.cmd test`

Expected: all frontend tests PASS.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS.

```powershell
git add ui/src/components/ResearchPage.tsx ui/src/components/research/ResearchPage.test.tsx ui/src/components/research/GlobalCommandBar.tsx ui/src/components/research/GlobalCommandBar.test.tsx ui/src/components/research/MarketContextBar.tsx ui/src/components/research/PriorityBriefing.tsx ui/src/components/research/OpportunityQueue.tsx ui/src/components/research/ResearchJobActivity.tsx ui/src/components/research/QualificationGatePanel.tsx ui/src/components/research/DemoPackagePreview.tsx ui/src/components/research/ResearchCommandHome.tsx
git commit -m "feat(ui): add research command center"
```

### Task 6: Add the unified detail workspace, evidence rail, and meaningful charts

**Files:**
- Create: `ui/src/components/research/MeaningfulCharts.tsx`
- Create: `ui/src/components/research/EvidenceRail.tsx`
- Create: `ui/src/components/research/ResearchWorkspace.tsx`
- Create: `ui/src/components/research/ResearchDrawers.tsx`
- Test: `ui/src/components/research/ResearchWorkspace.test.tsx`
- Modify: `ui/src/components/ResearchPage.tsx`

**Interfaces:**
- Consumes: selected `ResearchOpportunity`, snapshot price/comparison/evidence/gates, and drawer callbacks.
- Produces: two charts only—instrument context and candidate-versus-baseline—plus `ExplanationDrawer` and `ProvenanceDrawer`.

- [ ] **Step 1: Write failing workspace and chart-policy tests**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ResearchWorkspace } from "./ResearchWorkspace";
import { readyResearchSnapshot } from "./fixtures";

const opportunity = readyResearchSnapshot.opportunities[0];
it("states the question and text summary for every chart", () => {
  render(<ResearchWorkspace opportunity={opportunity} snapshot={readyResearchSnapshot} onExplain={vi.fn()} onProvenance={vi.fn()} />);
  expect(screen.getByRole("img", { name: /Did price and volume confirm the proposed entry/i })).toBeInTheDocument();
  expect(screen.getByText(/observed expansion reached 131.42/i)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Does candidate v0.7.3 beat its declared baseline across regimes/i })).toBeInTheDocument();
  expect(screen.getByText(/Thin liquidity is the only displayed cohort below baseline/i)).toBeInTheDocument();
});

it("keeps epistemic classes and conflicts visible", () => {
  render(<ResearchWorkspace opportunity={opportunity} snapshot={readyResearchSnapshot} onExplain={vi.fn()} onProvenance={vi.fn()} />);
  expect(screen.getByText("OBSERVED_FACT")).toBeInTheDocument();
  expect(screen.getByText("REPORTED_CLAIM")).toBeInTheDocument();
  expect(screen.getByText("MODEL_OUTPUT")).toBeInTheDocument();
  expect(screen.getByText("CONFLICTING")).toBeInTheDocument();
  expect(screen.getByText("MISSING")).toBeInTheDocument();
});

it("opens explanation and provenance without exposing order actions", () => {
  const onExplain = vi.fn(); const onProvenance = vi.fn();
  render(<ResearchWorkspace opportunity={opportunity} snapshot={readyResearchSnapshot} onExplain={onExplain} onProvenance={onProvenance} />);
  fireEvent.click(screen.getByRole("button", { name: "Explain conclusion" }));
  fireEvent.click(screen.getByRole("button", { name: "Inspect provenance" }));
  expect(onExplain).toHaveBeenCalledOnce(); expect(onProvenance).toHaveBeenCalledOnce();
  expect(screen.queryByRole("button", { name: /buy|sell|place order/i })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused workspace test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/research/ResearchWorkspace.test.tsx`

Expected: FAIL because workspace and chart components do not exist.

- [ ] **Step 3: Implement the two meaningful charts**

```tsx
import { Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ComparisonPoint, PricePoint } from "./contracts";

export function InstrumentContextChart({ symbol, points }: { symbol: string; points: PricePoint[] }) {
  const latest = points.at(-1)?.price;
  return <section className="meaningful-chart"><h3>Did price and volume confirm the proposed entry?</h3><p id="instrument-chart-summary">From {points[0]?.time ?? "unknown"} to {points.at(-1)?.time ?? "unknown"} UTC, observed expansion reached {latest?.toFixed(2)}; the invalidation marker is the primary risk and volume is contextual, not a second signal.</p><div role="img" aria-label={`Did price and volume confirm the proposed entry for ${symbol}? ${points.length} fixture observations.`} aria-describedby="instrument-chart-summary"><ResponsiveContainer width="100%" height={250}><ComposedChart data={points}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" /><XAxis dataKey="time" /><YAxis yAxisId="price" domain={["dataMin - 1", "dataMax + 1"]} /><YAxis yAxisId="volume" orientation="right" hide /><Tooltip /><Bar yAxisId="volume" dataKey="volume" fill="var(--chart-volume)" opacity={0.32} /><Line yAxisId="price" type="monotone" dataKey="price" stroke="var(--intelligence-cyan)" strokeWidth={2} dot={false} /></ComposedChart></ResponsiveContainer></div><table className="chart-data-table"><caption>Accessible price and volume values</caption><thead><tr><th>Time</th><th>Price</th><th>Volume</th><th>Context</th></tr></thead><tbody>{points.map((point) => <tr key={point.time}><td>{point.time}</td><td>{point.price}</td><td>{point.volume}</td><td>{point.marker ?? "Observed"}</td></tr>)}</tbody></table></section>;
}

export function BaselineComparisonChart({ points }: { points: ComparisonPoint[] }) {
  return <section className="meaningful-chart"><h3>Does candidate v0.7.3 beat its declared baseline across regimes?</h3><p id="comparison-chart-summary">Across the three displayed cohorts at the fixture cutoff, thin liquidity is the only cohort below baseline; that weakness is the primary risk and blocks Demo qualification.</p><div role="img" aria-label="Does candidate v0.7.3 beat its declared baseline across regimes? Thin liquidity underperforms." aria-describedby="comparison-chart-summary"><ResponsiveContainer width="100%" height={250}><BarChart data={points}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" /><XAxis dataKey="cohort" /><YAxis /><Tooltip /><Bar dataKey="candidate" fill="var(--intelligence-purple)" /><Bar dataKey="baseline" fill="var(--chart-baseline)" /></BarChart></ResponsiveContainer></div><table className="chart-data-table"><caption>Candidate and baseline basis-point results</caption><thead><tr><th>Cohort</th><th>Candidate</th><th>Baseline</th></tr></thead><tbody>{points.map((point) => <tr key={point.cohort}><td>{point.cohort}</td><td>{point.candidate}</td><td>{point.baseline}</td></tr>)}</tbody></table></section>;
}
```

- [ ] **Step 4: Implement evidence rail and workspace composition**

```tsx
import type { EvidenceItem, ResearchOpportunity } from "./contracts";
export function EvidenceRail({ opportunity, evidence, onExplain, onProvenance }: { opportunity: ResearchOpportunity; evidence: EvidenceItem[]; onExplain: () => void; onProvenance: () => void }) {
  return <aside className="evidence-rail" aria-label="Evidence, risk, and next action"><section><p className="panel-eyebrow">Evidence</p><ul>{evidence.map((item) => <li key={item.id} data-state={item.state.toLowerCase()}><span>{item.epistemicClass}</span><strong>{item.label}</strong><em>{item.state}</em><p>{item.summary}</p></li>)}</ul></section><section><p className="panel-eyebrow">Primary risk</p><p>{opportunity.primaryRisk}</p><p><strong>Invalidation:</strong> {opportunity.invalidation}</p><p><strong>Uncertainty:</strong> {opportunity.uncertainty}</p></section><section className="evidence-actions"><button type="button" onClick={onExplain}>Explain conclusion</button><button type="button" onClick={onProvenance}>Inspect provenance</button></section></aside>;
}
```

```tsx
import type { ResearchOpportunity, ResearchSnapshot } from "./contracts";
import { EvidenceRail } from "./EvidenceRail";
import { BaselineComparisonChart, InstrumentContextChart } from "./MeaningfulCharts";

export function ResearchWorkspace({ opportunity, snapshot, onExplain, onProvenance }: { opportunity: ResearchOpportunity; snapshot: ResearchSnapshot; onExplain: () => void; onProvenance: () => void }) {
  const lifecycle = ["SIGNAL", "INQUIRY", "HYPOTHESIS", "CANDIDATE", "EXPERIMENTS", "VERDICT", "DEMO PACKAGE"];
  return <section className="research-workspace" aria-labelledby="workspace-title"><header><div><p className="panel-eyebrow">{opportunity.state} · {opportunity.investigatedDirection}</p><h2 id="workspace-title">{opportunity.symbol} · {opportunity.title}</h2></div><div><strong>{opportunity.lastPrice}</strong><span>{opportunity.priceChangePct > 0 ? "+" : ""}{opportunity.priceChangePct}%</span></div></header><ol className="research-lifecycle" aria-label="Research lifecycle">{lifecycle.map((stage) => <li key={stage} aria-current={stage === opportunity.state ? "step" : undefined}>{stage}</li>)}</ol><nav aria-label="Research detail sections"><span>Summary</span><span>Market context</span><span>Evidence</span><span>Reasoning</span><span>Risks</span><span>Test history</span><span>Verdict</span><span>Next action</span></nav><div className="workspace-grid"><div className="workspace-content"><section className="workspace-summary"><h3>Why now</h3><p>{opportunity.whyNow}</p><dl><dt>Timing window</dt><dd>{opportunity.timingWindow}</dd><dt>Declared baseline</dt><dd>{opportunity.baseline}</dd><dt>Estimated advantage</dt><dd>{opportunity.estimatedAdvantageBps === null ? "Insufficient evidence" : `${opportunity.estimatedAdvantageBps} bp`}</dd></dl></section><div className="chart-grid"><InstrumentContextChart symbol={opportunity.symbol} points={snapshot.prices[opportunity.symbol] ?? []} />{opportunity.state === "CANDIDATE" ? <BaselineComparisonChart points={snapshot.comparison} /> : <section className="research-state" role="status"><h3>Baseline comparison unavailable</h3><p>This inquiry has no frozen candidate version, so no candidate-performance chart is claimed.</p></section>}</div></div><EvidenceRail opportunity={opportunity} evidence={snapshot.evidence} onExplain={onExplain} onProvenance={onProvenance} /></div></section>;
}
```

- [ ] **Step 5: Implement focus-restoring explanation and provenance drawers**

```tsx
import { useEffect, useRef } from "react";
import type { ResearchOpportunity, ResearchSnapshot } from "./contracts";

type Props = { kind: "EXPLANATION" | "PROVENANCE"; opportunity: ResearchOpportunity; snapshot: ResearchSnapshot; onClose: () => void };
export function ResearchDrawer({ kind, opportunity, snapshot, onClose }: Props) {
  const drawerRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const opener = useRef(document.activeElement as HTMLElement | null);
  useEffect(() => { closeRef.current?.focus(); return () => opener.current?.focus(); }, []);
  return <aside ref={drawerRef} className="research-drawer" role="dialog" aria-modal="true" aria-labelledby="research-drawer-title" onKeyDown={(event) => { if (event.key === "Escape") onClose(); if (event.key === "Tab") { const focusable = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>("button,[href],input,select,textarea,[tabindex]:not([tabindex='-1'])") ?? []); const first = focusable[0]; const last = focusable.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); } } }}><header><h2 id="research-drawer-title">{kind === "EXPLANATION" ? "Why this conclusion" : "Reproduce this view"}</h2><button ref={closeRef} type="button" onClick={onClose}>Close</button></header>{kind === "EXPLANATION" ? <div><p>{snapshot.briefing.summary}</p><p><strong>Risk:</strong> {opportunity.primaryRisk}</p><p><strong>Invalidation:</strong> {opportunity.invalidation}</p></div> : <dl><dt>Cutoff</dt><dd>{snapshot.context.cutoff}</dd><dt>Data mode</dt><dd>{snapshot.context.dataMode}</dd><dt>Candidate</dt><dd>{opportunity.state === "CANDIDATE" ? "v0.7.3" : "No frozen candidate"}</dd><dt>Baseline</dt><dd>{opportunity.baseline}</dd><dt>Sources</dt><dd>{snapshot.evidence.map((item) => item.source).join(" · ")}</dd></dl>}</aside>;
}
```

- [ ] **Step 6: Wire workspace selection and drawers into `LoadedResearchPage`**

After `ResearchCommandHome`, add:

```tsx
<ResearchWorkspace
  opportunity={selected}
  snapshot={snapshot}
  onExplain={() => setDrawer("EXPLANATION")}
  onProvenance={() => setDrawer("PROVENANCE")}
/>
{drawer ? <ResearchDrawer kind={drawer} opportunity={selected} snapshot={snapshot} onClose={() => setDrawer(null)} /> : null}
```

Add `const [drawer, setDrawer] = useState<"EXPLANATION" | "PROVENANCE" | null>(null);` and the required imports to `LoadedResearchPage`.

- [ ] **Step 7: Run workspace tests, all UI tests, changed validation, and commit**

Run from `ui`: `npm.cmd test -- src/components/research/ResearchWorkspace.test.tsx`

Expected: PASS, 3 tests.

Run from `ui`: `npm.cmd test`

Expected: all frontend tests PASS.

Run from repository root: `.venv\Scripts\python.exe tools\validate.py changed`

Expected: PASS.

```powershell
git add ui/src/components/ResearchPage.tsx ui/src/components/research/MeaningfulCharts.tsx ui/src/components/research/EvidenceRail.tsx ui/src/components/research/ResearchWorkspace.tsx ui/src/components/research/ResearchDrawers.tsx ui/src/components/research/ResearchWorkspace.test.tsx
git commit -m "feat(ui): add traceable research detail workspace"
```

### Task 7: Apply the approved visual system, responsive behavior, and App mode gate

**Files:**
- Modify: `ui/src/styles/tokens.css`
- Create: `ui/src/styles/mode-session.css`
- Create: `ui/src/styles/research-workstation.css`
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/components/mode-session/ModeSession.test.tsx`
- Modify: `ui/src/components/research/ResearchPage.test.tsx`

**Interfaces:**
- Consumes: mode-session and Research components from Tasks 1–6.
- Produces: the actual application entry flow, semantic theme tokens, desktop sidebar, narrow drawer, visible focus, and reduced-motion behavior.

- [ ] **Step 1: Add failing App integration and safety tests**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../App";

afterEach(() => vi.unstubAllGlobals());
it("opens at the three-mode launcher and enters the standalone Research workstation", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /Research/i }));
  expect(await screen.findByRole("heading", { name: "Research Command" })).toBeInTheDocument();
  expect(screen.getByText(/RESEARCH ONLY · EXECUTION NONE/i)).toBeInTheDocument();
});

it("switches back without remembering Research", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: /Research/i }));
  fireEvent.click(await screen.findByRole("button", { name: "Switch mode" }));
  expect(await screen.findByRole("heading", { name: /Choose how you enter/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused integration test and verify RED**

Run from `ui`: `npm.cmd test -- src/components/mode-session/ModeSession.test.tsx`

Expected: FAIL because `App` still renders the legacy shell directly.

- [ ] **Step 3: Add semantic tokens**

Append to `:root` in `tokens.css`:

```css
  --graphite-950: #05070b;
  --graphite-900: #090c12;
  --graphite-850: #0d1119;
  --graphite-800: #111722;
  --glass-matte: rgba(17, 23, 34, 0.82);
  --glass-strong: rgba(10, 14, 22, 0.94);
  --glass-border: rgba(155, 177, 210, 0.16);
  --glass-border-active: rgba(75, 224, 255, 0.48);
  --intelligence-cyan: #42e8ff;
  --intelligence-purple: #9a6cff;
  --outcome-positive: #38f58a;
  --outcome-negative: #ff4567;
  --state-caution: #ffc857;
  --chart-grid: rgba(154, 174, 204, 0.12);
  --chart-volume: #49647f;
  --chart-baseline: #758398;
  --research-sidebar-width: 248px;
```

- [ ] **Step 4: Add launcher CSS**

```css
.mode-session-surface{min-height:100vh;display:grid;isolation:isolate;color:var(--text-primary);background:radial-gradient(circle at 74% 12%,rgba(100,72,190,.18),transparent 34%),linear-gradient(145deg,var(--graphite-950),#09101c 58%,var(--graphite-950));}
.mode-launcher{width:min(1180px,calc(100% - 48px));margin:auto;padding:64px 0}.mode-launcher-header{max-width:760px;margin-bottom:48px}.mode-eyebrow,.mode-card-status{font:700 .68rem/1 var(--font-mono);letter-spacing:.14em;text-transform:uppercase;color:var(--intelligence-cyan)}
.mode-launcher h1,.mode-transition h1,.mode-dashboard h1{margin:12px 0;color:#f4f7fb;font-size:clamp(2.6rem,6vw,5.4rem);letter-spacing:-.055em;line-height:.96}.mode-launcher-header>p:last-child{max-width:620px;color:var(--text-secondary);line-height:1.65}
.mode-card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.mode-card{--mode-accent:var(--intelligence-cyan);display:grid;grid-template-rows:auto 1fr auto;gap:22px;min-height:260px;padding:27px;border:1px solid var(--glass-border);border-radius:10px;color:inherit;text-align:left;background:linear-gradient(145deg,rgba(28,38,55,.74),rgba(9,13,21,.92));box-shadow:0 24px 60px rgba(0,0,0,.34);backdrop-filter:blur(18px);cursor:pointer;transition:transform .16s ease,border-color .16s ease}.mode-card-demo{--mode-accent:var(--intelligence-purple)}.mode-card-live{--mode-accent:var(--state-caution)}.mode-card::before{content:"";position:absolute}.mode-card strong{align-self:end;font-size:clamp(2rem,4vw,3.2rem)}.mode-card-status{color:var(--mode-accent)}.mode-card>span:last-child{color:var(--text-secondary);line-height:1.55}.mode-card:hover{transform:translateY(-3px);border-color:var(--mode-accent)}
.startup-progress,.mode-transition,.live-confirmation{width:min(620px,calc(100% - 40px));margin:auto;padding:36px;border:1px solid var(--glass-border);border-radius:10px;background:var(--glass-strong);box-shadow:0 32px 90px rgba(0,0,0,.58)}.mode-transition-steps{display:grid;gap:10px;padding:0;list-style:none}.mode-transition-steps li[data-state=complete]{color:var(--outcome-positive)}.mode-transition-steps li[data-state=active]{color:var(--intelligence-cyan)}
.startup-progress [role=progressbar],.mode-transition [role=progressbar]{height:3px;margin-top:24px;overflow:hidden;background:rgba(255,255,255,.08)}.startup-progress [role=progressbar]::after,.mode-transition [role=progressbar]::after{content:"";display:block;width:40%;height:100%;background:linear-gradient(90deg,var(--intelligence-cyan),var(--intelligence-purple));animation:research-scan 1.15s ease-in-out infinite}
.live-confirmation-backdrop,.command-review-backdrop{position:fixed;z-index:100;inset:0;display:grid;place-items:center;background:rgba(2,4,8,.78);backdrop-filter:blur(10px)}.live-authority-summary{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--glass-border)}.live-authority-summary p{margin:0;padding:14px;color:var(--state-caution);background:var(--graphite-900)}.live-confirmation-actions,.mode-transition-actions{display:flex;gap:10px;margin-top:24px}
.mode-dashboard{grid-template-rows:auto 1fr}.mode-dashboard-bar{display:flex;justify-content:space-between;padding:16px 28px;border-bottom:1px solid var(--glass-border);background:var(--glass-matte)}.mode-dashboard-placeholder{align-self:center;width:min(820px,calc(100% - 40px));margin:auto}.mode-dashboard-empty{margin-top:28px;padding:20px;border:1px dashed var(--state-caution);color:var(--state-caution)}
@keyframes research-scan{from{transform:translateX(-120%)}to{transform:translateX(350%)}}
@media(max-width:760px){.mode-card-grid{grid-template-columns:1fr}.mode-launcher{width:min(100% - 28px,560px);padding:36px 0}.live-authority-summary{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.mode-card{transition:none}.mode-card:hover{transform:none}.startup-progress [role=progressbar]::after,.mode-transition [role=progressbar]::after{width:100%;animation:none}}
```

- [ ] **Step 5: Add Research workstation CSS**

```css
.research-workstation{min-height:100vh;display:grid;grid-template-columns:var(--research-sidebar-width) minmax(0,1fr);color:var(--text-primary);background:radial-gradient(circle at 62% -10%,rgba(66,232,255,.08),transparent 28%),var(--graphite-950)}
.research-sidebar{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:18px;padding:18px 14px;border-right:1px solid var(--glass-border);background:rgba(7,10,16,.96);overflow:auto}.research-brand{display:grid;grid-template-columns:auto 1fr;gap:2px 9px;align-items:center;padding:4px 6px 14px}.research-brand>span{grid-row:1/3;color:var(--intelligence-cyan);font:800 1.15rem var(--font-mono)}.research-brand small{color:var(--state-caution);font:.58rem var(--font-mono)}
.research-sidebar nav,.research-sidebar section{display:grid;gap:5px}.research-sidebar button{min-height:36px;border:1px solid transparent;border-radius:6px;color:var(--text-secondary);text-align:left;background:transparent;cursor:pointer}.research-sidebar nav button[aria-current=page]{color:white;border-color:var(--glass-border-active);background:linear-gradient(90deg,rgba(66,232,255,.11),rgba(154,108,255,.05))}.research-sidebar h2{margin:0;color:var(--text-muted);font:700 .62rem var(--font-mono);letter-spacing:.12em;text-transform:uppercase}.research-sidebar section button,.research-sidebar section p{margin:0;padding:6px;color:var(--text-secondary);font-size:.75rem}.research-sidebar .switch-mode{margin-top:auto;border-color:var(--glass-border)}
.research-surface{min-width:0}.research-fixture-banner{padding:7px 18px;border-bottom:1px solid rgba(255,200,87,.22);color:var(--state-caution);background:rgba(255,200,87,.045);font:650 .63rem var(--font-mono);letter-spacing:.06em}.research-mobile-header{display:none}.research-command-bar{position:sticky;z-index:20;top:0;display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;padding:12px 18px;border-bottom:1px solid var(--glass-border);background:rgba(5,7,11,.82);backdrop-filter:blur(18px)}.research-command-bar input{min-height:42px;padding:0 14px;border:1px solid var(--glass-border);border-radius:8px;color:white;background:var(--glass-matte)}.research-command-bar kbd{align-self:center;color:var(--text-muted);font:.65rem var(--font-mono)}
.research-main{padding:20px;max-width:1680px;margin:auto}.research-page-header{display:flex;justify-content:space-between;gap:28px;align-items:end;margin-bottom:15px}.research-page-header h1{margin:3px 0;font-size:clamp(1.8rem,3vw,2.8rem);letter-spacing:-.04em}.panel-eyebrow{margin:0;color:var(--intelligence-cyan);font:700 .62rem var(--font-mono);letter-spacing:.12em;text-transform:uppercase}.market-context{display:flex;gap:10px;overflow:auto;padding:9px 12px;border:1px solid var(--glass-border);border-radius:8px;background:var(--glass-matte)}.market-context span,.market-context time{white-space:nowrap;color:var(--text-secondary);font:.68rem var(--font-mono)}
.research-command-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(300px,.8fr);gap:14px;margin-top:14px}.priority-briefing,.opportunity-queue,.job-activity,.qualification-panel,.research-workspace,.meaningful-chart,.evidence-rail{border:1px solid var(--glass-border);border-radius:10px;background:linear-gradient(145deg,rgba(20,27,40,.82),rgba(10,14,22,.9));box-shadow:0 20px 48px rgba(0,0,0,.18);backdrop-filter:blur(16px)}.priority-briefing{padding:18px}.priority-briefing h2{max-width:780px;margin:8px 0;font-size:clamp(1.35rem,2.5vw,2.2rem)}.priority-briefing dl,.workspace-summary dl{display:grid;grid-template-columns:auto 1fr;gap:6px 12px}.priority-briefing dt,.workspace-summary dt{color:var(--text-muted)}
.opportunity-queue{grid-column:1;grid-row:2/4;padding:16px}.opportunity-queue header{display:flex;justify-content:space-between;gap:18px}.opportunity-queue ol,.job-activity ul,.qualification-panel ul,.evidence-rail ul{list-style:none;margin:12px 0 0;padding:0}.opportunity-queue li+li{margin-top:7px}.opportunity-queue button{width:100%;display:grid;grid-template-columns:40px 70px 72px minmax(180px,1fr) auto auto;gap:10px;align-items:center;padding:13px;border:1px solid var(--glass-border);border-radius:7px;color:var(--text-secondary);text-align:left;background:rgba(5,8,14,.5);cursor:pointer}.opportunity-queue button[aria-pressed=true]{border-color:var(--glass-border-active);box-shadow:inset 3px 0 var(--intelligence-cyan)}.opportunity-queue strong{color:white;font:800 1rem var(--font-mono)}.opportunity-queue small{grid-column:4/-1;color:var(--state-caution)}
.job-activity,.qualification-panel{padding:16px}.job-activity li,.qualification-panel li{display:grid;gap:5px;padding:10px 0;border-top:1px solid var(--glass-border)}.job-activity li[data-state=failed]{color:var(--outcome-negative)}.qualification-panel li{grid-template-columns:70px 1fr}.qualification-panel li[data-state=pass]>span{color:var(--outcome-positive)}.qualification-panel li[data-state=blocked]>span{color:var(--outcome-negative)}
.research-workspace{margin-top:14px;padding:16px}.research-workspace>header{display:flex;justify-content:space-between;gap:20px}.research-workspace h2{margin:5px 0}.research-lifecycle{display:flex;gap:5px;overflow:auto;margin:12px 0;padding:0;list-style:none}.research-lifecycle li{white-space:nowrap;padding:5px 7px;border:1px solid var(--glass-border);color:var(--text-muted);font:.58rem var(--font-mono)}.research-lifecycle li[aria-current=step]{border-color:var(--glass-border-active);color:var(--intelligence-cyan)}.research-workspace>nav{display:flex;gap:14px;overflow:auto;padding:12px 0;border-block:1px solid var(--glass-border);color:var(--text-muted);font:.65rem var(--font-mono)}.workspace-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;margin-top:14px}.workspace-summary{padding:4px 2px 12px}.chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.meaningful-chart{min-width:0;padding:14px}.meaningful-chart h3{margin:0 0 7px}.meaningful-chart>p{color:var(--text-secondary);font-size:.8rem}.chart-data-table{width:100%;border-collapse:collapse;font-size:.7rem}.chart-data-table caption{text-align:left;color:var(--text-muted)}.chart-data-table th,.chart-data-table td{padding:5px;border-bottom:1px solid var(--glass-border);text-align:left}.evidence-rail{padding:14px}.evidence-rail li{padding:10px 0;border-top:1px solid var(--glass-border)}.evidence-rail li>span,.evidence-rail li>em{display:inline-block;margin-right:6px;color:var(--intelligence-purple);font:.58rem var(--font-mono)}.evidence-rail li[data-state=conflicting]>em{color:var(--state-caution)}.evidence-actions{display:grid;gap:7px}
.research-drawer{position:fixed;z-index:80;top:0;right:0;width:min(430px,100%);height:100vh;padding:18px;border-left:1px solid var(--glass-border-active);background:var(--glass-strong);box-shadow:-28px 0 70px rgba(0,0,0,.5);overflow:auto}.research-drawer header{display:flex;justify-content:space-between}.command-review,.demo-package-preview{position:fixed;z-index:90;inset:50% auto auto 50%;transform:translate(-50%,-50%);width:min(620px,calc(100% - 32px));max-height:calc(100vh - 40px);overflow:auto;padding:24px;border:1px solid var(--glass-border-active);border-radius:10px;background:var(--glass-strong);box-shadow:0 28px 90px rgba(0,0,0,.65)}.command-review dl,.demo-package-preview dl{display:grid;grid-template-columns:120px 1fr;gap:8px}.demo-package-preview header{display:flex;justify-content:space-between;gap:16px}.research-state{width:min(680px,calc(100% - 32px));margin:18vh auto;padding:28px;border:1px solid var(--glass-border);background:var(--glass-strong)}
button:focus-visible,input:focus-visible{outline:2px solid var(--intelligence-cyan);outline-offset:2px}
@media(max-width:1100px){.research-command-grid{grid-template-columns:1fr}.opportunity-queue{grid-row:auto}.workspace-grid{grid-template-columns:1fr}.chart-grid{grid-template-columns:1fr}.evidence-rail{position:static}.opportunity-queue button{grid-template-columns:36px 65px 70px 1fr}.opportunity-queue button span:nth-of-type(4),.opportunity-queue button span:nth-of-type(5){grid-column:4}}
@media(max-width:760px){.research-workstation{grid-template-columns:1fr}.research-sidebar{position:fixed;z-index:70;inset:0 auto 0 0;width:min(var(--research-sidebar-width),84vw);transform:translateX(-105%);transition:transform .16s ease}.research-sidebar.open{transform:none}.research-sidebar-backdrop{position:fixed;z-index:60;inset:0;border:0;background:rgba(0,0,0,.62)}.research-mobile-header{display:flex;justify-content:space-between;padding:10px 14px}.research-page-header{display:block}.research-main{padding:12px}.opportunity-queue button{grid-template-columns:32px 62px 1fr}.opportunity-queue button>*{grid-column:auto}.opportunity-queue button span:nth-of-type(n+3),.opportunity-queue button small{grid-column:2/-1}.research-command-bar{padding:9px 12px}.research-command-bar kbd{display:none}}
@media(prefers-reduced-motion:reduce){.research-sidebar{transition:none}*{scroll-behavior:auto!important}}
```

- [ ] **Step 6: Gate the application without deleting the old shell**

In `App.tsx`:

1. Rename `function Shell()` to `export function LegacyShell()` so the old API-backed surface remains available for later Demo/Live integration.
2. Import `ApplicationBootstrap`, `ModePlaceholderDashboard`, `Mode`, `research-workstation.css`, and `mode-session.css`.
3. Add this destination function:

```tsx
function ModeDestination({ mode, onSwitchMode }: { mode: Mode; onSwitchMode: () => void }) {
  if (mode === "RESEARCH") return <ResearchPage onSwitchMode={onSwitchMode} />;
  return <ModePlaceholderDashboard mode={mode} onSwitchMode={onSwitchMode} />;
}
```

4. Replace `<Shell />` in the default export with:

```tsx
<ApplicationBootstrap>
  {(mode, onSwitchMode) => <ModeDestination mode={mode} onSwitchMode={onSwitchMode} />}
</ApplicationBootstrap>
```

Do not render `LegacyShell` from Research, Demo, or Live during this milestone because its mixed routes include authority-bearing paper/live surfaces that are not yet separated by the new mode contract.

- [ ] **Step 7: Run focused tests, all UI tests, build, searches, and changed validation**

Run from `ui`:

```powershell
npm.cmd test -- src/components/mode-session/ModeSession.test.tsx src/components/research/ResearchPage.test.tsx src/components/research/ResearchWorkspace.test.tsx
npm.cmd test
npm.cmd run build
```

Expected: all tests PASS and Vite build exits 0.

Run from repository root:

```powershell
rg -n "localStorage|sessionStorage|place order|connect broker|submit order" ui/src/components/mode-session ui/src/components/research
rg -n "var\(--outcome-positive\)|var\(--outcome-negative\)" ui/src/styles/research-workstation.css
.venv\Scripts\python.exe tools\validate.py changed --explain
```

Expected: the persistence/authority search returns no implementation matches; positive/negative tokens occur only in outcome or failure selectors; changed validation reports 0 failures and states whether FULL is required.

- [ ] **Step 8: Commit the integrated visual milestone**

```powershell
git add ui/src/App.tsx ui/src/styles/tokens.css ui/src/styles/mode-session.css ui/src/styles/research-workstation.css ui/src/components/mode-session/ModeSession.test.tsx ui/src/components/research/ResearchPage.test.tsx
git commit -m "feat(ui): integrate research workstation experience"
```

### Task 8: Exercise honest states, keyboard paths, responsiveness, and final validation

**Files:**
- Modify: `ui/src/components/research/ResearchPage.test.tsx`
- Create: `docs/product/ux/research-workstation-prototype-acceptance.md`

**Interfaces:**
- Consumes: the completed fixture adapters and application entry flow.
- Produces: executable acceptance coverage and a reproducible manual verification record; no new product capability.

- [ ] **Step 1: Add failing acceptance-state tests**

```tsx
it.each([
  ["EMPTY", "No investigations matched"],
  ["STALE", "STALE"],
  ["CONFLICTING", "CONFLICTING"],
  ["UNSUPPORTED", "Capability unavailable"],
  ["FAILED", "Research unavailable"],
] as const)("renders %s honestly", async (variant, expected) => {
  render(<ResearchPage adapter={createFixtureResearchAdapter(variant)} />);
  expect(await screen.findByText(expected)).toBeInTheDocument();
});

it("opens command search from Ctrl+K and closes the drawer on Escape", async () => {
  render(<ResearchPage adapter={createFixtureResearchAdapter()} />);
  await screen.findByRole("heading", { name: "Research Command" });
  fireEvent.keyDown(window, { key: "k", ctrlKey: true });
  expect(screen.getByRole("searchbox")).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Explain conclusion" }));
  const drawer = screen.getByRole("dialog", { name: "Why this conclusion" });
  fireEvent.keyDown(drawer, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "Why this conclusion" })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused test and verify RED where behavior is incomplete**

Run from `ui`: `npm.cmd test -- src/components/research/ResearchPage.test.tsx`

Expected: any missing stale/conflict presentation or keyboard behavior fails with the named assertion; no unrelated test should fail.

- [ ] **Step 3: Make stale and conflict status visible in the loaded page**

Immediately below `MarketContextBar` in `ResearchCommandHome`, render:

```tsx
{snapshot.context.freshness === "STALE" ? (
  <p className="research-warning" role="status">STALE · Data remains visible at cutoff {snapshot.context.cutoff}; no current-state claim is made.</p>
) : null}
{snapshot.evidence.some((item) => item.state === "CONFLICTING") ? (
  <p className="research-warning" role="status">CONFLICTING · Admitted evidence disagrees. Open the evidence rail before interpreting the candidate.</p>
) : null}
```

Add `.research-warning{padding:9px 12px;border:1px solid rgba(255,200,87,.35);color:var(--state-caution);background:rgba(255,200,87,.06)}` to `research-workstation.css`.

- [ ] **Step 4: Run all frontend verification**

Run from `ui`:

```powershell
npm.cmd test
npm.cmd run build
```

Expected: all Vitest tests PASS; Vite production build exits 0.

- [ ] **Step 5: Perform browser verification at three viewport widths**

Start the repository's existing UI/backend development environment. Verify at `1440×900`, `1024×768`, and `390×844`:

1. Fresh load shows real readiness, then Research / Demo / Live in that order.
2. Research opens the Command surface; desktop retains the left sidebar and mobile uses the drawer without page-level horizontal scrolling.
3. The first viewport shows context, most-important-now, ranked opportunity, primary risk, jobs, next action, and qualification state.
4. Selecting ES changes the detail header and instrument series without changing the rank order.
5. Ctrl+K focuses search; read-only `NVDA` search runs immediately; the comparison command requires review.
6. Both charts have named questions and textual/table alternatives; no ticker sparkline or chart wall appears.
7. Explanation and provenance drawers close on Escape and restore focus.
8. Demo and Live expose no order or broker actions; Live repeats confirmation after Switch mode.
9. With OS reduced motion enabled, cards/sidebar do not translate and progress remains understandable.

- [ ] **Step 6: Write the acceptance record**

Create `docs/product/ux/research-workstation-prototype-acceptance.md` with:

```markdown
# Research Workstation Prototype Acceptance

**Implementation scope:** Fixture-backed Research launcher and first milestone only

**Authority:** Research execution none; Demo and Live unavailable/locked

**Validated viewports:** 1440×900, 1024×768, 390×844

## Automated checks

- `cd ui; npm.cmd test`: PASS
- `cd ui; npm.cmd run build`: PASS
- `.venv\Scripts\python.exe tools\validate.py changed --explain`: PASS
- Full offline validation: record the exact selector result from Step 7

## Manual checks

- Launcher order, Live confirmation, Switch mode, and no persisted selection: PASS
- First-viewport priority and risk comprehension: PASS
- Sidebar desktop persistence and mobile drawer: PASS
- Command search and reviewed test launch: PASS
- Meaningful-chart questions, summaries, and tables: PASS
- Fixture, stale, conflict, unsupported, and failed labels: PASS
- Keyboard focus, Escape restoration, and reduced motion: PASS
- No Research paper, broker, or live-order authority: PASS

## Deferred by design

- Product Demo paper execution
- Product Live execution
- Real Research APIs
- Backend qualification or Research-to-Demo mutation
- Explore, Build, Test, Evaluate, and Promote deep workspaces
```

- [ ] **Step 7: Run repository final validation and inspect the exact change set**

Run from repository root:

```powershell
.venv\Scripts\python.exe tools\validate.py changed --explain
.venv\Scripts\python.exe tools\validate.py full
git status --short
git diff --check
git diff --stat
```

Expected: changed validation has 0 failures and 0 errors; full offline validation has 0 failures and 0 errors; no live provider suite is selected; diff check is silent; only intended UI and acceptance-document paths are present.

- [ ] **Step 8: Commit the acceptance checkpoint**

```powershell
git add ui/src/components/research/ResearchPage.test.tsx ui/src/components/research/ResearchCommandHome.tsx ui/src/styles/research-workstation.css docs/product/ux/research-workstation-prototype-acceptance.md
git diff --cached --check
git diff --cached --name-only
git commit -m "test(ui): accept research workstation prototype"
```

Expected staged paths are exactly the four paths above; the commit succeeds without including `evidence/ui1/assistant-audit/**` or any unrelated worktree dirt.

---

## Milestone boundary after Task 8

This plan ends with working, testable software for Stage 1 and Stage 2 of the approved specification: the revised launcher, standalone Research shell, Command home, opportunity selection, one detail workspace, evidence/provenance, job and qualification presentation, two meaningful charts, fixture variants, and accessibility/responsive foundations.

Create separate implementation plans before starting:

1. Explore / Build / Test / Evaluate / Promote deep workspaces and version history.
2. Real Research DTO/API integration and supported update transport.
3. Governed automated run records, immutable Demo-package creation, and Research-to-Demo handoff.
4. Product Demo paper-trading workstation.
5. Production visual, accessibility, performance, long-session, and large-result-set polish.

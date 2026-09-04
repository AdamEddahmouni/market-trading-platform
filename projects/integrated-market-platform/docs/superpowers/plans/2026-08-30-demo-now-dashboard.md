# Demo Now Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Demo root route with a polished, accessible dashboard that explains and controls the admitted BIYA replay, presents simulated portfolio state observationally, preserves attention actions, and guides the next safe inspection step while leaving Paper and Live unchanged.

**Architecture:** `WorkstationShell` continues to own shared context, attention, replay, navigation, drawer, inspector, and confirmed cursor state. A focused `ModeNowRoute` renders a Demo-only composition and loads the existing paper-portfolio query only inside that Demo branch; Paper and Live retain `NowPage`. Small presentational components receive explicit data, loading/error states, and safe callbacks, with no backend or authority changes.

**Tech Stack:** React 18.3, TypeScript 5.6, React Router 6.27, TanStack Query 5.59, Vitest 2.1, Testing Library 16.3, CSS

## Global Constraints

- This increment is UI-only: add no backend endpoint, schema, execution-authority, persistence, or dependency changes.
- Demo identifies the scenario as **BIYA admitted replay** and does not render a selector, catalog, alternate scenario, autoplay, pause, speed, order, paper-session, kill-switch, authorization-mutation, or execution control.
- Paper and Live continue to render the existing **Command Center** at `/`.
- The frontend mode never becomes execution authority; paper portfolio data is observational in Demo even if its payload advertises Paper authority.
- Replay cursor changes are bounded, disabled while pending, and displayed only after `api.scrubReplay` confirms success.
- Successful scrubs refresh context, attention, and instrument queries; failed scrubs retain the last confirmed cursor and announce failure politely.
- Portfolio metrics use `account.cash_display`, `pnl.total_display` with `account.realized_pnl_display` fallback, `exposure.gross_shares` with zero fallback, and `risk.open_order_count`.
- Replay, attention, portfolio, and scrub failures degrade within their own regions and do not replace the entire dashboard.
- The dashboard has one level-one heading, named regions, native controls, text equivalents for semantic color, visible focus, minimum `44px` targets, responsive reading order, reduced-motion independence, and forced-colors support.
- Use no new dependencies and do not redesign workstation surfaces outside the Demo landing page.
- Follow strict red-green-refactor: observe each focused test fail before writing its production implementation.
- After a red test edit, run the focused test and changed-files validation expecting the new assertion to fail; after the production edit, rerun both expecting green.
- Use the repository-local Windows tools from `ui`: `.\node_modules\.bin\vitest.cmd`, `.\node_modules\.bin\tsc.cmd`, and `.\node_modules\.bin\vite.cmd`; use `.\.venv\Scripts\python.exe` from the repository root.
- Run the UI domain validation at the feature milestone and the full offline validation exactly once at the final checkpoint.

---

## File structure

- Create `ui/src/components/AttentionFeed.tsx`: reusable attention loading/error/empty/card presentation with the existing action semantics.
- Create `ui/src/components/AttentionFeed.test.tsx`: callback, reason-code, empty, loading, and failure coverage.
- Modify `ui/src/components/NowPage.tsx`: retain Command Center and tier chart while delegating cards to `AttentionFeed`.
- Create `ui/src/components/demo-now/DemoReplayOverview.tsx`: replay-state derivation, BIYA status, progress, bounds, scrub controls, and timeline action.
- Create `ui/src/components/demo-now/DemoReplayOverview.test.tsx`: first/middle/final/empty/invalid/pending/failure behavior.
- Create `ui/src/components/demo-now/DemoPortfolioSummary.tsx`: four read-only portfolio metrics plus local loading/unavailable states.
- Create `ui/src/components/demo-now/DemoPortfolioSummary.test.tsx`: source-field, fallback, and no-mutation coverage.
- Create `ui/src/components/demo-now/DemoInspectNext.tsx`: deterministic highest-priority attention path and replay advance action.
- Create `ui/src/components/demo-now/DemoInspectNext.test.tsx`: ordering, workspace/inspect fallback, no-attention, and replay-bound coverage.
- Create `ui/src/components/demo-now/DemoNowPage.tsx`: semantic Demo page composition and independent region states.
- Create `ui/src/components/demo-now/DemoNowPage.test.tsx`: complete composition, local degradation, attention callbacks, and forbidden-control coverage.
- Create `ui/src/components/ModeNowRoute.tsx`: Demo branch with portfolio query and stable Paper/Live fallback.
- Modify `ui/src/App.tsx`: route through `ModeNowRoute`, expose query states, and own pending/error/confirmed scrub state.
- Modify `ui/src/App.test.tsx`: mode routing, route reset, confirmed scrub, failed scrub, and query refresh integration.
- Create `ui/src/styles/demo-now.css`: scoped polished Demo layout, responsive behavior, focus, reduced motion, and forced colors.
- Create `ui/src/vite-env.d.ts`: provide Vite asset-query types for the raw stylesheet contract test.

---

### Task 1: Extract the shared attention feed without changing Command Center behavior

**Files:**
- Create: `ui/src/components/AttentionFeed.test.tsx`
- Create: `ui/src/components/AttentionFeed.tsx`
- Modify: `ui/src/components/NowPage.tsx`

**Interfaces:**
- Consumes: `AttentionItem` from `../api/client` and the existing four item callbacks.
- Produces: `AttentionFeedProps`, `AttentionFeed`, and the unchanged public `NowPageProps` contract for later mode routing.

- [ ] **Step 1: Write the failing shared-feed tests**

Create `ui/src/components/AttentionFeed.test.tsx` with this complete test module:

```tsx
import type { ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../api/client";
import { AttentionFeed } from "./AttentionFeed";

const item: AttentionItem = {
  attention_id: "attention-1",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "Volume expands into the replay event",
  explanation_ref: "explain:attention:1",
  reasons: [{ code: "VOLUME_EXPANSION", label: "Volume exceeds the admitted baseline" }],
};

function callbacks() {
  return {
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
  };
}

describe("AttentionFeed", () => {
  it("preserves reason codes, tier identity, and all existing item actions", () => {
    const actions = callbacks();
    render(<AttentionFeed items={[item]} state="ready" {...actions} />);

    expect(screen.getByRole("article")).toHaveClass("tier-1");
    expect(screen.getByText("VOLUME_EXPANSION")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Why here?" }));
    fireEvent.click(screen.getByRole("button", { name: "Explain" }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    expect(actions.onWhy).toHaveBeenCalledWith(item);
    expect(actions.onExplain).toHaveBeenCalledWith(item);
    expect(actions.onInspect).toHaveBeenCalledWith(item);
    expect(actions.onOpenWorkspace).toHaveBeenCalledWith(item);
  });

  it("renders local loading, error, and optional empty messages", () => {
    const actions = callbacks();
    const { rerender } = render(
      <AttentionFeed items={[]} state="loading" emptyMessage="Nothing requires attention." {...actions} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading attention feed");

    rerender(<AttentionFeed items={[]} state="error" emptyMessage="Nothing requires attention." {...actions} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable");

    rerender(<AttentionFeed items={[]} state="ready" emptyMessage="Nothing requires attention." {...actions} />);
    expect(screen.getByText("Nothing requires attention.")).toBeInTheDocument();

    rerender(<AttentionFeed items={[]} state="ready" {...actions} />);
    expect(screen.queryByText("Nothing requires attention.")).not.toBeInTheDocument();
  });

  it("does not offer workspace navigation without an instrument", () => {
    render(
      <AttentionFeed
        items={[{ ...item, instrument_id: undefined }]}
        state="ready"
        {...callbacks()}
      />,
    );
    expect(screen.queryByRole("button", { name: "Open workspace" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Verify the test is red and record changed validation’s intentional failure**

Run from `ui`:

```powershell
.\node_modules\.bin\vitest.cmd run src/components/AttentionFeed.test.tsx
```

Expected: FAIL because `./AttentionFeed` does not exist.

Run from the repository root:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: FAIL only because the new Vitest module cannot resolve `AttentionFeed`; do not proceed if another suite fails.

- [ ] **Step 3: Implement the shared feed and refactor `NowPage`**

Create `ui/src/components/AttentionFeed.tsx`:

```tsx
import type { AttentionItem } from "../api/client";

export type AttentionFeedProps = {
  items: AttentionItem[];
  state?: "loading" | "ready" | "error";
  emptyMessage?: string;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function AttentionFeed({
  items,
  state = "ready",
  emptyMessage,
  onWhy,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: AttentionFeedProps) {
  if (state === "loading") return <p role="status">Loading attention feed…</p>;
  if (state === "error") return <p role="alert">Attention feed unavailable.</p>;
  if (!items.length) return emptyMessage ? <p className="unavailable">{emptyMessage}</p> : null;

  return (
    <div className="attention-feed">
      {items.map((item) => (
        <article key={item.attention_id} className={`attention-card tier-${item.tier ?? 2}`}>
          <div className="card-head">
            <h2>{item.headline}</h2>
            {item.instrument_id ? <span className="symbol">{item.instrument_id}</span> : null}
          </div>
          <ul className="reason-codes">
            {item.reasons.map((reason) => (
              <li key={reason.code}>
                <code>{reason.code}</code> {reason.label}
              </li>
            ))}
          </ul>
          <div className="card-actions">
            <button type="button" onClick={() => onWhy(item)}>Why here?</button>
            <button type="button" onClick={() => onExplain(item)}>Explain</button>
            <button type="button" onClick={() => onInspect(item)}>Inspect</button>
            {item.instrument_id ? (
              <button type="button" onClick={() => onOpenWorkspace(item)}>Open workspace</button>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
```

Replace `NowPage.tsx`’s local card map with `AttentionFeed`, export its props, and keep the chart and copy unchanged:

```tsx
import type { AttentionItem } from "../api/client";
import type { ChartCountPoint } from "../lib/chartTransforms";
import { AttentionFeed } from "./AttentionFeed";
import { CountBarChartPanel } from "./charts/ResearchChartPanels";

export type NowPageProps = {
  items: AttentionItem[];
  tierSummary?: ChartCountPoint[];
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function NowPage({ items, tierSummary, onWhy, onExplain, onInspect, onOpenWorkspace }: NowPageProps) {
  return (
    <section className="page now-page">
      <header className="page-header">
        <h1>Command Center</h1>
        <p>Attention-prioritized feed with reason codes — no opaque rank score.</p>
      </header>
      {tierSummary ? (
        <div className="chart-grid chart-grid-inline">
          <CountBarChartPanel
            title="Attention tiers (full feed)"
            series={tierSummary}
            provenance={{ source: "replay attention feed", method: "tier aggregation at cutoff" }}
            ariaLabel="Attention tier distribution chart"
          />
        </div>
      ) : null}
      <AttentionFeed
        items={items}
        onWhy={onWhy}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
      />
    </section>
  );
}
```

- [ ] **Step 4: Verify green and run changed-files validation**

From `ui`:

```powershell
.\node_modules\.bin\vitest.cmd run src/components/AttentionFeed.test.tsx src/App.test.tsx
```

Expected: both test files PASS and the existing Paper/Live Command Center behavior remains intact.

From the repository root:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: PASS with zero new warnings or failures.

- [ ] **Step 5: Commit the shared presentation**

```powershell
git add ui/src/components/AttentionFeed.tsx ui/src/components/AttentionFeed.test.tsx ui/src/components/NowPage.tsx
git commit -m "refactor(ui): share attention feed presentation"
```

---

### Task 2: Add confirmed, bounded replay overview controls

**Files:**
- Create: `ui/src/components/demo-now/DemoReplayOverview.test.tsx`
- Create: `ui/src/components/demo-now/DemoReplayOverview.tsx`

**Interfaces:**
- Consumes: confirmed `cursorIndex`, replay `eventCount`, `state`, `scrubState`, `onScrub(index): void`, and `onOpenTimeline(): void`.
- Produces: `deriveReplayProgress(cursorIndex, eventCount): ReplayProgress | null` and `DemoReplayOverview`.

- [ ] **Step 1: Write the failing replay derivation and component tests**

Create `ui/src/components/demo-now/DemoReplayOverview.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DemoReplayOverview, deriveReplayProgress } from "./DemoReplayOverview";

describe("deriveReplayProgress", () => {
  it.each([
    [0, 4, { cursorIndex: 0, ordinal: 1, eventCount: 4, percent: 25, hasPrevious: false, hasNext: true }],
    [2, 4, { cursorIndex: 2, ordinal: 3, eventCount: 4, percent: 75, hasPrevious: true, hasNext: true }],
    [99, 4, { cursorIndex: 3, ordinal: 4, eventCount: 4, percent: 100, hasPrevious: true, hasNext: false }],
    [0, 0, { cursorIndex: 0, ordinal: 0, eventCount: 0, percent: 0, hasPrevious: false, hasNext: false }],
  ] as const)("derives bounded progress for cursor %s of %s", (cursor, count, expected) => {
    expect(deriveReplayProgress(cursor, count)).toEqual(expected);
  });

  it.each([[Number.NaN, 4], [1.5, 4], [0, -1], [0, undefined]] as const)(
    "rejects invalid replay data",
    (cursor, count) => expect(deriveReplayProgress(cursor, count)).toBeNull(),
  );
});

function renderReplay(overrides: Partial<ComponentProps<typeof DemoReplayOverview>> = {}) {
  const props: ComponentProps<typeof DemoReplayOverview> = {
    cursorIndex: 1,
    eventCount: 4,
    state: "ready",
    scrubState: "idle",
    onScrub: vi.fn(),
    onOpenTimeline: vi.fn(),
    ...overrides,
  };
  render(<DemoReplayOverview {...props} />);
  return props;
}

describe("DemoReplayOverview", () => {
  it("shows truthful BIYA identity and invokes bounded replay actions", () => {
    const props = renderReplay();
    expect(screen.getByRole("region", { name: "Replay overview" })).toHaveTextContent("BIYA admitted replay");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("Event 2 of 4")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Replay progress" })).toHaveAttribute("aria-valuenow", "2");
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    fireEvent.click(screen.getByRole("button", { name: "Open full timeline" }));
    expect(props.onScrub).toHaveBeenNthCalledWith(1, 0);
    expect(props.onScrub).toHaveBeenNthCalledWith(2, 2);
    expect(props.onOpenTimeline).toHaveBeenCalledOnce();
  });

  it("enforces first, final, empty, and pending boundaries", () => {
    const { rerender } = render(
      <DemoReplayOverview cursorIndex={0} eventCount={4} state="ready" scrubState="idle" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    rerender(<DemoReplayOverview cursorIndex={3} eventCount={4} state="ready" scrubState="idle" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Next event" })).toBeDisabled();
    rerender(<DemoReplayOverview cursorIndex={0} eventCount={0} state="ready" scrubState="idle" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />);
    expect(screen.getByText("0 events")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next event" })).toBeDisabled();
    rerender(<DemoReplayOverview cursorIndex={1} eventCount={4} state="ready" scrubState="pending" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next event" })).toBeDisabled();
  });

  it("degrades loading, invalid, and failed scrub states locally", () => {
    const { rerender } = render(
      <DemoReplayOverview cursorIndex={0} eventCount={undefined} state="loading" scrubState="idle" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading replay status");
    rerender(<DemoReplayOverview cursorIndex={0} eventCount={undefined} state="error" scrubState="idle" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />);
    expect(screen.getByText("Replay status unavailable")).toBeInTheDocument();
    rerender(<DemoReplayOverview cursorIndex={1} eventCount={4} state="ready" scrubState="error" onScrub={vi.fn()} onOpenTimeline={vi.fn()} />);
    expect(screen.getByText("Event 2 of 4")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Replay could not move");
  });

  it("does not optimistically change a controlled cursor", () => {
    renderReplay({ cursorIndex: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    expect(screen.getByText("Event 2 of 4")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Verify red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoReplayOverview.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: both commands report the missing `DemoReplayOverview` module as the only new failure.

- [ ] **Step 3: Implement replay state derivation and the overview**

Create `ui/src/components/demo-now/DemoReplayOverview.tsx`:

```tsx
export type ReplayProgress = {
  cursorIndex: number;
  ordinal: number;
  eventCount: number;
  percent: number;
  hasPrevious: boolean;
  hasNext: boolean;
};

export function deriveReplayProgress(cursorIndex: number, eventCount: number | undefined): ReplayProgress | null {
  if (!Number.isInteger(cursorIndex) || eventCount === undefined || !Number.isInteger(eventCount) || eventCount < 0) {
    return null;
  }
  if (eventCount === 0) {
    return { cursorIndex: 0, ordinal: 0, eventCount: 0, percent: 0, hasPrevious: false, hasNext: false };
  }
  const boundedCursor = Math.min(Math.max(cursorIndex, 0), eventCount - 1);
  const ordinal = boundedCursor + 1;
  return {
    cursorIndex: boundedCursor,
    ordinal,
    eventCount,
    percent: Math.round((ordinal / eventCount) * 100),
    hasPrevious: boundedCursor > 0,
    hasNext: boundedCursor < eventCount - 1,
  };
}

type Props = {
  cursorIndex: number;
  eventCount?: number;
  state: "loading" | "ready" | "error";
  scrubState: "idle" | "pending" | "error";
  onScrub: (index: number) => void;
  onOpenTimeline: () => void;
};

export function DemoReplayOverview({ cursorIndex, eventCount, state, scrubState, onScrub, onOpenTimeline }: Props) {
  const progress = state === "ready" ? deriveReplayProgress(cursorIndex, eventCount) : null;
  const controlsDisabled = scrubState === "pending" || !progress || progress.eventCount === 0;

  return (
    <section className="demo-now-panel demo-replay-panel" aria-labelledby="demo-replay-title">
      <div className="demo-panel-heading">
        <div>
          <p className="demo-eyebrow">Historical scenario</p>
          <h2 id="demo-replay-title">Replay overview</h2>
        </div>
        <span className="demo-state-badge">Read-only replay</span>
      </div>
      <div className="demo-scenario-card">
        <strong>BIYA admitted replay</strong>
        <span>Known historical sequence · No execution risk</span>
      </div>
      {state === "loading" ? <p role="status">Loading replay status…</p> : null}
      {state === "error" || (state === "ready" && !progress) ? <p className="unavailable">Replay status unavailable.</p> : null}
      {progress ? (
        <>
          <div className="demo-replay-progress-copy">
            <strong>{progress.eventCount === 0 ? "0 events" : `Event ${progress.ordinal} of ${progress.eventCount}`}</strong>
            <span>{progress.percent}% observed</span>
          </div>
          {progress.eventCount > 0 ? (
            <div
              className="demo-replay-progress"
              role="progressbar"
              aria-label="Replay progress"
              aria-valuemin={1}
              aria-valuemax={progress.eventCount}
              aria-valuenow={progress.ordinal}
              aria-valuetext={`Event ${progress.ordinal} of ${progress.eventCount}`}
            >
              <span style={{ width: `${progress.percent}%` }} />
            </div>
          ) : null}
          <div className="demo-replay-actions">
            <button type="button" disabled={controlsDisabled || !progress.hasPrevious} onClick={() => onScrub(progress.cursorIndex - 1)}>Previous</button>
            <button className="primary" type="button" disabled={controlsDisabled || !progress.hasNext} onClick={() => onScrub(progress.cursorIndex + 1)}>Next event</button>
            <button type="button" onClick={onOpenTimeline}>Open full timeline</button>
          </div>
        </>
      ) : null}
      {scrubState === "pending" ? <p role="status">Moving to the requested replay event…</p> : null}
      {scrubState === "error" ? <p role="status">Replay could not move. The last confirmed event remains visible.</p> : null}
    </section>
  );
}
```

- [ ] **Step 4: Verify green, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoReplayOverview.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/demo-now/DemoReplayOverview.tsx ui/src/components/demo-now/DemoReplayOverview.test.tsx
git commit -m "feat(ui): add Demo replay overview"
```

Expected: focused tests and changed validation PASS, then the commit succeeds.

---

### Task 3: Add a strictly observational portfolio summary

**Files:**
- Create: `ui/src/components/demo-now/DemoPortfolioSummary.test.tsx`
- Create: `ui/src/components/demo-now/DemoPortfolioSummary.tsx`

**Interfaces:**
- Consumes: `PaperPortfolioResponse | undefined` plus `loading | ready | error` state.
- Produces: `portfolioMetrics(portfolio)` and `DemoPortfolioSummary`; neither exposes a callback or mutation hook.

- [ ] **Step 1: Write the failing portfolio tests**

Create `ui/src/components/demo-now/DemoPortfolioSummary.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PaperPortfolioResponse } from "../../api/client";
import { DemoPortfolioSummary, portfolioMetrics } from "./DemoPortfolioSummary";

function payload(): PaperPortfolioResponse {
  return {
    as_of_context: {
      mode: "REPLAY",
      as_of_time: "2026-08-30T12:00:00Z",
      timezone: "America/New_York",
      data_mode: "FIXTURE_REPLAY",
      execution_mode: "NONE",
      execution_authority: "BLOCKED",
    },
    authority_boundary: "PAPER_OBSERVABILITY",
    account: {
      paper_account_id: "acct",
      session_id: "session",
      currency: "USD",
      cash_display: "$98,450.00",
      cash_minor: 9845000,
      buying_power_minor: 9845000,
      initial_cash_minor: 10000000,
      realized_pnl_display: "+$125.00",
      realized_pnl_minor: 12500,
      data_mode: "FIXTURE_REPLAY",
      data_provider: "INTERNAL",
      execution_mode: "NONE",
      execution_authority: "BLOCKED",
      execution_provider: "INTERNAL",
    },
    positions: [],
    orders: [],
    fills: [],
    risk: {
      kill_switch_active: false,
      open_order_count: 2,
      reconciliation_status: "INTERNAL_AUTHORITATIVE",
      limits: { max_open_orders: 3, max_order_shares: 100, max_position_shares: 500 },
    },
    data_health: { state: "PASS" },
    exposure: { gross_shares: 240, net_shares: 120 },
    pnl: { total_display: "+$410.00", realized_display: "+$125.00" },
  };
}

describe("DemoPortfolioSummary", () => {
  it("uses the specified observational fields", () => {
    expect(portfolioMetrics(payload())).toEqual([
      { label: "Cash", value: "$98,450.00" },
      { label: "Total P&L", value: "+$410.00" },
      { label: "Gross exposure", value: "240 shares" },
      { label: "Open orders", value: "2" },
    ]);
    render(<DemoPortfolioSummary state="ready" portfolio={payload()} />);
    expect(screen.getByRole("region", { name: "Simulated portfolio" })).toHaveTextContent("Observational snapshot");
    expect(screen.getByText("+$410.00")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("falls back to realized P&L and zero exposure", () => {
    const value = payload();
    delete value.pnl;
    delete value.exposure;
    expect(portfolioMetrics(value)).toEqual([
      { label: "Cash", value: "$98,450.00" },
      { label: "Total P&L", value: "+$125.00" },
      { label: "Gross exposure", value: "0 shares" },
      { label: "Open orders", value: "2" },
    ]);
  });

  it("keeps loading and failure local without fabricated values", () => {
    const { rerender } = render(<DemoPortfolioSummary state="loading" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading simulated portfolio");
    rerender(<DemoPortfolioSummary state="error" />);
    expect(screen.getByText("Simulated portfolio unavailable")).toBeInTheDocument();
    expect(screen.queryByText("0 shares")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Verify red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoPortfolioSummary.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: the focused and changed validations fail only on the missing summary module.

- [ ] **Step 3: Implement the read-only summary**

Create `ui/src/components/demo-now/DemoPortfolioSummary.tsx`:

```tsx
import type { PaperPortfolioResponse } from "../../api/client";

export function portfolioMetrics(portfolio: PaperPortfolioResponse) {
  return [
    { label: "Cash", value: portfolio.account.cash_display },
    { label: "Total P&L", value: portfolio.pnl?.total_display ?? portfolio.account.realized_pnl_display },
    { label: "Gross exposure", value: `${portfolio.exposure?.gross_shares ?? 0} shares` },
    { label: "Open orders", value: String(portfolio.risk.open_order_count) },
  ];
}

type Props = {
  state: "loading" | "ready" | "error";
  portfolio?: PaperPortfolioResponse;
};

export function DemoPortfolioSummary({ state, portfolio }: Props) {
  const available = state === "ready" && portfolio;
  return (
    <section className="demo-now-panel demo-portfolio-panel" aria-labelledby="demo-portfolio-title">
      <div className="demo-panel-heading">
        <div>
          <p className="demo-eyebrow">Simulation account</p>
          <h2 id="demo-portfolio-title">Simulated portfolio</h2>
        </div>
        <span className="demo-state-badge">Observational snapshot</span>
      </div>
      {state === "loading" ? <p role="status">Loading simulated portfolio…</p> : null}
      {!available && state !== "loading" ? <p className="unavailable">Simulated portfolio unavailable.</p> : null}
      {available ? (
        <dl className="demo-metric-grid">
          {portfolioMetrics(portfolio).map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="demo-panel-note">Values are simulated and read-only in Demo.</p>
    </section>
  );
}
```

- [ ] **Step 4: Verify green, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoPortfolioSummary.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/demo-now/DemoPortfolioSummary.tsx ui/src/components/demo-now/DemoPortfolioSummary.test.tsx
git commit -m "feat(ui): summarize Demo portfolio observability"
```

Expected: focused tests and changed validation PASS.

---

### Task 4: Compose attention and the deterministic inspect-next path

**Files:**
- Create: `ui/src/components/demo-now/DemoInspectNext.test.tsx`
- Create: `ui/src/components/demo-now/DemoInspectNext.tsx`
- Create: `ui/src/components/demo-now/DemoNowPage.test.tsx`
- Create: `ui/src/components/demo-now/DemoNowPage.tsx`

**Interfaces:**
- Consumes: `AttentionItem[]`, the Task 1 feed, Task 2 replay panel, Task 3 portfolio panel, independent load states, and existing safe callbacks.
- Produces: `topAttentionItem(items)`, `DemoInspectNext`, `DemoNowPageProps`, and `DemoNowPage` for `ModeNowRoute`.

- [ ] **Step 1: Write the failing guided-path tests**

Create `ui/src/components/demo-now/DemoInspectNext.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../../api/client";
import { DemoInspectNext, topAttentionItem } from "./DemoInspectNext";

const lower: AttentionItem = {
  attention_id: "lower",
  priority_rank: 8,
  tier: 2,
  instrument_id: "OTHER",
  headline: "Lower priority item",
  explanation_ref: "explain:lower",
  reasons: [],
};
const top: AttentionItem = {
  attention_id: "top",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "Top replay signal",
  explanation_ref: "explain:top",
  reasons: [],
};

describe("DemoInspectNext", () => {
  it("selects the lowest priority rank without mutating the source array", () => {
    const items = [lower, top];
    expect(topAttentionItem(items)).toBe(top);
    expect(items).toEqual([lower, top]);
  });

  it("guides explain, workspace, then replay advance for the top item", () => {
    const onExplain = vi.fn();
    const onInspect = vi.fn();
    const onOpenWorkspace = vi.fn();
    const onAdvance = vi.fn();
    render(
      <DemoInspectNext items={[lower, top]} canAdvance replayPending={false} onExplain={onExplain} onInspect={onInspect} onOpenWorkspace={onOpenWorkspace} onAdvance={onAdvance} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Explain top replay signal" }));
    fireEvent.click(screen.getByRole("button", { name: "Open BIYA workspace" }));
    fireEvent.click(screen.getByRole("button", { name: "Advance one event" }));
    expect(onExplain).toHaveBeenCalledWith(top);
    expect(onOpenWorkspace).toHaveBeenCalledWith(top);
    expect(onInspect).not.toHaveBeenCalled();
    expect(onAdvance).toHaveBeenCalledOnce();
  });

  it("uses inspection when the top item has no instrument", () => {
    const noInstrument = { ...top, instrument_id: undefined };
    const onInspect = vi.fn();
    render(<DemoInspectNext items={[noInstrument]} canAdvance={false} replayPending={false} onExplain={vi.fn()} onInspect={onInspect} onOpenWorkspace={vi.fn()} onAdvance={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Inspect supporting evidence" }));
    expect(onInspect).toHaveBeenCalledWith(noInstrument);
    expect(screen.getByRole("button", { name: "Advance one event" })).toBeDisabled();
  });

  it("explains an empty attention state and retains a safe advance when available", () => {
    const onAdvance = vi.fn();
    render(<DemoInspectNext items={[]} canAdvance replayPending={false} onExplain={vi.fn()} onInspect={vi.fn()} onOpenWorkspace={vi.fn()} onAdvance={onAdvance} />);
    expect(screen.getByText(/No item requires inspection/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Advance one event" }));
    expect(onAdvance).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Verify the guided-path test is red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoInspectNext.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: only the missing `DemoInspectNext` module causes failure.

- [ ] **Step 3: Implement the deterministic guided path**

Create `ui/src/components/demo-now/DemoInspectNext.tsx`:

```tsx
import type { AttentionItem } from "../../api/client";

export function topAttentionItem(items: AttentionItem[]): AttentionItem | undefined {
  return items.reduce<AttentionItem | undefined>((current, item) => {
    if (!current || item.priority_rank < current.priority_rank) return item;
    return current;
  }, undefined);
}

type Props = {
  items: AttentionItem[];
  canAdvance: boolean;
  replayPending: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAdvance: () => void;
};

export function DemoInspectNext({ items, canAdvance, replayPending, onExplain, onInspect, onOpenWorkspace, onAdvance }: Props) {
  const top = topAttentionItem(items);
  return (
    <section className="demo-now-panel demo-inspect-panel" aria-labelledby="demo-inspect-title">
      <div className="demo-panel-heading">
        <div>
          <p className="demo-eyebrow">Guided research path</p>
          <h2 id="demo-inspect-title">Inspect next</h2>
        </div>
      </div>
      {top ? (
        <ol className="demo-step-list">
          <li><span>01</span><button type="button" onClick={() => onExplain(top)} aria-label={`Explain ${top.headline}`}>Understand why this item matters</button></li>
          <li><span>02</span>{top.instrument_id ? <button type="button" onClick={() => onOpenWorkspace(top)} aria-label={`Open ${top.instrument_id} workspace`}>Open the instrument workspace</button> : <button type="button" onClick={() => onInspect(top)}>Inspect supporting evidence</button>}</li>
          <li><span>03</span><button className="primary" type="button" disabled={!canAdvance || replayPending} onClick={onAdvance}>Advance one event</button></li>
        </ol>
      ) : (
        <div className="demo-empty-path">
          <p>No item requires inspection at the current event.</p>
          <button className="primary" type="button" disabled={!canAdvance || replayPending} onClick={onAdvance}>Advance one event</button>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Write the failing page-composition tests**

Create `ui/src/components/demo-now/DemoNowPage.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { DemoNowPage, type DemoNowPageProps } from "./DemoNowPage";

const attention: AttentionItem = {
  attention_id: "attention-1",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "Replay signal requires review",
  explanation_ref: "explain:attention:1",
  reasons: [{ code: "REPLAY_SIGNAL", label: "Signal entered at this event" }],
};

const portfolio = {
  account: { cash_display: "$100,000.00", realized_pnl_display: "$0.00" },
  pnl: { total_display: "+$25.00" },
  exposure: { gross_shares: 100 },
  risk: { open_order_count: 0 },
} as PaperPortfolioResponse;

function props(overrides: Partial<DemoNowPageProps> = {}): DemoNowPageProps {
  return {
    items: [attention],
    attentionState: "ready",
    replayState: "ready",
    cursorIndex: 0,
    eventCount: 4,
    scrubState: "idle",
    portfolioState: "ready",
    portfolio,
    onScrub: vi.fn(),
    onOpenTimeline: vi.fn(),
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
    ...overrides,
  };
}

describe("DemoNowPage", () => {
  it("composes one page heading and four named operational regions", () => {
    render(<DemoNowPage {...props()} />);
    expect(screen.getByRole("heading", { level: 1, name: "See the market unfold" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Replay overview" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Simulated portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "What matters now" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Inspect next" })).toBeInTheDocument();
  });

  it("preserves attention callbacks and supplies the confirmed next cursor", () => {
    const value = props({ cursorIndex: 1 });
    render(<DemoNowPage {...value} />);
    fireEvent.click(screen.getByRole("button", { name: "Why here?" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Explain" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    fireEvent.click(screen.getByRole("button", { name: "Advance one event" }));
    expect(value.onWhy).toHaveBeenCalledWith(attention);
    expect(value.onExplain).toHaveBeenCalledWith(attention);
    expect(value.onInspect).toHaveBeenCalledWith(attention);
    expect(value.onOpenWorkspace).toHaveBeenCalledWith(attention);
    expect(value.onScrub).toHaveBeenCalledWith(2);
  });

  it("degrades attention and portfolio independently while replay remains usable", () => {
    render(<DemoNowPage {...props({ attentionState: "error", portfolioState: "error", portfolio: undefined })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable");
    expect(screen.getByText("Simulated portfolio unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next event" })).toBeEnabled();
  });

  it("renders no execution or session mutation controls", () => {
    render(<DemoNowPage {...props()} />);
    for (const name of [/order ticket/i, /paper session/i, /kill switch/i, /authorization/i, /execute/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 5: Verify the composition test is red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoInspectNext.test.tsx src/components/demo-now/DemoNowPage.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: guided-path tests PASS; composition and changed validation fail only because `DemoNowPage` is absent.

- [ ] **Step 6: Implement the semantic Demo composition**

Create `ui/src/components/demo-now/DemoNowPage.tsx`:

```tsx
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { AttentionFeed } from "../AttentionFeed";
import { DemoInspectNext } from "./DemoInspectNext";
import { DemoPortfolioSummary } from "./DemoPortfolioSummary";
import { DemoReplayOverview, deriveReplayProgress } from "./DemoReplayOverview";

export type LoadState = "loading" | "ready" | "error";
export type ScrubState = "idle" | "pending" | "error";

export type DemoNowPageProps = {
  items: AttentionItem[];
  attentionState: LoadState;
  replayState: LoadState;
  cursorIndex: number;
  eventCount?: number;
  scrubState: ScrubState;
  portfolioState: LoadState;
  portfolio?: PaperPortfolioResponse;
  onScrub: (index: number) => void;
  onOpenTimeline: () => void;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function DemoNowPage(props: DemoNowPageProps) {
  const progress = props.replayState === "ready" ? deriveReplayProgress(props.cursorIndex, props.eventCount) : null;
  const canAdvance = Boolean(progress?.hasNext);
  return (
    <div className="page demo-now-page">
      <header className="demo-now-intro">
        <div>
          <p className="demo-eyebrow">Demo · Historical research</p>
          <h1>See the market unfold</h1>
          <p>Move through a known historical sequence, inspect the evidence at each event, and learn without execution risk.</p>
        </div>
        <span className="demo-intro-mark">BIYA / REPLAY</span>
      </header>
      <div className="demo-now-grid demo-now-grid-top">
        <DemoReplayOverview cursorIndex={props.cursorIndex} eventCount={props.eventCount} state={props.replayState} scrubState={props.scrubState} onScrub={props.onScrub} onOpenTimeline={props.onOpenTimeline} />
        <DemoPortfolioSummary state={props.portfolioState} portfolio={props.portfolio} />
      </div>
      <div className="demo-now-grid demo-now-grid-bottom">
        <section className="demo-now-panel demo-attention-panel" aria-labelledby="demo-attention-title">
          <div className="demo-panel-heading">
            <div>
              <p className="demo-eyebrow">Evidence queue</p>
              <h2 id="demo-attention-title">What matters now</h2>
            </div>
          </div>
          <AttentionFeed items={props.items} state={props.attentionState} emptyMessage="Nothing requires attention at the current event." onWhy={props.onWhy} onExplain={props.onExplain} onInspect={props.onInspect} onOpenWorkspace={props.onOpenWorkspace} />
        </section>
        <DemoInspectNext items={props.items} canAdvance={canAdvance} replayPending={props.scrubState === "pending"} onExplain={props.onExplain} onInspect={props.onInspect} onOpenWorkspace={props.onOpenWorkspace} onAdvance={() => { if (progress?.hasNext) props.onScrub(progress.cursorIndex + 1); }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Verify green, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/AttentionFeed.test.tsx src/components/demo-now/DemoInspectNext.test.tsx src/components/demo-now/DemoNowPage.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/demo-now/DemoInspectNext.tsx ui/src/components/demo-now/DemoInspectNext.test.tsx ui/src/components/demo-now/DemoNowPage.tsx ui/src/components/demo-now/DemoNowPage.test.tsx
git commit -m "feat(ui): compose Demo Now guidance"
```

Expected: all focused tests and changed validation PASS.

---

### Task 5: Route Demo only and preserve confirmed scrub state in the shell

**Files:**
- Create: `ui/src/components/ModeNowRoute.tsx`
- Modify: `ui/src/App.test.tsx`
- Modify: `ui/src/App.tsx`

**Interfaces:**
- Consumes: `Mode`, `DemoNowPageProps` excluding portfolio fields, `NowPage`, `usePaperPortfolioQuery`, existing navigation callbacks, and `api.scrubReplay`.
- Produces: `ModeNowRoute` and shell-owned `ScrubState`; Paper and Live continue to receive the exact existing `NowPage` props.

- [ ] **Step 1: Update App integration tests to describe mode-specific routing**

In `ui/src/App.test.tsx`, extend the hook mock with a complete `usePaperPortfolioQuery` result:

```tsx
usePaperPortfolioQuery: () => ({
  isLoading: false,
  isError: true,
  data: undefined,
}),
```

Change `useReplaySessionQuery` to:

```tsx
const replaySession = { cursor_index: 0, event_count: 4 };

useReplaySessionQuery: () => ({
  isLoading: false,
  error: null,
  data: replaySession,
}),
```

Declare `replaySession` once at module scope immediately before `vi.mock`; its stable object identity prevents the shell synchronization effect from resetting a newly confirmed local cursor during the test rerender.

Replace the shared-heading mode test with these exact assertions:

```tsx
it("opens the Demo dashboard", async () => {
  render(<App />);
  await enterMode("Demo");
  expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("DEMO");
  expect(screen.getByRole("heading", { name: "See the market unfold" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Command Center" })).not.toBeInTheDocument();
});

it.each([["Paper", "PAPER"], ["Live", "LIVE"]] as const)("keeps %s on Command Center", async (label, mode) => {
  render(<App />);
  await enterMode(label);
  expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent(mode);
  expect(screen.getByRole("heading", { name: "Command Center" })).toBeInTheDocument();
});
```

Update the route-reset assertion to expect **See the market unfold** after re-entering Demo.

- [ ] **Step 2: Add failing confirmed-success and failure integration tests**

Add `QueryClient` and `api` imports, and add `waitFor` to the existing Testing Library import rather than creating a duplicate import. Then add these tests:

```tsx
import { QueryClient } from "@tanstack/react-query";
import { api } from "./api/client";

it("confirms a scrub before changing the cursor and refreshes existing queries", async () => {
  const scrub = vi.spyOn(api, "scrubReplay").mockResolvedValueOnce({});
  const invalidate = vi.spyOn(QueryClient.prototype, "invalidateQueries");
  render(<App />);
  await enterMode("Demo");
  fireEvent.click(screen.getByRole("button", { name: "Next event" }));
  await waitFor(() => expect(screen.getByText("Event 2 of 4")).toBeInTheDocument());
  expect(scrub).toHaveBeenCalledWith(1);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["context"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["attention"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["instrument"] });
});

it("retains the confirmed cursor and announces a failed scrub", async () => {
  vi.spyOn(api, "scrubReplay").mockRejectedValueOnce(new Error("offline"));
  render(<App />);
  await enterMode("Demo");
  fireEvent.click(screen.getByRole("button", { name: "Next event" }));
  await screen.findByText(/Replay could not move/);
  expect(screen.getByText("Event 1 of 4")).toBeInTheDocument();
});
```

In `beforeEach`, call `vi.restoreAllMocks()` before resetting browser history so spies cannot leak between cases.

- [ ] **Step 3: Verify routing and scrub tests are red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/App.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: Demo routing and scrub assertions fail while existing launcher tests remain green.

- [ ] **Step 4: Implement `ModeNowRoute`**

Create `ui/src/components/ModeNowRoute.tsx`:

```tsx
import { usePaperPortfolioQuery } from "../api/hooks";
import type { ChartCountPoint } from "../lib/chartTransforms";
import type { Mode } from "./mode-session/types";
import { NowPage } from "./NowPage";
import { DemoNowPage, type DemoNowPageProps } from "./demo-now/DemoNowPage";

type Props = Omit<DemoNowPageProps, "portfolio" | "portfolioState"> & {
  mode: Mode;
  tierSummary?: ChartCountPoint[];
};

function DemoNowRoute(props: Omit<Props, "mode" | "tierSummary">) {
  const portfolioQuery = usePaperPortfolioQuery();
  const portfolioState = portfolioQuery.isLoading
    ? "loading"
    : portfolioQuery.isError || !portfolioQuery.data
      ? "error"
      : "ready";
  return <DemoNowPage {...props} portfolio={portfolioQuery.data} portfolioState={portfolioState} />;
}

export function ModeNowRoute({ mode, tierSummary, ...props }: Props) {
  if (mode === "DEMO") return <DemoNowRoute {...props} />;
  return (
    <NowPage
      items={props.items}
      tierSummary={tierSummary}
      onWhy={props.onWhy}
      onExplain={props.onExplain}
      onInspect={props.onInspect}
      onOpenWorkspace={props.onOpenWorkspace}
    />
  );
}
```

Do not move `usePaperPortfolioQuery` into `ModeNowRoute`; keeping it inside `DemoNowRoute` ensures Paper and Live do not start the extra query.

- [ ] **Step 5: Update `WorkstationShell` with explicit query and scrub states**

In `ui/src/App.tsx`:

1. Replace the `NowPage` import with `ModeNowRoute`, import `ADMITTED_REPLAY_INSTRUMENT_ID` with `AttentionItem`, and import `ScrubState` from `DemoNowPage`.
2. Add state beside `cursorIndex`:

```tsx
const [scrubState, setScrubState] = useState<ScrubState>("idle");
```

3. Derive independent query states after the three queries:

```tsx
const attentionState = attentionQuery.isLoading
  ? "loading"
  : attentionQuery.error || !attentionQuery.data
    ? "error"
    : "ready";
const replayState = replaySessionQuery.isLoading
  ? "loading"
  : replaySessionQuery.error || !replaySessionQuery.data
    ? "error"
    : "ready";
```

4. Replace `scrub` with this confirmed update flow:

```tsx
const scrub = async (index: number) => {
  setScrubState("pending");
  try {
    await api.scrubReplay(index);
    setCursorIndex(index);
    await refreshAll();
    setScrubState("idle");
  } catch {
    setScrubState("error");
  }
};
```

5. Replace the root `NowPage` element with:

```tsx
<ModeNowRoute
  mode={mode}
  items={attentionQuery.data?.items ?? []}
  tierSummary={attentionQuery.data?.tier_summary}
  attentionState={attentionState}
  replayState={replayState}
  cursorIndex={cursorIndex}
  eventCount={replaySessionQuery.data?.event_count}
  scrubState={scrubState}
  onScrub={(index) => { void scrub(index); }}
  onOpenTimeline={() => navigate(`/workspace/${ADMITTED_REPLAY_INSTRUMENT_ID}`)}
  onWhy={openExplain}
  onExplain={openExplain}
  onInspect={openInspect}
  onOpenWorkspace={(item) => {
    if (item.instrument_id) navigate(`/workspace/${item.instrument_id}`);
  }}
/>
```

The `replaySessionQuery` effect remains the only server-to-local cursor synchronization, and no optimistic cursor assignment occurs before `scrubReplay` resolves.

- [ ] **Step 6: Verify green, type-check, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/App.test.tsx src/components/demo-now/DemoNowPage.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/ModeNowRoute.tsx ui/src/App.tsx ui/src/App.test.tsx
git commit -m "feat(ui): route Demo to Now dashboard"
```

Expected: focused tests, TypeScript, and changed validation PASS; Paper and Live still assert Command Center.

---

### Task 6: Apply the approved visual hierarchy, responsiveness, and accessibility states

**Files:**
- Create: `ui/src/styles/demo-now.css`
- Create: `ui/src/vite-env.d.ts`
- Modify: `ui/src/App.tsx`

**Interfaces:**
- Consumes: only `.demo-*` class names emitted by Tasks 2–4 and existing token variables.
- Produces: a scoped two-row balanced command layout that reflows in DOM reading order and does not alter other workstation pages.

- [ ] **Step 1: Add a failing static contract test for the scoped stylesheet**

Create `ui/src/vite-env.d.ts` first so TypeScript recognizes Vite's `?raw` asset import used by the red test:

```ts
/// <reference types="vite/client" />
```

Add this test to the bottom of `ui/src/components/demo-now/DemoNowPage.test.tsx`:

```tsx
import demoNowCss from "../../styles/demo-now.css?raw";

describe("Demo Now visual accessibility contract", () => {
  it("keeps targets, focus, responsive, reduced-motion, and forced-color rules explicit", () => {
    expect(demoNowCss).toContain("min-height: 44px");
    expect(demoNowCss).toContain(":focus-visible");
    expect(demoNowCss).toContain("@media (max-width: 980px)");
    expect(demoNowCss).toContain("@media (max-width: 720px)");
    expect(demoNowCss).toContain("@media (prefers-reduced-motion: reduce)");
    expect(demoNowCss).toContain("@media (forced-colors: active)");
  });
});
```

- [ ] **Step 2: Verify the stylesheet contract is red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoNowPage.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: only the missing raw stylesheet import causes failure.

- [ ] **Step 3: Create the complete scoped stylesheet**

Create `ui/src/styles/demo-now.css`:

```css
.demo-now-page {
  --demo-accent: #67d8f4;
  --demo-accent-soft: rgba(103, 216, 244, 0.12);
  --demo-panel: rgba(18, 26, 38, 0.94);
  --demo-panel-strong: rgba(21, 34, 49, 0.98);
  --demo-line: rgba(128, 161, 188, 0.2);
  display: grid;
  gap: 20px;
  max-width: 1540px;
  margin: 0 auto;
  padding: clamp(4px, 1vw, 16px);
}

.demo-now-intro {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  padding: 20px 4px 8px;
  border-bottom: 1px solid var(--demo-line);
}

.demo-now-intro h1 {
  margin: 4px 0 8px;
  font-size: clamp(2rem, 4vw, 3.65rem);
  line-height: 0.98;
  letter-spacing: -0.045em;
}

.demo-now-intro p:not(.demo-eyebrow) {
  max-width: 760px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.demo-eyebrow,
.demo-intro-mark,
.demo-state-badge,
.demo-metric-grid dt,
.demo-replay-progress-copy span,
.demo-step-list > li > span {
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.demo-eyebrow {
  margin: 0 0 6px;
  color: var(--demo-accent);
  font-size: 0.7rem;
}

.demo-intro-mark,
.demo-state-badge {
  color: var(--text-secondary);
  font-size: 0.68rem;
}

.demo-intro-mark {
  flex: 0 0 auto;
  padding: 8px 10px;
  border: 1px solid var(--demo-line);
  background: rgba(255, 255, 255, 0.02);
}

.demo-now-grid {
  display: grid;
  gap: 18px;
  align-items: stretch;
}

.demo-now-grid-top {
  grid-template-columns: minmax(0, 1.65fr) minmax(300px, 1fr);
}

.demo-now-grid-bottom {
  grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.8fr);
}

.demo-now-panel {
  min-width: 0;
  padding: clamp(18px, 2.4vw, 28px);
  border: 1px solid var(--demo-line);
  border-radius: 10px;
  background: linear-gradient(145deg, var(--demo-panel-strong), var(--demo-panel));
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.18);
}

.demo-replay-panel {
  border-color: rgba(103, 216, 244, 0.34);
  background: radial-gradient(circle at 92% 8%, rgba(103, 216, 244, 0.12), transparent 34%), linear-gradient(145deg, #122234, #101824);
}

.demo-panel-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
  margin-bottom: 18px;
}

.demo-panel-heading h2 {
  margin: 0;
  font-size: clamp(1.15rem, 2vw, 1.55rem);
}

.demo-state-badge {
  padding: 6px 8px;
  border: 1px solid var(--demo-line);
  color: var(--text-secondary);
  white-space: nowrap;
}

.demo-scenario-card {
  display: grid;
  gap: 5px;
  margin-bottom: 22px;
  padding: 15px 16px;
  border-left: 3px solid var(--demo-accent);
  background: var(--demo-accent-soft);
}

.demo-scenario-card strong {
  font-size: 1.05rem;
}

.demo-scenario-card span,
.demo-panel-note,
.demo-empty-path p {
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
}

.demo-replay-progress-copy {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
  margin-bottom: 9px;
}

.demo-replay-progress-copy strong {
  font-family: var(--font-mono);
  font-size: 1.1rem;
}

.demo-replay-progress-copy span {
  color: var(--text-muted);
  font-size: 0.66rem;
}

.demo-replay-progress {
  height: 7px;
  margin-bottom: 20px;
  overflow: hidden;
  border: 1px solid rgba(103, 216, 244, 0.24);
  background: rgba(0, 0, 0, 0.28);
}

.demo-replay-progress > span {
  display: block;
  height: 100%;
  background: var(--demo-accent);
  transition: width 180ms ease-out;
}

.demo-replay-actions,
.demo-now-page .card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.demo-now-page button {
  min-width: 44px;
  min-height: 44px;
  padding: 9px 13px;
  border: 1px solid var(--demo-line);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.045);
  color: var(--text-primary);
  cursor: pointer;
  font: inherit;
}

.demo-now-page button.primary {
  border-color: var(--demo-accent);
  background: var(--demo-accent);
  color: #07131b;
  font-weight: 750;
}

.demo-now-page button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.demo-now-page button:focus-visible {
  outline: 3px solid var(--demo-accent);
  outline-offset: 3px;
}

.demo-metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--demo-line);
  background: var(--demo-line);
}

.demo-metric-grid > div {
  padding: 16px;
  background: rgba(8, 14, 22, 0.74);
}

.demo-metric-grid dt {
  color: var(--text-muted);
  font-size: 0.65rem;
}

.demo-metric-grid dd {
  margin: 8px 0 0;
  font-family: var(--font-mono);
  font-size: clamp(1rem, 2vw, 1.35rem);
}

.demo-panel-note {
  margin: 14px 0 0;
}

.demo-attention-panel .attention-feed {
  gap: 10px;
}

.demo-attention-panel .attention-card {
  border-radius: 7px;
  background: rgba(7, 13, 21, 0.52);
}

.demo-attention-panel .attention-card h2 {
  margin: 0;
  font-size: 1rem;
}

.demo-step-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.demo-step-list li {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  padding: 14px 0;
  border-top: 1px solid var(--demo-line);
}

.demo-step-list > li > span {
  color: var(--demo-accent);
  font-size: 0.68rem;
}

.demo-step-list button {
  width: 100%;
  text-align: left;
}

.demo-empty-path {
  display: grid;
  gap: 14px;
}

@media (max-width: 980px) {
  .demo-now-grid-top,
  .demo-now-grid-bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .demo-now-page {
    gap: 14px;
    padding: 0;
  }

  .demo-now-intro {
    align-items: start;
    flex-direction: column;
    padding-top: 8px;
  }

  .demo-now-panel {
    padding: 17px;
    border-radius: 7px;
  }

  .demo-panel-heading,
  .demo-replay-progress-copy {
    align-items: start;
    flex-direction: column;
  }

  .demo-state-badge {
    white-space: normal;
  }

  .demo-metric-grid {
    grid-template-columns: 1fr;
  }

  .demo-replay-actions button,
  .demo-now-page .card-actions button {
    flex: 1 1 145px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .demo-replay-progress > span {
    transition: none;
  }
}

@media (forced-colors: active) {
  .demo-now-panel,
  .demo-scenario-card,
  .demo-state-badge,
  .demo-intro-mark,
  .demo-replay-progress,
  .demo-now-page button {
    border: 2px solid CanvasText;
  }

  .demo-replay-progress > span,
  .demo-now-page button.primary {
    background: Highlight;
    color: HighlightText;
  }

  .demo-now-page button:focus-visible {
    outline-color: Highlight;
  }
}
```

Add this import after the existing App stylesheet imports:

```tsx
import "./styles/demo-now.css";
```

- [ ] **Step 4: Verify visual contract, type safety, and changed validation**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/demo-now/DemoNowPage.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: stylesheet contract, component tests, TypeScript, and changed validation PASS.

- [ ] **Step 5: Commit the scoped visual system**

```powershell
git add ui/src/styles/demo-now.css ui/src/vite-env.d.ts ui/src/components/demo-now/DemoNowPage.test.tsx ui/src/App.tsx
git commit -m "style(ui): polish Demo Now dashboard"
```

---

### Task 7: Run milestone and final acceptance validation

**Files:**
- Verify only; modify a source or test file only when a failing check identifies a concrete defect, then repeat that task’s focused red-green cycle.

**Interfaces:**
- Consumes: all components and contracts from Tasks 1–6.
- Produces: fresh evidence for all acceptance criteria and a clean implementation worktree.

- [ ] **Step 1: Run every focused Demo and route test together**

From `ui`:

```powershell
.\node_modules\.bin\vitest.cmd run src/components/AttentionFeed.test.tsx src/components/demo-now/DemoReplayOverview.test.tsx src/components/demo-now/DemoPortfolioSummary.test.tsx src/components/demo-now/DemoInspectNext.test.tsx src/components/demo-now/DemoNowPage.test.tsx src/App.test.tsx
```

Expected: all focused tests PASS, including Demo/Paper/Live routing, local failures, bounded controls, callback preservation, and forbidden-control assertions.

- [ ] **Step 2: Run the complete UI test, type, and production-build gates**

From `ui`:

```powershell
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\vite.cmd build
node scripts/check-bundle-budget.mjs
```

Expected: the complete Vitest suite passes; TypeScript reports no errors; Vite produces `dist`; the bundle budget exits zero. Existing React Router future-flag warnings may remain, but this work introduces no new warning or error.

- [ ] **Step 3: Run the UI domain validation milestone**

From the repository root:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py domain ui
```

Expected: PASS with zero failures.

- [ ] **Step 4: Run the full offline repository validation exactly once**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py full
```

Expected: PASS; do not invoke any live provider suite.

- [ ] **Step 5: Inspect the final diff and repository state**

```powershell
git diff --check
git status --short --branch
git log -7 --oneline
```

Expected: no whitespace errors; only the planned commits are ahead of the configured upstream; no uncommitted source or test changes remain. If a verification-driven fix was necessary, commit only its exact files with `git commit -m "fix(ui): correct Demo Now acceptance issue"` and rerun Steps 1–5 before reporting completion.

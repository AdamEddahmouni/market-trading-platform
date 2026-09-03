# Paper Now Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Paper-only Decision Canvas at `/` that combines truthful portfolio risk, attention-candidate review, backend order preview, and a draft-only handoff to a freshly revalidated workspace ticket.

**Architecture:** `ModeNowRoute` gains a Paper branch that loads the existing portfolio query and renders a focused `paper-now` component group. Pure helpers own risk/exception derivation and the shared versioned order-draft contract; the dashboard may preview but only `OrderTicket` may submit, after it revalidates a valid route-state draft against current Paper authority.

**Tech Stack:** React 18, TypeScript 5.6, React Router 6, TanStack Query 5, Zod-backed API types, Vitest, Testing Library, scoped CSS, repository validation scripts.

## Global Constraints

- This increment is UI-only; do not add or change backend endpoints, schemas, execution authority, or paper-session mutations.
- Demo continues to render `DemoNowPage`; Live continues to render the existing `NowPage` Command Center.
- Paper Command may call `/paper/orders/preview`, but it must not expose Submit, Cancel order, Open session, Close session, Archive session, or New session controls.
- Side and quantity start neutral/empty and remain explicit user choices; order type is fixed to `MARKET`.
- Navigation carries only a version-1 draft; never carry risk status, decision, preview output, or an idempotency key as authority.
- Workspace submission remains disabled until a new workspace preview returns `PASS` under current `INTERNAL_SIMULATION` plus `PAPER_ONLY` authority.
- Draft state is ephemeral: only a fresh React Router `PUSH` handoff is accepted; direct loads and reloads ignore history state.
- Every region fails independently; do not replace the page when one query or mutation fails.
- Interactive targets are at least 44 by 44 CSS pixels, with visible focus, reduced-motion, responsive, and forced-colors rules.
- Use the repository-local CPython 3.11 virtual environment and the validation cadence in `AGENTS.md`; full validation stays offline.
- Preserve the unrelated modified evidence files `evidence/ui1/assistant-audit/conversations.json` and `evidence/ui1/assistant-audit/messages.json`; never stage them.

## File Structure

- Create `ui/src/components/paper-now/paperOrderDraft.ts`: versioned route-state parsing, draft validation, fingerprinting, request construction, and attempt-key creation shared by Paper Command and `OrderTicket`.
- Create `ui/src/components/paper-now/paperOrderDraft.test.ts`: boundary tests for the shared draft contract.
- Create `ui/src/components/paper-now/paperDashboardViewModel.ts`: pure candidate, metric, utilization, money, and exception derivation.
- Create `ui/src/components/paper-now/paperDashboardViewModel.test.ts`: non-mutating, invalid-limit, over-limit, and no-guess coverage.
- Create `ui/src/components/paper-now/paperNowTestFixtures.ts`: typed test builders for portfolio and attention payloads.
- Create `ui/src/components/paper-now/PaperRiskRibbon.tsx`: five truthful headline metrics and accessible limit meters.
- Create `ui/src/components/paper-now/PaperCandidateQueue.tsx`: priority-ordered radio selection plus existing research actions.
- Create `ui/src/components/paper-now/PaperExceptionsPanel.tsx`: bounded explicit exception list and Portfolio link.
- Create `ui/src/components/paper-now/PaperPanels.test.tsx`: focused presentation and independent-state coverage.
- Create `ui/src/components/paper-now/PaperPreviewComposer.tsx`: controlled inputs, backend-only preview rendering, Retry, focus announcement, and safe-forward action.
- Create `ui/src/components/paper-now/PaperNowPage.tsx`: selection/draft/preview coordinator and four-region Decision Canvas composition.
- Create `ui/src/components/paper-now/PaperNowPage.test.tsx`: complete dashboard interaction, stale-response, authority, and forbidden-control coverage.
- Modify `ui/src/components/ModeNowRoute.tsx`: explicit Demo/Paper/Live branches and Paper portfolio query ownership.
- Modify `ui/src/App.tsx`: pass confirmed global Paper permission and import Paper styles.
- Modify `ui/src/App.test.tsx`: mode routing and dashboard-level regression coverage.
- Create `ui/src/components/paper/OrderTicket.test.tsx`: initial-draft and one-shot workspace revalidation coverage.
- Modify `ui/src/components/paper/OrderTicket.tsx`: optional initial draft, shared request builder, invalidation on edits, and workspace revalidation label.
- Modify `ui/src/components/WorkspaceRoute.tsx`: accept only fresh matching `PUSH` state and clear it after consumption.
- Modify `ui/src/components/WorkspacePage.tsx`: pass the validated optional draft to `OrderTicket`.
- Modify `ui/src/components/WorkspacePage.test.tsx`: confirm the draft reaches an authorized ticket without changing mode restrictions.
- Create `ui/src/components/WorkspaceRoute.test.tsx`: valid push, mismatched state, invalid state, and POP/reload behavior.
- Create `ui/src/styles/paper-now.css`: scoped Decision Canvas visual hierarchy and accessibility media rules.

---

### Task 1: Define the shared Paper order-draft boundary

**Files:**
- Create: `ui/src/components/paper-now/paperOrderDraft.ts`
- Create: `ui/src/components/paper-now/paperOrderDraft.test.ts`

**Interfaces:**
- Consumes: `PaperOrderRequest` from `ui/src/api/schemas.ts`.
- Produces: `PaperOrderDraft`, `PaperOrderSide`, `createPaperOrderDraft`, `parsePaperOrderDraft`, `paperOrderDraftFingerprint`, `buildPaperOrderRequest`, and `createPaperPreviewAttemptKey`.

- [ ] **Step 1: Write the failing draft-contract tests**

Create `ui/src/components/paper-now/paperOrderDraft.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import {
  buildPaperOrderRequest,
  createPaperOrderDraft,
  createPaperPreviewAttemptKey,
  paperOrderDraftFingerprint,
  parsePaperOrderDraft,
} from "./paperOrderDraft";

describe("paper order draft", () => {
  it("creates only an explicit integer MARKET draft within the account limit", () => {
    expect(createPaperOrderDraft({
      instrumentId: " biya ", side: "BUY", quantity: 25, maxOrderShares: 100,
      sourceAttentionId: "attention-1",
    })).toEqual({
      version: 1, instrumentId: "BIYA", side: "BUY", quantity: 25,
      orderType: "MARKET", sourceAttentionId: "attention-1",
    });
    expect(createPaperOrderDraft({ instrumentId: "BIYA", side: null, quantity: 25, maxOrderShares: 100 })).toBeNull();
    expect(createPaperOrderDraft({ instrumentId: "BIYA", side: "SELL", quantity: 1.5, maxOrderShares: 100 })).toBeNull();
    expect(createPaperOrderDraft({ instrumentId: "BIYA", side: "SELL", quantity: 101, maxOrderShares: 100 })).toBeNull();
  });

  it("accepts only a structurally valid version-1 draft matching the route symbol", () => {
    const draft = { version: 1, instrumentId: "BIYA", side: "SELL", quantity: 4, orderType: "MARKET" };
    expect(parsePaperOrderDraft(draft, "biya")).toEqual(draft);
    expect(parsePaperOrderDraft({ ...draft, instrumentId: "NVDA" }, "BIYA")).toBeUndefined();
    expect(parsePaperOrderDraft({ ...draft, version: 2 }, "BIYA")).toBeUndefined();
    expect(parsePaperOrderDraft({ ...draft, risk_status: "PASS" }, "BIYA")).toBeUndefined();
  });

  it("builds a request from the draft without carrying preview authority", () => {
    const draft = { version: 1 as const, instrumentId: "BIYA", side: "BUY" as const, quantity: 5, orderType: "MARKET" as const };
    expect(buildPaperOrderRequest(draft, "attempt-1")).toEqual({
      side: "BUY", quantity: 5, order_type: "MARKET", instrument_id: "BIYA", symbol: "BIYA",
      client_order_id: "attempt-1", idempotency_key: "attempt-1",
    });
    expect(paperOrderDraftFingerprint(draft)).toBe("BIYA|BUY|5|MARKET");
  });

  it("creates a new attempt key for each preview attempt", () => {
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002");
    expect(createPaperPreviewAttemptKey("paper-now")).not.toBe(createPaperPreviewAttemptKey("paper-now"));
  });
});
```

- [ ] **Step 2: Run the focused test and confirm red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/paperOrderDraft.test.ts
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: Vitest fails because `paperOrderDraft.ts` does not exist; changed validation reports the same UI failure.

- [ ] **Step 3: Implement the complete shared contract**

Create `ui/src/components/paper-now/paperOrderDraft.ts`:

```ts
import type { PaperOrderRequest } from "../../api/schemas";

export type PaperOrderSide = "BUY" | "SELL";

export type PaperOrderDraft = {
  version: 1;
  instrumentId: string;
  side: PaperOrderSide;
  quantity: number;
  orderType: "MARKET";
  sourceAttentionId?: string;
};

type DraftInput = {
  instrumentId: string;
  side: PaperOrderSide | null;
  quantity: number | null;
  maxOrderShares: number;
  sourceAttentionId?: string;
};

export function createPaperOrderDraft(input: DraftInput): PaperOrderDraft | null {
  const instrumentId = input.instrumentId.trim().toUpperCase();
  if (!instrumentId || !input.side || input.quantity === null) return null;
  if (!Number.isInteger(input.quantity) || input.quantity < 1) return null;
  if (!Number.isFinite(input.maxOrderShares) || input.maxOrderShares < 1 || input.quantity > input.maxOrderShares) return null;
  return {
    version: 1,
    instrumentId,
    side: input.side,
    quantity: input.quantity,
    orderType: "MARKET",
    ...(input.sourceAttentionId ? { sourceAttentionId: input.sourceAttentionId } : {}),
  };
}

export function parsePaperOrderDraft(value: unknown, routeSymbol: string): PaperOrderDraft | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const candidate = value as Record<string, unknown>;
  const allowed = new Set(["version", "instrumentId", "side", "quantity", "orderType", "sourceAttentionId"]);
  if (Object.keys(candidate).some((key) => !allowed.has(key))) return undefined;
  if (candidate.version !== 1 || candidate.orderType !== "MARKET") return undefined;
  if (candidate.side !== "BUY" && candidate.side !== "SELL") return undefined;
  if (typeof candidate.instrumentId !== "string" || candidate.instrumentId.trim().toUpperCase() !== routeSymbol.trim().toUpperCase()) return undefined;
  if (typeof candidate.quantity !== "number" || !Number.isInteger(candidate.quantity) || candidate.quantity < 1) return undefined;
  if (candidate.sourceAttentionId !== undefined && typeof candidate.sourceAttentionId !== "string") return undefined;
  return {
    version: 1,
    instrumentId: candidate.instrumentId.trim().toUpperCase(),
    side: candidate.side,
    quantity: candidate.quantity,
    orderType: "MARKET",
    ...(candidate.sourceAttentionId ? { sourceAttentionId: candidate.sourceAttentionId } : {}),
  };
}

export function paperOrderDraftFingerprint(draft: PaperOrderDraft): string {
  return `${draft.instrumentId}|${draft.side}|${draft.quantity}|${draft.orderType}`;
}

export function buildPaperOrderRequest(draft: PaperOrderDraft, attemptKey: string): PaperOrderRequest {
  return {
    side: draft.side,
    quantity: draft.quantity,
    order_type: draft.orderType,
    instrument_id: draft.instrumentId,
    symbol: draft.instrumentId,
    client_order_id: attemptKey,
    idempotency_key: attemptKey,
  };
}

export function createPaperPreviewAttemptKey(scope: "paper-now" | "workspace-ticket"): string {
  return `${scope}-${globalThis.crypto.randomUUID()}`;
}
```

- [ ] **Step 4: Verify green, run changed validation, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/paperOrderDraft.test.ts
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/paper-now/paperOrderDraft.ts ui/src/components/paper-now/paperOrderDraft.test.ts
git commit -m "feat(ui): define Paper order draft contract"
```

Expected: focused Vitest, TypeScript, and changed validation pass.

---

### Task 2: Derive candidates, risk metrics, and explicit exceptions

**Files:**
- Create: `ui/src/components/paper-now/paperDashboardViewModel.ts`
- Create: `ui/src/components/paper-now/paperDashboardViewModel.test.ts`
- Create: `ui/src/components/paper-now/paperNowTestFixtures.ts`

**Interfaces:**
- Consumes: `AttentionItem` and `PaperPortfolioResponse` API types.
- Produces: `sortPaperCandidates`, `nextPaperCandidateId`, `paperRiskMetrics`, `derivePaperExceptions`, `formatMinorCurrency`, `LimitUtilization`, `PaperRiskMetric`, and `PaperException`.

- [ ] **Step 1: Add typed test builders and failing pure tests**

Create `paperNowTestFixtures.ts`:

```ts
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";

export function attentionItem(overrides: Partial<AttentionItem> = {}): AttentionItem {
  return {
    attention_id: "attention-biya",
    priority_rank: 2,
    reasons: [{ code: "PRICE_VOLUME", label: "Price and volume expanded" }],
    instrument_id: "BIYA",
    headline: "BIYA setup",
    explanation_ref: "explain:attention:biya",
    tier: 1,
    ...overrides,
  };
}

type PortfolioOverrides = Omit<Partial<PaperPortfolioResponse>, "account" | "risk" | "data_health"> & {
  account?: Partial<PaperPortfolioResponse["account"]>;
  risk?: Partial<PaperPortfolioResponse["risk"]> & { limits?: Partial<PaperPortfolioResponse["risk"]["limits"]> };
  data_health?: Partial<PaperPortfolioResponse["data_health"]>;
};

export function paperPortfolio(overrides: PortfolioOverrides = {}): PaperPortfolioResponse {
  const account: PaperPortfolioResponse["account"] = {
    paper_account_id: "paper-acct",
    session_id: "paper-session",
    currency: "USD",
    cash_display: "1000.00",
    cash_minor: 100000,
    buying_power_minor: 250000,
    initial_cash_minor: 100000,
    realized_pnl_display: "25.00",
    realized_pnl_minor: 2500,
    data_mode: "FIXTURE_REPLAY",
    data_provider: "INTERNAL",
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
    execution_provider: "INTERNAL",
    ...overrides.account,
  };
  const limits = {
    max_open_orders: 5,
    max_order_shares: 100,
    max_position_shares: 500,
    ...overrides.risk?.limits,
  };
  const risk: PaperPortfolioResponse["risk"] = {
    kill_switch_active: false,
    open_order_count: 2,
    reconciliation_status: "INTERNAL_AUTHORITATIVE",
    ...overrides.risk,
    limits,
  };
  const dataHealth = { state: "PASS", detail: "Current", ...overrides.data_health };
  const { account: _account, risk: _risk, data_health: _dataHealth, ...topLevel } = overrides;
  return {
    as_of_context: {
      mode: "PAPER",
      data_mode: "FIXTURE_REPLAY",
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
      as_of_time: "2026-08-31T12:00:00Z",
      timezone: "America/New_York",
    },
    authority_boundary: "PAPER_ONLY",
    account,
    positions: [
      { instrument_id: "BIYA", symbol: "BIYA", quantity: 200, side: "LONG", mark_quality: "CURRENT" },
      { instrument_id: "NVDA", symbol: "NVDA", quantity: -50, side: "SHORT", mark_quality: "STALE" },
    ],
    orders: [],
    fills: [],
    risk,
    data_health: dataHealth,
    reconciliation_status: "INTERNAL_AUTHORITATIVE",
    exposure: { gross_shares: 250, net_shares: 150 },
    pnl: { realized_display: "25.00", unrealized_display: "10.00", total_display: "35.00" },
    ...topLevel,
  };
}
```

Create `paperDashboardViewModel.test.ts` with these exact cases:

```ts
import { describe, expect, it } from "vitest";
import { attentionItem, paperPortfolio } from "./paperNowTestFixtures";
import {
  derivePaperExceptions, formatMinorCurrency, nextPaperCandidateId,
  paperRiskMetrics, sortPaperCandidates,
} from "./paperDashboardViewModel";

describe("Paper dashboard view model", () => {
  it("sorts candidates without mutating the API array and keeps instrument-less items visible", () => {
    const items = [attentionItem({ attention_id: "late", priority_rank: 8 }), attentionItem({ attention_id: "none", priority_rank: 1, instrument_id: undefined }), attentionItem({ attention_id: "top", priority_rank: 2 })];
    expect(sortPaperCandidates(items).map((item) => item.attention_id)).toEqual(["none", "top", "late"]);
    expect(items.map((item) => item.attention_id)).toEqual(["late", "none", "top"]);
    expect(nextPaperCandidateId(items, null)).toBe("top");
    expect(nextPaperCandidateId(items, "late")).toBe("late");
    expect(nextPaperCandidateId(items.filter((item) => item.attention_id !== "late"), "late")).toBe("top");
  });

  it("formats buying power from minor units and never substitutes cash", () => {
    expect(formatMinorCurrency(250000, "USD")).toBe("$2,500.00");
    expect(formatMinorCurrency(Number.NaN, "USD")).toBeNull();
    expect(formatMinorCurrency(100, "NOT_A_CURRENCY")).toBeNull();
  });

  it("keeps raw limit values while clamping only visual utilization", () => {
    const metrics = paperRiskMetrics(paperPortfolio({ positions: [{ instrument_id: "BIYA", symbol: "BIYA", quantity: 700, side: "LONG", mark_quality: "CURRENT" }] }));
    expect(metrics.find((metric) => metric.id === "largest-position")).toMatchObject({ value: "700 / 500 sh", percent: 100 });
    expect(metrics.find((metric) => metric.id === "open-orders")).toMatchObject({ value: "2 / 5", percent: 40 });
  });

  it("shows unavailable utilization for zero or invalid denominators", () => {
    const payload = paperPortfolio();
    payload.risk.limits.max_position_shares = 0;
    payload.risk.limits.max_open_orders = Number.NaN;
    const metrics = paperRiskMetrics(payload);
    expect(metrics.find((metric) => metric.id === "largest-position")?.available).toBe(false);
    expect(metrics.find((metric) => metric.id === "open-orders")?.available).toBe(false);
  });

  it("orders explicit exceptions, caps at five, and does not guess unknown records", () => {
    const payload = paperPortfolio({
      orders: [{ state: "REJECTED", order_id: "o-1" }, { status: "WAITING_FOR_DATA", order_id: "o-2" }, { mystery: true }],
      risk: { kill_switch_active: true, open_order_count: 2, reconciliation_status: "DRIFT", limits: { max_open_orders: 5, max_order_shares: 100, max_position_shares: 500 }, last_decision: { risk_status: "BLOCKED", reason_code: "POSITION_LIMIT" } },
      data_health: { state: "UNAVAILABLE", detail: "feed offline" },
      reconciliation_status: "DRIFT",
    });
    const exceptions = derivePaperExceptions(payload);
    expect(exceptions).toHaveLength(5);
    expect(exceptions[0].code).toBe("KILL_SWITCH_ACTIVE");
    expect(exceptions.map((item) => item.message).join(" ")).not.toContain("mystery");
  });

  it("returns no exceptions for explicitly healthy states", () => {
    expect(derivePaperExceptions(paperPortfolio({ positions: [] }))).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the tests and confirm red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/paperDashboardViewModel.test.ts
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

Expected: failure on the missing view-model module.

- [ ] **Step 3: Implement the pure view model**

Create `paperDashboardViewModel.ts` with these exact exported shapes and rules:

```ts
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";

export type PaperRiskMetric = { id: string; label: string; value: string; detail?: string; available: boolean; percent?: number };
export type PaperException = { code: string; severity: 0 | 1 | 2; message: string; detail?: string };
export type LimitUtilization = { raw: number; limit: number; percent: number; available: boolean };

const HEALTHY = new Set(["PASS", "HEALTHY", "CURRENT", "AVAILABLE"]);
const RECONCILED = new Set(["PASS", "HEALTHY", "CLEAN", "RECONCILED", "INTERNAL_AUTHORITATIVE"]);
const PROBLEM_ORDER_STATE = /(BLOCKED|REJECTED|WAITING|FAILED)/;

function recordString(value: unknown, keys: string[]): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const row = value as Record<string, unknown>;
  for (const key of keys) if (typeof row[key] === "string" && row[key]) return row[key] as string;
  return undefined;
}

export function sortPaperCandidates(items: AttentionItem[]): AttentionItem[] {
  return [...items].sort((left, right) => left.priority_rank - right.priority_rank);
}

export function nextPaperCandidateId(items: AttentionItem[], currentId: string | null): string | null {
  const eligible = sortPaperCandidates(items).filter((item) => Boolean(item.instrument_id?.trim()));
  if (currentId && eligible.some((item) => item.attention_id === currentId)) return currentId;
  return eligible[0]?.attention_id ?? null;
}

export function formatMinorCurrency(minor: number, currency: string): string | null {
  if (!Number.isFinite(minor) || !currency) return null;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(minor / 100);
  } catch { return null; }
}

function utilization(raw: number, limit: number): LimitUtilization {
  const available = Number.isFinite(raw) && Number.isFinite(limit) && limit > 0;
  return { raw, limit, available, percent: available ? Math.min(100, Math.max(0, (Math.abs(raw) / limit) * 100)) : 0 };
}

export function paperRiskMetrics(portfolio: PaperPortfolioResponse): PaperRiskMetric[] {
  const largest = Math.max(0, ...portfolio.positions.map((position) => Math.abs(position.quantity)));
  const positionUse = utilization(largest, portfolio.risk.limits.max_position_shares);
  const orderUse = utilization(portfolio.risk.open_order_count, portfolio.risk.limits.max_open_orders);
  const buyingPower = formatMinorCurrency(portfolio.account.buying_power_minor, portfolio.account.currency);
  return [
    { id: "total-pnl", label: "Total P&L", value: portfolio.pnl?.total_display ?? portfolio.account.realized_pnl_display, available: true },
    { id: "buying-power", label: "Buying power", value: buyingPower ?? "Unavailable", available: buyingPower !== null },
    { id: "gross-exposure", label: "Gross exposure", value: `${portfolio.exposure?.gross_shares ?? 0} sh`, available: true },
    { id: "largest-position", label: "Largest position", value: positionUse.available ? `${positionUse.raw} / ${positionUse.limit} sh` : "Unavailable", detail: positionUse.available ? "Position share limit" : "Position limit unavailable", available: positionUse.available, percent: positionUse.available ? positionUse.percent : undefined },
    { id: "open-orders", label: "Open orders", value: orderUse.available ? `${orderUse.raw} / ${orderUse.limit}` : "Unavailable", detail: orderUse.available ? "Open-order limit" : "Open-order limit unavailable", available: orderUse.available, percent: orderUse.available ? orderUse.percent : undefined },
  ];
}

export function derivePaperExceptions(portfolio: PaperPortfolioResponse): PaperException[] {
  const rows: Array<PaperException & { sourceOrder: number }> = [];
  let sourceOrder = 0;
  const add = (item: PaperException) => rows.push({ ...item, sourceOrder: sourceOrder++ });
  if (portfolio.risk.kill_switch_active) add({ code: "KILL_SWITCH_ACTIVE", severity: 0, message: "Kill switch is active." });
  const health = portfolio.data_health.state.toUpperCase();
  if (!HEALTHY.has(health)) add({ code: `DATA_${health}`, severity: 0, message: `Data health is ${health}.`, detail: portfolio.data_health.detail });
  const reconciliation = (portfolio.reconciliation_status ?? portfolio.risk.reconciliation_status).toUpperCase();
  if (!RECONCILED.has(reconciliation)) add({ code: `RECONCILIATION_${reconciliation}`, severity: 0, message: `Reconciliation is ${reconciliation}.` });
  const decision = recordString(portfolio.risk.last_decision, ["risk_status", "decision", "status"]);
  if (decision && decision.toUpperCase() !== "PASS") add({ code: `RISK_${decision.toUpperCase()}`, severity: 1, message: `Last risk decision: ${decision}.`, detail: recordString(portfolio.risk.last_decision, ["reason_code", "reason", "decision_code"]) });
  portfolio.orders.forEach((order) => {
    const state = recordString(order, ["state", "status", "order_state"]);
    if (state && PROBLEM_ORDER_STATE.test(state.toUpperCase())) add({ code: `ORDER_${state.toUpperCase()}`, severity: 1, message: `Order ${recordString(order, ["order_id", "id"]) ?? "state"}: ${state}.` });
  });
  portfolio.positions.forEach((position) => {
    const quality = position.mark_quality?.toUpperCase();
    if (quality && !HEALTHY.has(quality)) add({ code: `MARK_${quality}`, severity: 2, message: `${position.symbol} mark is ${quality}.` });
  });
  return rows.sort((left, right) => left.severity - right.severity || left.sourceOrder - right.sourceOrder).slice(0, 5).map(({ sourceOrder: _sourceOrder, ...item }) => item);
}
```

- [ ] **Step 4: Verify green, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/paperDashboardViewModel.test.ts
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/paper-now/paperDashboardViewModel.ts ui/src/components/paper-now/paperDashboardViewModel.test.ts ui/src/components/paper-now/paperNowTestFixtures.ts
git commit -m "feat(ui): derive Paper dashboard state"
```

---

### Task 3: Build risk, candidate, and exception panels

**Files:**
- Create: `ui/src/components/paper-now/PaperRiskRibbon.tsx`
- Create: `ui/src/components/paper-now/PaperCandidateQueue.tsx`
- Create: `ui/src/components/paper-now/PaperExceptionsPanel.tsx`
- Create: `ui/src/components/paper-now/PaperPanels.test.tsx`

**Interfaces:**
- Consumes: `PaperRiskMetric[]`, `PaperException[]`, sorted `AttentionItem[]`, and the existing Why/Explain/Inspect/Open workspace callbacks.
- Produces: named regions with independent `loading | ready | error` behavior and accessible radio candidate selection.

- [ ] **Step 1: Write failing panel tests**

Create `PaperPanels.test.tsx` that renders each panel and asserts:

```tsx
expect(screen.getByRole("region", { name: "Risk summary" })).toHaveTextContent("Largest position200 / 500 sh");
expect(screen.getByRole("meter", { name: "Largest position utilization" })).toHaveAttribute("aria-valuenow", "40");
expect(screen.getByRole("radiogroup", { name: "Paper candidates" })).toBeInTheDocument();
expect(screen.getByRole("radio", { name: /BIYA/ })).toBeChecked();
expect(screen.getByText("Macro review").closest("article")).toHaveTextContent("Research only");
expect(screen.getByRole("button", { name: "Explain Macro review" })).toBeEnabled();
expect(screen.getByRole("region", { name: "Active exceptions" })).toHaveTextContent("No active exceptions");
expect(screen.getByRole("link", { name: "Open full portfolio" })).toHaveAttribute("href", "/portfolio");
```

Add these independent-state assertions after the primary panel test:

```tsx
it("keeps confirmed risk visible when attention fails", () => {
  render(<MemoryRouter><><PaperRiskRibbon portfolio={paperPortfolio()} state="ready" /><PaperCandidateQueue items={[]} state="error" selectedAttentionId={null} onSelect={vi.fn()} onWhy={vi.fn()} onExplain={vi.fn()} onInspect={vi.fn()} onOpenWorkspace={vi.fn()} /></></MemoryRouter>);
  expect(screen.getByRole("region", { name: "Risk summary" })).toHaveTextContent("$2,500.00");
  expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable");
});

it("keeps candidate research actions visible when portfolio fails", () => {
  render(<MemoryRouter><><PaperRiskRibbon state="error" /><PaperCandidateQueue items={[attentionItem()]} state="ready" selectedAttentionId="attention-biya" onSelect={vi.fn()} onWhy={vi.fn()} onExplain={vi.fn()} onInspect={vi.fn()} onOpenWorkspace={vi.fn()} /></></MemoryRouter>);
  expect(screen.getByRole("region", { name: "Risk summary" })).toHaveTextContent("Unavailable");
  expect(screen.getByRole("button", { name: "Explain BIYA setup" })).toBeEnabled();
});
```

- [ ] **Step 2: Run the panel test and confirm red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/PaperPanels.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

- [ ] **Step 3: Implement the three presentational panels**

Create `PaperRiskRibbon.tsx`:

```tsx
import type { PaperPortfolioResponse } from "../../api/client";
import { paperRiskMetrics } from "./paperDashboardViewModel";

type Props = { portfolio?: PaperPortfolioResponse; state: "loading" | "ready" | "error" };

export function PaperRiskRibbon({ portfolio, state }: Props) {
  return (
    <section className="paper-risk-ribbon" aria-label="Risk summary">
      <h2>Risk summary</h2>
      {state === "loading" ? <p role="status">Loading portfolio risk…</p> : null}
      {state === "error" || !portfolio ? <p className="unavailable">Portfolio risk unavailable.</p> : null}
      {state === "ready" && portfolio ? (
        <dl>
          {paperRiskMetrics(portfolio).map((metric) => (
            <div key={metric.id} className={metric.available ? "" : "unavailable"}>
              <dt>{metric.label}</dt><dd>{metric.value}</dd>
              {metric.detail ? <span>{metric.detail}</span> : null}
              {metric.percent !== undefined ? (
                <div className="paper-risk-meter" role="meter" aria-label={`${metric.label} utilization`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(metric.percent)} aria-valuetext={metric.value}>
                  <span style={{ width: `${metric.percent}%` }} />
                </div>
              ) : null}
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}
```

Create `PaperCandidateQueue.tsx`:

```tsx
import type { AttentionItem } from "../../api/client";
import { sortPaperCandidates } from "./paperDashboardViewModel";

type Props = {
  items: AttentionItem[]; state: "loading" | "ready" | "error"; selectedAttentionId: string | null;
  onSelect: (attentionId: string) => void; onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void; onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function PaperCandidateQueue({ items, state, selectedAttentionId, onSelect, onWhy, onExplain, onInspect, onOpenWorkspace }: Props) {
  const sorted = sortPaperCandidates(items);
  const hasEligible = sorted.some((item) => Boolean(item.instrument_id?.trim()));
  return (
    <section className="paper-panel paper-candidate-panel" aria-label="Candidate queue">
      <header><h2>Candidate queue</h2><span>{sorted.length} signals</span></header>
      {state === "loading" ? <p role="status">Loading attention feed…</p> : null}
      {state === "error" ? <p role="alert">Attention feed unavailable.</p> : null}
      {state === "ready" ? (
        <div role="radiogroup" aria-label="Paper candidates">
          {sorted.map((item) => {
            const selected = item.attention_id === selectedAttentionId;
            return (
              <article key={item.attention_id} className={`paper-candidate tier-${item.tier ?? 2}${selected ? " selected" : ""}`} aria-selected={selected}>
                <div className="card-head"><h3>{item.headline}</h3>{item.instrument_id ? <code>{item.instrument_id}</code> : null}</div>
                {item.instrument_id ? (
                  <label className="paper-candidate-selector"><input type="radio" name="paper-candidate" checked={selected} onChange={() => onSelect(item.attention_id)} /><span>{item.instrument_id} candidate{selected ? " · Selected candidate" : ""}</span></label>
                ) : <span className="paper-research-only">Research only</span>}
                <ul className="reason-codes">{item.reasons.map((reason) => <li key={reason.code}><code>{reason.code}</code> {reason.label}</li>)}</ul>
                <div className="card-actions">
                  <button type="button" aria-label={`Why here? ${item.headline}`} onClick={() => onWhy(item)}>Why here?</button>
                  <button type="button" aria-label={`Explain ${item.headline}`} onClick={() => onExplain(item)}>Explain</button>
                  <button type="button" aria-label={`Inspect ${item.headline}`} onClick={() => onInspect(item)}>Inspect</button>
                  {item.instrument_id ? <button type="button" aria-label={`Open ${item.instrument_id} workspace`} onClick={() => onOpenWorkspace(item)}>Open workspace</button> : null}
                </div>
              </article>
            );
          })}
          {!hasEligible ? <p className="unavailable">No instrument-backed candidate is available.</p> : null}
        </div>
      ) : null}
    </section>
  );
}
```

Create `PaperExceptionsPanel.tsx`:

```tsx
import { Link } from "react-router-dom";
import type { PaperPortfolioResponse } from "../../api/client";
import { derivePaperExceptions } from "./paperDashboardViewModel";

type Props = { portfolio?: PaperPortfolioResponse; state: "loading" | "ready" | "error" };

export function PaperExceptionsPanel({ portfolio, state }: Props) {
  const exceptions = state === "ready" && portfolio ? derivePaperExceptions(portfolio) : [];
  return (
    <section className="paper-panel paper-exceptions-panel" aria-label="Active exceptions">
      <header><h2>Active exceptions</h2><span>{exceptions.length}</span></header>
      {state === "loading" ? <p role="status">Loading exceptions…</p> : null}
      {state === "error" || !portfolio ? <p className="unavailable">Portfolio exceptions unavailable.</p> : null}
      {state === "ready" && portfolio && exceptions.length === 0 ? <p>No active exceptions</p> : null}
      {exceptions.length > 0 ? <ul>{exceptions.map((item) => <li key={`${item.code}-${item.message}`} data-severity={item.severity}><code>{item.code}</code><strong>{item.message}</strong>{item.detail ? <span>{item.detail}</span> : null}</li>)}</ul> : null}
      <Link to="/portfolio">Open full portfolio</Link>
    </section>
  );
}
```

- [ ] **Step 4: Verify green, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/PaperPanels.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/paper-now/PaperRiskRibbon.tsx ui/src/components/paper-now/PaperCandidateQueue.tsx ui/src/components/paper-now/PaperExceptionsPanel.tsx ui/src/components/paper-now/PaperPanels.test.tsx
git commit -m "feat(ui): add Paper decision panels"
```

---

### Task 4: Compose Paper Command and the safe preview workflow

**Files:**
- Create: `ui/src/components/paper-now/PaperPreviewComposer.tsx`
- Create: `ui/src/components/paper-now/PaperNowPage.tsx`
- Create: `ui/src/components/paper-now/PaperNowPage.test.tsx`

**Interfaces:**
- Consumes: Task 1 draft helpers, Task 2 derivations, Task 3 panels, `usePreviewPaperOrderMutation`, and existing attention callbacks.
- Produces: `PaperNowPageProps` and `PaperNowPage`; `onContinue(draft)` emits only a validated `PaperOrderDraft` after a current PASS.

- [ ] **Step 1: Write failing dashboard interaction tests**

Use `vi.hoisted` to expose `previewPaperOrder`, mock `usePreviewPaperOrderMutation` as `{ mutateAsync: previewPaperOrder, isPending: false }`, and render with `MemoryRouter`. Implement one test per behavior below; use `paperPortfolio()` and three `attentionItem()` calls with ranks `1` (no instrument), `2` (BIYA), and `3` (NVDA):

1. One `Paper Command` h1 and named regions `Risk summary`, `Candidate queue`, `Order preview`, and `Active exceptions`.
2. Highest-priority instrument-backed item is selected; an instrument-less rank-1 item remains researchable.
3. Neither BUY nor SELL is selected and quantity is empty on first render; Preview is disabled.
4. Selecting BUY and entering `10` enables Preview only when `paperActionsPermitted` and portfolio authority are valid.
5. Preview calls `mutateAsync` with symbol/instrument, explicit side/quantity, `MARKET`, and equal new client/idempotency keys.
6. PASS renders current/projected position, available exposure/limits/utilization/model fields and `Open workspace and revalidate`; BLOCKED renders reasons but no continuation.
7. Editing quantity after PASS removes the continuation immediately.
8. Resolve a first preview promise after changing quantity and completing a second preview; only the second response is rendered.
9. A rejected preview preserves side and quantity, announces an alert, and changes the action label to Retry.
10. The page contains none of: `Submit`, `Cancel order`, `Open session`, `Close session`, `Archive session`, `New Paper Session`.

- [ ] **Step 2: Run the tests and confirm red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/PaperNowPage.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

- [ ] **Step 3: Implement the controlled preview composer**

Create `PaperPreviewComposer.tsx`:

```tsx
import { useEffect, useRef } from "react";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import type { PaperOrderSide } from "./paperOrderDraft";

type Props = {
  instrumentId: string | null;
  side: PaperOrderSide | null;
  quantityText: string;
  maxOrderShares?: number;
  disabledReason?: string;
  pending: boolean;
  error: string | null;
  preview: PaperOrderPreviewResponse["preview"] | null;
  canContinue: boolean;
  onSideChange: (side: PaperOrderSide) => void;
  onQuantityChange: (value: string) => void;
  onPreview: () => void;
  onContinue: () => void;
};

function optionalRows(preview: PaperOrderPreviewResponse["preview"]) {
  const rows = [
    ["Current position", preview.current_position_shares],
    ["Projected position", preview.projected_position_shares],
    ["Current gross exposure", preview.current_gross_exposure_shares],
    ["Estimated gross exposure", preview.estimated_gross_exposure_shares],
    ["Current net exposure", preview.current_net_exposure_shares],
    ["Estimated net exposure", preview.estimated_net_exposure_shares],
  ] as const;
  return rows.filter((row) => row[1] !== undefined);
}

export function PaperPreviewComposer({ instrumentId, side, quantityText, maxOrderShares, disabledReason, pending, error, preview, canContinue, onSideChange, onQuantityChange, onPreview, onContinue }: Props) {
  const resultHeadingRef = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => { if (preview) resultHeadingRef.current?.focus(); }, [preview]);
  return (
    <section className="paper-panel paper-preview-panel" aria-label="Order preview">
      <header><div><span className="paper-eyebrow">Review and preview</span><h2>{instrumentId ?? "No candidate selected"}</h2></div><code>MARKET</code></header>
      <p>Choose direction and size. Preview validates current Paper risk; it does not authorize submission.</p>
      <fieldset disabled={!instrumentId || pending}><legend>Order side</legend><label><input type="radio" name="paper-side" checked={side === "BUY"} onChange={() => onSideChange("BUY")} />BUY</label><label><input type="radio" name="paper-side" checked={side === "SELL"} onChange={() => onSideChange("SELL")} />SELL</label></fieldset>
      <label className="paper-quantity">Quantity<input type="number" inputMode="numeric" min={1} max={maxOrderShares} value={quantityText} onChange={(event) => onQuantityChange(event.target.value)} disabled={!instrumentId || pending} /></label>
      <dl className="paper-order-fixed"><div><dt>Order type</dt><dd>MARKET</dd></div>{maxOrderShares !== undefined ? <div><dt>Account limit</dt><dd>{maxOrderShares} sh</dd></div> : null}</dl>
      {disabledReason ? <p id="paper-preview-disabled" className="muted">{disabledReason}</p> : null}
      <button type="button" className="primary" onClick={onPreview} disabled={Boolean(disabledReason) || pending} aria-describedby={disabledReason ? "paper-preview-disabled" : undefined}>{error ? "Retry preview" : "Preview order"}</button>
      {pending ? <p role="status">Validating draft…</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {preview ? (
        <div className={`paper-preview-result ${preview.risk_status === "PASS" ? "pass" : "blocked"}`}>
          <h3 ref={resultHeadingRef} tabIndex={-1}>Preview result</h3>
          <p>Risk <strong>{preview.risk_status}</strong> · {preview.decision}</p>
          {preview.reason_codes?.length ? <p>Reasons: {preview.reason_codes.join(", ")}</p> : null}
          {optionalRows(preview).length ? <dl>{optionalRows(preview).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value} sh</dd></div>)}</dl> : null}
          {preview.risk_limits ? <p>Limits: order {preview.risk_limits.max_order_shares} · position {preview.risk_limits.max_position_shares} · open orders {preview.risk_limits.max_open_orders}</p> : null}
          {preview.risk_utilization ? <ul>{Object.entries(preview.risk_utilization).map(([key, value]) => <li key={key}><code>{key}</code> {typeof value === "object" ? JSON.stringify(value) : String(value)}</li>)}</ul> : null}
          <p>Quality {preview.quality_state ?? "UNKNOWN"} · Fill preview {preview.fill_preview_available === undefined ? "UNKNOWN" : preview.fill_preview_available ? "AVAILABLE" : "UNAVAILABLE"}</p>
          {preview.execution_model ? <p>Model {preview.execution_model}{preview.execution_model_version ? ` · ${preview.execution_model_version}` : ""}</p> : null}
          {canContinue ? <button type="button" className="primary" onClick={onContinue}>Open workspace and revalidate</button> : null}
        </div>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 4: Implement the page coordinator with stale-response protection**

Create `PaperNowPage.tsx` with this complete coordinator:

```tsx
import { useEffect, useRef, useState } from "react";
import type { AttentionItem, PaperPortfolioResponse } from "../../api/client";
import { ApiRequestError } from "../../api/fetchJson";
import { usePreviewPaperOrderMutation } from "../../api/hooks";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import { PaperCandidateQueue } from "./PaperCandidateQueue";
import { PaperExceptionsPanel } from "./PaperExceptionsPanel";
import { PaperPreviewComposer } from "./PaperPreviewComposer";
import { PaperRiskRibbon } from "./PaperRiskRibbon";
import { nextPaperCandidateId } from "./paperDashboardViewModel";
import { buildPaperOrderRequest, createPaperOrderDraft, createPaperPreviewAttemptKey, paperOrderDraftFingerprint, type PaperOrderDraft, type PaperOrderSide } from "./paperOrderDraft";

export type PaperNowPageProps = {
  items: AttentionItem[];
  attentionState: "loading" | "ready" | "error";
  portfolio?: PaperPortfolioResponse;
  portfolioState: "loading" | "ready" | "error";
  paperActionsPermitted: boolean;
  onWhy: (item: AttentionItem) => void;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onContinue: (draft: PaperOrderDraft) => void;
};

type ConfirmedPreview = { fingerprint: string; value: PaperOrderPreviewResponse["preview"] };

export function PaperNowPage({ items, attentionState, portfolio, portfolioState, paperActionsPermitted, onWhy, onExplain, onInspect, onOpenWorkspace, onContinue }: PaperNowPageProps) {
  const [selectedAttentionId, setSelectedAttentionId] = useState<string | null>(() => nextPaperCandidateId(items, null));
  const [side, setSide] = useState<PaperOrderSide | null>(null);
  const [quantityText, setQuantityText] = useState("");
  const [confirmedPreview, setConfirmedPreview] = useState<ConfirmedPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const currentFingerprintRef = useRef("");
  const previewMutation = usePreviewPaperOrderMutation();

  useEffect(() => {
    const next = nextPaperCandidateId(items, selectedAttentionId);
    if (next !== selectedAttentionId) {
      currentFingerprintRef.current = "";
      setConfirmedPreview(null);
      setPreviewError(null);
      setSelectedAttentionId(next);
    }
  }, [items, selectedAttentionId]);
  const selected = items.find((item) => item.attention_id === selectedAttentionId && item.instrument_id?.trim()) ?? null;
  const quantity = /^\d+$/.test(quantityText) ? Number(quantityText) : null;
  const authorized = Boolean(paperActionsPermitted && portfolio && portfolio.account.execution_mode === "INTERNAL_SIMULATION" && portfolio.account.execution_authority === "PAPER_ONLY");
  const draft = selected?.instrument_id && portfolio ? createPaperOrderDraft({ instrumentId: selected.instrument_id, side, quantity, maxOrderShares: portfolio.risk.limits.max_order_shares, sourceAttentionId: selected.attention_id }) : null;
  const fingerprint = draft ? paperOrderDraftFingerprint(draft) : "";
  currentFingerprintRef.current = fingerprint;
  const canContinue = Boolean(draft && confirmedPreview?.fingerprint === fingerprint && confirmedPreview.value.risk_status === "PASS");

  function invalidatePreview() { currentFingerprintRef.current = ""; setConfirmedPreview(null); setPreviewError(null); }
  async function previewDraft() {
    if (!draft) return;
    const requestFingerprint = paperOrderDraftFingerprint(draft);
    setPreviewError(null); setConfirmedPreview(null);
    try {
      const response = await previewMutation.mutateAsync(buildPaperOrderRequest(draft, createPaperPreviewAttemptKey("paper-now")));
      if (currentFingerprintRef.current === requestFingerprint) setConfirmedPreview({ fingerprint: requestFingerprint, value: response.preview });
    } catch (error) {
      if (currentFingerprintRef.current === requestFingerprint) setPreviewError(error instanceof ApiRequestError ? `${error.code}: ${error.message}` : "Preview failed. Retry when ready.");
    }
  }

  const disabledReason = portfolioState === "loading" ? "Portfolio limits are loading." : portfolioState === "error" || !portfolio ? "Portfolio limits are unavailable." : !selected ? "Select an instrument-backed candidate." : !authorized ? "Paper authority is unavailable. Manage the simulation session in Portfolio." : !draft ? `Choose Buy or Sell and enter 1–${portfolio.risk.limits.max_order_shares} shares.` : undefined;

  return (
    <section className="page paper-now-page">
      <header className="paper-now-header"><div><span className="paper-eyebrow">Paper-only simulation</span><h1>Paper Command</h1><p>Review portfolio risk, validate a deliberate draft, then revalidate in the instrument workspace before simulated submission.</p></div><dl><div><dt>Session</dt><dd>{portfolio?.account.session_id ?? "Unavailable"}</dd></div><div><dt>Execution</dt><dd>{portfolio?.account.execution_mode ?? "Unavailable"}</dd></div><div><dt>Authority</dt><dd>{portfolio?.account.execution_authority ?? "Unavailable"}</dd></div><div><dt>Data health</dt><dd>{portfolio?.data_health.state ?? "Unavailable"}</dd></div></dl></header>
      <PaperRiskRibbon portfolio={portfolio} state={portfolioState} />
      <div className="paper-decision-grid">
        <PaperCandidateQueue items={items} state={attentionState} selectedAttentionId={selectedAttentionId} onSelect={(id) => { invalidatePreview(); setSelectedAttentionId(id); }} onWhy={onWhy} onExplain={onExplain} onInspect={onInspect} onOpenWorkspace={onOpenWorkspace} />
        <PaperPreviewComposer instrumentId={selected?.instrument_id ?? null} side={side} quantityText={quantityText} maxOrderShares={portfolio?.risk.limits.max_order_shares} disabledReason={disabledReason} pending={previewMutation.isPending} error={previewError} preview={confirmedPreview?.value ?? null} canContinue={canContinue} onSideChange={(value) => { invalidatePreview(); setSide(value); }} onQuantityChange={(value) => { invalidatePreview(); setQuantityText(value); }} onPreview={() => { void previewDraft(); }} onContinue={() => { if (draft && canContinue) onContinue(draft); }} />
        <PaperExceptionsPanel portfolio={portfolio} state={portfolioState} />
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Verify green, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/PaperNowPage.test.tsx src/components/paper-now/PaperPanels.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/paper-now/PaperPreviewComposer.tsx ui/src/components/paper-now/PaperNowPage.tsx ui/src/components/paper-now/PaperNowPage.test.tsx
git commit -m "feat(ui): add Paper Command preview workflow"
```

---

### Task 5: Route Paper mode without changing Demo or Live

**Files:**
- Modify: `ui/src/components/ModeNowRoute.tsx`
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/App.test.tsx`

**Interfaces:**
- Consumes: `PaperNowPage`, global `paperActionsPermitted`, `usePaperPortfolioQuery`, `useNavigate`, and the existing Demo props.
- Produces: exact route selection `DEMO -> DemoNowPage`, `PAPER -> PaperNowPage`, `LIVE -> NowPage`.

- [ ] **Step 1: Make the App route test red for Paper Command**

In the hooks mock, add `usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false })`. Change the old Paper/Live parameterized test into:

```tsx
it("opens Paper Command in Paper mode", async () => {
  render(<App />);
  await enterMode("Paper");
  expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("PAPER");
  expect(screen.getByRole("heading", { name: "Paper Command" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Command Center" })).not.toBeInTheDocument();
});

it("keeps Live on Command Center", async () => {
  render(<App />);
  await enterMode("Live");
  expect(screen.getByRole("region", { name: "Session environment" })).toHaveTextContent("LIVE");
  expect(screen.getByRole("heading", { name: "Command Center" })).toBeInTheDocument();
});
```

Also assert Demo still shows `See the market unfold` and no Paper heading.

- [ ] **Step 2: Run App tests and confirm only Paper routing is red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/App.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

- [ ] **Step 3: Add the Paper route branch**

Extend `ModeNowRoute` props with `paperActionsPermitted: boolean`. Keep portfolio hooks inside mode-specific child components so Live makes no Paper request. Add:

```tsx
function PaperNowRoute({ paperActionsPermitted, ...props }: Omit<Props, "mode" | "tierSummary">) {
  const navigate = useNavigate();
  const portfolioQuery = usePaperPortfolioQuery();
  const portfolioState = portfolioQuery.isLoading
    ? "loading"
    : portfolioQuery.isError || !portfolioQuery.data ? "error" : "ready";
  return (
    <PaperNowPage
      items={props.items}
      attentionState={props.attentionState}
      portfolio={portfolioQuery.data}
      portfolioState={portfolioState}
      paperActionsPermitted={paperActionsPermitted}
      onWhy={props.onWhy}
      onExplain={props.onExplain}
      onInspect={props.onInspect}
      onOpenWorkspace={props.onOpenWorkspace}
      onContinue={(draft) => navigate(`/workspace/${draft.instrumentId}`, { state: draft })}
    />
  );
}
```

Destructure `paperActionsPermitted` in `ModeNowRoute`; return Demo first, Paper second, and existing `NowPage` last. Do not pass Paper-only props into `DemoNowPage`.

In `App.tsx`, pass `paperActionsPermitted={paperActionsPermitted}` to `ModeNowRoute`.

- [ ] **Step 4: Verify all three modes, validate, and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/App.test.tsx src/components/demo-now/DemoNowPage.test.tsx src/components/paper-now/PaperNowPage.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/ModeNowRoute.tsx ui/src/App.tsx ui/src/App.test.tsx
git commit -m "feat(ui): route Paper to Command dashboard"
```

---

### Task 6: Consume the draft once and revalidate inside the workspace

**Files:**
- Create: `ui/src/components/WorkspaceRoute.test.tsx`
- Create: `ui/src/components/paper/OrderTicket.test.tsx`
- Modify: `ui/src/components/WorkspaceRoute.tsx`
- Modify: `ui/src/components/WorkspacePage.tsx`
- Modify: `ui/src/components/WorkspacePage.test.tsx`
- Modify: `ui/src/components/paper/OrderTicket.tsx`

**Interfaces:**
- Consumes: `PaperOrderDraft`, `parsePaperOrderDraft`, `buildPaperOrderRequest`, and current Paper authority/limits.
- Produces: optional `initialPaperOrderDraft` from route to page, optional `initialDraft` from page to ticket, and exactly one automatic workspace preview.

- [ ] **Step 1: Add failing route-consumption tests**

Create `WorkspaceRoute.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceRoute } from "./WorkspaceRoute";

vi.mock("../api/hooks", () => ({
  useInstrumentQuery: () => ({ isLoading: false, error: null, data: { bars: [], features: [] } }),
  useWorkspaceSqueezeQuery: () => ({ isLoading: false, data: null }),
}));
vi.mock("./WorkspacePage", () => ({
  WorkspacePage: ({ initialPaperOrderDraft }: { initialPaperOrderDraft?: unknown }) => <output data-testid="draft">{initialPaperOrderDraft ? JSON.stringify(initialPaperOrderDraft) : "none"}</output>,
}));

const validDraft = { version: 1, instrumentId: "BIYA", side: "SELL", quantity: 12, orderType: "MARKET" };
const routeProps = { mode: "PAPER" as const, paperActionsPermitted: true, onScrub: vi.fn(), onExplain: vi.fn(), onInspect: vi.fn(), cursorIndex: 0, maxIndex: 0 };

function Launcher({ state }: { state: unknown }) {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate("/workspace/BIYA", { state })}>Open</button>;
}

function renderPush(state: unknown) {
  render(<MemoryRouter initialEntries={["/start"]}><Routes><Route path="/start" element={<Launcher state={state} />} /><Route path="/workspace/:symbol" element={<WorkspaceRoute {...routeProps} />} /></Routes></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Open" }));
}

describe("WorkspaceRoute Paper draft state", () => {
  it("accepts a matching version-1 draft from a fresh PUSH", async () => {
    renderPush(validDraft);
    expect(await screen.findByTestId("draft")).toHaveTextContent('"instrumentId":"BIYA"');
  });

  it.each([
    { ...validDraft, instrumentId: "NVDA" },
    { ...validDraft, risk_status: "PASS" },
    { ...validDraft, version: 2 },
  ])("ignores invalid or authority-bearing state", async (state) => {
    renderPush(state);
    expect(await screen.findByTestId("draft")).toHaveTextContent("none");
  });

  it("ignores history state on POP so reloads are ephemeral", async () => {
    render(<MemoryRouter initialEntries={[{ pathname: "/workspace/BIYA", state: validDraft }]}><Routes><Route path="/workspace/:symbol" element={<WorkspaceRoute {...routeProps} />} /></Routes></MemoryRouter>);
    expect(await screen.findByTestId("draft")).toHaveTextContent("none");
  });
});
```

- [ ] **Step 2: Add failing ticket revalidation tests**

Create `OrderTicket.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PaperOrderPreviewResponse } from "../../api/schemas";
import type { PaperOrderDraft } from "../paper-now/paperOrderDraft";
import { OrderTicket } from "./OrderTicket";

const mocks = vi.hoisted(() => ({ previewPaperOrder: vi.fn(), submitPaperOrder: vi.fn() }));
vi.mock("../../api/hooks", () => ({
  usePreviewPaperOrderMutation: () => ({ mutateAsync: mocks.previewPaperOrder, isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: mocks.submitPaperOrder, isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePaperPortfolioQuery: () => ({ data: {}, refetch: vi.fn() }),
}));

const validDraft: PaperOrderDraft = { version: 1, instrumentId: "BIYA", side: "SELL", quantity: 12, orderType: "MARKET", sourceAttentionId: "attention-biya" };

function previewResponse(preview: Partial<PaperOrderPreviewResponse["preview"]>): PaperOrderPreviewResponse {
  return {
    as_of_context: { mode: "PAPER", data_mode: "FIXTURE_REPLAY", execution_mode: "INTERNAL_SIMULATION", execution_authority: "PAPER_ONLY", as_of_time: "2026-08-31T12:00:00Z", timezone: "America/New_York" },
    preview: { risk_status: "PASS", decision: "ALLOW", ...preview },
  };
}

function renderTicket(initialDraft?: PaperOrderDraft) {
  return render(<OrderTicket symbol="BIYA" executionAuthority="PAPER_ONLY" executionMode="INTERNAL_SIMULATION" dataMode="FIXTURE_REPLAY" maxOrderShares={100} initialDraft={initialDraft} />);
}

describe("OrderTicket workspace revalidation", () => {
  beforeEach(() => { mocks.previewPaperOrder.mockReset(); mocks.submitPaperOrder.mockReset(); });

  it("imports a draft, auto-previews once, and gates Submit on the fresh PASS", async () => {
    let resolvePreview!: (value: PaperOrderPreviewResponse) => void;
    mocks.previewPaperOrder.mockReturnValueOnce(new Promise((resolve) => { resolvePreview = resolve; }));
    renderTicket(validDraft);
    expect(await screen.findByDisplayValue("12")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SELL" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(mocks.previewPaperOrder).toHaveBeenCalledTimes(1));
    expect(mocks.previewPaperOrder).toHaveBeenCalledWith(expect.objectContaining({ side: "SELL", quantity: 12, instrument_id: "BIYA" }));
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    resolvePreview(previewResponse({ risk_status: "PASS", decision: "ALLOW" }));
    expect(await screen.findByRole("heading", { name: "Revalidated in workspace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

it("keeps Submit disabled for a blocked workspace preview", async () => {
  mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({ risk_status: "BLOCKED", decision: "BLOCK", reason_codes: ["POSITION_LIMIT"] }));
  renderTicket(validDraft);
  expect(await screen.findByText(/POSITION_LIMIT/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
});

it("retains the imported draft when automatic preview fails", async () => {
  mocks.previewPaperOrder.mockRejectedValueOnce(new Error("offline"));
  renderTicket(validDraft);
  expect(await screen.findByText("Preview failed")).toBeInTheDocument();
  expect(screen.getByRole("spinbutton", { name: "Quantity" })).toHaveValue(12);
  expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
});

it("does not auto-preview an ordinary workspace ticket", () => {
  renderTicket();
  expect(mocks.previewPaperOrder).not.toHaveBeenCalled();
});

it("invalidates a workspace PASS when the user edits the draft", async () => {
  mocks.previewPaperOrder.mockResolvedValueOnce(previewResponse({ risk_status: "PASS", decision: "ALLOW" }));
  renderTicket(validDraft);
  expect(await screen.findByRole("heading", { name: "Revalidated in workspace" })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("spinbutton", { name: "Quantity" }), { target: { value: "13" } });
  expect(screen.queryByRole("heading", { name: "Revalidated in workspace" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
});
});
```

- [ ] **Step 3: Run focused tests and confirm red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/WorkspaceRoute.test.tsx src/components/paper/OrderTicket.test.tsx src/components/WorkspacePage.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

- [ ] **Step 4: Accept only fresh matching PUSH state in `WorkspaceRoute`**

Import `useEffect`, `useState`, `useLocation`, `useNavigate`, and `useNavigationType`. After deriving `instrumentId`, initialize once:

```tsx
const location = useLocation();
const navigate = useNavigate();
const navigationType = useNavigationType();
const [initialPaperOrderDraft] = useState(() =>
  navigationType === "PUSH" ? parsePaperOrderDraft(location.state, instrumentId) : undefined,
);

useEffect(() => {
  if (location.state !== null) navigate(location.pathname, { replace: true, state: null });
}, [location.pathname, location.state, navigate]);
```

Pass `initialPaperOrderDraft` to `WorkspacePage`. In `WorkspacePage`, add `initialPaperOrderDraft?: PaperOrderDraft` to Props and pass it to `<OrderTicket initialDraft={initialPaperOrderDraft} />` only in the already-authorized branch.

- [ ] **Step 5: Refactor `OrderTicket` around a confirmed request**

Add `initialDraft?: PaperOrderDraft` to `OrderTicketProps`. Initialize side/quantity from it, otherwise preserve current ticket defaults. Replace the memoized timestamp key with per-attempt keys and store `confirmedRequest: PaperOrderRequest | null` plus `previewOrigin: "manual" | "workspace" | null`. Add `aria-pressed={side === "BUY"}` and `aria-pressed={side === "SELL"}` to the existing side buttons so imported state is exposed accessibly.

Create one `invalidatePreview()` that clears preview, confirmed request, origin, and error; call it in every side, quantity, and symbol change handler. Implement:

```tsx
async function performPreview(origin: "manual" | "workspace") {
  const currentDraft = createPaperOrderDraft({
    instrumentId: ticketSymbol, side, quantity, maxOrderShares,
    sourceAttentionId: initialDraft?.sourceAttentionId,
  });
  if (!currentDraft) { setError(ticketSymbol ? "ENTER A VALID QUANTITY" : "SELECT AN INSTRUMENT"); return; }
  const request = buildPaperOrderRequest(currentDraft, createPaperPreviewAttemptKey("workspace-ticket"));
  setError(null); setPreview(null); setConfirmedRequest(null); setPreviewOrigin(null);
  try {
    const response = await previewMutation.mutateAsync(request);
    setPreview(response.preview); setConfirmedRequest(request); setPreviewOrigin(origin);
  } catch (err) {
    setError(err instanceof ApiRequestError ? `${err.code}: ${err.message}` : "Preview failed");
  }
}
```

Use a ref to ensure one automatic attempt:

```tsx
const automaticPreviewAttempted = useRef(false);
useEffect(() => {
  if (!initialDraft || !authorized || automaticPreviewAttempted.current) return;
  if (!createPaperOrderDraft({ instrumentId: initialDraft.instrumentId, side: initialDraft.side, quantity: initialDraft.quantity, maxOrderShares, sourceAttentionId: initialDraft.sourceAttentionId })) return;
  automaticPreviewAttempted.current = true;
  void performPreview("workspace");
}, [authorized, initialDraft, maxOrderShares]);
```

Submit only `confirmedRequest`; do not generate or reconstruct another instrument/draft. Keep Submit gated by `authorized`, current PASS, and non-null confirmed request. The result heading is `Revalidated in workspace` for workspace origin and `Preview` otherwise.

- [ ] **Step 6: Verify route, ticket, and existing restrictions; validate and commit**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/WorkspaceRoute.test.tsx src/components/paper/OrderTicket.test.tsx src/components/WorkspacePage.test.tsx src/components/PortfolioPage.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/components/WorkspaceRoute.tsx ui/src/components/WorkspaceRoute.test.tsx ui/src/components/WorkspacePage.tsx ui/src/components/WorkspacePage.test.tsx ui/src/components/paper/OrderTicket.tsx ui/src/components/paper/OrderTicket.test.tsx
git commit -m "feat(ui): revalidate Paper drafts in workspace"
```

---

### Task 7: Apply the Decision Canvas visual and accessibility contract

**Files:**
- Create: `ui/src/styles/paper-now.css`
- Modify: `ui/src/App.tsx`
- Modify: `ui/src/components/paper-now/PaperNowPage.test.tsx`

**Interfaces:**
- Consumes: only `.paper-*` classes from Tasks 3–4 and existing workstation token variables.
- Produces: risk ribbon plus three-column canvas, stacked DOM-order layout, 44px targets, focus, reduced-motion, and forced-colors behavior.

- [ ] **Step 1: Add a failing raw stylesheet contract test**

Import `paperNowCss` from `../../styles/paper-now.css?raw` and assert it contains:

```tsx
expect(paperNowCss).toContain("grid-template-columns: minmax(260px, 0.9fr) minmax(340px, 1.35fr) minmax(250px, 0.8fr)");
expect(paperNowCss).toContain("min-height: 44px");
expect(paperNowCss).toContain(":focus-visible");
expect(paperNowCss).toContain("@media (max-width: 1080px)");
expect(paperNowCss).toContain("@media (max-width: 720px)");
expect(paperNowCss).toContain("@media (prefers-reduced-motion: reduce)");
expect(paperNowCss).toContain("@media (forced-colors: active)");
```

- [ ] **Step 2: Run the stylesheet test and confirm red**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/PaperNowPage.test.tsx
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
```

- [ ] **Step 3: Create the scoped Paper stylesheet**

Create `ui/src/styles/paper-now.css`:

```css
.paper-now-page {
  --paper-accent: #48d6c4;
  --paper-accent-soft: rgba(72, 214, 196, 0.12);
  --paper-line: rgba(131, 168, 188, 0.24);
  --paper-panel: rgba(15, 23, 33, 0.94);
  display: grid;
  gap: 18px;
  width: min(100%, 1580px);
  margin: 0 auto;
  padding: clamp(4px, 1vw, 16px);
}

.paper-now-header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 28px;
  padding: 18px 4px;
  border-bottom: 1px solid var(--paper-line);
}

.paper-now-header h1 { margin: 4px 0 8px; font-size: clamp(2rem, 4vw, 3.4rem); line-height: 1; letter-spacing: -0.04em; }
.paper-now-header p { max-width: 760px; margin: 0; color: var(--text-secondary); }
.paper-eyebrow { color: var(--paper-accent); font: 0.7rem var(--font-mono); letter-spacing: 0.1em; text-transform: uppercase; }
.paper-now-header dl { display: grid; grid-template-columns: repeat(2, minmax(120px, 1fr)); gap: 8px; margin: 0; }
.paper-now-header dl div { padding: 9px 11px; border: 1px solid var(--paper-line); background: rgba(255, 255, 255, 0.02); }
.paper-now-header dt, .paper-risk-ribbon dt, .paper-order-fixed dt { color: var(--text-muted); font: 0.64rem var(--font-mono); letter-spacing: 0.08em; text-transform: uppercase; }
.paper-now-header dd, .paper-risk-ribbon dd, .paper-order-fixed dd { margin: 5px 0 0; font-family: var(--font-mono); }

.paper-risk-ribbon { padding: 16px 18px; border: 1px solid rgba(72, 214, 196, 0.28); background: linear-gradient(120deg, rgba(72, 214, 196, 0.08), rgba(15, 23, 33, 0.96)); }
.paper-risk-ribbon h2 { margin: 0 0 12px; font-size: 0.92rem; }
.paper-risk-ribbon dl { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 1px; margin: 0; background: var(--paper-line); }
.paper-risk-ribbon dl > div { min-width: 0; padding: 12px; background: #101923; }
.paper-risk-ribbon dd { font-size: clamp(0.9rem, 1.4vw, 1.15rem); overflow-wrap: anywhere; }
.paper-risk-ribbon dl span { display: block; margin-top: 4px; color: var(--text-muted); font-size: 0.7rem; }
.paper-risk-meter { height: 5px; margin-top: 9px; overflow: hidden; border: 1px solid var(--paper-line); background: rgba(0, 0, 0, 0.32); }
.paper-risk-meter > span { display: block; height: 100%; background: var(--paper-accent); transition: width 160ms ease-out; }

.paper-decision-grid { display: grid; grid-template-columns: minmax(260px, 0.9fr) minmax(340px, 1.35fr) minmax(250px, 0.8fr); gap: 16px; align-items: start; }
.paper-panel { min-width: 0; padding: 18px; border: 1px solid var(--paper-line); border-radius: 9px; background: var(--paper-panel); }
.paper-panel > header { display: flex; justify-content: space-between; gap: 12px; align-items: start; margin-bottom: 14px; }
.paper-panel h2, .paper-panel h3 { margin: 0; }
.paper-preview-panel { border-color: rgba(72, 214, 196, 0.48); background: radial-gradient(circle at 90% 0, rgba(72, 214, 196, 0.13), transparent 34%), linear-gradient(145deg, #132632, #111923); box-shadow: 0 20px 55px rgba(0, 0, 0, 0.22); }

.paper-candidate-panel [role="radiogroup"] { display: grid; gap: 10px; }
.paper-candidate { padding: 13px; border: 1px solid var(--paper-line); background: rgba(5, 11, 17, 0.42); }
.paper-candidate.selected { border: 2px solid var(--paper-accent); background: var(--paper-accent-soft); }
.paper-candidate .card-head { display: flex; justify-content: space-between; gap: 8px; }
.paper-candidate .card-head h3 { font-size: 0.98rem; }
.paper-candidate-selector, .paper-research-only { display: flex; align-items: center; gap: 9px; min-height: 44px; font-family: var(--font-mono); font-size: 0.74rem; }
.paper-candidate-selector input { width: 20px; height: 20px; accent-color: var(--paper-accent); }
.paper-research-only { color: var(--text-muted); }
.paper-candidate .reason-codes { margin: 8px 0 12px; padding-left: 18px; color: var(--text-secondary); font-size: 0.78rem; }
.paper-candidate .card-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }

.paper-preview-panel fieldset { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 18px 0 12px; padding: 0; border: 0; }
.paper-preview-panel legend { margin-bottom: 7px; font-weight: 700; }
.paper-preview-panel fieldset label { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; border: 1px solid var(--paper-line); }
.paper-preview-panel fieldset label:has(input:checked) { border-color: var(--paper-accent); background: var(--paper-accent-soft); }
.paper-quantity { display: grid; gap: 7px; margin-bottom: 12px; }
.paper-quantity input { width: 100%; min-height: 44px; padding: 9px 11px; border: 1px solid var(--paper-line); background: rgba(0, 0, 0, 0.28); color: var(--text-primary); font: inherit; }
.paper-order-fixed { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.paper-order-fixed div { padding: 10px; border: 1px solid var(--paper-line); }
.paper-preview-result { margin-top: 16px; padding: 15px; border: 2px solid var(--paper-line); }
.paper-preview-result.pass { border-color: var(--paper-accent); }
.paper-preview-result.blocked { border-color: var(--danger, #e36d77); }
.paper-preview-result h3:focus { outline: none; }
.paper-preview-result dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; }

.paper-exceptions-panel ul { display: grid; gap: 8px; margin: 0 0 14px; padding: 0; list-style: none; }
.paper-exceptions-panel li { display: grid; gap: 4px; padding: 10px; border-left: 3px solid var(--paper-line); background: rgba(0, 0, 0, 0.2); }
.paper-exceptions-panel li[data-severity="0"] { border-left-color: var(--danger, #e36d77); }
.paper-exceptions-panel li[data-severity="1"] { border-left-color: var(--warning, #e1b85b); }
.paper-exceptions-panel li span { color: var(--text-secondary); font-size: 0.78rem; }

.paper-now-page button, .paper-now-page a, .paper-preview-panel input, .paper-candidate-selector { min-height: 44px; }
.paper-now-page button { min-width: 44px; padding: 9px 12px; border: 1px solid var(--paper-line); border-radius: 5px; background: rgba(255, 255, 255, 0.045); color: var(--text-primary); cursor: pointer; }
.paper-now-page button.primary { border-color: var(--paper-accent); background: var(--paper-accent); color: #061513; font-weight: 800; }
.paper-now-page button:disabled { cursor: not-allowed; opacity: 0.45; }
.paper-now-page button:focus-visible, .paper-now-page a:focus-visible, .paper-now-page input:focus-visible { outline: 3px solid var(--paper-accent); outline-offset: 3px; }

@media (max-width: 1080px) {
  .paper-risk-ribbon dl { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .paper-decision-grid { grid-template-columns: minmax(260px, 0.85fr) minmax(360px, 1.15fr); }
  .paper-exceptions-panel { grid-column: 1 / -1; }
}

@media (max-width: 720px) {
  .paper-now-page { padding: 0; }
  .paper-now-header { align-items: start; flex-direction: column; }
  .paper-now-header dl, .paper-risk-ribbon dl, .paper-decision-grid { grid-template-columns: 1fr; }
  .paper-exceptions-panel { grid-column: auto; }
  .paper-panel, .paper-risk-ribbon { border-radius: 6px; }
  .paper-candidate .card-actions { grid-template-columns: 1fr; }
  .paper-preview-panel button.primary { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  .paper-risk-meter > span, .paper-preview-result { transition: none; }
}

@media (forced-colors: active) {
  .paper-panel, .paper-risk-ribbon, .paper-candidate, .paper-preview-result, .paper-exceptions-panel li, .paper-now-page button, .paper-now-page input { border: 2px solid CanvasText; }
  .paper-candidate.selected, .paper-preview-result.pass { border-color: Highlight; }
  .paper-risk-meter > span, .paper-now-page button.primary { background: Highlight; color: HighlightText; }
  .paper-now-page button:focus-visible, .paper-now-page a:focus-visible, .paper-now-page input:focus-visible { outline-color: Highlight; }
}
```

Add `import "./styles/paper-now.css";` beside the Demo stylesheet import in `App.tsx`.

- [ ] **Step 4: Verify visual contract, type safety, and changed validation**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/PaperNowPage.test.tsx src/components/paper-now/PaperPanels.test.tsx
.\node_modules\.bin\tsc.cmd --noEmit
cd ..
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py changed
git add ui/src/styles/paper-now.css ui/src/App.tsx ui/src/components/paper-now/PaperNowPage.test.tsx
git commit -m "style(ui): polish Paper Decision Canvas"
```

---

### Task 8: Run milestone and final acceptance validation

**Files:**
- Verify only; modify a source or test file only when a failing check identifies a concrete defect, then repeat that task's focused red-green cycle.

**Interfaces:**
- Consumes: all Task 1–7 contracts.
- Produces: fresh evidence for all 15 specification acceptance criteria and a clean planned diff.

- [ ] **Step 1: Run all focused Paper, route, and regression tests together**

```powershell
cd ui
.\node_modules\.bin\vitest.cmd run src/components/paper-now/paperOrderDraft.test.ts src/components/paper-now/paperDashboardViewModel.test.ts src/components/paper-now/PaperPanels.test.tsx src/components/paper-now/PaperNowPage.test.tsx src/components/paper/OrderTicket.test.tsx src/components/WorkspaceRoute.test.tsx src/components/WorkspacePage.test.tsx src/components/PortfolioPage.test.tsx src/components/demo-now/DemoNowPage.test.tsx src/App.test.tsx
```

Expected: all focused tests pass, including stale-response rejection, no forbidden controls, fresh workspace PASS gating, reload discard, and Demo/Live preservation.

- [ ] **Step 2: Run the complete UI gates**

```powershell
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\tsc.cmd --noEmit
.\node_modules\.bin\vite.cmd build
node scripts/check-bundle-budget.mjs
cd ..
```

Expected: all UI tests pass; TypeScript has zero errors; production build succeeds; bundle budget exits zero.

- [ ] **Step 3: Run the UI domain milestone**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py domain ui
```

Expected: UI domain validation passes with zero failures.

- [ ] **Step 4: Run full offline repository validation exactly once**

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe tools\validate.py full
```

Expected: full offline validation passes; do not select any live-provider suite.

- [ ] **Step 5: Inspect the final diff and preserve unrelated evidence changes**

```powershell
git diff --check
git status --short --branch
git log -10 --oneline
```

Expected: no whitespace errors; the two pre-existing `evidence/ui1/assistant-audit/*.json` modifications remain unstaged; only planned Paper UI commits are new. If a verification fix was needed, stage only its exact UI files, commit with `git commit -m "fix(ui): correct Paper Command acceptance issue"`, and rerun Steps 1–5.

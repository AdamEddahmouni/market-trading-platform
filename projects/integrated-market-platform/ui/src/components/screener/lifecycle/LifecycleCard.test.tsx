import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SchemaMismatchError } from "../../../api/fetchJson";
import type { TradeLifecycle } from "../../../api/screenerLifecycle";
import LifecycleCard from "./LifecycleCard";
import TradeLifecycleGroups, { LifecycleBoundary } from "./TradeLifecycleGroups";
import { breachedPosition, closedEpisode, decision, detailOf, lifecycle, lifecycleList, openPosition } from "./lifecycleFixture";

const mocks = vi.hoisted(() => ({ detail: vi.fn(), prepare: vi.fn() }));
vi.mock("../../../api/screenerLifecycle", () => ({ tradeLifecycle: mocks.detail }));
vi.mock("../../../api/screenerAction", () => ({ prepareAction: mocks.prepare, previewAction: vi.fn(), runAction: vi.fn(), actionHistory: vi.fn() }));

function Workspace() {
  const location = useLocation();
  return <p>Workspace {location.pathname} {JSON.stringify(location.state)}</p>;
}
const renderWith = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={["/screener"]}><Routes><Route path="/screener" element={node} /><Route path="/workspace/:id" element={<Workspace />} /></Routes></MemoryRouter>
</QueryClientProvider>);
const card = (value: TradeLifecycle, runId: string | null = "run-1") => renderWith(<LifecycleCard lifecycle={value} runId={runId} />);
const text = (testId: string) => screen.getByTestId(testId).textContent ?? "";

afterEach(() => vi.clearAllMocks());

describe("lifecycle card — semantic truth", () => {
  it("shows an ENTER decision without a fill as decided, not executed, and never as a position", () => {
    card(lifecycle());
    expect(screen.getByRole("heading", { name: "#1 AAPL" })).toBeInTheDocument();
    expect(text("lifecycle-stage")).toBe("ENTER DECIDED · NOT EXECUTED");
    expect(text("lifecycle-entry")).toContain("DECIDED — NOT EXECUTED");
    expect(text("lifecycle-entry")).toContain("Paper: no fill");
    expect(text("lifecycle-entry")).toContain("Decision reference $150.00");
    expect(text("lifecycle-entry")).toContain("quote, not a fill");
    expect(text("lifecycle-position")).toBe("PositionFLAT");
    expect(screen.queryByText(/POSITION OPEN/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("lifecycle-unrealized")).not.toBeInTheDocument();
    expect(screen.queryByTestId("lifecycle-realized")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Open Paper Workspace" })).not.toBeInTheDocument();
  });

  it("shows NO ACTION and CONSIDER ENTRY as complete flat lifecycles", () => {
    const view = card(lifecycle({ stage: "NO_ACTION", decision: decision({ action_state: "NO_ACTION", direction: null, execution_readiness: "NOT_PREVIEWED" }),
      entry: { ...lifecycle().entry, status: "NOT_PROPOSED", decision_reference: null } }));
    expect(text("lifecycle-stage")).toBe("NO ACTION");
    expect(text("lifecycle-entry")).toContain("None");
    expect(text("lifecycle-evidence")).toBe("Evidence2 supporting · 2 conflicting · 0 weak · 1 missing · 1 blocked");
    view.unmount();
    card(lifecycle({ stage: "CONSIDERING_ENTRY", decision: decision({ action_state: "CONSIDER_ENTRY" }), entry: { ...lifecycle().entry, status: "CONSIDERED", decision_reference: null } }));
    expect(text("lifecycle-stage")).toBe("CONSIDERING ENTRY");
    expect(text("lifecycle-entry")).toContain("Considered — not decided");
  });

  it("explains a decision that needs fresh evidence with translated blockers", () => {
    card(lifecycle({ stage: "REVALIDATION_REQUIRED", decision: decision({ action_state: "REVALIDATION_REQUIRED", origin: "SERVER_FAILSAFE", execution_readiness: "BLOCKED",
      blocker_codes: ["CANDIDATE_EXPIRED", "QUOTE_STALE_OR_UNAVAILABLE"], model: { provider_id: "fixture", model_id: "controlled", prompt_id: "p", called: false } }),
      entry: { ...lifecycle().entry, status: "BLOCKED" }, freshness: { ...lifecycle().freshness, decision_current: false } }));
    expect(text("lifecycle-stage")).toBe("DECISION NEEDS FRESH EVIDENCE");
    const blockers = screen.getByTestId("lifecycle-blockers");
    expect(blockers).toHaveTextContent("Decision needs fresh evidence");
    expect(blockers).toHaveTextContent("Candidate evidence expired");
    expect(blockers).toHaveTextContent("Current quote is stale or unavailable");
    expect(screen.queryByRole("button", { name: /Prepare Paper/ })).not.toBeInTheDocument();
  });

  it("shows an open position from the simulated fill, the current mark and signed P&L in text", () => {
    card(openPosition());
    expect(text("lifecycle-stage")).toBe("POSITION OPEN · HOLD");
    expect(text("lifecycle-entry")).toContain("Filled (simulated)");
    expect(text("lifecycle-entry")).toMatch(/Position opened 2026-10-06 10:31:14 ET · simulated Paper fill \$150\.20/);
    expect(text("lifecycle-position")).toBe("PositionLONG 6 · average entry $150.20");
    expect(text("lifecycle-mark")).toBe("Current mark$151.00 · CURRENT · MOOMOO · 2s old");
    expect(screen.getByTestId("lifecycle-unrealized-value")).toHaveTextContent("+$4.80");
    expect(screen.getByTestId("lifecycle-unrealized-value")).toHaveAccessibleName("gain of $4.80");
    expect(text("lifecycle-risk")).toContain("SMA trailing stop · ACTIVE · active stop $140.00 · SMA $140.00 · distance $11.00");
    expect(text("lifecycle-risk")).toContain("Deterministic risk control · Model: none");
    expect(text("lifecycle-exit")).toContain("No exit");
    expect(screen.getByRole("link", { name: "Open Paper Workspace" })).toHaveAttribute("href", "/workspace/AAPL");
    expect(screen.getByRole("link", { name: "Open Portfolio" })).toHaveAttribute("href", "/portfolio");
  });

  it("never presents a stale or missing mark as current P&L", () => {
    const stale = openPosition();
    const view = card({ ...stale, position: { ...stale.position, mark: { ...stale.position.mark!, quality: "STALE", source_quality: "STALE", age_ms: 600_000 } },
      pnl: { ...stale.pnl, quality: "STALE" } });
    expect(text("lifecycle-mark")).toBe("Current mark$151.00 · STALE · MOOMOO · 10m old");
    expect(text("lifecycle-unrealized")).toContain("STALE — not a current valuation");
    view.unmount();
    card({ ...stale, position: { ...stale.position, mark: { ...stale.position.mark!, price_minor: null, quality: "UNAVAILABLE" } }, pnl: { ...stale.pnl, unrealized_minor: null, quality: "UNAVAILABLE" } });
    expect(text("lifecycle-mark")).toContain("Unavailable — no mark for this position");
    expect(screen.getByTestId("lifecycle-unrealized-value")).toHaveTextContent("Unavailable");
    expect(screen.getByTestId("lifecycle-unrealized-value")).not.toHaveTextContent("$0.00");
  });

  it("states a missing or stale stop instead of drawing a zero level", () => {
    const open = openPosition();
    const view = card({ ...open, risk_control: { ...open.risk_control, status: "NOT_CONFIGURED", configured: false, stop: null, policy: null } });
    expect(text("lifecycle-risk")).toContain("SMA trailing stop not configured");
    expect(text("lifecycle-risk")).not.toContain("$0.00");
    view.unmount();
    card({ ...open, risk_control: { ...open.risk_control, status: "STALE" } });
    expect(text("lifecycle-risk")).toContain("Stop update stale · active stop $140.00");
    expect(text("lifecycle-risk")).toContain("last legitimate level retained, not current");
  });

  it("keeps the position open after an EXIT decision and attributes a stop breach to risk control, not AI", () => {
    card(breachedPosition());
    expect(text("lifecycle-stage")).toBe("EXIT DECIDED · POSITION STILL OPEN");
    expect(text("lifecycle-decision")).toContain("EXIT");
    expect(text("lifecycle-decision")).toContain("Deterministic risk control · Model: none");
    expect(text("lifecycle-position")).toContain("LONG 6");
    expect(text("lifecycle-exit")).toContain("EXIT decided — position still open");
    expect(text("lifecycle-exit")).toContain("Paper close: NOT SUBMITTED");
    expect(text("lifecycle-risk")).toContain("BREACHED");
    expect(text("lifecycle-risk")).toContain("observed $139.00");
    expect(screen.queryByText(/POSITION CLOSED/)).not.toBeInTheDocument();
  });

  it("prepares a Paper exit only through the governed handoff to the Workspace", async () => {
    mocks.prepare.mockResolvedValue({ version: 1, instrumentId: "AAPL", side: "SELL", quantity: 6, orderType: "MARKET", sourceAttentionId: "lane:order-flow",
      sourceContext: { headline: "x", source_time: 1, reasons: [{ code: "ACTION_DECISION", label: "AD-3" }] } });
    card(breachedPosition());
    fireEvent.click(screen.getByRole("button", { name: "Prepare Paper Exit" }));
    expect(await screen.findByText(/Workspace \/workspace\/AAPL/)).toHaveTextContent("AD-3");
    expect(mocks.prepare).toHaveBeenCalledWith("AD-3");
  });

  it("offers no exit handoff when the decision is blocked, expired or already closed", () => {
    const breached = breachedPosition();
    const blocked = card({ ...breached, decision: { ...breached.decision!, execution_readiness: "BLOCKED", blocker_codes: ["PAPER_AUTHORITY_UNAVAILABLE"] }, exit: { ...breached.exit, status: "BLOCKED" } });
    expect(screen.queryByRole("button", { name: "Prepare Paper Exit" })).not.toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-blockers")).toHaveTextContent("Paper authority unavailable");
    blocked.unmount();
    const expired = card({ ...breached, freshness: { ...breached.freshness, decision_current: false } });
    expect(screen.queryByRole("button", { name: "Prepare Paper Exit" })).not.toBeInTheDocument();
    expired.unmount();
    card(closedEpisode());
    expect(screen.queryByRole("button", { name: /Prepare Paper/ })).not.toBeInTheDocument();
  });

  it("shows a closed episode from its fills with realized P&L and no current position P&L", () => {
    card(closedEpisode(), null);
    expect(text("lifecycle-stage")).toBe("POSITION CLOSED");
    expect(text("lifecycle-exit")).toMatch(/Closed \(simulated close fill\) · Position closed 2026-10-06 11:22:04 ET · simulated close fill \$138\.70/);
    expect(text("lifecycle-position")).toBe("PositionFLAT — episode closed");
    expect(screen.getByTestId("lifecycle-realized-value")).toHaveTextContent("−$69.00");
    expect(screen.getByTestId("lifecycle-realized-value")).toHaveAccessibleName("loss of $69.00");
    expect(screen.queryByTestId("lifecycle-unrealized")).not.toBeInTheDocument();
    expect(screen.queryByTestId("lifecycle-mark")).not.toBeInTheDocument();
    expect(screen.queryByText(/good trade|bad trade|win rate|expectancy/i)).not.toBeInTheDocument();
  });

  it("never calls unlinked Paper activity AI-selected", () => {
    const open = openPosition();
    card({ ...open, group: "UNLINKED_PAPER_ACTIVITY", ai_selected: false, position_origin: "UNLINKED_PAPER_ACTIVITY", candidate: null, decision: null,
      origin: { run_id: null, same_as_current_run: false, lineage: "LINEAGE_UNAVAILABLE" } }, null);
    expect(screen.getByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    expect(text("lifecycle-origin")).toContain("Unlinked Paper activity — no AI candidate or decision lineage");
    expect(text("lifecycle-origin")).not.toContain("AI-selected");
    expect(text("lifecycle-evidence")).toBe("EvidenceLineage unavailable");
    expect(text("lifecycle-decision")).toBe("DecisionNot assessed yet");
  });
});

describe("lifecycle detail", () => {
  it("loads evidence and history with one request, only when expanded", async () => {
    mocks.detail.mockResolvedValue(detailOf(closedEpisode()));
    card(closedEpisode(), null);
    expect(mocks.detail).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "View lifecycle" }));
    const detail = await screen.findByTestId("lifecycle-detail");
    expect(mocks.detail).toHaveBeenCalledTimes(1);
    expect(mocks.detail).toHaveBeenCalledWith("TE-aapl-1", null, expect.any(AbortSignal));
    const supporting = within(detail).getAllByRole("region", { name: "Supporting" })[0];
    expect(supporting).toHaveTextContent("QUOTE · price: 150.0 — CONTROLLED_FIXTURE · 2026-10-06 10:28:00 ET · CURRENT · REALTIME");
    const conflicting = within(detail).getAllByRole("region", { name: "Conflicting" })[0];
    expect(conflicting).toHaveTextContent("SENTIMENT · label: NEGATIVE");
    expect(conflicting).toHaveTextContent("PUBLICATION-BASED");
    expect(conflicting).toHaveTextContent("Evidence alignment CONFLICTING");
    const missing = within(detail).getAllByRole("region", { name: "Missing or unavailable" })[0];
    expect(missing).toHaveTextContent("Missing: OPTIONS");
    expect(missing).toHaveTextContent("Excluded: LEVEL2 · STALE");
    const events = Array.from(screen.getByTestId("lifecycle-timeline").children).map((row) => row.querySelector(":scope > strong")?.textContent);
    expect(events).toEqual(["Candidate selected", "Action decision: ENTER", "Paper simulated fill — position opened", "Risk control: EXIT", "Paper simulated close fill — position closed"]);
    expect(within(detail).getByTestId("lifecycle-experiment")).toHaveTextContent("execution INTERNAL SIMULATION · market data LIVE OBSERVATIONAL");
    expect(within(detail).getByTestId("lifecycle-experiment")).toHaveTextContent("not live capital");
    expect(screen.getByRole("button", { name: "Hide lifecycle" })).toHaveAttribute("aria-expanded", "true");
  });

  it("shows an old decision with the evidence it froze, not the newest evidence", async () => {
    mocks.detail.mockResolvedValue(detailOf(openPosition()));
    card(openPosition());
    fireEvent.click(screen.getByRole("button", { name: "View lifecycle" }));
    await screen.findByTestId("lifecycle-detail");
    const old = screen.getAllByTestId("lifecycle-decision-AD-1")[0];
    expect(old).toHaveTextContent("ENTER");
    expect(old).toHaveTextContent("price: 150.0");
    expect(old).not.toHaveTextContent("price: 151.0");
    expect(old).toHaveTextContent("Current quote available");
    expect(old).toHaveTextContent("AI proposal: ENTER → server decision: ENTER");
    const current = screen.getAllByTestId("lifecycle-decision-AD-2")[0];
    expect(current).toHaveTextContent("HOLD");
    expect(current).toHaveTextContent("price: 151.0");
  });

  it("does not let one lifecycle's late response populate another", async () => {
    let resolveA: (value: TradeLifecycle) => void = () => undefined;
    const b = openPosition({ lifecycle_id: "TE-nvda-1", instrument_id: "NVDA", symbol: "NVDA", group: "ACTIVE_MANAGED" });
    mocks.detail.mockImplementation((id: string) => id === "TE-aapl-1" ? new Promise((resolve) => { resolveA = resolve; }) : Promise.resolve(detailOf(b, { limitations: ["NVDA_ONLY"] })));
    renderWith(<TradeLifecycleGroups runId={null} list={lifecycleList({ active_managed: [openPosition({ group: "ACTIVE_MANAGED" }), b], counts: { selected: 0, active_managed: 2, recent_closed: 0, unlinked: 0 } })} />);
    const aapl = screen.getByTestId("lifecycle-card-AAPL");
    const nvda = screen.getByTestId("lifecycle-card-NVDA");
    fireEvent.click(within(aapl).getByRole("button", { name: "View lifecycle" }));
    fireEvent.click(within(nvda).getByRole("button", { name: "View lifecycle" }));
    expect(await within(nvda).findByTestId("lifecycle-detail")).toHaveTextContent("Nvda only");
    resolveA(detailOf(openPosition(), { limitations: ["AAPL_ONLY"] }));
    expect(await within(aapl).findByTestId("lifecycle-detail")).toHaveTextContent("Aapl only");
    expect(within(nvda).getByTestId("lifecycle-detail")).not.toHaveTextContent("Aapl only");
  });

  it("names a malformed detail payload instead of rendering it", async () => {
    mocks.detail.mockRejectedValue(new SchemaMismatchError("/screener/trade-lifecycles/TE-aapl-1", []));
    card(openPosition());
    fireEvent.click(screen.getByRole("button", { name: "View lifecycle" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Lifecycle detail is unavailable");
    expect(alert).toHaveTextContent("did not match the format this build expects");
    expect(screen.queryByTestId("lifecycle-detail")).not.toBeInTheDocument();
  });
});

describe("lifecycle groups", () => {
  it("keeps an active position visible without a current run and separates the groups", () => {
    const managed = openPosition({ group: "ACTIVE_MANAGED", candidate: { ...openPosition().candidate!, selected_in_current_run: false } });
    renderWith(<TradeLifecycleGroups runId="run-2" list={lifecycleList({ active_managed: [managed], recent_closed: [closedEpisode({ lifecycle_id: "TE-old", symbol: "MSFT", instrument_id: "MSFT" })],
      counts: { selected: 0, active_managed: 1, recent_closed: 4, unlinked: 0 } })} />);
    const active = screen.getByRole("region", { name: "Active managed positions" });
    expect(within(active).getByTestId("lifecycle-origin")).toHaveTextContent("Active managed position — opened from AI Screener run selected 10:28:00 ET; not selected by the latest run");
    expect(within(active).getByTestId("lifecycle-stage")).toHaveTextContent("POSITION OPEN · HOLD");
    expect(within(active).getByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Recent closed episodes" })).toHaveTextContent("1 of 4");
    expect(screen.queryByRole("region", { name: "Unlinked Paper activity" })).not.toBeInTheDocument();
  });

  it("states the market-data and execution boundary separately", async () => {
    renderWith(<LifecycleBoundary list={lifecycleList({ limitations: ["PAPER_EXPERIMENT_REQUIRED"] })} />);
    const boundary = screen.getByTestId("lifecycle-boundary");
    expect(boundary).toHaveTextContent("Market data: LIVE OBSERVATIONAL · Execution: SIMULATED PAPER");
    expect(boundary).toHaveTextContent("No active Paper experiment");
    await waitFor(() => expect(mocks.detail).not.toHaveBeenCalled());
  });
});

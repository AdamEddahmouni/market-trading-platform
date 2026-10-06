import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperPortfolioResponseSchema, PaperTradesResponseSchema } from "../../api/schemas";
import { PaperExperimentCreate, PaperExperimentPanel } from "./PaperExperimentPanel";
import { experimentPortfolio, experimentTrades } from "./paperExperimentFixture";

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  createError: null as Error | null,
  close: vi.fn(),
  closeError: null as Error | null,
  trades: [] as unknown[],
}));

vi.mock("../../api/hooks", () => ({
  useCreatePaperExperimentMutation: () => ({
    mutate: mocks.create,
    isPending: false,
    isError: Boolean(mocks.createError),
    error: mocks.createError,
  }),
  useClosePaperExperimentMutation: () => ({
    mutate: mocks.close,
    isPending: false,
    isError: Boolean(mocks.closeError),
    error: mocks.closeError,
  }),
  usePaperTradesInfiniteQuery: () => ({
    data: { pages: [{ trades: mocks.trades, total_count: mocks.trades.length }] },
    isLoading: false,
    isError: false,
    hasNextPage: false,
    isFetchingNextPage: false,
    fetchNextPage: vi.fn(),
  }),
  usePaperEquityHistoryQuery: () => ({
    data: {
      total_count: 1,
      snapshots: [
        {
          snapshot_id: 1,
          captured_at_ns: 1791309918000000000,
          trigger: "EXPERIMENT_CREATED",
          quality: "CURRENT",
          cash_minor: 10_000_000,
          equity_minor: 10_000_000,
          realized_pnl_minor: 0,
          unrealized_pnl_minor: 0,
          total_pnl_minor: 0,
        },
      ],
    },
  }),
}));

const onViewTrace = vi.fn();

function renderPanel(payload: ReturnType<typeof experimentPortfolio>, canAct = true) {
  // The payload must satisfy the same schema the client applies to the real route.
  const data = PaperPortfolioResponseSchema.parse(payload);
  return render(
    <MemoryRouter>
      <PaperExperimentPanel data={data} canAct={canAct} onViewTrace={onViewTrace} />
    </MemoryRouter>,
  );
}

function metric(label: string) {
  const summary = screen.getByTestId("experiment-summary");
  const term = within(summary).getByText(label, { selector: "dt" });
  return term.parentElement!.querySelector("dd")!;
}

describe("PaperExperimentPanel", () => {
  beforeEach(() => {
    mocks.create.mockClear();
    mocks.close.mockClear();
    mocks.closeError = null;
    mocks.createError = null;
    mocks.trades = PaperTradesResponseSchema.parse({
      experiment_id: "PPE-TEST0001",
      trades: experimentTrades(),
      total_count: 2,
      page_size: 25,
      next_cursor: null,
    }).trades;
    onViewTrace.mockClear();
  });

  it("requires an explicit action to create the $100,000 experiment", () => {
    render(<PaperExperimentCreate />);
    expect(screen.getByRole("heading", { name: "No active Paper experiment" })).toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Create $100,000 Paper experiment" }));
    expect(mocks.create).toHaveBeenCalledTimes(1);
  });

  it("shows the backend refusal when Paper simulation is not authorized", () => {
    mocks.createError = new Error("PAPER_EXECUTION_NOT_AUTHORIZED: internal Paper simulation is not enabled for this backend");
    render(<PaperExperimentCreate />);
    expect(screen.getByRole("alert")).toHaveTextContent("Experiment was not created: PAPER_EXECUTION_NOT_AUTHORIZED");
  });

  it("shows the experiment identity and every summary value from the server valuation", () => {
    renderPanel(experimentPortfolio());
    expect(screen.getByText("OCT1-09 PAPER EXPERIMENT · SIMULATED CAPITAL")).toBeInTheDocument();
    expect(screen.getByTestId("experiment-status")).toHaveTextContent("ACTIVE");
    expect(metric("Initial capital")).toHaveTextContent("$100,000.00");
    expect(metric("Cash")).toHaveTextContent("$79,200.00");
    expect(metric("Reserved cash")).toHaveTextContent("$0.00");
    expect(metric("Buying power")).toHaveTextContent("$79,200.00");
    expect(metric("Position value")).toHaveTextContent("$21,100.00");
    expect(metric("Realized P&L")).toHaveTextContent("+$200.00");
    expect(metric("Unrealized P&L")).toHaveTextContent("+$100.00");
    expect(metric("Total equity")).toHaveTextContent("$100,300.00");
    expect(metric("Total Paper P&L")).toHaveTextContent("+$300.00");
    expect(metric("Paper experiment return")).toHaveTextContent("+0.30%");
    expect(screen.getByTestId("experiment-quality")).toHaveTextContent("Valuation quality: CURRENT");
  });

  it("separates live market data from simulated execution and never claims live capital", () => {
    renderPanel(experimentPortfolio());
    const boundary = screen.getByTestId("experiment-boundary");
    expect(boundary).toHaveTextContent("LIVE/CURRENT MARKET DATA + SIMULATED PAPER EXECUTION");
    expect(boundary).toHaveTextContent("live observational feed from MOOMOO");
    expect(boundary).toHaveTextContent("Internal Paper simulation (INTERNAL)");
    expect(boundary).toHaveTextContent("Live capital: No");
    expect(screen.getByTestId("experiment-panel")).not.toHaveTextContent(/live (order|trading|fill)/i);
  });

  it("names the actual data mode and provider instead of a fixed label", () => {
    const payload = experimentPortfolio();
    payload.boundary.market_data = { mode: "FIXTURE_REPLAY", provider: "INTERNAL", running_mode: "FIXTURE_REPLAY", state: "AVAILABLE" };
    renderPanel(payload);
    const boundary = screen.getByTestId("experiment-boundary");
    expect(boundary).toHaveTextContent("FIXTURE REPLAY DATA (NOT LIVE MARKET DATA) + SIMULATED PAPER EXECUTION");
    expect(boundary).not.toHaveTextContent("MOOMOO");
    expect(boundary).not.toHaveTextContent("LIVE/CURRENT");
  });

  it("says when the live feed is deferred or the data mode is not running", () => {
    const deferred = experimentPortfolio();
    deferred.boundary.market_data.state = "EXECUTION_DEFERRED";
    const { unmount } = renderPanel(deferred);
    expect(screen.getByTestId("experiment-boundary")).toHaveTextContent("LIVE MARKET DATA NOT YET VERIFIED");
    unmount();
    const missing = experimentPortfolio();
    missing.boundary.market_data = { mode: "LIVE_OBSERVATIONAL", provider: "MOOMOO", running_mode: "FIXTURE_REPLAY", state: "MARKET_DATA_UNAVAILABLE" };
    renderPanel(missing);
    expect(screen.getByTestId("experiment-boundary")).toHaveTextContent("MARKET DATA UNAVAILABLE");
    expect(screen.getByTestId("experiment-boundary")).toHaveTextContent("Orders are blocked");
  });

  it("lists each instrument with its own mark, value and unrealized P&L", () => {
    renderPanel(experimentPortfolio());
    const aapl = screen.getByTestId("experiment-position-AAPL");
    const nvda = screen.getByTestId("experiment-position-NVDA");
    expect(aapl).toHaveTextContent("LONG");
    expect(aapl).toHaveTextContent("$150.00");
    expect(aapl).toHaveTextContent("$155.00");
    expect(aapl).toHaveTextContent("$9,300.00");
    expect(aapl).toHaveTextContent("+$300.00");
    expect(aapl).toHaveTextContent("MOOMOO · PASS · 10s old");
    expect(nvda).toHaveTextContent("$240.00");
    expect(nvda).toHaveTextContent("$236.00");
    expect(nvda).toHaveTextContent("$11,800.00");
    expect(nvda).toHaveTextContent("−$200.00");
    expect(within(nvda).getByLabelText("loss of $200.00")).toBeInTheDocument();
  });

  it("never shows $0.00 for a position without a mark", () => {
    renderPanel(experimentPortfolio({ nvdaMark: null }));
    const nvda = screen.getByTestId("experiment-position-NVDA");
    expect(nvda).toHaveTextContent("No mark — not valued");
    expect(nvda).not.toHaveTextContent("$0.00");
    expect(within(nvda).getAllByText("Unavailable").length).toBeGreaterThanOrEqual(3);
    expect(metric("Total equity")).toHaveTextContent("Unavailable");
    expect(metric("Unrealized P&L")).toHaveTextContent("Unavailable");
    expect(metric("Total Paper P&L")).toHaveTextContent("Unavailable");
    expect(metric("Paper experiment return")).toHaveTextContent("Unavailable");
    expect(metric("Cash")).toHaveTextContent("$79,200.00");
    const quality = screen.getByTestId("experiment-quality");
    expect(quality).toHaveTextContent("Valuation quality: PARTIAL");
    expect(quality).toHaveTextContent("NVDA (no mark)");
    expect(screen.getByRole("status")).toHaveTextContent(/Total equity is unavailable/);
  });

  it("carries a stale mark as a degraded valuation", () => {
    renderPanel(experimentPortfolio({ nvdaQuality: "STALE", quality: "DEGRADED" }));
    expect(screen.getByTestId("experiment-position-NVDA")).toHaveTextContent("MOOMOO · STALE");
    const quality = screen.getByTestId("experiment-quality");
    expect(quality).toHaveTextContent("Valuation quality: DEGRADED");
    expect(quality).toHaveTextContent("not a current valuation");
    expect(quality).toHaveTextContent("NVDA (not current)");
    expect(metric("Total equity")).toHaveTextContent("$100,300.00");
  });

  it("shows trade history with costs, realized P&L, decision source and drilldown", () => {
    renderPanel(experimentPortfolio());
    const table = screen.getByTestId("experiment-trades");
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("SELL");
    expect(rows[1]).toHaveTextContent("$155.00");
    expect(rows[1]).toHaveTextContent("REDUCE");
    expect(rows[1]).toHaveTextContent("+$200.00");
    expect(rows[1]).toHaveTextContent("Operator ticket (no governed decision)");
    expect(rows[2]).toHaveTextContent("BUY");
    expect(rows[2]).toHaveTextContent("Governed AI decision");
    expect(rows[2]).toHaveTextContent("$0.00");
    fireEvent.click(within(rows[2]).getByRole("button", { name: "View decision" }));
    expect(screen.getByText("AD-1")).toBeInTheDocument();
    expect(screen.getByText("RUN-1")).toBeInTheDocument();
    expect(screen.getByText("RISK-1")).toBeInTheDocument();
    expect(screen.getByText(/Simulated fill \(SIMULATED_FILL\) of 100 of 100 requested/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open execution trace" }));
    expect(onViewTrace).toHaveBeenCalledWith("INT", "ORD");
  });

  it("states the fill, cost and slippage assumptions", () => {
    renderPanel(experimentPortfolio());
    const block = screen.getByTestId("experiment-assumptions");
    expect(block).toHaveTextContent("simulation.bar_conservative · phase7.bar-conservative/1.1.0");
    expect(block).toHaveTextContent("$0.00 per share (none charged)");
    expect(block).toHaveTextContent("$0.00 per order (none charged)");
    expect(block).toHaveTextContent("NOT_SEPARATELY_MODELED");
    expect(block).toHaveTextContent("not evidence of a profitable strategy");
  });

  it("surfaces the fail-closed reason when close is refused", () => {
    mocks.closeError = new Error("OPEN_POSITIONS_REMAIN: flatten every position before closing the experiment");
    renderPanel(experimentPortfolio());
    fireEvent.click(screen.getByRole("button", { name: "Close experiment" }));
    expect(mocks.close).toHaveBeenCalledWith("PPE-TEST0001");
    expect(screen.getByTestId("experiment-close-error")).toHaveTextContent("OPEN_POSITIONS_REMAIN");
    expect(screen.getByTestId("experiment-close-error")).toHaveTextContent("never sells positions for you");
  });

  it("hides close without authority and labels tables for assistive technology", () => {
    renderPanel(experimentPortfolio(), false);
    expect(screen.queryByRole("button", { name: "Close experiment" })).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Positions in this account" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Trade history (simulated fills)" })).toBeInTheDocument();
    expect(screen.getByRole("note", { name: "Market data and execution boundary" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "NVDA" })).toBeInTheDocument();
  });
});

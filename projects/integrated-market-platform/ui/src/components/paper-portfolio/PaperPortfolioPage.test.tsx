import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPaperOrderHistoryInfiniteQueryMock } from "../../test/paperOrderHistoryQueryMock";
import { PaperPortfolioPage } from "./PaperPortfolioPage";

function portfolioPayload() {
  return {
    account: {
      paper_account_id: "acct",
      session_id: "sess",
      currency: "USD",
      cash_display: "1000.00",
      cash_minor: 100000,
      buying_power_minor: 100000,
      initial_cash_minor: 100000,
      realized_pnl_display: "0.00",
      realized_pnl_minor: 0,
      data_mode: "FIXTURE_REPLAY",
      data_provider: "INTERNAL",
      execution_mode: "NONE",
      execution_authority: "BLOCKED",
      execution_provider: "INTERNAL",
    },
    authority_boundary: "PAPER_OBSERVABILITY",
    positions: [],
    orders: [],
    fills: [],
    risk: {
      kill_switch_active: false,
      open_order_count: 0,
      reconciliation_status: "INTERNAL_AUTHORITATIVE",
      limits: { max_open_orders: 3, max_order_shares: 100, max_position_shares: 500 },
    },
    data_health: { state: "PASS", detail: "fixture" },
    as_of_context: {
      mode: "REPLAY",
      as_of_time: "2026-08-30T12:00:00Z",
      timezone: "America/New_York",
      data_mode: "FIXTURE_REPLAY",
      execution_mode: "NONE",
      execution_authority: "BLOCKED",
    },
    active_instrument: "BIYA",
    active_instrument_source: "WORKSPACE",
  };
}

let portfolio = portfolioPayload();
const cancelPaperOrder = vi.fn().mockResolvedValue({});

vi.mock("../../api/hooks", () => ({
  usePaperPortfolioQuery: () => ({
    isLoading: false,
    isError: false,
    data: portfolio,
    refetch: vi.fn(),
  }),
  usePaperStrategyProfitabilityQuery: () => ({ isLoading: false, isError: true, data: undefined }),
  usePaperOrderHistoryInfiniteQuery: () => createPaperOrderHistoryInfiniteQueryMock(portfolio.orders),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useClosePaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCancelPaperOrderMutation: () => ({ mutateAsync: cancelPaperOrder, isPending: false }),
}));

function renderPage(paperActionsPermitted: boolean) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PaperPortfolioPage paperActionsPermitted={paperActionsPermitted} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PaperPortfolioPage", () => {
  beforeEach(() => {
    portfolio = portfolioPayload();
    cancelPaperOrder.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ sessions: [] }),
      }),
    );
  });

  it("fails closed when global Paper context is incompatible", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";

    renderPage(false);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Archive session" })).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Paper authority unavailable/i);
    expect(screen.getAllByRole("link", { name: "Open Workspace" }).length).toBeGreaterThan(0);
  });

  it("fails closed when the action payload lacks Paper authority", () => {
    renderPage(true);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Paper authority unavailable/i);
    expect(screen.getByRole("heading", { name: "Profitability lineage" })).toBeInTheDocument();
  });

  it("requires an explicit instrument before opening a new Paper session", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    portfolio.active_instrument = null;
    portfolio.active_instrument_source = "NONE";

    renderPage(true);

    const newSession = screen.getByRole("button", { name: "New Paper Session" });
    expect(newSession).toBeDisabled();
    expect(newSession).toHaveAttribute("title", "Choose an instrument in Workspace first.");
  });

  it("shows Paper actions only when both authority checks pass", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";

    renderPage(true);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open Workspace" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "New Paper Session" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive session" })).toBeInTheDocument();
    expect(screen.getByText(/Paper simulation account — not live capital/i)).toBeInTheDocument();
  });

  it("keeps operational history and trace readable when Paper authority is unavailable", async () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    portfolio.orders = [
      {
        order_id: "order-1",
        intent_id: "intent-1",
        client_order_id: "client-1",
        correlation_id: "lane:squeeze",
        side: "BUY",
        desired_quantity: 1,
        order_type: "MARKET",
        state: "FILLED",
        symbol: "BIYA",
        submitted_sequence: 1,
      },
    ];

    renderPage(false);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByText("BIYA")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open BIYA Workspace" })).toHaveAttribute(
      "href",
      "/workspace/BIYA",
    );
    fireEvent.click(screen.getByRole("rowheader", { name: /BIYA/ }));
    expect(screen.getByRole("button", { name: "View trace" })).toBeInTheDocument();
  });

  it("renders empty holdings with a Workspace handoff and never submits from Portfolio", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    renderPage(true);
    expect(screen.getByRole("heading", { name: "No open positions" })).toBeInTheDocument();
    expect(screen.getByText(/No simulated orders yet/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Open Workspace" }).length).toBeGreaterThan(0);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
  });

  it("points Fills at Order history instead of a vague activity section", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    renderPage(true);

    expect(screen.queryByText(/activity section below/i)).not.toBeInTheDocument();
    const handoff = screen.getByRole("link", { name: "Order history" });
    expect(handoff).toHaveAttribute("href", "#portfolio-order-history");
    expect(document.getElementById("portfolio-order-history")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Fills" })).toBeInTheDocument();
  });

  it("keeps the header Workspace handoff on the active instrument", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    renderPage(true);
    const handoffs = screen.getAllByRole("link", { name: "Open Workspace" });
    expect(handoffs.length).toBeGreaterThan(0);
    for (const handoff of handoffs) {
      expect(handoff).toHaveAttribute("href", "/workspace/BIYA");
    }
  });

  it("keeps session history behind a compact disclosure", () => {
    renderPage(false);
    const disclosure = screen.getByTestId("portfolio-session-history");
    expect(disclosure).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Refresh sessions" })).toBeInTheDocument();
  });

  it("keeps account and fills detail behind a secondary disclosure", () => {
    renderPage(false);
    const secondary = screen.getByTestId("portfolio-secondary");
    expect(secondary).not.toHaveAttribute("open");
    expect(within(secondary).getByRole("heading", { name: "Account" })).toBeInTheDocument();
  });

  it("puts exposure, positions, and orders ahead of account and fills detail", () => {
    portfolio.orders = [
      { order_id: "order-9", symbol: "AAPL", side: "BUY", desired_quantity: 10, state: "WORKING" },
    ];
    renderPage(false);
    const headings = screen
      .getAllByRole("heading")
      .map((node) => node.textContent?.trim() ?? "")
      .filter(Boolean);
    const positions = headings.indexOf("Positions");
    const working = headings.indexOf("Working orders");
    const account = headings.indexOf("Account");
    const fills = headings.indexOf("Fills");
    expect(positions).toBeGreaterThanOrEqual(0);
    expect(working).toBeGreaterThan(positions);
    expect(account).toBeGreaterThan(working);
    expect(fills).toBeGreaterThan(account);
  });

  it("leads the glance strip with position and working-order counts", () => {
    renderPage(false);
    const glance = screen.getByTestId("portfolio-glance");
    expect(within(glance).getByText("Positions")).toBeInTheDocument();
    expect(within(glance).getByText("Working orders")).toBeInTheDocument();
  });

  it("carries a position's own instrument into its Workspace handoff", () => {
    portfolio.positions = [
      {
        instrument_id: "AAPL",
        symbol: "AAPL",
        quantity: 120,
        side: "LONG",
        mark_display: "228.41",
        mark_quality: "FRESH",
        average_fill_display: "221.06",
        unrealized_pnl_display: "882.00",
      },
    ];
    renderPage(false);
    const handoff = screen.getByRole("link", { name: "Open AAPL Workspace" });
    expect(handoff).toHaveAttribute("href", "/workspace/AAPL");
    expect(screen.getByText("Long")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
  });

  it("reveals deeper position context only for the selected row", () => {
    portfolio.positions = [
      {
        instrument_id: "AAPL",
        symbol: "AAPL",
        quantity: 120,
        side: "SHORT",
        mark_display: "228.41",
        mark_provider: "INTERNAL",
        mark_quality: "FRESH",
        average_fill_display: "221.06",
        unrealized_pnl_display: "882.00",
      },
    ];
    renderPage(false);
    expect(screen.queryByTestId("portfolio-position-selection")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("rowheader", { name: /AAPL/ }));
    const selection = screen.getByTestId("portfolio-position-selection");
    expect(within(selection).getByText("INTERNAL")).toBeInTheDocument();
    expect(within(selection).getByRole("link", { name: "Open Workspace" })).toHaveAttribute(
      "href",
      "/workspace/AAPL",
    );
    fireEvent.click(within(selection).getByRole("button", { name: "Clear selection" }));
    expect(screen.queryByTestId("portfolio-position-selection")).not.toBeInTheDocument();
  });

  it("withholds order cancel while Paper authority is unavailable", () => {
    portfolio.orders = [
      { order_id: "order-9", symbol: "AAPL", side: "BUY", desired_quantity: 10, state: "WORKING" },
    ];
    renderPage(true);
    expect(screen.queryByRole("button", { name: /Cancel working AAPL order/i })).not.toBeInTheDocument();
  });

  it("cancels a working order through the backend contract when Paper authority allows it", async () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    portfolio.orders = [
      { order_id: "order-9", symbol: "AAPL", side: "BUY", desired_quantity: 10, state: "WORKING" },
    ];
    renderPage(true);
    fireEvent.click(screen.getByRole("button", { name: /Cancel working AAPL order/i }));
    await waitFor(() => expect(cancelPaperOrder).toHaveBeenCalledWith("order-9"));
  });

  it("never offers cancel for a filled order even with Paper authority", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    portfolio.orders = [
      { order_id: "order-8", symbol: "AAPL", side: "BUY", desired_quantity: 10, state: "FILLED" },
    ];
    renderPage(true);
    expect(screen.queryByRole("button", { name: /Cancel working AAPL order/i })).not.toBeInTheDocument();
  });

  it.each([
    { label: "HTTP failure", response: { ok: false, json: async () => ({ sessions: [] }) } },
    { label: "malformed response", response: { ok: true, json: async () => ({ message: "error" }) } },
    { label: "malformed session", response: { ok: true, json: async () => ({ sessions: [{}] }) } },
  ])("shows unavailable session history on $label", async ({ response }) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
    renderPage(false);
    await waitFor(() =>
      expect(screen.getByText(/Session list unavailable/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText("No persisted sessions yet.")).not.toBeInTheDocument();
  });
});

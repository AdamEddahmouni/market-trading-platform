import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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
    active_instrument_source: "FIXTURE_DEFAULT",
  };
}

let portfolio = portfolioPayload();

vi.mock("../../api/hooks", () => ({
  usePaperPortfolioQuery: () => ({
    isLoading: false,
    isError: false,
    data: portfolio,
  }),
  usePaperOrderHistoryInfiniteQuery: () => createPaperOrderHistoryInfiniteQueryMock(portfolio.orders),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useClosePaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderPage(paperActionsPermitted: boolean) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <PaperPortfolioPage paperActionsPermitted={paperActionsPermitted} />
    </QueryClientProvider>,
  );
}

describe("PaperPortfolioPage", () => {
  beforeEach(() => {
    portfolio = portfolioPayload();
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
  });

  it("fails closed when the action payload lacks Paper authority", () => {
    renderPage(true);

    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/Paper authority unavailable/i);
  });

  it("shows Paper actions only when both authority checks pass", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";

    renderPage(true);

    expect(screen.getByText("Order ticket")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New Paper Session" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Archive session" })).toBeInTheDocument();
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
    expect(screen.getByText("SHORT SQUEEZE")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /View trace for BIYA/i })).toBeInTheDocument();
  });

  it("renders order history empty state", () => {
    portfolio.account.execution_mode = "INTERNAL_SIMULATION";
    portfolio.account.execution_authority = "PAPER_ONLY";
    renderPage(true);
    expect(screen.getByText(/No simulated orders yet/i)).toBeInTheDocument();
  });
});

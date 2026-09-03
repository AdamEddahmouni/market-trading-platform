import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { PortfolioPage } from "./PortfolioPage";

vi.mock("../api/hooks", () => ({
  useContextQuery: () => ({
    data: {
      as_of_context: {
        scope_symbols: ["BIYA"],
        data_mode: "FIXTURE_REPLAY",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
      },
    },
  }),
  usePaperPortfolioQuery: () => ({
    isLoading: false,
    isError: false,
    data: {
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
        scope_symbols: ["BIYA"],
        data_mode: "FIXTURE_REPLAY",
        execution_mode: "NONE",
        execution_authority: "BLOCKED",
      },
      active_instrument: "BIYA",
      active_instrument_source: "FIXTURE_DEFAULT",
    },
  }),
  usePreviewPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSubmitPaperOrderMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenPaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useClosePaperSessionMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <PortfolioPage />
    </QueryClientProvider>,
  );
}

describe("PortfolioPage", () => {
  it("renders order ticket with blocked execution gating", () => {
    renderPage();
    expect(screen.getByText("Order ticket")).toBeInTheDocument();
    expect(screen.getByText(/AUTH: BLOCKED/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Preview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
  });
});

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
    expect(screen.getByText(/Simulated portfolio unavailable/)).toBeInTheDocument();
    expect(screen.queryByText("0 shares")).not.toBeInTheDocument();
  });
});

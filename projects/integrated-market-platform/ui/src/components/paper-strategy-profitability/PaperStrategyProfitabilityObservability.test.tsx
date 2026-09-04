import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PaperStrategyProfitabilityResponse } from "../../api/schemas";
import { PaperStrategyProfitabilityObservability } from "./PaperStrategyProfitabilityObservability";

let query: { isLoading: boolean; isError: boolean; data?: PaperStrategyProfitabilityResponse };

vi.mock("../../api/hooks", () => ({
  usePaperStrategyProfitabilityQuery: () => query,
}));

function renderComponent() {
  return render(
    <MemoryRouter>
      <PaperStrategyProfitabilityObservability />
    </MemoryRouter>,
  );
}

describe("PaperStrategyProfitabilityObservability", () => {
  beforeEach(() => {
    query = { isLoading: false, isError: true };
  });

  it("keeps observability visible when the strategy authority is unavailable", () => {
    renderComponent();

    expect(screen.getByRole("heading", { name: "Profitability lineage" })).toBeInTheDocument();
    expect(screen.getByText(/strategy runtime observability is unavailable/i)).toBeInTheDocument();
  });

  it("renders an empty state without introducing submission controls", () => {
    query = { isLoading: false, isError: false, data: emptyPayload() };

    renderComponent();

    expect(screen.getByText(/No strategy-linked Paper allocations yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("separates account-ledger P&L from strategy-attributed P&L", () => {
    query = { isLoading: false, isError: false, data: filledPayload() };

    renderComponent();

    expect(screen.getByText("$5.00")).toBeInTheDocument();
    expect(screen.getByText("strategy-alpha")).toBeInTheDocument();
    expect(screen.getByText("$1.00")).toBeInTheDocument();
    expect(screen.getByText("Review in Workspace")).toHaveAttribute("href", "/workspace/AAPL");
    expect(screen.getByText(/non-additive/i)).toBeInTheDocument();
  });
});

function emptyPayload(): PaperStrategyProfitabilityResponse {
  return {
    schema_version: "ui/paper-strategy-profitability/1.0.0",
    authority_boundary: "PAPER_OBSERVABILITY_READ_ONLY",
    account_id: "paper-account",
    mode: "PAPER",
    as_of_context: { as_of_ns: 100, point_in_time: false },
    attribution_semantics: {
      pnl_source: "StrategyAttributionV1.trading_outcome",
      materialization: "CUMULATIVE",
      aggregation: "LATEST_COMPLETE_SNAPSHOT_ONLY",
      portfolio_ledger_is_authoritative: true,
    },
    data_health: { state: "EMPTY", detail: "empty" },
    disclaimer: "Attribution is a sidecar.",
    account_ledger_pnl: { currency: "USD", realized_pnl_minor: 0, unrealized_pnl_minor: 0 },
    items: [],
    total_count: 0,
  };
}

function filledPayload(): PaperStrategyProfitabilityResponse {
  return {
    ...emptyPayload(),
    data_health: { state: "PASS", detail: "ok" },
    account_ledger_pnl: { currency: "USD", realized_pnl_minor: 500, unrealized_pnl_minor: 0 },
    items: [
      {
        allocation: { allocation_decision_id: "allocation-1", account_id: "paper-account", mode: "PAPER" },
        strategy_match: { match_id: "match-1", strategy_id: "strategy-alpha" },
        forecast: { forecast_id: "forecast-1", target: { instrument_id: "AAPL" } },
        economic_assessment: null,
        opportunity: null,
        portfolio_snapshot: null,
        proposal: null,
        risk_decision: null,
        orders: [],
        fills: [{ fill_id: "fill-1" }],
        attribution: {
          attribution_id: "attribution-1",
          materialization_semantics: "CUMULATIVE",
          allocation_quantity: 2,
          fill_refs: [{ kind: "fill", id: "fill-1" }],
          trading_outcome: {
            realized_pnl_minor: 100,
            ending_position_quantity: 0,
            ending_cost_basis_minor: 0,
            total_commission_minor: 0,
            total_fees_minor: 0,
          },
        },
        prediction_ledger_entry: null,
        prediction_outcome: null,
        settlement: { state: "SETTLED", inspection_only: true },
      },
    ],
    total_count: 1,
  };
}

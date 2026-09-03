import { describe, expect, it } from "vitest";
import type { PaperPortfolioResponse } from "../../api/client";
import { buildPaperRiskContext } from "./buildPaperRiskContext";

function portfolio(overrides: Partial<PaperPortfolioResponse> = {}): PaperPortfolioResponse {
  return {
    as_of_context: {
      mode: "REPLAY",
      data_mode: "FIXTURE_REPLAY",
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
      as_of_time: "2026-08-31T12:00:00Z",
      timezone: "America/New_York",
    },
    authority_boundary: "PAPER_ONLY",
    account: {
      paper_account_id: "paper-1",
      session_id: "sess-1",
      currency: "USD",
      cash_display: "$100",
      cash_minor: 10000,
      buying_power_minor: 10000,
      initial_cash_minor: 10000,
      realized_pnl_display: "$0",
      realized_pnl_minor: 0,
      data_mode: "FIXTURE_REPLAY",
      data_provider: "FIXTURE",
      execution_mode: "INTERNAL_SIMULATION",
      execution_authority: "PAPER_ONLY",
      execution_provider: "INTERNAL",
    },
    positions: [{ instrument_id: "BIYA", symbol: "BIYA", quantity: 5, side: "LONG" }],
    orders: [{ symbol: "BIYA", state: "OPEN" }],
    exposure: { gross_shares: 5 },
    pnl: { total_display: "$0" },
    data_health: { state: "PASS" },
    reconciliation_status: "PASS",
    risk: {
      kill_switch_active: false,
      limits: { max_order_shares: 100, max_position_shares: 500, max_open_orders: 10 },
      last_decision: null,
      open_order_count: 1,
      reconciliation_status: "PASS",
    },
    ...overrides,
  } as PaperPortfolioResponse;
}

describe("buildPaperRiskContext", () => {
  it("maps ready portfolio with symbol position and open orders", () => {
    const model = buildPaperRiskContext(
      portfolio({
        account: {
          ...portfolio().account,
          reserved_cash_minor: 2500,
          reserved_cash_display: "$25.00",
          equity_minor: 12500,
          equity_display: "$125.00",
          valuation_quality: "COMPLETE",
        },
      }),
      "BIYA",
      true,
      "ready",
    );
    expect(model.phase).toBe("ready");
    expect(model.symbolPosition).toBe("5 sh");
    expect(model.openOrdersForSymbol).toBe(1);
    expect(model.items.some((item) => item.id === "buying-power")).toBe(true);
    expect(model.items.find((item) => item.id === "reserved-cash")?.value).toBe("$25.00");
    expect(model.items.find((item) => item.id === "equity")?.value).toBe("$125.00");
  });

  it("warns when authority is unavailable", () => {
    const model = buildPaperRiskContext(portfolio(), "BIYA", false, "ready");
    expect(model.warnings.join(" ")).toMatch(/authority unavailable/i);
  });

  it("fails closed on error phase", () => {
    const model = buildPaperRiskContext(undefined, "BIYA", false, "error");
    expect(model.phase).toBe("error");
    expect(model.warnings[0]).toMatch(/Risk context is unavailable/i);
  });
});

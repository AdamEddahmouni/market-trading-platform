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

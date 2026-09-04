import { describe, expect, it } from "vitest";
import {
  buildPaperStrategyProfitabilityModel,
  type PaperStrategyProfitabilityResponse,
} from "./paperStrategyProfitabilityModel";

describe("buildPaperStrategyProfitabilityModel", () => {
  it("keeps cumulative attribution snapshots non-additive", () => {
    const payload = {
      schema_version: "ui/paper-strategy-profitability/1.0.0",
      authority_boundary: "PAPER_OBSERVABILITY_READ_ONLY",
      account_id: "paper-account",
      mode: "PAPER",
      as_of_context: { as_of_ns: 100, point_in_time: true },
      attribution_semantics: {
        pnl_source: "StrategyAttributionV1.trading_outcome",
        materialization: "CUMULATIVE",
        aggregation: "LATEST_COMPLETE_SNAPSHOT_ONLY",
        portfolio_ledger_is_authoritative: true,
      },
      data_health: { state: "PASS", detail: "ok" },
      disclaimer: "Attribution is a sidecar.",
      account_ledger_pnl: { currency: "USD", realized_pnl_minor: 500, unrealized_pnl_minor: 0 },
      items: [
        {
          allocation: { allocation_decision_id: "a-1", account_id: "paper-account", mode: "PAPER" },
          strategy_match: { match_id: "m-1", strategy_id: "strategy-a" },
          forecast: { forecast_id: "f-1", target: { instrument_id: "AAPL" } },
          attribution: {
            attribution_id: "attr-1",
            materialization_semantics: "CUMULATIVE",
            allocation_quantity: 1,
            fill_refs: [{ kind: "fill", id: "fill-1" }],
            trading_outcome: { realized_pnl_minor: 100 },
          },
          orders: [],
          fills: [],
          settlement: { state: "PENDING", inspection_only: true },
        },
        {
          allocation: { allocation_decision_id: "a-2", account_id: "paper-account", mode: "PAPER" },
          strategy_match: { match_id: "m-2", strategy_id: "strategy-b" },
          forecast: { forecast_id: "f-2", target: { instrument_id: "MSFT" } },
          attribution: {
            attribution_id: "attr-2",
            materialization_semantics: "CUMULATIVE",
            allocation_quantity: 2,
            fill_refs: [{ kind: "fill", id: "fill-2" }],
            trading_outcome: { realized_pnl_minor: 150 },
          },
          orders: [],
          fills: [],
          settlement: { state: "SETTLED", inspection_only: true },
        },
      ],
      total_count: 2,
    } as PaperStrategyProfitabilityResponse;

    const model = buildPaperStrategyProfitabilityModel(payload);

    expect(model.rows).toHaveLength(2);
    expect(model.strategyAttribution.realizedPnlMinor).toBeNull();
    expect(model.strategyAttribution.isAdditive).toBe(false);
    expect(model.ledgerRealizedPnlMinor).toBe(500);
    expect(model.settledCount).toBe(1);
  });
});

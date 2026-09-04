import { describe, expect, it } from "vitest";
import { queryKeys } from "./hooks";
import { PaperStrategyProfitabilityResponseSchema } from "./schemas";

describe("Paper strategy profitability API contract", () => {
  it("parses a read-only response and isolates account/session query keys", () => {
    const payload = {
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
      disclaimer: "Read only.",
      account_ledger_pnl: { currency: "USD", realized_pnl_minor: 0, unrealized_pnl_minor: 0 },
      items: [],
      total_count: 0,
    };

    expect(PaperStrategyProfitabilityResponseSchema.parse(payload).mode).toBe("PAPER");
    expect(queryKeys.paperStrategyProfitability("account-a", "session-a")).not.toEqual(
      queryKeys.paperStrategyProfitability("account-b", "session-a"),
    );
    expect(queryKeys.paperStrategyProfitability("account-a", "session-a")).not.toEqual(
      queryKeys.paperStrategyProfitability("account-a", "session-b"),
    );
  });
});

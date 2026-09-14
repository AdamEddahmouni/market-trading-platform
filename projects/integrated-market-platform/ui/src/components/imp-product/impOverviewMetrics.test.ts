import { describe, expect, it } from "vitest";
import type { PaperPortfolioResponse } from "../../api/client";
import { overviewKpisFromLiveContext, overviewKpisFromPortfolio } from "./impOverviewMetrics";

const portfolio = {
  account: { cash_display: "$50,000", realized_pnl_display: "+$10" },
  pnl: { total_display: "+$25", unrealized_display: "+$15" },
  positions: [{ instrument_id: "BIYA" }],
  exposure: { gross_shares: 100 },
  risk: { open_order_count: 2 },
  data_health: { state: "OK" },
} as PaperPortfolioResponse;

describe("overviewKpisFromPortfolio", () => {
  it("maps admitted portfolio fields without inventing metrics", () => {
    const cells = overviewKpisFromPortfolio(portfolio, "ready");
    expect(cells.find((c) => c.id === "cash")?.value).toBe("$50,000");
    expect(cells.find((c) => c.id === "total-pnl")?.value).toBe("+$25");
    expect(cells.find((c) => c.id === "positions")?.value).toBe("1");
  });

  it("degrades on error", () => {
    const cells = overviewKpisFromPortfolio(undefined, "error");
    expect(cells.every((c) => c.detail === "Unavailable")).toBe(true);
  });
});

describe("overviewKpisFromLiveContext", () => {
  it("surfaces observational context only", () => {
    const cells = overviewKpisFromLiveContext({
      state: "ready",
      attentionCount: 3,
      dataMode: "LIVE_OBSERVATIONAL",
      executionAuthority: "NONE",
      providerName: "MOOMOO",
      connectionState: "CONNECTED",
      opportunityFeedStatus: "READY",
    });
    expect(cells.find((c) => c.id === "attention")?.value).toBe("3");
    expect(cells.find((c) => c.id === "authority")?.detail).toMatch(/off/i);
  });
});

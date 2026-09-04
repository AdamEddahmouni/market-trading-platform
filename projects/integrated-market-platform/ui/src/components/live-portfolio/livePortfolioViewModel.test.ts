import { describe, expect, it } from "vitest";
import { canarySnapshot } from "../live-now/liveNowTestFixtures";
import {
  livePortfolioOrders,
  livePortfolioPositions,
  liveProgramCapMetrics,
} from "./livePortfolioViewModel";

describe("livePortfolioViewModel", () => {
  it("maps broker positions from the canary snapshot", () => {
    const snapshot = canarySnapshot({
      live_positions: [
        { instrument_id: "AAPL", quantity: 5, side: "LONG" },
        { symbol: "NVDA", quantity: -2, side: "SHORT" },
      ],
    });

    expect(livePortfolioPositions(snapshot)).toEqual([
      { id: "AAPL-0", symbol: "AAPL", quantity: "5", detail: "LONG" },
      { id: "NVDA-1", symbol: "NVDA", quantity: "-2", detail: "SHORT" },
    ]);
  });

  it("maps open broker orders from the canary snapshot", () => {
    const snapshot = canarySnapshot({
      open_broker_orders: [{ order_id: "ord-1", side: "BUY", quantity: 1 }],
    });

    expect(livePortfolioOrders(snapshot)).toEqual([
      { id: "order-0", orderId: "ord-1", detail: "BUY · 1" },
    ]);
  });

  it("reports program cap usage and remaining values", () => {
    const snapshot = canarySnapshot({
      program_cap_usage: { sessions_completed: 1, orders_submitted: 2, notional_minor: 3000 },
      program_cap_remaining: { sessions: 4, orders: 8, notional_minor: 97000 },
    });

    expect(liveProgramCapMetrics(snapshot)).toEqual(
      expect.arrayContaining([
        { id: "sessions-used", label: "Sessions completed", value: "1" },
        { id: "orders-remaining", label: "Orders remaining", value: "8" },
      ]),
    );
  });
});

import { describe, expect, it } from "vitest";
import { paperPortfolio } from "../paper-now/paperNowTestFixtures";
import {
  buildPortfolioAttention,
  buildPortfolioPositions,
  buildPortfolioSummaryMetrics,
  classifySignedDisplay,
  marksDecay,
  paperCapitalHonesty,
  positionNeedsAttention,
} from "./paperPortfolioPresentation";

describe("paperPortfolioPresentation", () => {
  it("classifies signed P&L with non-color spoken labels", () => {
    expect(classifySignedDisplay("25.00")).toEqual({
      text: "25.00",
      direction: "gain",
      spoken: "gain 25.00",
    });
    expect(classifySignedDisplay("-4.50")).toMatchObject({ direction: "loss", spoken: "loss -4.50" });
    expect(classifySignedDisplay("0.00")).toMatchObject({ direction: "flat" });
    expect(classifySignedDisplay(undefined).direction).toBe("unavailable");
  });

  it("formats buying power from minor units and never substitutes cash", () => {
    const metrics = buildPortfolioSummaryMetrics(
      paperPortfolio({ account: { cash_display: "1000.00", buying_power_minor: 250000 } }),
    );
    expect(metrics.find((row) => row.id === "cash")?.value).toBe("1000.00");
    expect(metrics.find((row) => row.id === "buying-power")).toMatchObject({
      value: "$2,500.00",
      available: true,
    });
  });

  it("does not invent unrealized P&L when the contract omits it", () => {
    const data = paperPortfolio({ pnl: { realized_display: "1.00" } });
    const unrealized = buildPortfolioSummaryMetrics(data).find((row) => row.id === "unrealized");
    expect(unrealized?.available).toBe(false);
    expect(unrealized?.value).toBe("Unavailable");
  });

  it("labels Paper vs Demo capital as simulated", () => {
    expect(paperCapitalHonesty("PAPER").sentence).toMatch(/Paper simulation/i);
    expect(paperCapitalHonesty("DEMO").sentence).toMatch(/Demo account/i);
    expect(paperCapitalHonesty("PAPER").sentence).not.toMatch(/live capital is/i);
  });

  it("maps contract exceptions only — no synthetic alerts", () => {
    const healthy = buildPortfolioAttention(paperPortfolio({ positions: [] }));
    expect(healthy).toEqual([]);
    const items = buildPortfolioAttention(
      paperPortfolio({
        risk: {
          kill_switch_active: true,
          open_order_count: 0,
          reconciliation_status: "INTERNAL_AUTHORITATIVE",
          limits: { max_open_orders: 5, max_order_shares: 100, max_position_shares: 500 },
        },
      }),
    );
    expect(items.map((row) => row.code)).toContain("KILL_SWITCH_ACTIVE");
    expect(items[0]?.tone).toBe("critical");
  });

  it("hands positions to Workspace by instrument_id and flags stale marks", () => {
    const rows = buildPortfolioPositions(paperPortfolio());
    const biya = rows.find((row) => row.symbol === "BIYA");
    const nvda = rows.find((row) => row.symbol === "NVDA");
    expect(biya?.workspaceHref).toBe("/workspace/BIYA");
    expect(positionNeedsAttention(biya!)).toBe(false);
    expect(positionNeedsAttention(nvda!)).toBe(true);
  });

  it("treats fixture replay marks as non-decaying", () => {
    expect(marksDecay("FIXTURE_REPLAY")).toBe(false);
    expect(marksDecay("LIVE_OBSERVATIONAL")).toBe(true);
  });
});

import { describe, expect, it } from "vitest";
import { attentionItem, paperPortfolio } from "./paperNowTestFixtures";
import {
  derivePaperExceptions, formatMinorCurrency, nextPaperCandidateId,
  paperRiskMetrics, sortPaperCandidates,
} from "./paperDashboardViewModel";

describe("Paper dashboard view model", () => {
  it("sorts candidates without mutating the API array and keeps instrument-less items visible", () => {
    const items = [attentionItem({ attention_id: "late", priority_rank: 8 }), attentionItem({ attention_id: "none", priority_rank: 1, instrument_id: undefined }), attentionItem({ attention_id: "top", priority_rank: 2 })];
    expect(sortPaperCandidates(items).map((item) => item.attention_id)).toEqual(["none", "top", "late"]);
    expect(items.map((item) => item.attention_id)).toEqual(["late", "none", "top"]);
    expect(nextPaperCandidateId(items, null)).toBe("top");
    expect(nextPaperCandidateId(items, "late")).toBe("late");
    expect(nextPaperCandidateId(items.filter((item) => item.attention_id !== "late"), "late")).toBe("top");
  });

  it("formats buying power from minor units and never substitutes cash", () => {
    expect(formatMinorCurrency(250000, "USD")).toBe("$2,500.00");
    expect(formatMinorCurrency(Number.NaN, "USD")).toBeNull();
    expect(formatMinorCurrency(100, "NOT_A_CURRENCY")).toBeNull();
  });

  it("keeps raw limit values while clamping only visual utilization", () => {
    const metrics = paperRiskMetrics(paperPortfolio({ positions: [{ instrument_id: "BIYA", symbol: "BIYA", quantity: 700, side: "LONG", mark_quality: "CURRENT" }] }));
    expect(metrics.find((metric) => metric.id === "largest-position")).toMatchObject({ value: "700 / 500 sh", percent: 100 });
    expect(metrics.find((metric) => metric.id === "open-orders")).toMatchObject({ value: "2 / 5", percent: 40 });
  });

  it("shows unavailable utilization for zero or invalid denominators", () => {
    const payload = paperPortfolio();
    payload.risk.limits.max_position_shares = 0;
    payload.risk.limits.max_open_orders = Number.NaN;
    const metrics = paperRiskMetrics(payload);
    expect(metrics.find((metric) => metric.id === "largest-position")?.available).toBe(false);
    expect(metrics.find((metric) => metric.id === "open-orders")?.available).toBe(false);
  });

  it("orders explicit exceptions, caps at five, and does not guess unknown records", () => {
    const payload = paperPortfolio({
      orders: [{ state: "REJECTED", order_id: "o-1" }, { status: "WAITING_FOR_DATA", order_id: "o-2" }, { mystery: true }],
      risk: { kill_switch_active: true, open_order_count: 2, reconciliation_status: "DRIFT", limits: { max_open_orders: 5, max_order_shares: 100, max_position_shares: 500 }, last_decision: { risk_status: "BLOCKED", reason_code: "POSITION_LIMIT" } },
      data_health: { state: "UNAVAILABLE", detail: "feed offline" },
      reconciliation_status: "DRIFT",
    });
    const exceptions = derivePaperExceptions(payload);
    expect(exceptions).toHaveLength(5);
    expect(exceptions[0].code).toBe("KILL_SWITCH_ACTIVE");
    expect(exceptions.map((item) => item.message).join(" ")).not.toContain("mystery");
  });

  it("returns no exceptions for explicitly healthy states", () => {
    expect(derivePaperExceptions(paperPortfolio({ positions: [] }))).toEqual([]);
  });
});

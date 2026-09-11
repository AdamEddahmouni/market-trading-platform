import { describe, expect, it } from "vitest";
import { buildForwardTestPanelModel, formatForwardTestState } from "./buildForwardTestPanelModel";

describe("buildForwardTestPanelModel", () => {
  it("summarizes pending and evaluated counts", () => {
    const model = buildForwardTestPanelModel([
      {
        forward_test_id: "ftd-1",
        session_id: "fts-1",
        account_id: "paper-a",
        mode: "PAPER",
        run_kind: "FORWARD_TEST",
        test_mode: "SIGNAL_ONLY",
        symbol: "ACME",
        decision_time_ns: 1,
        source_time_ns: 1,
        state: "OBSERVING",
        direction: "BUY",
        quantity: null,
        strategy_id: "s1",
        strategy_version: "1.0.0",
        evaluation_horizon_ns: 100,
        paper_order_id: null,
        evaluation_state: "OBSERVING",
      },
      {
        forward_test_id: "ftd-2",
        session_id: "fts-1",
        account_id: "paper-a",
        mode: "PAPER",
        run_kind: "FORWARD_TEST",
        test_mode: "SIGNAL_ONLY",
        symbol: "ACME",
        decision_time_ns: 2,
        source_time_ns: 2,
        state: "EVALUATED",
        direction: "SELL",
        quantity: null,
        strategy_id: "s1",
        strategy_version: "1.0.0",
        evaluation_horizon_ns: 100,
        paper_order_id: null,
        evaluation_state: "EVALUATED",
        signal_outcome: { directional_correct: true, percentage_return: 0.01, quality: "COMPLETE" },
      },
    ]);
    expect(model.pendingCount).toBe(1);
    expect(model.evaluatedCount).toBe(1);
    expect(model.modeLabel).toBe("PAPER");
    expect(model.label).toBe("Forward Test");
  });

  it("labels evaluated and rejected states", () => {
    expect(formatForwardTestState("EVALUATED")).toBe("Evaluated");
    expect(formatForwardTestState("REJECTED")).toBe("Rejected");
    expect(formatForwardTestState("OBSERVING")).toBe("Pending");
  });
});

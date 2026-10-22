import { describe, expect, it } from "vitest";
import {
  boundaryModel,
  decisionSourceLabel,
  formatMoney,
  formatReturn,
  formatSignedMoney,
  markAge,
} from "./paperExperimentPresentation";

describe("paperExperimentPresentation", () => {
  it("renders a missing value as Unavailable, never as zero", () => {
    expect(formatMoney(null, "USD")).toBe("Unavailable");
    expect(formatMoney(undefined, "USD")).toBe("Unavailable");
    expect(formatMoney(0, "USD")).toBe("$0.00");
    expect(formatSignedMoney(null, "USD")).toEqual({ text: "Unavailable", direction: "unavailable", label: "unavailable" });
    expect(formatReturn(null)).toBe("Unavailable");
    expect(markAge(null, 0)).toBe("Unavailable");
  });

  it("puts the sign in the text and the accessible label", () => {
    expect(formatSignedMoney(40_000, "USD")).toEqual({ text: "+$400.00", direction: "gain", label: "gain of $400.00" });
    expect(formatSignedMoney(-1_250, "USD")).toEqual({ text: "−$12.50", direction: "loss", label: "loss of $12.50" });
    expect(formatSignedMoney(0, "USD").direction).toBe("flat");
    expect(formatReturn(40)).toBe("+0.40%");
    expect(formatReturn(-125)).toBe("−1.25%");
    expect(formatReturn(0)).toBe("0.00%");
  });

  it("never describes simulated execution as live", () => {
    for (const mode of ["INTERNAL_SIMULATION", "BROKER_PAPER", "SOMETHING_NEW"]) {
      const model = boundaryModel({
        capital: { kind: "SIMULATED", live_capital: false },
        execution: { mode, provider: "INTERNAL", execution_authority: "PAPER_ONLY", fill_kind: "SIMULATED_FILL" },
        market_data: { mode: "LIVE_OBSERVATIONAL", provider: "MOOMOO", running_mode: "LIVE_OBSERVATIONAL", state: "AVAILABLE" },
      });
      expect(model.executionLine).not.toMatch(/live/i);
      expect(model.executionLine).toMatch(/simulat|paper/i);
      expect(model.capitalLine).toBe("Live capital: No. All capital is simulated.");
    }
  });

  it("labels decision sources", () => {
    expect(decisionSourceLabel("AI_DECISION_GOVERNED")).toBe("Governed AI decision");
    expect(decisionSourceLabel("MANUAL_TEST")).toBe("Operator ticket (no governed decision)");
  });
});

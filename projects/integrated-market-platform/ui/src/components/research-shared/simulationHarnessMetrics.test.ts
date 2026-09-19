import { describe, expect, it } from "vitest";
import { extractSimulationHarnessMetrics } from "./simulationHarnessMetrics";

describe("simulationHarnessMetrics", () => {
  it("reads optional drawdown when present without inventing defaults", () => {
    const metrics = extractSimulationHarnessMetrics({
      authority_boundary: "READ_ONLY_SIMULATION",
      mode_label: "SIMULATION",
      ledger_summary: { entry_count: 1, max_drawdown: 120 },
      risk_decisions: [],
      fills: [],
      orders: [],
      intents: [],
      attributions: [],
      reconciliation: {},
    });
    const drawdown = metrics.find((row) => row.id === "drawdown");
    expect(drawdown?.value).toBe("120");
    expect(drawdown?.evidenceClass).toBe("simulation");
  });

  it("reports unavailable drawdown when contract omits the field", () => {
    const metrics = extractSimulationHarnessMetrics({
      authority_boundary: "READ_ONLY_SIMULATION",
      mode_label: "SIMULATION",
      ledger_summary: { entry_count: 0 },
      risk_decisions: [],
      fills: [],
      orders: [],
      intents: [],
      attributions: [],
      reconciliation: {},
      fill_audit: { status: "PASS" },
    });
    expect(metrics.find((row) => row.id === "drawdown")?.value).toBe("UNAVAILABLE");
    expect(metrics.find((row) => row.id === "fill-realism")?.value).toBe("UNAVAILABLE");
    expect(metrics.find((row) => row.id === "fill-audit-status")?.value).toBe("PASS");
    expect(metrics.find((row) => row.id === "slippage")?.value).toBe("UNAVAILABLE");
  });
});

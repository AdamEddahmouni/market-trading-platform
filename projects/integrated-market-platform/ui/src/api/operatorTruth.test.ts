import { describe, expect, it } from "vitest";
import { operatorTruthById, operatorTruthSection } from "./operatorTruth";
import type { OperatorDiagnostics } from "./schemas";

describe("operatorTruth helpers", () => {
  const diagnostics = {
    schema_version: "operator-diagnostics/1.1.0",
    severity: "OK",
    operator_truth: {
      schema_version: "operator-truth/1.0.0",
      rows: [{ id: "item9-corpus", truth: "IDLE" as const, detail: "2/3" }],
      by_id: { "item9-corpus": "IDLE" as const },
    },
    sections: {},
  } satisfies OperatorDiagnostics;

  it("reads backend by_id without remapping 2/3 to DEGRADED", () => {
    expect(operatorTruthSection(diagnostics)?.by_id["item9-corpus"]).toBe("IDLE");
    expect(operatorTruthById(diagnostics, "item9-corpus")).toBe("IDLE");
    expect(operatorTruthById(diagnostics, "item9-corpus")).not.toBe("DEGRADED");
  });
});

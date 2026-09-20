import { describe, expect, it } from "vitest";
import type { OperatorDiagnostics } from "../../api/schemas";
import { operatorTruthById, operatorTruthSection } from "../../api/operatorTruth";
import { preferItem9OperatorTruth } from "./consumeOperatorTruth";

const BASE: OperatorDiagnostics = {
  schema_version: "operator-diagnostics/1.0.0",
  severity: "OK",
  sections: {},
};

describe("consumeOperatorTruth", () => {
  it("returns undefined when operator_truth is absent", () => {
    expect(operatorTruthSection(BASE)).toBeUndefined();
    expect(operatorTruthById(BASE, "item9-corpus")).toBeUndefined();
    expect(preferItem9OperatorTruth(BASE, "item9-corpus", "IDLE")).toBe("IDLE");
  });

  it("reads top-level operator_truth.by_id including Item 9 2/3 IDLE", () => {
    const diagnostics: OperatorDiagnostics = {
      ...BASE,
      operator_truth: {
        schema_version: "operator-truth/1.0.0",
        by_id: { "item9-corpus": "IDLE", "live-execution": "BLOCKED" },
      },
    };
    expect(operatorTruthSection(diagnostics)?.by_id?.["item9-corpus"]).toBe("IDLE");
    expect(operatorTruthById(diagnostics, "item9-corpus")).toBe("IDLE");
    expect(operatorTruthById(diagnostics, "item9-corpus")).not.toBe("DEGRADED");
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "UNKNOWN")).toBe("IDLE");
  });

  it("reads nested sections.operator_truth when the top-level field is missing", () => {
    const diagnostics: OperatorDiagnostics = {
      ...BASE,
      sections: {
        operator_truth: { by_id: { "item9-preflight": "IDLE" } },
      },
    };
    expect(operatorTruthById(diagnostics, "item9-preflight")).toBe("IDLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-preflight", "DEGRADED")).toBe("IDLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-preflight", "BLOCKED")).toBe("BLOCKED");
  });

  it("does not let backend DEGRADED override local calendar IDLE", () => {
    const diagnostics: OperatorDiagnostics = {
      ...BASE,
      operator_truth: { by_id: { "item9-corpus": "DEGRADED" } },
    };
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "IDLE")).toBe("IDLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "IDLE")).not.toBe("DEGRADED");
  });

  it("prefers backend UNAVAILABLE over local guesses instead of minting 2/3 IDLE", () => {
    const diagnostics: OperatorDiagnostics = {
      ...BASE,
      operator_truth: { by_id: { "item9-corpus": "UNAVAILABLE" } },
    };
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "UNKNOWN")).toBe("UNAVAILABLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "DEGRADED")).toBe("UNAVAILABLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "NOT_OBSERVED")).toBe("UNAVAILABLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "UNKNOWN")).not.toBe("IDLE");
    expect(preferItem9OperatorTruth(diagnostics, "item9-corpus", "IDLE")).toBe("IDLE");
  });
});

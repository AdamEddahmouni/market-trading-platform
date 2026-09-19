import { describe, expect, it } from "vitest";
import { WorkspaceSqueezeResponseSchema } from "./api/schemas";

describe("WorkspaceSqueezeResponseSchema", () => {
  it("parses squeeze workspace depth fields", () => {
    const parsed = WorkspaceSqueezeResponseSchema.parse({
      symbol: "AVTX",
      source: "short-squeeze-project",
      bridge_mode: "READ_ONLY",
      available: true,
      replay_chart_available: false,
      ignition_state: "WATCH",
      freshness: "FROZEN",
      rules: [{ rule_id: "R1", category: "SHORT_PRESSURE_CONFIRMATION", outcome: "FAIL", reason: "x" }],
      state_machine: {
        current_state: "WATCH",
        last_transition_label: "frozen",
        changed_criteria: [{ rule_id: "R1", category: "SHORT_PRESSURE_CONFIRMATION", outcome: "FAIL", reason: "x" }],
        unchanged_criteria: [],
      },
      readiness: {
        freshness_state: "FROZEN",
        provenance_admissible: true,
        rule_outcome_totals: { FAIL: 1, PASS: 0, UNKNOWN: 0, INCOMPLETE: 0 },
      },
    });
    expect(parsed.state_machine?.current_state).toBe("WATCH");
    expect(parsed.readiness?.provenance_admissible).toBe(true);
  });

  it("parses cross_lane_evidence with provenance fields", () => {
    const parsed = WorkspaceSqueezeResponseSchema.parse({
      symbol: "NVDA",
      source: "short-squeeze-project",
      bridge_mode: "READ_ONLY",
      available: true,
      replay_chart_available: false,
      cross_lane_evidence: [
        {
          lane: "options",
          signal: "CALL_DEMAND_ANOMALY",
          strength: "MODERATE",
          available: true,
          source_ref: "whale:options",
          detail: "elevated unusual activity",
          provenance_class: "DERIVED",
          quality_flags: ["FLOW_DIRECTION_UNCERTAIN"],
        },
      ],
    });
    expect(parsed.cross_lane_evidence?.[0]?.provenance_class).toBe("DERIVED");
  });

  it("retains inference_kind and observed_at_presence instead of stripping them", () => {
    const parsed = WorkspaceSqueezeResponseSchema.parse({
      symbol: "NVDA",
      source: "short-squeeze-project",
      bridge_mode: "READ_ONLY",
      available: true,
      replay_chart_available: false,
      cross_lane_evidence: [
        {
          lane: "market_context",
          signal: "SYNTHESIS_CONTRADICTION_DETECTED",
          strength: "HIGH",
          available: true,
          source_ref: "mc-synth",
          detail: "narrative contradiction",
          observed_at: "2026-07-15T14:45:00.000000000Z",
          provenance_class: "MODEL_OUTPUT",
          inference_kind: "MODEL_INFERENCE",
          observed_at_presence: "PRESENT",
        },
        {
          lane: "order_flow",
          signal: "AGGRESSIVE_BUY_PRESSURE",
          strength: "HIGH",
          available: true,
          source_ref: "tape",
          detail: "aggressive buy",
          observed_at: "",
          provenance_class: "RAW",
          inference_kind: "OBSERVED",
          observed_at_presence: "EMPTY",
        },
      ],
    });
    expect(parsed.cross_lane_evidence?.[0]?.inference_kind).toBe("MODEL_INFERENCE");
    expect(parsed.cross_lane_evidence?.[0]?.observed_at_presence).toBe("PRESENT");
    expect(parsed.cross_lane_evidence?.[0]?.inference_kind).not.toBe("OBSERVED");
    expect(parsed.cross_lane_evidence?.[1]?.inference_kind).toBe("OBSERVED");
    expect(parsed.cross_lane_evidence?.[1]?.observed_at_presence).toBe("EMPTY");
  });
});

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
});

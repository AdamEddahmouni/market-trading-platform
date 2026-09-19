import { describe, expect, it } from "vitest";
import { buildGovernanceFacts } from "./governanceStatusPresentation";

describe("governanceStatusPresentation", () => {
  it("never claims Item 9 calibrated without capability state", () => {
    const facts = buildGovernanceFacts({
      asOf: {
        mode: "PAPER",
        as_of_time: "2026-01-01T00:00:00Z",
        timezone: "UTC",
        execution_authority: "PAPER_ONLY",
        execution_mode: "INTERNAL_SIMULATION",
      },
    });
    const item9 = facts.find((row) => row.id === "item9-calibration");
    expect(item9?.value).toMatch(/NOT CALIBRATED/i);
    expect(item9?.value).not.toMatch(/3\/3/);
  });

  it("reads Item 9 corpus gate from diagnostics when provided", () => {
    const facts = buildGovernanceFacts({
      diagnostics: {
        schema_version: "operator-diagnostics/1.0.0",
        severity: "DEGRADED",
        sections: {
          runtime: {
            git_sha: "abc",
            item9_corpus_status: {
              availability: "AVAILABLE",
              report: {
                calibration_state: "NOT_CALIBRATED",
                fitting_allowed: false,
                sample_gate_progress: { distinct_rth_dates: "2/3" },
              },
            },
            runtime_resilience: { collector_process: { active_collector_detected: false } },
          },
          governance: { live_execution_env: false },
        },
      },
    });
    expect(facts.find((row) => row.id === "item9-rth-dates")?.value).toBe("2/3");
    expect(facts.find((row) => row.id === "live-execution")?.value).toBe("Live OFF");
  });
});

import { describe, expect, it } from "vitest";
import type { WorkspaceEvidenceResponse } from "../../api/schemas";
import { buildPaperDecisionSnapshot } from "./buildPaperDecisionSnapshot";

const evidence = (lanes: WorkspaceEvidenceResponse["lanes"]): WorkspaceEvidenceResponse => ({
  instrument: "BIYA",
  as_of_context: {
    mode: "REPLAY",
    data_mode: "FIXTURE_REPLAY",
    execution_mode: "INTERNAL_SIMULATION",
    execution_authority: "PAPER_ONLY",
    as_of_time: "2026-08-31T12:00:00Z",
    timezone: "America/New_York",
  },
  lanes,
  what_matters_now: lanes,
  evidence_mix_summary: "MIXED",
  research_context_execution_authority: "RESEARCH_ONLY",
});

const lane = (
  laneName: string,
  direction: string | null,
  summary: string,
): WorkspaceEvidenceResponse["lanes"][number] => ({
  instrument: "BIYA",
  lane: laneName,
  evidence_type: "TEST",
  quality: "PASS",
  relevance: "HIGH",
  direction,
  summary,
  freshness_label: "CURRENT",
});

describe("buildPaperDecisionSnapshot", () => {
  it("classifies supports, contradicts, unclear, and gaps", () => {
    const snapshot = buildPaperDecisionSnapshot(
      evidence([
        lane("SHORT_SQUEEZE", "POSITIVE", "Ignition supportive"),
        lane("ORDER_FLOW", "NEGATIVE", "Flow contradicts"),
        lane("CATALYST", "NEUTRAL", "Headline present"),
      ]),
      "ready",
      "squeeze",
    );
    expect(snapshot.supports).toHaveLength(1);
    expect(snapshot.contradicts).toHaveLength(1);
    expect(snapshot.unclear).toHaveLength(1);
    expect(snapshot.dataGaps.length).toBeGreaterThan(0);
    expect(snapshot.overallInsufficient).toBe(false);
    expect(snapshot.supports[0]?.text).toMatch(/Primary handoff evidence/i);
  });

  it("reports insufficient overall evidence when no directional lanes exist", () => {
    const snapshot = buildPaperDecisionSnapshot(
      evidence([lane("OPTIONS", "UNKNOWN", "Activity present")]),
      "ready",
      null,
    );
    expect(snapshot.overallInsufficient).toBe(true);
  });

  it("handles loading and error phases", () => {
    expect(buildPaperDecisionSnapshot(undefined, "loading", null).phase).toBe("loading");
    expect(buildPaperDecisionSnapshot(undefined, "error", null, "offline").phaseMessage).toBe("offline");
  });
});

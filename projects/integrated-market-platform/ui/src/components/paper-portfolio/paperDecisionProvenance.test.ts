import { describe, expect, it } from "vitest";
import { LANE_MODULE_IDS } from "../paper-now/paperOrderDraft";
import { parsePersistedPaperDecisionProvenance } from "./paperDecisionProvenance";

describe("parsePersistedPaperDecisionProvenance", () => {
  it("classifies all known lane correlations", () => {
    for (const laneId of LANE_MODULE_IDS) {
      const provenance = parsePersistedPaperDecisionProvenance(`lane:${laneId}`, "client-1");
      expect(provenance.sourceCategory).toBe("WORKSPACE_LANE");
      expect(provenance.laneId).toBe(laneId);
      expect(provenance.isDecisionProvenance).toBe(true);
    }
  });

  it("classifies attention direct id format", () => {
    const provenance = parsePersistedPaperDecisionProvenance("ATT-123", "client-1");
    expect(provenance.sourceCategory).toBe("PAPER_COMMAND");
    expect(provenance.attentionId).toBe("ATT-123");
    expect(provenance.badgeLabel).toBe("PAPER COMMAND");
  });

  it("classifies attention: prefix format", () => {
    const provenance = parsePersistedPaperDecisionProvenance("attention:ATT-123", "client-1");
    expect(provenance.sourceCategory).toBe("PAPER_COMMAND");
    expect(provenance.attentionId).toBe("ATT-123");
  });

  it("treats default client-order correlation as manual", () => {
    const provenance = parsePersistedPaperDecisionProvenance("client-abc", "client-abc");
    expect(provenance.sourceCategory).toBe("MANUAL");
    expect(provenance.badgeLabel).toBe("MANUAL");
    expect(provenance.isDecisionProvenance).toBe(false);
  });

  it("treats missing correlation as manual", () => {
    const provenance = parsePersistedPaperDecisionProvenance(undefined, "client-abc");
    expect(provenance.sourceCategory).toBe("MANUAL");
  });

  it("degrades malformed lane correlation safely", () => {
    const provenance = parsePersistedPaperDecisionProvenance("lane:", "client-1");
    expect(provenance.sourceCategory).toBe("UNKNOWN");
    expect(provenance.type).toBe("UNKNOWN");
  });

  it("degrades malformed attention correlation safely", () => {
    const provenance = parsePersistedPaperDecisionProvenance("attention:", "client-1");
    expect(provenance.sourceCategory).toBe("UNKNOWN");
  });

  it("does not label arbitrary correlation as Paper Command", () => {
    const provenance = parsePersistedPaperDecisionProvenance("corr-p3-trace", "client-1");
    expect(provenance.sourceCategory).toBe("UNKNOWN");
    expect(provenance.isDecisionProvenance).toBe(false);
  });

  it("degrades unsupported prefix safely", () => {
    const provenance = parsePersistedPaperDecisionProvenance("research:CAND-123", "client-1");
    expect(provenance.sourceCategory).toBe("UNKNOWN");
  });

  it("accepts attention-biya style ids from Paper Command", () => {
    const provenance = parsePersistedPaperDecisionProvenance("attention-biya", "client-1");
    expect(provenance.sourceCategory).toBe("PAPER_COMMAND");
  });

  it("surfaces persisted attention snapshot in operational provenance", () => {
    const provenance = parsePersistedPaperDecisionProvenance(
      "attention-biya",
      "client-1",
      "BIYA",
      {
        source_type: "paper_command_attention",
        source_id: "attention-biya",
        headline: "Short interest elevated into catalyst window",
        tier: 1,
        reasons: [{ code: "SI", label: "Short interest elevated" }],
      },
    );
    expect(provenance.persistedSourceContext.snapshotAvailable).toBe(true);
    expect(provenance.persistedSourceContext.headline).toBe(
      "Short interest elevated into catalyst window",
    );
    expect(provenance.tableSourceSummary).toBe("Short interest elevated into catalyst window");
  });

  it("hides mismatched snapshot from persisted context", () => {
    const provenance = parsePersistedPaperDecisionProvenance(
      "lane:squeeze",
      "client-1",
      "BIYA",
      {
        source_type: "paper_command_attention",
        source_id: "ATT-1",
        headline: "Should not show",
      },
    );
    expect(provenance.persistedSourceContext.snapshotMismatch).toBe(true);
    expect(provenance.persistedSourceContext.snapshotAvailable).toBe(false);
  });
});

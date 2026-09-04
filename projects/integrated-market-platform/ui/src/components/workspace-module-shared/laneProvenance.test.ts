import { describe, expect, it } from "vitest";
import {
  extractLaneProvenance,
  extractLaneProvenanceFallback,
  isLaneDataStale,
  laneProvenanceSummary,
} from "./laneProvenance";

describe("laneProvenance", () => {
  it("extracts server-attached lane provenance", () => {
    const data = {
      lane_provenance: {
        lane_id: "squeeze",
        source_kind: "lane_payload",
        source_time: 1_700_000_000_000_000_000,
        retrieved_at: 1_700_000_300_000_000_000,
      },
    };
    expect(extractLaneProvenance(data)?.source_time).toBe(1_700_000_000_000_000_000);
  });

  it("falls back to as_of_context without fabricating handoff time", () => {
    const data = {
      as_of_context: { as_of_time: "2024-01-15T14:30:00.000000000Z" },
    };
    const provenance = extractLaneProvenanceFallback(data, "order-flow");
    expect(provenance?.source_kind).toBe("context_as_of");
    expect(provenance?.source_time).toBeGreaterThan(0);
  });

  it("marks stale when source is older than retrieval threshold", () => {
    const provenance = {
      lane_id: "squeeze",
      source_kind: "lane_payload" as const,
      source_time: 1_000_000_000_000_000_000,
      retrieved_at: 1_700_000_000_000_000_000,
    };
    expect(isLaneDataStale(provenance)).toBe(true);
    expect(laneProvenanceSummary(provenance)).toContain("may be stale");
  });

  it("returns unavailable message when source time is unknown", () => {
    const provenance = {
      lane_id: "catalyst",
      source_kind: "unknown" as const,
      retrieved_at: 1_700_000_000_000_000_000,
    };
    expect(laneProvenanceSummary(provenance)).toContain("unavailable");
  });
});

import { describe, expect, it } from "vitest";
import { mapWorkspaceBarsToImpRecords } from "./workspaceImpBarFeed";

const canonicalRow = {
  time: "2024-01-02T15:05:00.000000000Z",
  open: "100",
  high: "101",
  low: "99",
  close: "100.5",
  volume: 1200,
  epistemic_class: "OBSERVED",
  bar_id: "bar-1",
  source_time_ns: 1_704_207_600_000_000_000,
  available_time_ns: 1_704_207_660_000_000_000,
  provenance: {
    event_type: "BAR_OHLCV_1M" as const,
    normalized_event_id: "bar-1",
  },
};

describe("workspaceImpBarFeed", () => {
  it("maps canonical BAR_OHLCV_1M rows to ImpBarRecord", () => {
    const mapped = mapWorkspaceBarsToImpRecords("IMP:ADMITTED:ES", [canonicalRow]);
    expect(mapped).toHaveLength(1);
    expect(mapped?.[0].bar_id).toBe("bar-1");
    expect(mapped?.[0].timeframe).toBe("1m");
    expect(mapped?.[0].provenance.event_type).toBe("BAR_OHLCV_1M");
  });

  it("returns null when canonical identity is missing", () => {
    const legacy = { ...canonicalRow, bar_id: undefined };
    expect(mapWorkspaceBarsToImpRecords("IMP:ADMITTED:ES", [legacy])).toBeNull();
  });
});

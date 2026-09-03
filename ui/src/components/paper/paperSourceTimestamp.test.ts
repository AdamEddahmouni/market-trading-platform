import { describe, expect, it } from "vitest";
import { epochToMillis, formatPaperSourceTimeLabel, millisToEpochNs } from "./paperSourceTimestamp";

describe("paperSourceTimestamp", () => {
  it("converts epoch nanoseconds to milliseconds", () => {
    expect(epochToMillis(1_700_000_000_000_000_000)).toBe(1_700_000_000_000);
  });

  it("treats values below ns threshold as milliseconds", () => {
    expect(epochToMillis(1_700_000_000_000)).toBe(1_700_000_000_000);
  });

  it("converts millis to epoch ns", () => {
    expect(millisToEpochNs(1_700_000_000_000)).toBe(1_700_000_000_000_000_000);
  });

  it("formats a valid timestamp label", () => {
    const label = formatPaperSourceTimeLabel(1_700_000_000_000);
    expect(label).toBeTruthy();
    expect(label).toMatch(/2023/);
  });

  it("returns null for invalid values", () => {
    expect(formatPaperSourceTimeLabel(null)).toBeNull();
    expect(formatPaperSourceTimeLabel(0)).toBeNull();
    expect(formatPaperSourceTimeLabel(-1)).toBeNull();
    expect(formatPaperSourceTimeLabel(Number.NaN)).toBeNull();
  });
});

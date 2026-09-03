import { describe, expect, it } from "vitest";
import { handoffTimeFromNow, resolvePaperDecisionSourceTime } from "./resolvePaperDecisionSourceTime";

describe("resolvePaperDecisionSourceTime", () => {
  const canonicalNs = 1_787_000_000_000_000_000;
  const handoffNs = 1_787_100_000_000_000_000;

  it("prefers canonical source time over handoff time", () => {
    expect(
      resolvePaperDecisionSourceTime({
        canonicalSourceTime: canonicalNs,
        handoffTime: handoffNs,
      }),
    ).toBe(canonicalNs);
  });

  it("falls back to handoff time when canonical is absent", () => {
    expect(resolvePaperDecisionSourceTime({ handoffTime: handoffNs })).toBe(handoffNs);
  });

  it("returns undefined when both are missing", () => {
    expect(resolvePaperDecisionSourceTime({})).toBeUndefined();
  });

  it("rejects zero, negative, NaN, and Infinity", () => {
    expect(resolvePaperDecisionSourceTime({ canonicalSourceTime: 0 })).toBeUndefined();
    expect(resolvePaperDecisionSourceTime({ canonicalSourceTime: -1 })).toBeUndefined();
    expect(resolvePaperDecisionSourceTime({ canonicalSourceTime: Number.NaN })).toBeUndefined();
    expect(resolvePaperDecisionSourceTime({ canonicalSourceTime: Number.POSITIVE_INFINITY })).toBeUndefined();
  });

  it("accepts epoch milliseconds fixtures", () => {
    expect(resolvePaperDecisionSourceTime({ canonicalSourceTime: 1_700_000_000_000 })).toBe(1_700_000_000_000);
  });

  it("truncates fractional values", () => {
    expect(resolvePaperDecisionSourceTime({ canonicalSourceTime: 1_700_000_000_000.9 })).toBe(1_700_000_000_000);
  });

  it("builds handoff time from injectable clock", () => {
    expect(handoffTimeFromNow(() => 1_700_000_000_000)).toBe(1_700_000_000_000_000_000);
  });
});

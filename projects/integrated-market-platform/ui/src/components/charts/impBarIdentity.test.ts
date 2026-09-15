import { describe, expect, it } from "vitest";
import {
  assertMonotonicBarIdentity,
  type ImpBarRecord,
  impBarOpenMs,
  toVelaBarProjection,
} from "./impBarIdentity";

function bar(openMs: number, seed: number): ImpBarRecord {
  const barId = `IMP:ES:5m:${openMs}`;
  return {
    bar_id: barId,
    instrument_id: "IMP:ADMITTED:ES",
    timeframe: "5m",
    source_time_ns: openMs * 1_000_000,
    available_time_ns: (openMs + 300_000) * 1_000_000,
    ohlcv: {
      open: 100 + seed,
      high: 101 + seed,
      low: 99 + seed,
      close: 100.5 + seed,
      volume: 1000,
    },
    data_kind: "SYNTHETIC_GOVERNED",
    provenance: { event_type: "BAR_OHLCV_1M", normalized_event_id: barId },
  };
}

describe("impBarIdentity", () => {
  it("projects governed source_time_ns to Vela ms open", () => {
    const record = bar(1_700_000_000_000, 0);
    expect(impBarOpenMs(record)).toBe(1_700_000_000_000);
    expect(toVelaBarProjection(record).time).toBe(1_700_000_000_000);
  });

  it("assertMonotonicBarIdentity accepts strictly increasing bars", () => {
    expect(() =>
      assertMonotonicBarIdentity([bar(1000, 0), bar(2000, 1), bar(3000, 2)]),
    ).not.toThrow();
  });

  it("assertMonotonicBarIdentity rejects non-monotonic source_time_ns", () => {
    expect(() => assertMonotonicBarIdentity([bar(2000, 0), bar(2000, 1)])).toThrow(
      /non-monotonic source_time_ns/,
    );
  });

  it("assertMonotonicBarIdentity rejects duplicate bar_id", () => {
    const first = bar(1000, 0);
    const duplicate = { ...bar(2000, 1), bar_id: first.bar_id };
    expect(() => assertMonotonicBarIdentity([first, duplicate])).toThrow(/duplicate bar_id/);
  });
});

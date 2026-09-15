import { performance } from "node:perf_hooks";
import { describe, expect, it } from "vitest";
import { createGovernedFeed } from "./governedSyntheticFeed";
import { assertMonotonicBarIdentity, toVelaSeries } from "./impBarIdentity";
import { applyImpMarkers, sampleImpMarkers, type ImpChartMarker } from "./impSemanticAnnotations";
import { impBarSeriesFingerprint } from "./workspaceImpBarFeed";

function measureMs(fn: () => void): number {
  const start = performance.now();
  fn();
  return performance.now() - start;
}

function feedWithBars(count: number) {
  return createGovernedFeed("IMP:ADMITTED:ES", "5m", count).bars;
}

function denseMarkers(bars: ReturnType<typeof feedWithBars>, count: number): ImpChartMarker[] {
  const markers: ImpChartMarker[] = [];
  const step = Math.max(1, Math.floor(bars.length / count));
  for (let i = 0; i < bars.length && markers.length < count; i += step) {
    markers.push({
      marker_id: `dense-${i}`,
      kind: "opportunity",
      bar_id: bars[i].bar_id,
      label: `Opp ${i}`,
    });
  }
  return markers;
}

describe("Lane F Vela acceptance measurements (software fixture)", () => {
  it("records IMP projection throughput for large bar counts", () => {
    const counts = [10_000, 50_000, 100_000] as const;
    const rows: { bars: number; toVelaSeriesMs: number; fingerprintMs: number }[] = [];

    for (const count of counts) {
      const bars = feedWithBars(count);
      assertMonotonicBarIdentity(bars);
      const toVelaSeriesMs = measureMs(() => {
        const series = toVelaSeries(bars);
        expect(series.length).toBe(count);
      });
      const fingerprintMs = measureMs(() => {
        expect(impBarSeriesFingerprint(bars)).toMatch(/^\d+:/);
      });
      rows.push({ bars: count, toVelaSeriesMs, fingerprintMs });
    }

    // Emit once for Lane F evidence capture (vitest stdout).
    console.info("[lane-f-vela-perf] projection", JSON.stringify(rows));

    for (const row of rows) {
      expect(row.toVelaSeriesMs).toBeLessThan(500);
      expect(row.fingerprintMs).toBeLessThan(50);
    }
  });

  it("projects dense semantic markers without throwing (mock Vela host)", () => {
    const bars = feedWithBars(5_000);
    const markers = denseMarkers(bars, 250);
    const add = () => ({ id: `d-${Math.random()}` });
    const chart = {
      drawings: { supported: true, add, remove: () => undefined },
    };
    const ms = measureMs(() => {
      const ids = applyImpMarkers(chart, markers, bars);
      expect(ids.length).toBeGreaterThan(200);
    });
    console.info("[lane-f-vela-perf] dense-markers", { markers: markers.length, applyMs: ms });
    expect(ms).toBeLessThan(200);
  });

  it("sample workspace marker bundle covers annotation kinds used in lab", () => {
    const bars = feedWithBars(120);
    const kinds = new Set(sampleImpMarkers(bars).map((m) => m.kind));
    expect(kinds.has("opportunity")).toBe(true);
    expect(kinds.has("sec_public_record")).toBe(true);
    expect(kinds.has("paper")).toBe(true);
  });
});

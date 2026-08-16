import { describe, expect, it } from "vitest";
import { ResearchAnalyticsResponseSchema } from "./api/schemas";
import { countByLabel, hasChartData } from "./lib/chartTransforms";

describe("chartTransforms", () => {
  it("aggregates labels", () => {
    const series = countByLabel([
      { label: "1" },
      { label: "2" },
      { label: "1" },
    ]);
    expect(series).toEqual([
      { label: "1", count: 2 },
      { label: "2", count: 1 },
    ]);
  });

  it("detects empty chart data", () => {
    expect(hasChartData([{ label: "a", count: 0 }])).toBe(false);
    expect(hasChartData([{ label: "a", count: 2 }])).toBe(true);
  });
});

describe("ResearchAnalyticsResponseSchema", () => {
  it("parses research analytics payload", () => {
    const parsed = ResearchAnalyticsResponseSchema.parse({
      as_of_context: {
        mode: "REPLAY",
        as_of_time: "2026-01-01T00:00:00.000000000Z",
        timezone: "America/New_York",
      },
      authority_boundary: "READ_ONLY_RESEARCH_VISUALIZATION",
      disclaimer: "Research only",
      epistemic_class: "RESEARCH_PROJECTION",
      panels: {
        attention_tiers: {
          available: true,
          provenance: { source: "replay", method: "tier" },
          series: [{ label: "1", count: 2 }],
        },
        squeeze_outcomes: {
          available: false,
          provenance: { source: "donor" },
          series: [],
        },
        strategy_outcomes: {
          available: true,
          provenance: { source: "strategy" },
          series: [{ label: "signal", count: 1 }],
          signal_timeline: [
            { observation_index: 1, cumulative_signals: 1, outcome: "signal" },
          ],
        },
        risk_decisions: {
          available: true,
          provenance: { source: "risk" },
          series: [{ label: "APPROVE", count: 1 }],
        },
      },
    });
    expect(parsed.panels.strategy_outcomes.signal_timeline?.length).toBe(1);
  });
});

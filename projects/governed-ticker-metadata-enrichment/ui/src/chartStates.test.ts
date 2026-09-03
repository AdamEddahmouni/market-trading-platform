import { describe, expect, it, vi } from "vitest";
import { ResearchAnalyticsResponseSchema } from "./api/schemas";
import { hasChartData } from "./lib/chartTransforms";

describe("chart empty and error states", () => {
  it("detects empty chart series", () => {
    expect(hasChartData([])).toBe(false);
    expect(hasChartData([{ label: "tier-1", count: 0 }])).toBe(false);
    expect(hasChartData([{ label: "tier-1", count: 2 }])).toBe(true);
  });

  it("fetchJson surfaces HTTP failures", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);
    const { fetchJson } = await import("./api/fetchJson");
    await expect(fetchJson("/research/analytics", ResearchAnalyticsResponseSchema)).rejects.toThrow(
      "Request failed",
    );
    vi.unstubAllGlobals();
  });
});

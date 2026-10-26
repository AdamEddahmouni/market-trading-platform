import { afterEach, describe, expect, it, vi } from "vitest";
import { performanceApi } from "./paperPerformance";

afterEach(() => vi.unstubAllGlobals());
describe("Paper performance API", () => {
  it("enrolls only the selected experiment, with no trading command", async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      run_id: "PPR-x", experiment_id: "PPE-x", first_session: "2026-10-27",
      fixed_10: "2026-11-09", fixed_20: "2026-11-23",
    }) });
    vi.stubGlobal("fetch", fetcher);
    await performanceApi.enroll("PPE-x");
    expect(fetcher.mock.calls[0][0]).toBe("/evaluation/paper-performance/runs");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ experiment_id: "PPE-x" });
  });
  it("downloads the exact saved revision and handles failures", async () => {
    const blob = new Blob(["saved"]);
    const fetcher = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob });
    vi.stubGlobal("fetch", fetcher);
    expect(await performanceApi.download("PPR-x", "PPEVAL-old", "csv")).toBe(blob);
    expect(fetcher.mock.calls[0][0]).toBe("/evaluation/paper-performance/runs/PPR-x/export?format=csv&report_id=PPEVAL-old");
    fetcher.mockResolvedValue({ ok: false });
    await expect(performanceApi.download("PPR-x", "PPEVAL-old", "html")).rejects.toThrow("could not be downloaded");
  });
});

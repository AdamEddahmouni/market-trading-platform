import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAiScreenerPreview, postAiScreener } from "./screenerAi";

const scope = { universe: "US_EQUITIES" as const, search: "A", sort: "volume", descending: true,
  filters: [{ id: "rsi", field: "rsi_14", operator: "gt", value: 50 }], result_set: "set-1" };
const ai = { state: "AVAILABLE" as const, reason: null, provider_id: "inference.test", model_id: "candidate.v1",
  runtime: "LOCAL_MODEL" as const, engine: "local", engine_model: "candidate.v1", engines: [] };
const preview = { schema_version: "screener-ai-screener-preview/1.0.0" as const, ai, scope: { ...scope },
  matched_count: 42, intake_count: 20, max_intake: 20, estimate: null,
  evidence_summary: { sufficient: 3, blocked: 1, missing: 4, weak: 2 },
  decision_cutoff: "2026-10-02T15:00:00Z", result_set: "set-1" };

afterEach(() => vi.unstubAllGlobals());

describe("AI Screener API contract", () => {
  it("serializes the active scope for read-only preview", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(preview), { status: 200 })));
    await fetchAiScreenerPreview(scope);
    const url = String(vi.mocked(fetch).mock.calls[0][0]);
    expect(url).toContain("/screener/ai-screener/preview?");
    expect(url).toContain("universe=US_EQUITIES");
    expect(url).toContain("result_set=set-1");
    expect(url).toContain("filters=");
  });

  it("keeps model invocation behind the explicit POST contract", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...preview, schema_version: "screener-ai-screener/1.0.0", state: "NO_GROUNDED_CANDIDATES",
      scope: { ...scope }, run_id: "run-1", generated_at: "2026-10-02T15:00:00Z", valid_until: "2026-10-02T15:05:00Z", input_hash: "hash",
      provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL", prompt_id: "p", prompt_version: "1", prompt_hash: "ph",
      packet_bytes: 1, cache: "MISS", simulated: true, tokens_input: null, tokens_output: null, latency_ms: 1,
      evidence: [], candidates: [], limitations: ["Insufficient grounding."], coverage: {} }), { status: 200 })));
    const result = await postAiScreener(scope);
    expect(result.state).toBe("NO_GROUNDED_CANDIDATES");
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/screener/ai-screener");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toMatchObject({ universe: "US_EQUITIES", result_set: "set-1" });
  });

  it("rejects unsupported response versions before rendering", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...preview, schema_version: "screener-ai-screener-preview/2.0.0" }), { status: 200 })));
    await expect(fetchAiScreenerPreview(scope)).rejects.toThrow();
  });
});

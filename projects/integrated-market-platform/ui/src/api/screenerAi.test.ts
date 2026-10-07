import { afterEach, describe, expect, it, vi } from "vitest";
import { aiScopeKey, fetchAiScreenerPreview, fetchAiScreenerRun, fetchAiScreenerRuns, postAiScreener } from "./screenerAi";

const scope = { universe: "US_EQUITIES" as const, search: "A", sort: "volume", descending: true,
  filters: [{ id: "rsi", field: "rsi_14", operator: "gt", value: 50 }], result_set: "set-1" };
const ai = { state: "AVAILABLE" as const, reason: null, provider_id: "inference.test", model_id: "candidate.v1",
  runtime: "LOCAL_MODEL" as const, engine: "local", engine_model: "candidate.v1", engines: [] };
const preview = { schema_version: "screener-ai-screener-preview/1.0.0" as const, ai, scope: { ...scope },
  matched_count: 42, intake_count: 20, max_intake: 20, estimate: null,
  evidence_summary: { sufficient: 3, blocked: 1, missing: 4, weak: 2 },
  decision_cutoff: "2026-10-02T15:00:00Z", result_set: "set-1" };

const stored = { ...preview, schema_version: "screener-ai-screener/1.0.0", state: "NO_GROUNDED_CANDIDATES",
  scope: { ...scope }, run_id: "run-1", generated_at: "2026-10-02T15:00:00Z", valid_until: "2026-10-02T15:05:00Z", input_hash: "hash",
  provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL", prompt_id: "p", prompt_version: "1", prompt_hash: "ph",
  packet_bytes: 1, cache: "MISS", simulated: true, tokens_input: null, tokens_output: null, latency_ms: 1,
  evidence: [], candidates: [], limitations: ["Insufficient grounding."], coverage: {} };
const running = { schema_version: "screener-ai-screener-run/1.0.0", run_id: "track-1", account_id: "paper", state: "RUNNING", joined: false, scope: { ...scope },
  stage: "MODEL_CALL", stage_order: ["SCOPE", "NEWS", "EVIDENCE", "PACKET", "BUDGET_RESERVED", "MODEL_CALL", "VALIDATION", "STORED"],
  stages: [{ stage: "MODEL_CALL", started_at: "2026-10-02T15:00:01Z", elapsed_ms: 7000, detail: {} }], started_at: "2026-10-02T15:00:00Z", finished_at: null,
  elapsed_ms: 8000, engine: { provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL" }, timeout_seconds: 45,
  typical_latency_ms: null, typical_latency_samples: 0, intake_count: 20, sufficient_count: 3, packet_bytes: 95600, summary: null, result: null, error: null };

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

  it("keeps model invocation behind the explicit POST contract, which returns a run at once", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(running), { status: 200 })));
    const run = await postAiScreener(scope);
    expect(run.state).toBe("RUNNING");
    expect(run.result).toBeNull();
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/screener/ai-screener");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toMatchObject({ universe: "US_EQUITIES", result_set: "set-1" });
  });

  it("reads run status with GET and carries the stored result only when the run has finished", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => new Response(JSON.stringify(String(url).endsWith("/runs/active")
      ? { schema_version: "screener-ai-screener-runs/1.0.0", active: running, latest: null }
      : { ...running, state: "COMPLETED", stage: null, finished_at: "2026-10-02T15:00:12Z", result: stored,
          summary: { state: "NO_GROUNDED_CANDIDATES", reason: null, candidate_run_id: "run-1", selected: [], provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL", limitations: [] } }), { status: 200 })));
    expect((await fetchAiScreenerRuns()).active?.stage).toBe("MODEL_CALL");
    const done = await fetchAiScreenerRun("track 1");
    expect(done.result?.state).toBe("NO_GROUNDED_CANDIDATES");
    expect(vi.mocked(fetch).mock.calls.map(([url, init]) => [url, init?.method ?? "GET"])).toEqual([
      ["/screener/ai-screener/runs/active", "GET"], ["/screener/ai-screener/runs/track%201", "GET"]]);
  });

  it("rejects a run whose state this build does not know", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...running, state: "PAUSED" }), { status: 200 })));
    await expect(fetchAiScreenerRun("track-1")).rejects.toThrow();
  });

  it("identifies a run by its Screener query, not by the list snapshot or key order", () => {
    const filters = [{ operator: "gt", value: 50, field: "rsi_14", id: "rsi" }];
    expect(aiScopeKey({ ...scope, result_set: "set-2", filters } as never)).toBe(aiScopeKey({ ...scope, view: "Overview", screen: "" }));
    expect(aiScopeKey({ ...scope, search: "B" })).not.toBe(aiScopeKey(scope));
    expect(aiScopeKey({ ...scope, screen: "saved-1" } as never)).not.toBe(aiScopeKey(scope));
  });

  it("rejects unsupported response versions before rendering", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...preview, schema_version: "screener-ai-screener-preview/2.0.0" }), { status: 200 })));
    await expect(fetchAiScreenerPreview(scope)).rejects.toThrow();
  });
});

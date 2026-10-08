import { afterEach, describe, expect, it, vi } from "vitest";
import { aiScopeKey, fetchAiScreenerCoverage, fetchAiScreenerPreview, fetchAiScreenerRun, fetchAiScreenerRuns, postAiScreener, postStopAiScreenerRun } from "./screenerAi";

const scope = { universe: "US_EQUITIES" as const, search: "A", sort: "volume", descending: true,
  filters: [{ id: "rsi", field: "rsi_14", operator: "gt", value: 50 }], result_set: "set-1" };
const ai = { state: "AVAILABLE" as const, reason: null, provider_id: "inference.test", model_id: "candidate.v1",
  runtime: "LOCAL_MODEL" as const, engine: "local", engine_model: "candidate.v1", engines: [] };
const preview = { schema_version: "screener-ai-screener-preview/1.0.0" as const, ai, scope: { ...scope },
  matched_count: 42, intake_count: 42, max_intake: 50, estimate: null,
  evidence_summary: { sufficient: 3, blocked: 1, missing: 4, weak: 2 },
  decision_cutoff: "2026-10-02T15:00:00Z", result_set: "set-1" };

const stored = { ...preview, schema_version: "screener-ai-screener/1.0.0", state: "NO_GROUNDED_CANDIDATES",
  scope: { ...scope }, run_id: "run-1", generated_at: "2026-10-02T15:00:00Z", valid_until: "2026-10-02T15:05:00Z", input_hash: "hash",
  provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL", prompt_id: "p", prompt_version: "1", prompt_hash: "ph",
  packet_bytes: 1, cache: "MISS", simulated: true, tokens_input: null, tokens_output: null, latency_ms: 1,
  evidence: [], candidates: [], limitations: ["Insufficient grounding."], coverage: {} };
const coverage = { method_version: "ai-screener-coverage/1.0.0", status: "COMPLETE_NO_SELECTION", reason: null, universe_count: 42, assessed_count: 42,
  eligible_count: 40, ai_evaluated_count: 40, ai_coverage_pct: 100, batches_planned: 1, batches_completed: 1, model_calls: 1, finalist_count: 0,
  selected_count: 0, coverage_complete: true, selection_complete: true, reconciled: true,
  counts: { evaluated: 40, ineligible: 0, evidence_blocked: 2, unprocessed: 0, by_class: { AI_EVALUATED: 40, EVIDENCE_STALE: 2 }, reasons: { "EVIDENCE_STALE:STALE": 2 } },
  budget: { capped: false, tokens_input: 0, tokens_output: 0 }, reduction: { rounds_planned: 0, rounds_completed: 0 } };
const running = { schema_version: "screener-ai-screener-run/2.0.0", run_id: "track-1", account_id: "paper", state: "RUNNING", joined: false, scope: { ...scope },
  stage: "BATCH_INFERENCE", stage_order: ["ENUMERATION", "ELIGIBILITY", "PLANNING", "BUDGET_HELD", "BATCH_INFERENCE", "GLOBAL_REDUCTION", "STORED"],
  stages: [{ stage: "BATCH_INFERENCE", started_at: "2026-10-02T15:00:01Z", elapsed_ms: 7000, detail: { batch: 1, batches_planned: 1, step: "MODEL_CALL" } }],
  started_at: "2026-10-02T15:00:00Z", finished_at: null,
  elapsed_ms: 8000, engine: { provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL" }, timeout_seconds: 45,
  typical_latency_ms: null, typical_latency_samples: 0, intake_count: null, sufficient_count: null, packet_bytes: 95600,
  progress: { universe_count: 42, assessed_count: 42, eligible_count: 40, batches_planned: 1 }, stop_requested: false, stop_requested_at: null,
  summary: null, result: null, error: null };

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
      ? { schema_version: "screener-ai-screener-runs/2.0.0", state: "RUNNING", ai: { state: "AVAILABLE", reason: null, provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL" },
          budget: null, active: running, latest: null, interrupted: [] }
      : { ...running, state: "COMPLETED", stage: null, finished_at: "2026-10-02T15:00:12Z", result: { ...stored, universe_coverage: coverage, provisional: [] },
          summary: { state: "NO_GROUNDED_CANDIDATES", reason: null, candidate_run_id: "run-1", selected: [], provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL", limitations: [],
            coverage, provisional_count: 0 } }), { status: 200 })));
    const current = await fetchAiScreenerRuns();
    expect([current.state, current.active?.stage, current.budget]).toEqual(["RUNNING", "BATCH_INFERENCE", null]);
    expect(current.active?.progress).toMatchObject({ universe_count: 42, eligible_count: 40 });
    const done = await fetchAiScreenerRun("track 1");
    expect(done.result?.state).toBe("NO_GROUNDED_CANDIDATES");
    expect([done.result?.universe_coverage?.coverage_complete, done.summary?.coverage?.counts.evidence_blocked]).toEqual([true, 2]);
    expect(vi.mocked(fetch).mock.calls.map(([url, init]) => [url, init?.method ?? "GET"])).toEqual([
      ["/screener/ai-screener/runs/active", "GET"], ["/screener/ai-screener/runs/track%201", "GET"]]);
  });

  it("stops a run with an explicit POST and reads receipts with GET", async () => {
    const receipts = { schema_version: "screener-ai-screener-coverage/1.0.0", run_id: "track-1", unfinished_calls: [],
      calls: [{ call_id: "BATCH_INFERENCE:0:0", stage: "BATCH_INFERENCE", round: null, index: 0, of: 1, outcome: "COMPLETED", state: "NO_GROUNDED_CANDIDATES",
        reason: null, evidence_cutoff: "2026-10-02T15:00:01Z", instrument_ids: ["EQ:A"], selected: [], tokens_input: 10, tokens_output: 2 }],
      rows: { phase: "FINAL", class: null, total: 42, offset: 0, limit: 500, items: [{ instrument_id: "EQ:Z", class: "EVIDENCE_STALE", reasons: ["STALE"] }] } };
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => new Response(JSON.stringify(String(url).includes("/coverage") ? receipts
      : { ...running, stop_requested: true, stop_requested_at: "2026-10-02T15:00:05Z" }), { status: 200 })));
    const stopping = await postStopAiScreenerRun("track 1");
    expect([stopping.state, stopping.stop_requested]).toEqual(["RUNNING", true]);
    const read = await fetchAiScreenerCoverage("track 1");
    expect(read.rows.items[0]).toEqual({ instrument_id: "EQ:Z", class: "EVIDENCE_STALE", reasons: ["STALE"] });
    expect(vi.mocked(fetch).mock.calls.map(([url, init]) => [url, init?.method ?? "GET"])).toEqual([
      ["/screener/ai-screener/runs/track%201/stop", "POST"], ["/screener/ai-screener/runs/track%201/coverage?class=NOT_EVALUATED&limit=500", "GET"]]);
  });

  it("rejects a run in the previous run contract instead of rendering it as full-universe", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ ...running, schema_version: "screener-ai-screener-run/1.0.0" }), { status: 200 })));
    await expect(fetchAiScreenerRun("track-1")).rejects.toThrow();
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

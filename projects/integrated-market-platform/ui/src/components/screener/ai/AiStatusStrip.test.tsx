import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AiScreenerRun, AiScreenerRuns } from "../../../api/screenerAi";
import AiStatusStrip, { countdown, plainReason } from "./AiStatusStrip";

const api = vi.hoisted(() => ({ runs: vi.fn(), post: vi.fn(), loop: vi.fn(), stop: vi.fn(), stopRun: vi.fn() }));
vi.mock("../../../api/screenerAi", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerAi")>(),
  fetchAiScreenerRuns: api.runs, postAiScreener: api.post, postStopAiScreenerRun: api.stopRun }));
vi.mock("../../../api/screenerReevaluation", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerReevaluation")>(),
  reevaluationStatus: api.loop, stopReevaluation: api.stop }));

const scope = { universe: "US_EQUITIES" as const, search: "", sort: "volume", descending: true, filters: [], settled: true };
const ahead = (ms: number) => new Date(Date.now() + ms).toISOString();
const STAGES = ["ENUMERATION", "ELIGIBILITY", "PLANNING", "BUDGET_HELD", "BATCH_INFERENCE", "GLOBAL_REDUCTION", "STORED"];
const coverage = (overrides: Record<string, unknown> = {}) => ({ method_version: "ai-screener-coverage/1.0.0", status: "COMPLETE_NO_SELECTION", reason: null,
  universe_count: 4_630, assessed_count: 4_630, eligible_count: 150, ai_evaluated_count: 150, ai_coverage_pct: 100, batches_planned: 3, batches_completed: 3,
  model_calls: 3, finalist_count: 0, selected_count: 0, coverage_complete: true, selection_complete: true, reconciled: true,
  counts: { evaluated: 150, ineligible: 0, evidence_blocked: 4_480, unprocessed: 0, by_class: {}, reasons: {} },
  budget: { capped: true, required_tokens: 150_000, available_tokens: 160_000, required_requests: 4, available_requests: 26, tokens_input: 43_000, tokens_output: 638 },
  reduction: { rounds_planned: 1, rounds_completed: 0 }, ...overrides });
const stage = (name: string, elapsed_ms: number, detail: Record<string, unknown> = {}) => ({ stage: name, started_at: "2026-10-07T14:00:00Z", elapsed_ms, detail });
const run = (overrides: Partial<AiScreenerRun> = {}): AiScreenerRun => ({ schema_version: "screener-ai-screener-run/2.0.0", run_id: "track-1", account_id: "paper",
  state: "RUNNING", joined: false, scope, stage: "BATCH_INFERENCE", stage_order: STAGES,
  stages: [stage("PLANNING", 30), stage("BUDGET_HELD", 2, { held_tokens: 150_000, held_requests: 4 }),
    stage("BATCH_INFERENCE", 7_000, { batch: 2, batches_planned: 3, batches_completed: 1, step: "MODEL_CALL" })],
  started_at: "2026-10-07T14:00:00Z", finished_at: null, elapsed_ms: 8_000, engine: { provider_id: "anthropic.messages", model_id: "claude-haiku-4-5", runtime: "PAID_API" },
  timeout_seconds: 45, typical_latency_ms: 10_800, typical_latency_samples: 3, intake_count: null, sufficient_count: null, packet_bytes: 95_600,
  progress: { universe_count: 4_630, assessed_count: 4_630, eligible_count: 150, batches_planned: 3, batches_completed: 1, rows_evaluated: 50 },
  stop_requested: false, stop_requested_at: null, summary: null, result: null, error: null, ...overrides } as AiScreenerRun);
const finished = (summary: Record<string, unknown> = {}) => run({ state: "COMPLETED", stage: null, finished_at: "2026-10-07T13:58:12Z",
  summary: { state: "NO_GROUNDED_CANDIDATES", reason: null, candidate_run_id: "run-1", selected: [], intake_count: 150, cache: "MISS", provider_id: "anthropic.messages",
    model_id: "claude-haiku-4-5", runtime: "PAID_API", tokens_input: 43_000, tokens_output: 638, valid_until: ahead(42_500), limitations: [],
    coverage: coverage(), provisional_count: 0, ...summary } as AiScreenerRun["summary"] });
const picked = [{ instrument_id: "EQ:A", rank: 1 }, { instrument_id: "EQ:B", rank: 2 }];
const budget = { day: "2026-10-07", tokens: 87_000, max_tokens: 200_000, requests: 4, max_requests: 30, headroom: 113_000, requests_left: 26,
  held_tokens: 0, held_requests: 0, run_size: 150_000, run_size_basis: "LAST_RUN_HOLD", runs_left: 0, resets_at: ahead(5 * 3_600_000) };
const status = (overrides: Partial<AiScreenerRuns> = {}): AiScreenerRuns => ({ schema_version: "screener-ai-screener-runs/2.0.0", state: "IDLE",
  ai: { state: "AVAILABLE", reason: null, provider_id: "anthropic.messages", model_id: "claude-haiku-4-5", runtime: "PAID_API" }, budget, active: null, latest: null,
  interrupted: [], ...overrides });
const loop = (worker_state: string, worker_label: string, extra: Record<string, unknown> = {}) => ({ schema_version: "reevaluation-status/1.0.0", worker_state, worker_label,
  engine: { state: "AVAILABLE", reason: null, provider_id: "p", model_id: "m", runtime: "PAID_API", budget: null }, durability: "DURABLE", paper_execution: "MANUAL_ONLY", ...extra });

const onOpen = vi.fn();
const mount = (value = scope) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <AiStatusStrip scope={value} onOpen={onOpen} /></QueryClientProvider>);
const strip = () => screen.getByRole("region", { name: "AI status" });

beforeEach(() => { api.loop.mockResolvedValue(loop("NOT_CONFIGURED", "Not configured")); });
afterEach(() => vi.resetAllMocks());

describe("AI status strip", () => {
  it("idle: says when the last pass ran, what it selected from how much, when its evidence expires and when the loop next runs", async () => {
    api.runs.mockResolvedValue(status({ latest: finished({ state: "CURRENT", selected: picked, coverage: coverage({ status: "GLOBAL_SELECTION_COMPLETE", selected_count: 2 }) }) }));
    api.loop.mockResolvedValue(loop("RUNNING", "Running", { next_scheduled: ahead(133_500) }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent(/Idle · last pass 09:58:12 ET · 2 selected · 150 AI-evaluated of 4,630 rows · evidence expires in 0:4[123] · next automatic cycle in 2:1[234]/));
    expect(strip()).toHaveTextContent("Budget 87k / 200k tokens · 26 of 30 requests left · last run used 44k");
    expect(strip().querySelector(".ai-strip-engine")).toHaveTextContent("claude-haiku-4-5 · paid");
    expect(strip().querySelector(".ai-strip-budget")).toHaveAttribute("title", expect.stringContaining("The last run held 150,000 tokens for its whole plan."));
    // The last run being large never disables the next one: each run states what it needs before any model call.
    expect(within(strip()).getByRole("button", { name: "Run now" })).toBeEnabled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("running: shows the batch, the step, measured time, real counts and what slow would look like, and offers Stop but no second run", async () => {
    api.runs.mockResolvedValue(status({ state: "RUNNING", active: run(), budget: { ...budget, held_tokens: 100_000, held_requests: 3 } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Running · batch 2 of 3 · model call · 7.0s in this stage · claude-haiku-4-5 · 4,630 rows · 150 eligible · 50 AI-evaluated · 1 of 3 batches done · typical 11s from 3 measured calls · request times out at 45s"));
    expect(strip()).toHaveTextContent("26 of 30 requests left · this run holds 100k");
    expect(strip()).toHaveClass("running");
    expect(strip().querySelector(".ai-strip-engine")).toBeNull();
    expect(within(strip()).queryByRole("button", { name: "Run now" })).toBeNull();
    expect(strip()).not.toHaveTextContent("%");
    api.stopRun.mockResolvedValue(run({ stop_requested: true }));
    fireEvent.click(within(strip()).getByRole("button", { name: "Stop run" }));
    await waitFor(() => expect(api.stopRun).toHaveBeenCalledWith("track-1"));
    expect(api.stop).not.toHaveBeenCalled();
  });

  it("a stop already requested says the call in flight is finishing and cannot be requested twice", async () => {
    api.runs.mockResolvedValue(status({ state: "RUNNING", active: run({ stop_requested: true }) }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Stopping after the call in flight · batch 2 of 3"));
    expect(within(strip()).getByRole("button", { name: "Stopping…" })).toBeDisabled();
  });

  it("an unfinished run is never summarised as a selection, and a run a restart killed is named", async () => {
    api.runs.mockResolvedValue(status({ latest: finished({ state: "INCOMPLETE", reason: "AI_COVERAGE_BUDGET_INSUFFICIENT", selected: [],
      coverage: coverage({ status: "AI_COVERAGE_BUDGET_INSUFFICIENT", ai_evaluated_count: 0, ai_coverage_pct: 0, eligible_count: 4_605, batches_planned: 93, batches_completed: 0,
        coverage_complete: false, selection_complete: false }) }) }));
    const view = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("last pass 09:58:12 ET incomplete · 0 of 4,605 eligible rows AI-evaluated (today's budget cannot pay for every eligible row plus the global comparison (AI_COVERAGE_BUDGET_INSUFFICIENT))"));
    expect(strip()).not.toHaveTextContent("selected ·");
    view.unmount();
    api.runs.mockResolvedValue(status({ interrupted: [{ run_id: "dead", status: "INTERRUPTED", reason: "SERVER_RESTARTED_DURING_RUN", finished_at: "2026-10-07T13:00:00Z",
      calls_completed: 2, unknown_provider_outcomes: 1 }] }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Interrupted · the server restarted during the run · 2 model calls had finished · 1 had no recorded outcome and stays charged. Nothing was resumed."));
  });

  it("states an expired result, a failed pass and a pass that gave no result in plain words with the code", async () => {
    api.runs.mockResolvedValue(status({ latest: finished({ state: "CURRENT", selected: picked, valid_until: ahead(-5_000) }) }));
    const view = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("2 selected · 150 AI-evaluated of 4,630 rows · evidence expired · automatic passes not configured"));
    view.unmount();
    api.runs.mockResolvedValue(status({ latest: run({ state: "FAILED", stage: null, finished_at: "2026-10-07T13:58:12Z", error: { code: "EVIDENCE_PACKET_BOUND_EXCEEDED", stage: "PACKET" } }) }));
    const second = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Idle · last pass 09:58:12 ET failed (too much evidence for one call (EVIDENCE_PACKET_BOUND_EXCEEDED))"));
    second.unmount();
    api.runs.mockResolvedValue(status({ latest: finished({ state: "UNAVAILABLE", reason: "SYNTHESIS_DAILY_TOKEN_LIMIT", coverage: null }) }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("last pass 09:58:12 ET gave no result (the run would exceed today's token budget (SYNTHESIS_DAILY_TOKEN_LIMIT))"));
  });

  it("waiting for budget: says why and when the budget resets, and offers no run", async () => {
    api.runs.mockResolvedValue(status({ state: "WAITING_FOR_BUDGET", ai: { state: "UNAVAILABLE", reason: "SYNTHESIS_DAILY_BUDGET_EXHAUSTED", provider_id: "anthropic.messages",
      model_id: "claude-haiku-4-5", runtime: "PAID_API" }, budget: { ...budget, tokens: 200_000, headroom: 0, runs_left: 0 } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent(/Waiting for budget · today's model budget is used up \(SYNTHESIS_DAILY_BUDGET_EXHAUSTED\) · resets \d\d:\d\d:\d\d ET \(in (4:59:5\d|5:00:00)\)/));
    expect(within(strip()).queryByRole("button", { name: "Run now" })).toBeNull();
  });

  it("waiting for budget with no reason reported says the shared budget is used up", async () => {
    api.runs.mockResolvedValue(status({ state: "WAITING_FOR_BUDGET", budget: { ...budget, requests_left: 0 } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Waiting for budget · today's shared budget is used up"));
  });

  it("blocked and not configured name the reason; a local model has no API cost", async () => {
    api.runs.mockResolvedValue(status({ state: "BLOCKED", budget: null, ai: { state: "UNAVAILABLE", reason: "LOCAL_MODEL_UNREACHABLE", provider_id: "local", model_id: "small", runtime: "LOCAL_MODEL" } }));
    const view = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Blocked · LOCAL_MODEL_UNREACHABLE"));
    expect(strip()).toHaveTextContent("Local model · no API cost");
    view.unmount();
    api.runs.mockResolvedValue(status({ state: "NOT_CONFIGURED", budget: null, ai: { state: "NOT_CONFIGURED", reason: "ANTHROPIC_API_KEY_NOT_SET", provider_id: null, model_id: null, runtime: null } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Not configured · no API key is set for the selected engine (ANTHROPIC_API_KEY_NOT_SET)"));
    expect(strip().querySelector(".ai-strip-budget")).toBeNull();
    expect(within(strip()).queryByRole("button", { name: "Run now" })).toBeNull();
  });

  it("promises no number of runs: it states the budget and what is left", async () => {
    api.runs.mockResolvedValue(status({ budget: { ...budget, run_size: null, run_size_basis: null, runs_left: null } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Idle · no pass since the server started"));
    expect(strip()).toHaveTextContent("Budget 87k / 200k tokens · 26 of 30 requests left");
    expect(strip()).not.toHaveTextContent("runs left");
    expect(strip().querySelector(".ai-strip-budget")).toHaveAttribute("title", expect.stringContaining("No run has held tokens yet."));
  });

  it("reports a stopped loop and an unreadable loop without guessing", async () => {
    api.runs.mockResolvedValue(status());
    api.loop.mockResolvedValue(loop("STOPPED", "Stopped"));
    const view = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("automatic passes: stopped"));
    expect(within(strip()).queryByRole("button", { name: "Stop automatic passes" })).toBeNull();
    view.unmount();
    api.loop.mockRejectedValue(new Error("PAPER_AUTHORITY_REQUIRED"));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("automatic passes: status unavailable"));
  });

  it("Run now posts the current scope once; Stop only stops the loop; Open only opens the detail", async () => {
    api.runs.mockResolvedValue(status());
    api.loop.mockResolvedValue(loop("RUNNING", "Running", { next_scheduled: ahead(60_000) }));
    api.post.mockResolvedValue(run());
    api.stop.mockResolvedValue(loop("STOPPED", "Stopped"));
    mount();
    fireEvent.click(await within(strip()).findByRole("button", { name: "Open" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(await within(strip()).findByRole("button", { name: "Stop automatic passes" }));
    await waitFor(() => expect(api.stop).toHaveBeenCalledTimes(1));
    expect(api.post).not.toHaveBeenCalled();
    fireEvent.click(await within(strip()).findByRole("button", { name: "Run now" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith(scope);
  });

  it("does not offer a run while the Screener scope is still loading, and reports a start that failed", async () => {
    api.runs.mockResolvedValue(status());
    const view = mount({ ...scope, settled: false });
    expect(await within(strip()).findByRole("button", { name: "Run now" })).toBeDisabled();
    view.unmount();
    api.post.mockRejectedValue(new Error("network"));
    mount();
    fireEvent.click(await within(strip()).findByRole("button", { name: "Run now" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not start a run.");
  });

  it("says status is unavailable instead of showing idle, and is not a live region", async () => {
    api.runs.mockRejectedValue(new Error("offline"));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Status unavailable; a run may still be in progress on the server."));
    expect(strip()).not.toHaveTextContent("Idle");
    expect(within(strip()).queryByRole("status")).toBeNull();
    expect(within(strip()).queryByRole("button", { name: "Run now" })).toBeNull();
  });
});

describe("strip wording helpers", () => {
  it("counts down in minutes and seconds, then hours", () => {
    expect(countdown(133_000)).toBe("2:13");
    expect(countdown(900)).toBe("0:01");
    expect(countdown(-5)).toBe("0:00");
    expect(countdown(3_723_000)).toBe("1:02:03");
  });

  it("keeps the code beside the plain words and passes unknown codes through", () => {
    expect(plainReason("EVIDENCE_PACKET_BOUND_EXCEEDED")).toBe("too much evidence for one call (EVIDENCE_PACKET_BOUND_EXCEEDED)");
    expect(plainReason("SOMETHING_NEW")).toBe("SOMETHING_NEW");
    expect(plainReason(null)).toBe("no reason reported");
  });
});

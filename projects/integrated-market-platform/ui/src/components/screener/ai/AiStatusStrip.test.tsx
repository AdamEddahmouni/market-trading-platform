import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AiScreenerRun, AiScreenerRuns } from "../../../api/screenerAi";
import AiStatusStrip, { countdown, plainReason } from "./AiStatusStrip";

const api = vi.hoisted(() => ({ runs: vi.fn(), post: vi.fn(), loop: vi.fn(), stop: vi.fn() }));
vi.mock("../../../api/screenerAi", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerAi")>(),
  fetchAiScreenerRuns: api.runs, postAiScreener: api.post }));
vi.mock("../../../api/screenerReevaluation", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerReevaluation")>(),
  reevaluationStatus: api.loop, stopReevaluation: api.stop }));

const scope = { universe: "US_EQUITIES" as const, search: "", sort: "volume", descending: true, filters: [], settled: true };
const ahead = (ms: number) => new Date(Date.now() + ms).toISOString();
const STAGES = ["SCOPE", "NEWS", "EVIDENCE", "PACKET", "BUDGET_RESERVED", "MODEL_CALL", "VALIDATION", "STORED"];
const stage = (name: string, elapsed_ms: number, detail: Record<string, unknown> = {}) => ({ stage: name, started_at: "2026-10-07T14:00:00Z", elapsed_ms, detail });
const run = (overrides: Partial<AiScreenerRun> = {}): AiScreenerRun => ({ schema_version: "screener-ai-screener-run/1.0.0", run_id: "track-1", account_id: "paper",
  state: "RUNNING", joined: false, scope, stage: "MODEL_CALL", stage_order: STAGES,
  stages: [stage("PACKET", 30), stage("BUDGET_RESERVED", 2, { reserved_tokens: 38_700 }), stage("MODEL_CALL", 7_000)],
  started_at: "2026-10-07T14:00:00Z", finished_at: null, elapsed_ms: 8_000, engine: { provider_id: "anthropic.messages", model_id: "claude-haiku-4-5", runtime: "PAID_API" },
  timeout_seconds: 45, typical_latency_ms: 10_800, typical_latency_samples: 3, intake_count: 20, sufficient_count: 4, packet_bytes: 95_600,
  summary: null, result: null, error: null, ...overrides } as AiScreenerRun);
const finished = (summary: Record<string, unknown> = {}) => run({ state: "COMPLETED", stage: null, finished_at: "2026-10-07T13:58:12Z",
  summary: { state: "NO_GROUNDED_CANDIDATES", reason: null, candidate_run_id: "run-1", selected: [], intake_count: 20, cache: "MISS", provider_id: "anthropic.messages",
    model_id: "claude-haiku-4-5", runtime: "PAID_API", tokens_input: 43_000, tokens_output: 638, valid_until: ahead(42_500), limitations: [], ...summary } as AiScreenerRun["summary"] });
const budget = { day: "2026-10-07", tokens: 87_000, max_tokens: 200_000, requests: 4, max_requests: 30, tokens_left: 113_000, requests_left: 26,
  per_run_tokens: 38_700, per_run_basis: "LAST_RESERVATION", runs_left: 2, resets_at: ahead(5 * 3_600_000) };
const status = (overrides: Partial<AiScreenerRuns> = {}): AiScreenerRuns => ({ schema_version: "screener-ai-screener-runs/1.1.0", state: "IDLE",
  ai: { state: "AVAILABLE", reason: null, provider_id: "anthropic.messages", model_id: "claude-haiku-4-5", runtime: "PAID_API" }, budget, active: null, latest: null, ...overrides });
const loop = (worker_state: string, worker_label: string, extra: Record<string, unknown> = {}) => ({ schema_version: "reevaluation-status/1.0.0", worker_state, worker_label,
  engine: { state: "AVAILABLE", reason: null, provider_id: "p", model_id: "m", runtime: "PAID_API", budget: null }, durability: "DURABLE", paper_execution: "MANUAL_ONLY", ...extra });

const onOpen = vi.fn();
const mount = (value = scope) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <AiStatusStrip scope={value} onOpen={onOpen} /></QueryClientProvider>);
const strip = () => screen.getByRole("region", { name: "AI status" });

beforeEach(() => { api.loop.mockResolvedValue(loop("NOT_CONFIGURED", "Not configured")); });
afterEach(() => vi.resetAllMocks());

describe("AI status strip", () => {
  it("idle: says when the last pass ran, what it selected, when its evidence expires and when the loop next runs", async () => {
    api.runs.mockResolvedValue(status({ latest: finished() }));
    api.loop.mockResolvedValue(loop("RUNNING", "Running", { next_scheduled: ahead(133_500) }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent(/Idle · last pass 09:58:12 ET · 0 of 20 selected · evidence expires in 0:4[123] · next automatic cycle in 2:1[234]/));
    expect(strip()).toHaveTextContent("Budget 87k / 200k tokens · ~2 runs left · last run used 44k");
    expect(strip().querySelector(".ai-strip-budget")).toHaveAttribute("title", expect.stringContaining("A run is counted as 38,700 tokens, the last amount reserved for this model."));
    expect(within(strip()).getByRole("button", { name: "Run now" })).toBeEnabled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("running: shows the stage, measured time, model, candidates and what slow would look like, and offers no second run", async () => {
    api.runs.mockResolvedValue(status({ state: "RUNNING", active: run() }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Running · model call 7.0s · claude-haiku-4-5 · 20 candidates · typical 11s from 3 measured calls · request times out at 45s"));
    expect(strip()).toHaveTextContent("~2 runs left · this run holds 39k");
    expect(strip()).toHaveClass("running");
    expect(within(strip()).queryByRole("button", { name: "Run now" })).toBeNull();
    expect(strip()).not.toHaveTextContent("%");
  });

  it("states an expired result, a failed pass and a pass that gave no result in plain words with the code", async () => {
    api.runs.mockResolvedValue(status({ latest: finished({ valid_until: ahead(-5_000) }) }));
    const view = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("0 of 20 selected · evidence expired · automatic passes not configured"));
    view.unmount();
    api.runs.mockResolvedValue(status({ latest: run({ state: "FAILED", stage: null, finished_at: "2026-10-07T13:58:12Z", error: { code: "EVIDENCE_PACKET_BOUND_EXCEEDED", stage: "PACKET" } }) }));
    const second = mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Idle · last pass 09:58:12 ET failed (too much evidence for one call (EVIDENCE_PACKET_BOUND_EXCEEDED))"));
    second.unmount();
    api.runs.mockResolvedValue(status({ latest: finished({ state: "UNAVAILABLE", reason: "SYNTHESIS_DAILY_TOKEN_LIMIT" }) }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("last pass 09:58:12 ET gave no result (the run would exceed today's token budget (SYNTHESIS_DAILY_TOKEN_LIMIT))"));
  });

  it("waiting for budget: says why and when the budget resets, and offers no run", async () => {
    api.runs.mockResolvedValue(status({ state: "WAITING_FOR_BUDGET", ai: { state: "UNAVAILABLE", reason: "SYNTHESIS_DAILY_BUDGET_EXHAUSTED", provider_id: "anthropic.messages",
      model_id: "claude-haiku-4-5", runtime: "PAID_API" }, budget: { ...budget, tokens: 200_000, tokens_left: 0, runs_left: 0 } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent(/Waiting for budget · today's model budget is used up \(SYNTHESIS_DAILY_BUDGET_EXHAUSTED\) · resets \d\d:\d\d:\d\d ET \(in (4:59:5\d|5:00:00)\)/));
    expect(strip()).toHaveTextContent("~0 runs left");
    expect(within(strip()).queryByRole("button", { name: "Run now" })).toBeNull();
  });

  it("waiting for budget because one more run of the measured size does not fit", async () => {
    api.runs.mockResolvedValue(status({ state: "WAITING_FOR_BUDGET", budget: { ...budget, runs_left: 0 } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Waiting for budget · another run of the last measured size does not fit in today's budget"));
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

  it("does not count runs left before any run has reserved tokens", async () => {
    api.runs.mockResolvedValue(status({ budget: { ...budget, per_run_tokens: null, per_run_basis: null, runs_left: null } }));
    mount();
    await waitFor(() => expect(strip()).toHaveTextContent("Idle · no pass since the server started"));
    expect(strip()).toHaveTextContent("Budget 87k / 200k tokens · 26 of 30 requests left · run size not yet measured");
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

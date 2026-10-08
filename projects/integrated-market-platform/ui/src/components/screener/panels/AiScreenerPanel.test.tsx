import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AiScreenerPanel from "./AiScreenerPanel";
import { SpecialistContext, type SpecialistSelection } from "./shared";
import type { AiScreenerPreview, AiScreenerResult, AiScreenerRun, AiScreenerRuns } from "../../../api/screenerAi";
import { SchemaMismatchError } from "../../../api/fetchJson";
import { lifecycle, lifecycleList, openPosition } from "../lifecycle/lifecycleFixture";

const mocks = vi.hoisted(() => ({ preview: vi.fn(), run: vi.fn(), post: vi.fn(), runs: vi.fn(), detail: vi.fn(), engine: vi.fn(), lifecycles: vi.fn(), lifecycle: vi.fn(),
  stop: vi.fn(), receipts: vi.fn() }));
vi.mock("../../../api/screenerLifecycle", () => ({ tradeLifecycles: mocks.lifecycles, tradeLifecycle: mocks.lifecycle }));
vi.mock("../../../api/screenerAi", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerAi")>(),
  fetchAiScreenerPreview: mocks.preview, postAiScreener: mocks.post, fetchAiScreenerRuns: mocks.runs, fetchAiScreenerRun: mocks.detail,
  postStopAiScreenerRun: mocks.stop, fetchAiScreenerCoverage: mocks.receipts }));
vi.mock("../../../api/screenerNews", async (importOriginal) => ({ ...await importOriginal<typeof import("../../../api/screenerNews")>(), postSynthesisEngine: mocks.engine }));

const scope = { universe: "US_EQUITIES" as const, search: "A", sort: "volume", descending: true, filters: [] };
const ai = { state: "AVAILABLE" as const, reason: null, provider_id: "inference.test", model_id: "candidate.v1",
  runtime: "LOCAL_MODEL" as const, engine: "local", engine_model: "candidate.v1", engines: [] };
const preview = { schema_version: "screener-ai-screener-preview/1.0.0" as const, ai, scope, matched_count: 4,
  intake_count: 4, max_intake: 50, estimate: null, evidence_summary: { sufficient: 1, blocked: 0, missing: 0, weak: 0 },
  decision_cutoff: "2026-10-02T15:00:00Z", result_set: null } as AiScreenerPreview;
const result = { schema_version: "screener-ai-screener/1.0.0" as const, state: "CURRENT", reason: null, scope,
  matched_count: 4, intake_count: 4, max_intake: 50, result_set: null, run_id: "run-1", decision_cutoff: "2026-10-02T15:00:00Z",
  generated_at: "2026-10-02T15:00:00Z", valid_until: "2026-10-02T15:05:00Z", input_hash: "hash", provider_id: "inference.test",
  model_id: "candidate.v1", runtime: "LOCAL_MODEL", prompt_id: "p", prompt_version: "1", prompt_hash: "ph", packet_bytes: 1,
  cache: "MISS" as const, simulated: true, tokens_input: null, tokens_output: null, latency_ms: 1, evidence: [], candidates: [],
  limitations: ["No candidate selected."], coverage: {} } as AiScreenerResult;

const STAGES = ["ENUMERATION", "ELIGIBILITY", "PLANNING", "BUDGET_HELD", "BATCH_INFERENCE", "GLOBAL_REDUCTION", "STORED"];
const coverage = (overrides: Record<string, unknown> = {}) => ({ method_version: "ai-screener-coverage/1.0.0", status: "GLOBAL_SELECTION_COMPLETE", reason: null,
  universe_count: 4_630, assessed_count: 4_630, eligible_count: 150, ai_evaluated_count: 150, ai_coverage_pct: 100, batches_planned: 3, batches_completed: 3,
  model_calls: 4, finalist_count: 2, selected_count: 1, coverage_complete: true, selection_complete: true, reconciled: true,
  counts: { evaluated: 150, ineligible: 12, evidence_blocked: 4_468, unprocessed: 0, by_class: {}, reasons: { "EVIDENCE_STALE:STALE": 4_468, "INELIGIBLE:NO_SECOND_STRONG_EVIDENCE": 12 } },
  budget: { capped: true, required_tokens: 150_000, available_tokens: 160_000, required_requests: 4, available_requests: 26, tokens_input: 43_000, tokens_output: 638 },
  reduction: { rounds_planned: 1, rounds_completed: 1 }, ...overrides });
const stage = (name: string, elapsed_ms: number, detail: Record<string, unknown> = {}) => ({ stage: name, started_at: "2026-10-02T15:00:00Z", elapsed_ms, detail });
const trackedRun = (overrides: Partial<AiScreenerRun> = {}): AiScreenerRun => ({ schema_version: "screener-ai-screener-run/2.0.0", run_id: "track-1", account_id: "paper",
  state: "RUNNING", joined: false, scope, stage: "BATCH_INFERENCE", stage_order: STAGES,
  stages: [stage("ENUMERATION", 40, { universe_count: 4_630 }), stage("ELIGIBILITY", 900, { eligible_count: 150 }), stage("PLANNING", 30, { batches_planned: 3 }),
    stage("BATCH_INFERENCE", 7_000, { batch: 2, batches_planned: 3, batches_completed: 1, step: "MODEL_CALL" })],
  started_at: "2026-10-02T15:00:00Z", finished_at: null, elapsed_ms: 7_990, engine: { provider_id: "inference.test", model_id: "candidate.v1", runtime: "PAID_API" },
  timeout_seconds: 45, typical_latency_ms: 10_800, typical_latency_samples: 3, intake_count: null, sufficient_count: null, packet_bytes: 95_600,
  progress: { universe_count: 4_630, assessed_count: 4_630, eligible_count: 150, batches_planned: 3, batches_completed: 1, rows_evaluated: 50 },
  stop_requested: false, stop_requested_at: null, summary: null, result: null, error: null, ...overrides } as AiScreenerRun);
/** What the server reports once a run has finished: the stored result plus how the run went. */
const finishedRun = (value: AiScreenerResult, overrides: Partial<AiScreenerRun> = {}) => trackedRun({ run_id: `track-${value.run_id}`, state: "COMPLETED", stage: null,
  scope: value.scope as AiScreenerRun["scope"], finished_at: "2026-10-02T15:00:12Z", elapsed_ms: 12_300, result: value,
  summary: { state: value.state, reason: value.reason ?? null, candidate_run_id: value.run_id, selected: value.candidates.map(({ instrument_id, rank }) => ({ instrument_id, rank })),
    provider_id: value.provider_id, model_id: value.model_id, runtime: value.runtime, limitations: value.limitations }, ...overrides });
// A stand-in for the server's run registry: POST starts or finishes a run, the two GETs only read it.
const server: { active: AiScreenerRun | null; latest: AiScreenerRun | null; results: Map<string, AiScreenerRun> } = { active: null, latest: null, results: new Map() };
const finish = (run: AiScreenerRun) => { server.active = null; server.latest = { ...run, result: null }; server.results.set(run.run_id, run); };

const panelApi = { isVisible: true, onDidVisibilityChange: () => ({ dispose: () => undefined }) } as never;
const selection = (overrides: Partial<SpecialistSelection> = {}): SpecialistSelection => ({
  row: null, universe: "US_EQUITIES", supportedPanels: new Set(["ai_screener"]), settledId: null, quote: undefined, filters: [],
  screenerScope: scope, openInstrument: vi.fn(), demand: null, actions: { close: vi.fn(), move: vi.fn(), resize: vi.fn() }, ...overrides,
});
const renderPanel = (value = selection()) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><SpecialistContext.Provider value={value}><AiScreenerPanel api={panelApi} /></SpecialistContext.Provider></MemoryRouter>
</QueryClientProvider>);

beforeEach(() => {
  server.active = null; server.latest = null; server.results.clear();
  mocks.lifecycles.mockResolvedValue(lifecycleList());
  // Existing cases describe only the stored result; the run that carried it is wrapped here.
  mocks.post.mockImplementation(async (requested: typeof scope) => {
    const value = await mocks.run(requested);
    const run = value.schema_version === "screener-ai-screener-run/2.0.0" ? value as AiScreenerRun : finishedRun({ ...value, scope: requested });
    if (run.state === "RUNNING") server.active = run; else finish(run);
    return run;
  });
  mocks.runs.mockImplementation(async (): Promise<AiScreenerRuns> => ({ schema_version: "screener-ai-screener-runs/2.0.0", state: server.active ? "RUNNING" : "IDLE",
    ai: { state: "AVAILABLE", reason: null, provider_id: "inference.test", model_id: "candidate.v1", runtime: "LOCAL_MODEL" }, budget: null, active: server.active, latest: server.latest }));
  mocks.detail.mockImplementation(async (id: string) => server.results.get(id) ?? Promise.reject(new Error("SCREENER_AI_RUN_UNKNOWN")));
});
afterEach(() => vi.clearAllMocks());

describe("AI Screener panel", () => {
  it.each(["CONFLICTING", "CONFIRMING", "MIXED", "UNKNOWN", "CONTEXT_ONLY"] as const)("displays deterministic %s independently of model prose and drills into News", async (alignment) => {
    mocks.preview.mockResolvedValue(preview);
    const openInstrument = vi.fn(); const openPanel = vi.fn(); const openNews = vi.fn();
    mocks.run.mockResolvedValue({ ...result, valid_until: "2099-01-01T00:00:00Z", evidence: [{
      instrument: { instrument_id: "EQ:A" }, current_market_evidence: [], blocked: [], missing: [], weak: [], sufficient: true,
      reference_evidence: [{ evidence_id: "EV:NEWS", capability: "NEWS", source: "finviz", role: "REFERENCE_CONTEXT", freshness_status: "CURRENT", valid_until: "2099-01-01T00:00:00Z", facts: {
        headline: "Apple warns on margins", story_id: "story-1", published_at: "2026-10-02T14:42:00Z", latest_published_at: "2026-10-02T14:42:00Z", source_count: 2, provider_count: 1,
        sources: [{ provider_id: "finviz", publisher: "Reuters", retrieved_at: "2026-10-02T14:43:00Z" }], match_confidence: "EXACT", match_basis: "PROVIDER_TICKER", categories: [{ label: "Earnings" }], window: "4h", coverage_state: "DELAYED",
        sentiment: { state: "SCORED", label: "NEGATIVE", model_id: "ProsusAI/finbert", model_revision: "rev001", sentiment_version: "news/finbert-sentiment/1.0.0", basis: "IMP_DERIVED_FINBERT", probabilities: { positive: .05, neutral: .05, negative: .9 } },
      } }],
      news: { state: "AVAILABLE", story_count: 1, window: "4h", snapshot_at: "2026-10-02T15:00:00Z", providers: [{ id: "newsapi", state: "DELAYED", reason: null }],
        sentiment: { dominant: alignment === "UNKNOWN" ? null : "NEGATIVE", state: alignment === "UNKNOWN" ? "UNAVAILABLE" : "CURRENT", reason: alignment === "UNKNOWN" ? "MODEL_LOADING" : null, scored: alignment === "UNKNOWN" ? 0 : 1, unscored: alignment === "UNKNOWN" ? 1 : 0,
          model_id: "ProsusAI/finbert", model_revision: "rev001", sentiment_version: "news/finbert-sentiment/1.0.0", basis: "IMP_DERIVED_FINBERT", method: "Counts of story top labels", counts: { negative: 1 } } },
      alignments: [{ alignment_id: "AL:1", kind: "NEWS_SENTIMENT_VS_PRICE", result: alignment, observed_direction: "POSITIVE", method: "headline-language-vs-observed-direction/1.0.0", cutoff: "2026-10-02T15:00:00Z", news_refs: ["EV:NEWS"], sentiment_refs: ["EV:TONE"], comparator_ref: "EV:PRICE", limitations: [] }],
    }], candidates: [{ instrument_id: "EQ:A", rank: 1, rationale: "Review admitted observations.", supporting_refs: [], conflicting_refs: [], weak_refs: [], missing_capabilities: [], uncertainties: [] }] });
    renderPanel(selection({ openInstrument, openNews, actions: { close: vi.fn(), move: vi.fn(), resize: vi.fn(), open: openPanel } }));
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    expect(await screen.findByText(`Evidence alignment: ${alignment} · sentiment vs observed price direction`)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Apple warns on margins · NEWS"));
    expect(screen.getByText(/finviz: Reuters/)).toBeInTheDocument();
    expect(screen.getByText(/EXACT · PROVIDER_TICKER/)).toBeInTheDocument();
    expect(screen.getByText(/Published/)).toBeInTheDocument();
    expect(screen.getByText(/probabilities.*negative/)).toBeInTheDocument();
    expect(screen.getByText(/Coverage: newsapi: DELAYED/)).toBeInTheDocument();
    if (alignment === "UNKNOWN") expect(screen.getByText(/Headline language: NOT_SCORED.*MODEL_LOADING/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open News & Analysis" }));
    expect(openNews).toHaveBeenCalledWith("EQ:A", { instrument_id: "EQ:A" }); expect(openInstrument).not.toHaveBeenCalled();
  });
  describe("engine picker safety", () => {
    const engines = [
      { id: "local", label: "Local model", runtime: "LOCAL_MODEL" as const, models: ["small-4b"], default_model: "small-4b", context_window: 8192, state: "AVAILABLE" as const, reason: null },
      { id: "anthropic", label: "Anthropic Claude", runtime: "PAID_API" as const, models: ["claude-haiku-4-5"], default_model: "claude-haiku-4-5", context_window: null, state: "AVAILABLE" as const, reason: null },
    ];
    const engine_fit = [{ engine: "local", fits: false, packet_size: 37_340, context_window: 8192 }, { engine: "anthropic", fits: null, packet_size: 37_340, context_window: null }];
    const paid = { ...ai, runtime: "PAID_API" as const, engine: "anthropic", engine_model: "claude-haiku-4-5", engines };

    it("asks before switching, says the change is machine-wide, and sends nothing until confirmed", async () => {
      mocks.preview.mockResolvedValue({ ...preview, ai: paid, engine_fit });
      mocks.engine.mockResolvedValue({ ...paid, runtime: "LOCAL_MODEL", engine: "local", engine_model: "small-4b" });
      renderPanel();
      const select = await screen.findByRole("combobox", { name: "Engine/model" });
      // A model too small for this packet is marked, not silently selectable; an unknown limit claims nothing.
      expect(within(select).getByRole("option", { name: "Local model · small-4b · local · current packet does not fit: needs ~37k tokens, model context 8k" })).toBeInTheDocument();
      expect(within(select).getByRole("option", { name: "Anthropic Claude · claude-haiku-4-5 · paid" })).toBeInTheDocument();
      fireEvent.change(select, { target: { value: "local|small-4b" } });
      const confirm = screen.getByRole("alertdialog", { name: "Confirm AI engine change" });
      expect(confirm).toHaveTextContent("Switch the AI engine to Local model · small-4b?");
      expect(confirm).toHaveTextContent("This applies to every AI panel on this machine (News synthesis, AI Screener, Action Decisions and automatic passes)");
      expect(confirm).toHaveTextContent("The current packet does not fit: needs ~37k tokens, model context 8k. An AI Screener run on it would be refused or cut short.");
      expect(mocks.engine).not.toHaveBeenCalled();
      fireEvent.click(within(confirm).getByRole("button", { name: "Keep current engine" }));
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(mocks.engine).not.toHaveBeenCalled();
      fireEvent.change(screen.getByRole("combobox", { name: "Engine/model" }), { target: { value: "local|small-4b" } });
      fireEvent.click(screen.getByRole("button", { name: "Switch engine" }));
      await waitFor(() => expect(mocks.engine).toHaveBeenCalledWith("local", "small-4b"));
      expect(mocks.engine).toHaveBeenCalledTimes(1);
      expect(mocks.post).not.toHaveBeenCalled();
    });

    it("is locked while automatic passes run", async () => {
      mocks.preview.mockResolvedValue({ ...preview, ai: { ...paid, engine_lock: { locked: true, reason: "REEVALUATION_LOOP_RUNNING" } }, engine_fit });
      renderPanel();
      expect(await screen.findByRole("combobox", { name: "Engine/model" })).toBeDisabled();
      expect(screen.getByText("Locked while automatic passes are running. Stop them to change the engine.")).toBeInTheDocument();
      expect(mocks.engine).not.toHaveBeenCalled();
    });

    it("warns when the engine already selected cannot hold the current packet", async () => {
      mocks.preview.mockResolvedValue({ ...preview, ai: { ...paid, runtime: "LOCAL_MODEL", engine: "local", engine_model: "small-4b" }, engine_fit });
      renderPanel();
      expect(await screen.findByText("The current packet does not fit: needs ~37k tokens, model context 8k. Choose another engine or narrow the Screener scope.")).toBeInTheDocument();
    });

    it("says when the server reports a model cannot run the AI Screener", async () => {
      const model_contracts = [{ model: "claude-haiku-4-5", ai_screener_compatible: false, reason: "MODEL_REQUEST_CONTRACT_UNSUPPORTED", unsupported_capability: "MODEL_NOT_IN_CAPABILITY_TABLE" }];
      const reported = engines.map((engine) => engine.id === "anthropic" ? { ...engine, model_contracts } : engine);
      mocks.preview.mockResolvedValue({ ...preview, ai: { ...paid, engines: reported }, engine_fit });
      renderPanel();
      const select = await screen.findByRole("combobox", { name: "Engine/model" });
      const text = "cannot run the AI Screener (MODEL_REQUEST_CONTRACT_UNSUPPORTED: MODEL_NOT_IN_CAPABILITY_TABLE)";
      expect(within(select).getByRole("option", { name: `Anthropic Claude · claude-haiku-4-5 · paid · ${text}` })).toBeInTheDocument();
      expect(screen.getByText(`The selected model ${text}. Choose another model.`)).toBeInTheDocument();
    });
  });

  it("previews the bounded scope but never runs inference on open", async () => {
    mocks.preview.mockResolvedValue(preview);
    renderPanel();
    expect(await screen.findByRole("button", { name: "Run AI Screener" })).toBeInTheDocument();
    expect(mocks.preview).toHaveBeenCalledWith(scope, expect.any(AbortSignal));
    expect(mocks.run).not.toHaveBeenCalled();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("shows the stage the server is in with measured time, then the result once the server has it", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue(trackedRun());
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    const progress = await screen.findByRole("region", { name: "AI Screener run progress" });
    expect(progress).toHaveTextContent("Running · batch 2 of 3 · model call · 7.0s in this stage · candidate.v1 · 4,630 rows · 150 eligible · 50 AI-evaluated · 1 of 3 batches done · 8.0s in total");
    expect(progress).toHaveTextContent("typical 11s from 3 measured calls · request times out at 45s");
    // No budget wrapped this engine and the comparison has not begun: neither stage is claimed.
    expect(progress).toHaveTextContent("Budget held for the whole runnot needed");
    expect(progress).toHaveTextContent("Comparing batch finalists—");
    expect(progress.querySelector('[aria-current="step"]')).toHaveTextContent("Model batches7.0s · 1 of 3 done");
    // Counts only: nothing is extrapolated into a percentage while the run is in progress.
    expect(progress).not.toHaveTextContent("%");
    expect(screen.getByRole("button", { name: "Stop run" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Running AI Screener…" })).toBeDisabled();
    expect(screen.queryByRole("region", { name: "AI Screener result" })).toBeNull();
    finish(finishedRun({ ...result, valid_until: "2099-01-01T00:00:00Z" }));
    const shown = await screen.findByRole("region", { name: "AI Screener result" }, { timeout: 3_000 });
    expect(shown).toHaveTextContent("Run took 12.3s on the server");
    expect(screen.queryByRole("region", { name: "AI Screener run progress" })).toBeNull();
    expect(screen.getByRole("button", { name: "Run AI Screener" })).toBeEnabled();
    expect(mocks.post).toHaveBeenCalledTimes(1);
  });

  it("re-attaches to a run already in progress after a reload without starting anything", async () => {
    mocks.preview.mockResolvedValue(preview);
    server.active = trackedRun({ stage: "ELIGIBILITY", stages: [stage("ENUMERATION", 40), stage("ELIGIBILITY", 2_500)], typical_latency_ms: null, typical_latency_samples: 0,
      progress: { universe_count: 4_630 } });
    renderPanel();
    expect(await screen.findByRole("region", { name: "AI Screener run progress" })).toHaveTextContent("Running · checking evidence 2.5s · candidate.v1 · 4,630 rows");
    expect(await screen.findByRole("button", { name: "Running AI Screener…" })).toBeDisabled();
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("joins the run in progress instead of starting a second one", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue(trackedRun({ joined: true }));
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    expect(await screen.findByText("Joined the run already in progress; no second run was started.")).toBeInTheDocument();
  });

  it("names a failed run by its stage and stable code", async () => {
    mocks.preview.mockResolvedValue(preview);
    server.latest = trackedRun({ state: "FAILED", stage: null, error: { code: "MARKET_SNAPSHOT_UNAVAILABLE", stage: "ENUMERATION" } });
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent("AI Screener run failed while reading every screener row · MARKET_SNAPSHOT_UNAVAILABLE. No result was recorded. Retry explicitly.");
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("states that a run assesses the whole matched universe, not a capped intake", async () => {
    mocks.preview.mockResolvedValue({ ...preview, matched_count: 4_630 });
    renderPanel();
    expect(await screen.findByText(/4,630 matched · a run assesses every matched row and sends each eligible row to the model in batches of up to 50/)).toBeInTheDocument();
    expect(screen.queryByText(/intake capped/)).toBeNull();
  });

  it("a finished full-universe run shows its accounting, why rows were not evaluated, and its receipts on request", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue({ ...result, valid_until: "2099-01-01T00:00:00Z", intake_count: 150,
      universe_coverage: coverage({ reason: "FINALISTS_EXCLUDED_AT_FINAL_CUTOFF", reduction: { rounds_planned: 1, rounds_completed: 1, finalists_excluded_count: 1 } }),
      candidates: [{ instrument_id: "EQ:A", rank: 1, rationale: "Review admitted observations.", supporting_refs: [], conflicting_refs: [], weak_refs: [], missing_capabilities: [], uncertainties: [] }] });
    mocks.receipts.mockResolvedValue({ schema_version: "screener-ai-screener-coverage/1.0.0", run_id: "track-run-1", unfinished_calls: [],
      calls: [{ call_id: "BATCH_INFERENCE:0:0", stage: "BATCH_INFERENCE", round: null, index: 0, of: 3, outcome: "COMPLETED", state: "CURRENT", reason: null,
        evidence_cutoff: "2026-10-02T15:00:01Z", instrument_ids: ["EQ:A", "EQ:B"], selected: [{ instrument_id: "EQ:A", rank: 1 }], tokens_input: 1_000, tokens_output: 100 }],
      rows: { phase: "FINAL", class: null, total: 4_630, offset: 0, limit: 500, items: [{ instrument_id: "EQ:Z", class: "EVIDENCE_STALE", reasons: ["STALE"] },
        { instrument_id: "EQ:A", class: "AI_EVALUATED", reasons: [] }] } });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    const summary = await screen.findByRole("region", { name: "AI Screener coverage" });
    expect(summary).toHaveTextContent("Final · every eligible row was evaluated and the finalists were compared globally");
    expect(summary).toHaveTextContent("4,630 rows · 4,630 assessed · 150 eligible · 150 AI-evaluated (100% of eligible) · batch 3 of 3 · 2 batch finalists · 4 model calls");
    expect(summary).toHaveTextContent("Not evaluated: 12 ineligible · 4,468 evidence missing, stale or unavailable · 0 eligible but not processed.");
    expect(summary).toHaveTextContent("the plan needed 150k tokens and 4 requests · 160k tokens and 26 requests were available · used 44k tokens");
    expect(summary).toHaveTextContent("EVIDENCE_STALE:STALE · 4,468");
    expect(summary).toHaveTextContent("1 batch finalist was left out of the final comparison: no admissible current evidence at that cutoff.");
    expect(mocks.receipts).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Batch receipts and rows not evaluated"));
    expect(await screen.findByText(/Batch 1 of 3 · 2 rows · COMPLETED · CURRENT · cutoff 2026-10-02T15:00:01Z · 1 selected/)).toBeInTheDocument();
    expect(screen.getByText("EQ:Z · EVIDENCE_STALE · STALE")).toBeInTheDocument();
    expect(screen.getByText("Rows the model did not evaluate: showing 2 of 4,630.")).toBeInTheDocument();
    expect(mocks.receipts).toHaveBeenCalledWith("track-run-1", expect.any(AbortSignal));
    // A completed global selection is the only result that offers an Action Decision.
    expect(screen.getByRole("heading", { name: /#1 EQ:A/ })).toBeInTheDocument();
  });

  it("a run that did not finish is labelled partial, lists finalists as provisional, and offers no Action Decision", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue({ ...result, state: "INCOMPLETE", reason: "PROVISIONAL_PARTIAL_COVERAGE", valid_until: "2026-10-02T15:00:00Z", intake_count: 100,
      limitations: ["This run did not finish. Listed finalists are provisional and are not a global selection."],
      universe_coverage: coverage({ status: "PROVISIONAL_PARTIAL_COVERAGE", reason: "BATCH_FAILED:ANTHROPIC_OVERLOADED_ERROR", ai_evaluated_count: 100, ai_coverage_pct: 66.67,
        batches_completed: 2, model_calls: 3, finalist_count: 1, selected_count: 0, coverage_complete: false, selection_complete: false,
        counts: { evaluated: 100, ineligible: 12, evidence_blocked: 4_468, unprocessed: 50, by_class: {}, reasons: { "UNPROCESSED:BATCH_FAILED:ANTHROPIC_OVERLOADED_ERROR": 50 } } }),
      provisional: [{ instrument_id: "EQ:P", batch: 1, rank_in_batch: 1, rationale: "Review admitted observations.", evidence_cutoff: "2026-10-02T15:00:01Z", valid_until: "2026-10-02T15:01:01Z" }] });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    const summary = await screen.findByRole("region", { name: "AI Screener coverage" });
    expect(summary).toHaveTextContent("Partial · the run did not finish; this is not a search of the whole universe · BATCH_FAILED:ANTHROPIC_OVERLOADED_ERROR");
    expect(summary).toHaveTextContent("100 AI-evaluated (66.67% of eligible) · batch 2 of 3");
    expect(summary).toHaveTextContent("50 eligible but not processed");
    expect(screen.getByText(/This run did not finish, so it is not a selection from the whole universe\./)).toBeInTheDocument();
    const provisional = screen.getByRole("region", { name: "Provisional batch finalists" });
    expect(provisional).toHaveTextContent("Provisional · 1 batch finalist from the batches that finished. This run did not finalize a global selection, so these finalists cannot be evaluated for action.");
    expect(provisional).toHaveTextContent("EQ:P · batch 1 rank 1");
    expect(screen.queryByRole("heading", { name: /#1/ })).toBeNull();
    expect(screen.queryByText("Evidence expired — rerun AI Screener.")).toBeNull();
    expect(screen.queryByRole("button", { name: /Evaluate/ })).toBeNull();
  });

  it("Stop asks the server once and says the call in flight is finishing", async () => {
    mocks.preview.mockResolvedValue(preview);
    server.active = trackedRun();
    mocks.stop.mockImplementation(async () => { server.active = trackedRun({ stop_requested: true }); return server.active; });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Stop run" }));
    await waitFor(() => expect(mocks.stop).toHaveBeenCalledWith("track-1"));
    expect(await screen.findByRole("button", { name: "Stopping after the call in flight…" }, { timeout: 3_000 })).toBeDisabled();
    expect(await screen.findByRole("region", { name: "AI Screener run progress" })).toHaveTextContent("Stopping after the call in flight · batch 2 of 3");
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("keeps a result for the same query after the Screener list refreshes, and says so", async () => {
    mocks.preview.mockResolvedValue(preview);
    finish(finishedRun({ ...result, valid_until: "2099-01-01T00:00:00Z", result_set: "set-1", scope: { ...scope, result_set: "set-1" } as AiScreenerResult["scope"] }));
    renderPanel(selection({ screenerScope: { ...scope, result_set: "set-2" } }));
    expect(await screen.findByRole("region", { name: "AI Screener result" })).toHaveTextContent("the Screener list has refreshed since; this result is as of its cutoff");
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("never draws the latest result under a different Screener query", async () => {
    mocks.preview.mockResolvedValue(preview);
    finish(finishedRun({ ...result, valid_until: "2099-01-01T00:00:00Z", scope: { ...scope, search: "B" } as AiScreenerResult["scope"] }));
    renderPanel();
    expect(await screen.findByText("The latest run answered a different Screener scope (US_EQUITIES). Run AI Screener to answer this one.")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "AI Screener result" })).toBeNull();
    expect(mocks.detail).not.toHaveBeenCalled();
  });

  it("does not render a result that arrives after the scope changes", async () => {
    mocks.preview.mockResolvedValue(preview);
    let resolveRun: (value: AiScreenerResult) => void = () => undefined;
    mocks.run.mockReturnValue(new Promise<AiScreenerResult>((resolve) => { resolveRun = resolve; }));
    const view = renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    const nextScope = { ...scope, search: "B" };
    view.rerender(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <SpecialistContext.Provider value={selection({ screenerScope: nextScope })}><AiScreenerPanel api={panelApi} /></SpecialistContext.Provider>
    </QueryClientProvider>);
    resolveRun(result);
    await waitFor(() => expect(screen.queryByText(/CURRENT · inference\.test/)).toBeNull());
  });

  it("shows blocked evidence and opens an outside-page candidate without a selected row", async () => {
    mocks.preview.mockResolvedValue(preview);
    const openInstrument = vi.fn();
    mocks.run.mockResolvedValue({ ...result, valid_until: "2099-01-01T00:00:00Z", evidence: [{
      instrument: { instrument_id: "EQ:OUTSIDE" }, current_market_evidence: [], reference_evidence: [],
      blocked: [{ capability: "ORDER_FLOW", reason_codes: ["AGE_EXCEEDS_POLICY"] }], missing: [], weak: [], sufficient: true,
    }], candidates: [{ instrument_id: "EQ:OUTSIDE", rank: 1, rationale: "Admitted observations warrant review.", supporting_refs: [],
      conflicting_refs: [], weak_refs: [], missing_capabilities: [], uncertainties: ["Coverage is limited."] }] });
    renderPanel(selection({ row: null, openInstrument }));
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    expect(await screen.findByText(/ORDER_FLOW.*AGE_EXCEEDS_POLICY/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open in Screener workflow" }));
    expect(openInstrument).toHaveBeenCalledWith("EQ:OUTSIDE");
  });

  it("withdraws expired evidence without running another inference", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue({ ...result, valid_until: new Date(Date.now() + 1000).toISOString() });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    await screen.findByRole("region", { name: "AI Screener result" });
    expect(await screen.findByText("Evidence expired — rerun AI Screener.", {}, { timeout: 2500 })).toBeInTheDocument();
    expect(mocks.run).toHaveBeenCalledTimes(1);
  });

  it("reports a failed explicit run", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockRejectedValue(new Error("network unavailable"));
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("AI Screener run failed");
  });
});

describe("AI Screener trade lifecycle", () => {
  const selected = { ...result, valid_until: "2099-01-01T00:00:00Z", evidence: [{ instrument: { instrument_id: "AAPL" }, current_market_evidence: [], reference_evidence: [], blocked: [], missing: [], weak: [], sufficient: true }],
    candidates: [{ instrument_id: "AAPL", rank: 1, rationale: "AAPL shows observed strength.", supporting_refs: [], conflicting_refs: [], weak_refs: [], missing_capabilities: [], uncertainties: [] }] } as unknown as AiScreenerResult;
  const run = (id: string) => ({ run_id: id, state: "CURRENT", valid_until: "2099-01-01T00:00:00Z", selected_count: 1 });

  it("shows managed positions before any AI run and never calls a model to do it", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.lifecycles.mockResolvedValue(lifecycleList({ active_managed: [openPosition({ group: "ACTIVE_MANAGED" })], counts: { selected: 0, active_managed: 1, recent_closed: 0, unlinked: 0 } }));
    renderPanel();
    const active = await screen.findByRole("region", { name: "Active managed positions" });
    expect(active).toHaveTextContent("POSITION OPEN · HOLD");
    expect(active).toHaveTextContent("LONG 6");
    expect(screen.getByTestId("lifecycle-boundary")).toHaveTextContent("Market data: LIVE OBSERVATIONAL · Execution: SIMULATED PAPER");
    expect(mocks.lifecycles).toHaveBeenCalledWith(null, expect.any(AbortSignal));
    expect(mocks.run).not.toHaveBeenCalled();
  });

  it("renders each selected candidate as its lifecycle with one list request per run", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue(selected);
    mocks.lifecycles.mockImplementation(async (id: string | null) => id ? lifecycleList({ run: run(id), selected: [lifecycle()], counts: { selected: 1, active_managed: 0, recent_closed: 0, unlinked: 0 } }) : lifecycleList());
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    const card = await screen.findByTestId("lifecycle-card-AAPL");
    expect(card).toHaveTextContent("ENTER DECIDED · NOT EXECUTED");
    expect(card).toHaveTextContent("2 supporting · 2 conflicting · 0 weak · 1 missing · 1 blocked");
    expect(screen.getByRole("button", { name: "Open decision assessment" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open in Screener workflow" })).toBeInTheDocument();
    expect(mocks.lifecycles.mock.calls.filter(([id]) => id === "run-1")).toHaveLength(1);
    expect(mocks.lifecycle).not.toHaveBeenCalled();
  });

  it("never draws a previous run's lifecycle under a new rank list", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.run.mockResolvedValue({ ...selected, run_id: "run-2" });
    // A stale projection for run-1 arrives for the run-2 request.
    mocks.lifecycles.mockResolvedValue(lifecycleList({ run: run("run-1"), selected: [openPosition()], counts: { selected: 1, active_managed: 0, recent_closed: 0, unlinked: 0 } }));
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
    expect(await screen.findByRole("heading", { name: "#1 AAPL" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.lifecycles).toHaveBeenCalledWith("run-2", expect.any(AbortSignal)));
    expect(await screen.findByText("Loading lifecycle…")).toBeInTheDocument();
    expect(screen.queryByTestId("lifecycle-card-AAPL")).not.toBeInTheDocument();
    expect(screen.queryByText(/POSITION OPEN/)).not.toBeInTheDocument();
  });

  it("fails visibly when the lifecycle payload does not match this build", async () => {
    mocks.preview.mockResolvedValue(preview);
    mocks.lifecycles.mockRejectedValue(new SchemaMismatchError("/screener/trade-lifecycles", []));
    renderPanel();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Trade lifecycle is unavailable");
    expect(alert).toHaveTextContent("did not match the format this build expects");
  });
});


it("displays the exact current price, provider, observation and receive clocks used by AI", async () => {
  mocks.preview.mockResolvedValue(preview);
  const evidence = { evidence_id: "EV:PRICE", capability: "QUOTE", instrument_id: "NVDA", role: "CURRENT_MARKET",
    source: "MOOMOO_OPEND", as_of: "2026-10-06T18:05:23Z", received_at: "2026-10-06T18:05:23.500Z",
    delivery_mode: "REALTIME", freshness_status: "CURRENT", decision_admissibility: "ADMISSIBLE",
    valid_until: "2099-01-01T00:00:00Z", weak_reasons: [], facts: { price: 240.27, bid: 240.26, ask: 240.28 } };
  mocks.run.mockResolvedValue({ ...result, valid_until: "2099-01-01T00:00:00Z", evidence: [{
    instrument: { instrument_id: "NVDA" }, current_market_evidence: [evidence], reference_evidence: [],
    blocked: [], missing: [], weak: [], sufficient: true,
  }], candidates: [{ instrument_id: "NVDA", rank: 1, rationale: "Observed evidence for review.", supporting_refs: ["EV:PRICE"],
    conflicting_refs: [], weak_refs: [], missing_capabilities: [], uncertainties: [] }] });
  renderPanel();
  fireEvent.click(await screen.findByRole("button", { name: "Run AI Screener" }));
  expect(await screen.findByText("$240.27")).toBeInTheDocument();
  expect(screen.getByText("MOOMOO_OPEND")).toBeInTheDocument();
  expect(screen.getByText("2026-10-06T18:05:23Z")).toBeInTheDocument();
  expect(screen.getByText("2026-10-06T18:05:23.500Z")).toBeInTheDocument();
  expect(screen.getByText("CURRENT · ADMISSIBLE · CURRENT_MARKET")).toBeInTheDocument();
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AiScreenerPanel from "./AiScreenerPanel";
import { SpecialistContext, type SpecialistSelection } from "./shared";
import type { AiScreenerPreview, AiScreenerResult } from "../../../api/screenerAi";
import { SchemaMismatchError } from "../../../api/fetchJson";
import { lifecycle, lifecycleList, openPosition } from "../lifecycle/lifecycleFixture";

const mocks = vi.hoisted(() => ({ preview: vi.fn(), run: vi.fn(), engine: vi.fn(), lifecycles: vi.fn(), lifecycle: vi.fn() }));
vi.mock("../../../api/screenerLifecycle", () => ({ tradeLifecycles: mocks.lifecycles, tradeLifecycle: mocks.lifecycle }));
vi.mock("../../../api/screenerAi", () => ({ fetchAiScreenerPreview: mocks.preview, postAiScreener: mocks.run }));
vi.mock("../../../api/screenerNews", () => ({ postSynthesisEngine: mocks.engine }));

const scope = { universe: "US_EQUITIES" as const, search: "A", sort: "volume", descending: true, filters: [] };
const ai = { state: "AVAILABLE" as const, reason: null, provider_id: "inference.test", model_id: "candidate.v1",
  runtime: "LOCAL_MODEL" as const, engine: "local", engine_model: "candidate.v1", engines: [] };
const preview = { schema_version: "screener-ai-screener-preview/1.0.0" as const, ai, scope, matched_count: 4,
  intake_count: 4, max_intake: 20, estimate: null, evidence_summary: { sufficient: 1, blocked: 0, missing: 0, weak: 0 },
  decision_cutoff: "2026-10-02T15:00:00Z", result_set: null } as AiScreenerPreview;
const result = { schema_version: "screener-ai-screener/1.0.0" as const, state: "CURRENT", reason: null, scope,
  matched_count: 4, intake_count: 4, max_intake: 20, result_set: null, run_id: "run-1", decision_cutoff: "2026-10-02T15:00:00Z",
  generated_at: "2026-10-02T15:00:00Z", valid_until: "2026-10-02T15:05:00Z", input_hash: "hash", provider_id: "inference.test",
  model_id: "candidate.v1", runtime: "LOCAL_MODEL", prompt_id: "p", prompt_version: "1", prompt_hash: "ph", packet_bytes: 1,
  cache: "MISS" as const, simulated: true, tokens_input: null, tokens_output: null, latency_ms: 1, evidence: [], candidates: [],
  limitations: ["No candidate selected."], coverage: {} } as AiScreenerResult;

const panelApi = { isVisible: true, onDidVisibilityChange: () => ({ dispose: () => undefined }) } as never;
const selection = (overrides: Partial<SpecialistSelection> = {}): SpecialistSelection => ({
  row: null, universe: "US_EQUITIES", supportedPanels: new Set(["ai_screener"]), settledId: null, quote: undefined, filters: [],
  screenerScope: scope, openInstrument: vi.fn(), demand: null, actions: { close: vi.fn(), move: vi.fn(), resize: vi.fn() }, ...overrides,
});
const renderPanel = (value = selection()) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><SpecialistContext.Provider value={value}><AiScreenerPanel api={panelApi} /></SpecialistContext.Provider></MemoryRouter>
</QueryClientProvider>);

beforeEach(() => { mocks.lifecycles.mockResolvedValue(lifecycleList()); });
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
  it("previews the bounded scope but never runs inference on open", async () => {
    mocks.preview.mockResolvedValue(preview);
    renderPanel();
    expect(await screen.findByRole("button", { name: "Run AI Screener" })).toBeInTheDocument();
    expect(mocks.preview).toHaveBeenCalledWith(scope, expect.any(AbortSignal));
    expect(mocks.run).not.toHaveBeenCalled();
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

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import AiScreenerPanel from "./AiScreenerPanel";
import { SpecialistContext, type SpecialistSelection } from "./shared";
import type { AiScreenerPreview, AiScreenerResult } from "../../../api/screenerAi";

const mocks = vi.hoisted(() => ({ preview: vi.fn(), run: vi.fn(), engine: vi.fn() }));
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
  <SpecialistContext.Provider value={value}><AiScreenerPanel api={panelApi} /></SpecialistContext.Provider>
</QueryClientProvider>);

afterEach(() => vi.clearAllMocks());

describe("AI Screener panel", () => {
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

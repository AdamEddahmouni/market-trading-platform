import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PreviewSqueeze } from "../components/screener/squeeze/PreviewSqueeze";
import { SqueezeLifecycle } from "../components/squeeze/SqueezeLifecycle";
import { MetricList } from "../components/screener/squeeze/SqueezeEvidence";
import ShortSqueezePanel from "../components/screener/panels/ShortSqueezePanel";
import { SpecialistContext, type SpecialistSelection } from "../components/screener/panels/shared";
import { fetchScreenerSqueeze, SqueezeSchema } from "./screenerSqueeze";

const metric = (extra: Record<string, unknown> = {}) => ({ id: "short_float_pct", label: "Short float", value: 24.8,
  unit: "percent", source: "FINVIZ_ELITE", source_label: "Finviz", quality: "SNAPSHOT",
  clock: { kind: "SNAPSHOT", as_of: "2026-09-27T16:00:00Z" }, reason: null, note: null, detail: {}, ...extra });
export const squeezePayload = (extra: Record<string, unknown> = {}) => ({
  schema_version: "screener-squeeze/1.0.0", generated_at: "2026-09-27T16:00:00Z", instrument_id: "AAPL",
  universe: "US_EQUITIES", symbol: "AAPL", company: "Apple Inc", view: "summary", market_session: "CLOSED",
  capability: { TEMPORAL_LIFECYCLE: "NOT_SUPPORTED" }, source_state: "PARTIAL",
  assessment: { model: "imp_squeeze_snapshot.v1", adapted_from: "squeeze_causal_baseline.v4",
    rule_policy: "phase_3a_transparent_candidate_policy.v1", state: "VULNERABLE", state_basis: "SNAPSHOT_ASSESSMENT",
    trigger: "SHORT_FLOAT_ELEVATED", transition: null, hysteresis: "NOT_APPLIED_NO_STATE_HISTORY",
    lifecycle: [
      { state: "BASELINE", current: false, reachable: true, unreachable_reason: null },
      { state: "VULNERABLE", current: true, reachable: true, unreachable_reason: null },
      { state: "ACTIVE_SQUEEZE", current: false, reachable: false, unreachable_reason: "Dealer positioning unavailable" },
    ], rules: [], supporting: [], contradicting: [], context: [], missing: ["BORROW"], mechanism_labels: [],
    quality_flags: [], classes_supporting: ["SHORT_CROWDING"], probability: null, score: null },
  sections: { structural_pressure: [metric(), metric({ id: "borrow_fee", label: "Borrow fee", value: null,
    source: "LENDING", source_label: "Securities lending", quality: "NOT_CONFIGURED", clock: { kind: "PROVIDER", as_of: null }, reason: "NO_LENDING_SOURCE" })],
    ignition: [metric({ id: "change_pct", label: "Change", value: 12.4 })],
    live_confirmation: [metric({ id: "order_flow_net", label: "Net aggressor volume", value: null, quality: "NOT_SUBSCRIBED",
      source: "MOOMOO_TRADES", source_label: "Moomoo trades", clock: { kind: "STREAMING", as_of: null }, reason: "NOT_SUBSCRIBED" })],
    exhaustion: { evidence: [], temporal: "NOT_EVALUATED_NO_STATE_HISTORY", note: "No state history" } },
  headlines: [], evidence: { supporting: [], conflicting: [], context: [], missing: [{ code: "BORROW", label: "Borrow fee / availability", reason: "NO_LENDING_SOURCE" }] },
  coverage: { supporting: 0, conflicting: 0, unavailable: 2, stale: 0, pending: 0 },
  sources: [{ id: "FINVIZ_ELITE", label: "Finviz", state: "SNAPSHOT", clock_kind: "SNAPSHOT", as_of: "2026-09-27T16:00:00Z", reason: null }],
  why_listed: { state: "MATCHED", items: [{ filter_id: "sf", field: "short_float_pct", label: "Short Float", operator: "gt",
    value: 20, observed: 24.8, passed: true, missing: false, text: "Short Float 24.8% is above 20%" }] },
  discovery_thresholds: { SHORT_FLOAT_ELEVATED: { value: 20, operator: "gt", source: "IMP SHORT_SQUEEZE_DISCOVERY" } },
  historical_context: null, disclaimer: "Current snapshot evidence only; no trade instruction.", ...extra,
});

const row = { instrument: { instrument_id: "AAPL", venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol: "AAPL",
  company: "Apple Inc", sector: null, industry: null, fields: {} } as never;
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
const actions = { close: vi.fn(), move: vi.fn(), resize: vi.fn() };
const selection = (overrides: Partial<SpecialistSelection> = {}): SpecialistSelection => ({ row,
  settledId: "AAPL", universe: "US_EQUITIES", quote: undefined, filters: [], supportedPanels: new Set(["short_squeeze"]),
  demand: null, actions, ...overrides });
const panelApi = { isVisible: true, onDidVisibilityChange: () => ({ dispose: () => undefined }) } as never;

describe("S8 selected-instrument presentation", () => {
  it("shows only supported lifecycle steps as potentially reachable", () => {
    const assessment = SqueezeSchema.parse(squeezePayload()).assessment;
    render(createElement(SqueezeLifecycle, { state: assessment.state, stages: assessment.lifecycle }));
    expect(screen.getByText("Vulnerable").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Active squeeze evidence").closest("li")).toHaveTextContent("Unavailable");
  });

  it("keeps a publication trade date on its calendar day", () => {
    const publication = SqueezeSchema.parse(squeezePayload({ sections: {
      ...squeezePayload().sections, structural_pressure: [metric({ id: "threshold_status", label: "Reg SHO threshold list",
        value: false, unit: "boolean", source: "REG_SHO", source_label: "Reg SHO lists",
        quality: "PUBLICATION_CURRENT", clock: { kind: "DAILY_LIST", as_of: "2026-09-25" } })],
    } })).sections.structural_pressure;
    render(createElement(MetricList, { title: "Structural pressure", items: publication }));
    expect(screen.getByText(/Sep 25, 2026 trade date/)).toBeInTheDocument();
  });

  it("requests preview only after a settled selection and keeps it compact", async () => {
    respond(squeezePayload());
    const queryClient = client();
    const renderPreview = (settledId: string | null) => createElement(QueryClientProvider, { client: queryClient },
      createElement(PreviewSqueeze, { row, settledId, filters: [], onOpenPanel: vi.fn() }));
    const view = render(renderPreview(null));
    expect(fetch).not.toHaveBeenCalled();
    view.rerender(renderPreview("NVDA"));
    expect(fetch).not.toHaveBeenCalled();
    view.rerender(renderPreview("AAPL"));
    expect(await screen.findByText("Short Float 24.8% is above 20%")).toBeInTheDocument();
    expect(document.querySelector(".screener-squeeze-coverage")).toHaveTextContent("Unavailable 2");
    expect(screen.getByRole("button", { name: "Open Short Squeeze Panel" })).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("shows partial evidence and source clocks in the dock panel", async () => {
    respond(squeezePayload({ view: "detail" }));
    render(createElement(QueryClientProvider, { client: client() }, createElement(SpecialistContext.Provider,
      { value: selection() }, createElement(ShortSqueezePanel, { api: panelApi } as never))));
    expect(await screen.findByText("Short Float 24.8% is above 20%")).toBeInTheDocument();
    expect(screen.getByText("Borrow fee")).toBeInTheDocument();
    expect(screen.getAllByText(/Finviz · snapshot · snapshot/).length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: "Short Squeeze for AAPL" })).toBeInTheDocument();
    expect(screen.getByText("Borrow fee / availability · no lending source")).toBeInTheDocument();
  });

  it("never requests selected squeeze detail for Futures", async () => {
    respond(squeezePayload({ view: "detail" }));
    render(createElement(QueryClientProvider, { client: client() }, createElement(SpecialistContext.Provider,
      { value: selection({ universe: "FUTURES" }) }, createElement(ShortSqueezePanel, { api: panelApi } as never))));
    expect(screen.getByText("Short Squeeze evidence is available for US equities only.")).toBeInTheDocument();
    await waitFor(() => expect(fetch).not.toHaveBeenCalled());
  });

  it("does not render an old panel response under a new selected ticker", async () => {
    let resolveOld: (value: Response) => void = () => undefined;
    vi.stubGlobal("fetch", vi.fn((url: string) => String(url).includes("instrument=AAPL")
      ? new Promise<Response>((resolve) => { resolveOld = resolve; })
      : Promise.resolve(new Response(JSON.stringify(squeezePayload({ instrument_id: "NVDA", symbol: "NVDA", view: "detail" })), { status: 200 }))));
    const queryClient = client();
    const renderPanel = (value: SpecialistSelection) => createElement(QueryClientProvider, { client: queryClient },
      createElement(SpecialistContext.Provider, { value }, createElement(ShortSqueezePanel, { api: panelApi } as never)));
    const view = render(renderPanel(selection()));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const nvda = { ...row, instrument: { instrument_id: "NVDA", venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol: "NVDA" } as never;
    view.rerender(renderPanel(selection({ row: nvda, settledId: "NVDA" })));
    expect(await screen.findByRole("region", { name: "Short Squeeze for NVDA" })).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    resolveOld(new Response(JSON.stringify(squeezePayload({ view: "detail" })), { status: 200 }));
    await waitFor(() => expect(screen.getByRole("region", { name: "Short Squeeze for NVDA" })).toBeInTheDocument());
    expect(screen.queryByRole("region", { name: "Short Squeeze for AAPL" })).toBeNull();
  });
});
const respond = (body: unknown) => vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })));
afterEach(() => vi.unstubAllGlobals());

describe("S8 squeeze API contract", () => {
  it("keeps source clocks, missing values, and exact Screener predicates", async () => {
    respond(squeezePayload());
    const result = await fetchScreenerSqueeze("AAPL", { universe: "US_EQUITIES", view: "summary",
      filters: [{ id: "sf", field: "short_float_pct", operator: "gt", value: 20 }] });
    expect(result.sections.structural_pressure[1].value).toBeNull();
    expect(result.sections.structural_pressure[1].clock.kind).toBe("PROVIDER");
    expect(result.why_listed.items[0].observed).toBe(24.8);
    expect(String(vi.mocked(fetch).mock.calls[0][0])).toContain("filters=");
  });
  it("rejects another instrument, view, or unsupported schema before rendering", async () => {
    for (const body of [squeezePayload({ instrument_id: "NVDA" }), squeezePayload({ view: "detail" }),
      squeezePayload({ schema_version: "screener-squeeze/2.0.0" })]) {
      respond(body);
      await expect(fetchScreenerSqueeze("AAPL", { universe: "US_EQUITIES", view: "summary" })).rejects.toThrow();
    }
  });
  it("rejects fabricated scores, invalid clocks, and a falsely current unreachable state", () => {
    const base = squeezePayload();
    expect(SqueezeSchema.safeParse(base).success).toBe(true);
    expect(SqueezeSchema.safeParse({ ...base, assessment: { ...base.assessment, score: 70 } }).success).toBe(false);
    expect(SqueezeSchema.safeParse({ ...base, sections: { ...base.sections, structural_pressure: [metric({ clock: { kind: "LIVE", as_of: null } })] } }).success).toBe(false);
    expect(SqueezeSchema.safeParse({ ...base, assessment: { ...base.assessment, state: "ACTIVE_SQUEEZE" } }).success).toBe(false);
  });
});

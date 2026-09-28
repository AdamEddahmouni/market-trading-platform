import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "./ScreenerPage";
import { classifyZones } from "./srClassify";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), save: vi.fn(), remove: vi.fn(), last: vi.fn(),
  preview: vi.fn(), squeeze: vi.fn(), layout: vi.fn(), priceLines: [] as number[],
}));
vi.mock("../../api/screener", () => ({
  fetchScreener: mocks.fetch, fetchScreenerConfig: mocks.config, saveScreenerScreen: mocks.save,
  deleteScreenerScreen: mocks.remove, persistLastScreenerConfig: mocks.last, updateScreenerWindow: mocks.window,
  releaseScreenerWindow: mocks.release, releaseScreenerWindowOnUnload: mocks.release,
  fetchScreenerPreview: mocks.preview, persistScreenerPreviewLayout: mocks.layout,
}));
vi.mock("../../api/screenerSqueeze", () => ({ fetchScreenerSqueeze: mocks.squeeze }));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34, scrollToIndex: vi.fn(),
  }),
}));
vi.mock("lightweight-charts", () => ({
  LineStyle: { Dashed: 2 },
  createChart: vi.fn(() => ({
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(), createPriceLine: vi.fn((options: { price: number }) => { mocks.priceLines.push(options.price); return options; }),
      removePriceLine: vi.fn(),
    })),
    timeScale: vi.fn(() => ({ setVisibleLogicalRange: vi.fn(), fitContent: vi.fn() })),
    applyOptions: vi.fn(), remove: vi.fn(),
  })),
}));

const field = (value: number | null) => ({ value, source: "FINVIZ_ELITE", state: value === null ? "UNAVAILABLE" : "SNAPSHOT", as_of: "2026-09-25T15:00:00Z" });
const makeRow = (symbol: string, company: string, price: number, change: number) => ({
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY" },
  symbol, company, sector: "Technology", industry: "Software",
  fields: { price: field(price), change_pct: field(change), volume: field(1000), rel_volume: field(3) },
});
const rows = [makeRow("AAPL", "Apple Inc", 12, 2), makeRow("MSFT", "Microsoft Corp", 20, -3)];
const payload = {
  schema_version: "screener/1.0.0", universe: "US_EQUITIES", generated_at: "2026-09-25T15:00:00Z",
  universe_as_of: "2026-09-25T15:00:00Z", screener_as_of: "2026-09-25T15:00:00Z", market_session: "REGULAR",
  source_error: null, provider_health: [{ provider: "FINVIZ_ELITE", state: "HEALTHY", reason: null }],
};
const bar = (index: number, close: number) => ({ time: 1_790_000_000 + index * 300, start: "2026-09-25T14:00:00Z", end: "2026-09-25T14:05:00Z",
  open: close, high: close + 0.1, low: close - 0.1, close, volume: 100, session: "REGULAR" });

function preview(symbol: string, price: number, overrides: Record<string, unknown> = {}) {
  return {
    schema_version: "screener-preview/1.0.0", generated_at: "2026-09-25T15:00:00Z", market_session: "REGULAR",
    instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY", symbol, company: `${symbol} Co`, sector: "Technology", industry: "Software" },
    quote: { state: "UNAVAILABLE", fields: {} },
    key_data: [{ field: "rel_volume", label: "Relative Volume", unit: "ratio", value: 3, source: "FINVIZ_ELITE", state: "SNAPSHOT", as_of: "2026-09-25T15:00:00Z" },
      { field: "bid", label: "Bid", unit: "USD", value: null, source: null, state: "UNAVAILABLE", as_of: null }],
    bars: { timeframe: "5m", session_scope: "EXTENDED", provider: "MOOMOO_OPEND", source_id: "MOOMOO_OPEND_CUR_KLINE_1M", state: "CURRENT",
      reason: null, provider_reason: null, received_at: "2026-09-25T15:00:01Z", latest_complete_bar_end: "2026-09-25T15:00:00Z",
      bar_count: 3, bars: [bar(0, price - 1), bar(1, price), bar(2, price + 0.2)], forming: null },
    levels: { method: "AUTO_SR_V1", timeframe: "5m", session_scope: "EXTENDED", bar_state: "CURRENT", state: "AVAILABLE", reason: null, reasons: [],
      calculated_at: "2026-09-25T15:00:02Z", input_bar_count: 60, input_latest_bar_end: "2026-09-25T15:00:00Z", min_strength: 20,
      strength_semantics: "Zone strength is structural evidence, not a probability.",
      zones: [{ lower: price - 1, upper: price - 0.9, center: price - 0.95, touches: 3, strength: 55, last_touch_end_ns: 1, kinds: ["LOW"] },
        { lower: price + 0.5, upper: price + 0.6, center: price + 0.55, touches: 2, strength: 61, last_touch_end_ns: 1, kinds: ["HIGH"] }],
      price: { value: price, source: "LAST_BAR_CLOSE", state: "CURRENT", as_of: "2026-09-25T15:00:00Z" },
      support: null, resistance: null, testing: null },
    why: {
      matched: { state: "MATCHED", items: [{ filter_id: "r", label: "Relative Volume", passed: true, missing: false, text: `${symbol} Relative Volume 3.00× is above 2.00×` }] },
      moving: { headline_window_start: "2026-09-24T20:00:00Z", items: [
        { class: "OBSERVED", kind: "PRICE_MOVE", text: "Change +2.00% on the session", source: "FINVIZ_ELITE", as_of: null },
        { class: "DERIVED", kind: "RELATIVE_VOLUME", text: "Relative volume 3.00× versus average volume", source: "FINVIZ_ELITE", as_of: null },
        { class: "INSUFFICIENT_EVIDENCE", kind: "CAUSATION", text: "No verified catalyst or causal driver identified from currently available evidence", source: "IMP", as_of: null }] },
    },
    futures: { mapping_version: "FUTURES_CONTEXT_MAP_V1", causal_note: "Context only; futures movement is not evidence of what moved this instrument.", items: [
      { root: "NQ", name: "E-mini Nasdaq-100", relationship_type: "SECTOR", relationship_reason: "Technology/growth index context.",
        contract: { state: "CURRENT", reason: null, contract_id: "NQZ26", last_trade_date: "2026-12-18" }, quote: null,
        availability: "UNAVAILABLE", unavailable_reason: "NOT_ENTITLED" },
      { root: "ES", name: "E-mini S&P 500", relationship_type: "BROAD_MARKET", relationship_reason: "Broad US equity market context.",
        contract: { state: "CURRENT", reason: null, contract_id: "ESZ26", last_trade_date: "2026-12-18" },
        quote: { price: 6155.25, price_basis: "LAST", change_pct: 0.42, provider: "MOOMOO_OPEND", as_of: "2026-09-25T15:00:00Z", age_ms: 180, state: "LIVE" },
        availability: "AVAILABLE", unavailable_reason: null }] },
    ...overrides,
  };
}

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/screener"]}>
    <Routes><Route path="/screener" element={<ScreenerPage />} /><Route path="/workspace/:symbol" element={<div>Instrument workspace</div>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

// S1 rebuilds cell renderers when the quote window answers, remounting cell
// nodes; click only after that settles so the clicked node is attached.
async function clickRow(symbol: string) {
  await screen.findByText(symbol);
  await waitFor(() => expect(mocks.window).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
  fireEvent.click(screen.getByText(symbol, { selector: ".screener-symbol strong" }));
}

function setNarrow(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
}

describe("Screener Quick Preview", () => {
  beforeEach(() => {
    setNarrow(false);
    mocks.priceLines.length = 0;
    mocks.config.mockReset().mockResolvedValue({ schema_version: 1, persistence_available: true, catalog: [], presets: [], saved: [], last: null,
      preview_layout: { version: 1, open: true, width: 400 } });
    mocks.fetch.mockReset().mockResolvedValue({ ...payload, rows, result_count: rows.length });
    mocks.window.mockReset().mockResolvedValue({ quotes: {}, active: 0, cap: 32 });
    mocks.release.mockReset().mockResolvedValue({ released: true });
    mocks.last.mockReset().mockResolvedValue({});
    mocks.layout.mockReset().mockResolvedValue({ result: {} });
    mocks.preview.mockReset().mockImplementation(async (id: string) => preview(id, id === "AAPL" ? 12 : 20));
    mocks.squeeze.mockReset().mockImplementation(async (id: string) => ({ instrument_id: id, universe: "US_EQUITIES", symbol: id,
      assessment: { state: "BASELINE", state_basis: "SNAPSHOT_ASSESSMENT" }, source_state: "PARTIAL",
      coverage: { supporting: 0, conflicting: 0, unavailable: 2, stale: 0, pending: 0 },
      sections: { structural_pressure: [], ignition: [], live_confirmation: [] },
      why_listed: { state: "NO_ACTIVE_FILTERS", items: [] } }));
    vi.stubGlobal("crypto", { randomUUID: () => "abc-123" });
  });

  it("opens on row selection and renders chart, levels, why, key data, and futures", async () => {
    mount();
    await clickRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(within(pane).getByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith("AAPL", "5m", "EXTENDED", [], expect.anything(), "US_EQUITIES", null));
    expect(await within(pane).findByRole("img", { name: /AAPL 5m candles, 3 completed bars/ })).toBeInTheDocument();
    expect(within(pane).getByText("Auto S/R · 5m · Extended")).toBeInTheDocument();
    expect(within(pane).getByText("$11.00–11.10")).toBeInTheDocument();
    expect(within(pane).getByText("7.50% below")).toBeInTheDocument();
    expect(within(pane).getByText("$12.50–12.60")).toBeInTheDocument();
    expect(within(pane).getByText("4.17% above")).toBeInTheDocument();
    expect(within(pane).getByText(/Support zone 11.00 to 11.10, 7.50% below/)).toBeInTheDocument();
    expect(within(pane).getByText(/Levels calculated .* ET · bars to/)).toBeInTheDocument();
    expect(mocks.priceLines).toEqual(expect.arrayContaining([11.1, 11, 12.5, 12.6]));
    expect(within(pane).getByText("AAPL Relative Volume 3.00× is above 2.00×")).toBeInTheDocument();
    expect(within(pane).getByRole("heading", { name: "Observed" })).toBeInTheDocument();
    expect(within(pane).getByRole("heading", { name: "Derived" })).toBeInTheDocument();
    expect(within(pane).getByRole("heading", { name: "Insufficient evidence" })).toBeInTheDocument();
    expect(within(pane).getByText(/No verified catalyst or causal driver/)).toBeInTheDocument();
    fireEvent.click(within(pane).getByRole("tab", { name: "Key Data" }));
    expect(within(pane).getByText("3.00×")).toBeInTheDocument();
    fireEvent.click(within(pane).getByRole("tab", { name: "Futures" }));
    expect(within(pane).getByText("NQZ26")).toBeInTheDocument();
    expect(within(pane).getByText("Technology/growth index context.")).toBeInTheDocument();
    expect(within(pane).getByText(/Price unavailable · No futures quote entitlement/)).toBeInTheDocument();
    expect(within(pane).getByText("ESZ26")).toBeInTheDocument();
    expect(within(pane).getByText("+0.42%")).toBeInTheDocument();
    expect(within(pane).getByText(/Live · MOOMOO_OPEND · 180ms/)).toBeInTheDocument();
    expect(within(pane).getByText(/not evidence of what moved/)).toBeInTheDocument();
  });

  it("never lets a slow older response overwrite a newer selection", async () => {
    const pending: Record<string, (value: unknown) => void> = {};
    const signals: Record<string, AbortSignal> = {};
    mocks.preview.mockImplementation((id: string, _tf: string, _scope: string, _filters: unknown, signal: AbortSignal) => {
      signals[id] = signal;
      return new Promise((resolve) => { pending[id] = resolve; });
    });
    mount();
    await clickRow("AAPL");
    await waitFor(() => expect(pending.AAPL).toBeDefined());
    fireEvent.keyDown(screen.getByRole("grid"), { key: "ArrowDown" });
    await waitFor(() => expect(pending.MSFT).toBeDefined());
    await act(async () => { pending.MSFT(preview("MSFT", 20)); });
    const pane = screen.getByRole("complementary", { name: "Quick preview" });
    expect(await within(pane).findByText("MSFT Relative Volume 3.00× is above 2.00×")).toBeInTheDocument();
    await act(async () => { pending.AAPL(preview("AAPL", 12)); });
    expect(within(pane).getByRole("heading", { name: "MSFT" })).toBeInTheDocument();
    expect(within(pane).queryByText(/AAPL Relative Volume/)).not.toBeInTheDocument();
    expect(signals.AAPL.aborted).toBe(true);
  });

  it("closes, reopens, keeps selection, and persists layout", async () => {
    mount();
    await clickRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    fireEvent.click(within(pane).getByRole("button", { name: "Close quick preview" }));
    expect(screen.queryByRole("complementary", { name: "Quick preview" })).not.toBeInTheDocument();
    expect(screen.getByRole("grid")).toHaveFocus();
    await waitFor(() => expect(mocks.layout).toHaveBeenCalledWith({ open: false, width: 400 }));
    expect(screen.getByText("AAPL").closest("[role=row]")).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    const reopened = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(await within(reopened).findByRole("heading", { name: "AAPL" })).toBeInTheDocument();
  });

  it("resizes with the keyboard within bounds", async () => {
    mount();
    await screen.findByText("AAPL");
    const splitter = screen.getByRole("separator", { name: "Resize quick preview" });
    expect(splitter).toHaveAttribute("aria-valuenow", "400");
    fireEvent.keyDown(splitter, { key: "ArrowLeft" });
    expect(splitter).toHaveAttribute("aria-valuenow", "416");
    fireEvent.keyDown(splitter, { key: "End" });
    expect(splitter).toHaveAttribute("aria-valuenow", "320");
    fireEvent.keyDown(splitter, { key: "ArrowRight" });
    expect(splitter).toHaveAttribute("aria-valuenow", "320");
    await waitFor(() => expect(mocks.layout).toHaveBeenLastCalledWith({ open: true, width: 320 }));
    expect(screen.getByRole("complementary", { name: "Quick preview" })).toHaveStyle({ width: "320px" });
  });

  it("uses an overlay drawer at narrow desktop widths", async () => {
    setNarrow(true);
    mount();
    await screen.findByText("AAPL");
    expect(screen.queryByRole("separator", { name: "Resize quick preview" })).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Quick preview" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("AAPL"));
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(pane).toHaveClass("overlay");
    fireEvent.keyDown(pane, { key: "Escape" });
    expect(screen.queryByRole("complementary", { name: "Quick preview" })).not.toBeInTheDocument();
  });

  it("switches timeframe and shows an unavailable chart and levels without fallback", async () => {
    mocks.preview.mockImplementation(async (id: string, timeframe: string) => timeframe === "15m"
      ? preview(id, 12, {
        bars: { ...preview(id, 12).bars, timeframe: "15m", state: "UNAVAILABLE", reason: "BAR_SOURCE_UNAVAILABLE", provider_reason: "OPEND_UNAVAILABLE", bars: [], bar_count: 0, latest_complete_bar_end: null },
        levels: { ...preview(id, 12).levels, timeframe: "15m", state: "UNAVAILABLE", reason: "BAR_SOURCE_UNAVAILABLE", zones: [], price: null },
      }) : preview(id, 12));
    mount();
    await clickRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    await within(pane).findByRole("img", { name: /5m candles/ });
    fireEvent.click(within(pane).getByRole("button", { name: "15m" }));
    expect(await within(pane).findByText("Chart unavailable · OpenD is not reachable")).toBeInTheDocument();
    expect(within(pane).getByText("Levels unavailable · Current bars unavailable")).toBeInTheDocument();
    expect(within(pane).getByText("Auto S/R · 15m · Extended")).toBeInTheDocument();
    expect(mocks.preview).toHaveBeenCalledWith("AAPL", "15m", "EXTENDED", [], expect.anything(), "US_EQUITIES", null);
    expect(within(pane).queryByRole("img", { name: /candles/ })).not.toBeInTheDocument();
  });

  it("moves the live price marker from L1 while levels keep their own clock", async () => {
    mocks.window.mockResolvedValue({ active: 1, cap: 32, quotes: { AAPL: { state: "LIVE", age_ms: 120, fields: {
      price: { value: 12.55, source: "MOOMOO", state: "LIVE", as_of_ns: 1 } } } } });
    mount();
    await clickRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(await within(pane).findByText("Testing zone")).toBeInTheDocument();
    expect(within(pane).getAllByText("$12.55")).toHaveLength(2); // header quote and S/R current marker
    expect(within(pane).getByText("L1 live · 120ms")).toBeInTheDocument();
    expect(within(pane).getByText(/Levels calculated/)).toBeInTheDocument();
    expect(within(pane).getByText("No resistance zone")).toBeInTheDocument();
  });

  it("keeps S1 keyboard handoff and supports tab keyboard navigation", async () => {
    mount();
    await screen.findByText("AAPL");
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(await within(pane).findByRole("heading", { name: "AAPL" })).toBeInTheDocument();
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(await within(pane).findByRole("heading", { name: "MSFT" })).toBeInTheDocument();
    const why = await within(pane).findByRole("tab", { name: "Why" });
    why.focus();
    fireEvent.keyDown(why, { key: "ArrowRight" });
    expect(within(pane).getByRole("tab", { name: "Key Data" })).toHaveAttribute("aria-selected", "true");
    expect(within(pane).getByRole("tab", { name: "Key Data" })).toHaveFocus();
    fireEvent.keyDown(within(pane).getByRole("tab", { name: "Key Data" }), { key: "End" });
    // S8: Squeeze is last for US equities; left returns to Options.
    expect(within(pane).getByRole("tab", { name: "Squeeze" })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(within(pane).getByRole("tab", { name: "Squeeze" }), { key: "ArrowLeft" });
    expect(within(pane).getByRole("tab", { name: "Options" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(within(pane).getByRole("button", { name: "Open Instrument" }));
    expect(screen.getByText("Instrument workspace")).toBeInTheDocument();
  });

  it("keeps the snapshot quote clock separate from the last bar close", async () => {
    mocks.preview.mockImplementation(async (id: string) => {
      const base = preview(id, 12);
      return { ...base, levels: { ...base.levels, price: { value: 11.5, source: "LAST_BAR_CLOSE", state: "SESSION_CLOSED", as_of: "2026-09-26T00:00:00Z" } } };
    });
    mount();
    await clickRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(await within(pane).findByText("$11.50")).toBeInTheDocument();
    expect(within(pane).getByText("$12.00")).toBeInTheDocument();
    expect(within(pane).getByText("Snapshot")).toBeInTheDocument();
    expect(within(pane).getByText(/Last bar close · Fri 20:00 ET/)).toBeInTheDocument();
  });

  it("requests only the settled row when arrowing quickly", async () => {
    mount();
    await screen.findByText("AAPL");
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(await within(pane).findByText("MSFT Relative Volume 3.00× is above 2.00×")).toBeInTheDocument();
    expect(mocks.preview.mock.calls.map((call) => call[0])).toEqual(["MSFT"]);
  });

  it("requests Squeeze only while its tab is open and only for the final rapid row", async () => {
    const symbols = ["GME", "NVDA", "AAPL", "AMC", "CVNA"];
    mocks.fetch.mockResolvedValue({ ...payload, rows: symbols.map((symbol) => makeRow(symbol, `${symbol} Inc`, 12, 2)), result_count: 5 });
    mount();
    await screen.findByText("GME");
    expect(mocks.squeeze).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("GME", { selector: ".screener-symbol strong" }));
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    fireEvent.click(await within(pane).findByRole("tab", { name: "Squeeze" }));
    await waitFor(() => expect(mocks.squeeze).toHaveBeenCalledWith("GME", expect.objectContaining({ view: "summary" })));
    mocks.squeeze.mockClear();
    const grid = screen.getByRole("grid");
    for (let index = 0; index < 4; index += 1) fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(await within(pane).findByRole("heading", { name: "CVNA" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.squeeze.mock.calls.map((call) => call[0])).toEqual(["CVNA"]));
    expect(within(pane).getByRole("button", { name: "Open Short Squeeze Panel" })).toBeInTheDocument();
  });

  it("Enter still opens the canonical workspace from the grid", async () => {
    mount();
    await screen.findByText("AAPL");
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    fireEvent.keyDown(grid, { key: "Enter" });
    expect(screen.getByText("Instrument workspace")).toBeInTheDocument();
  });

  it("clears the preview when the selection leaves the result set", async () => {
    mount();
    await clickRow("MSFT");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    expect(await within(pane).findByRole("heading", { name: "MSFT" })).toBeInTheDocument();
    mocks.fetch.mockResolvedValue({ ...payload, rows: [rows[0]], result_count: 1 });
    fireEvent.change(screen.getByRole("textbox", { name: "Search instruments" }), { target: { value: "App" } });
    expect(await within(pane).findByText(/Select a row to preview it/)).toBeInTheDocument();
  });

  it("shows a no-filter explanation instead of inventing reasons", async () => {
    mocks.preview.mockImplementation(async (id: string) => preview(id, 12, { why: { ...preview(id, 12).why, matched: { state: "NO_ACTIVE_FILTERS", items: [] } } }));
    mount();
    await clickRow("AAPL");
    expect(await screen.findByText(/No filters are active/)).toBeInTheDocument();
  });
});

describe("classifyZones", () => {
  it("agrees with the backend AUTO_SR_V1 classification fixture", () => {
    const fixture = JSON.parse(readFileSync(resolve(process.cwd(), "../tests/fixtures/screener/auto_sr_classify_cases.json"), "utf8"));
    for (const item of fixture.cases) {
      const result = classifyZones(item.zones, item.price, fixture.min_strength);
      expect(result.support?.center ?? null, item.name).toBe(item.support_center);
      expect(result.resistance?.center ?? null, item.name).toBe(item.resistance_center);
      expect(result.testing?.center ?? null, item.name).toBe(item.testing_center);
      if (item.support_distance_pct != null) expect(result.support!.distance_pct).toBeCloseTo(item.support_distance_pct, 3);
      if (item.resistance_distance_pct != null) expect(result.resistance!.distance_pct).toBeCloseTo(item.resistance_distance_pct, 3);
    }
    expect(classifyZones(fixture.cases[0].zones, null, 20)).toEqual({ support: null, resistance: null, testing: null });
  });
});

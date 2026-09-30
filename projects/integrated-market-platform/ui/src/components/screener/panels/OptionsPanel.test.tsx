import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "../ScreenerPage";
import { hotVolumeThreshold } from "./OptionsPanel";
import ScreenerDock from "./ScreenerDock";
import { stateMessage } from "../options/optionsFormat";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), last: vi.fn(), preview: vi.fn(), layout: vi.fn(),
  panelLayout: vi.fn(), demand: vi.fn(), releasePanels: vi.fn(), cvd: vi.fn(), options: vi.fn(),
}));
vi.mock("../../../api/screener", async (original) => ({
  ...(await original<typeof import("../../../api/screener")>()),
  fetchScreener: mocks.fetch, fetchScreenerConfig: mocks.config, saveScreenerScreen: vi.fn(), deleteScreenerScreen: vi.fn(),
  persistLastScreenerConfig: mocks.last, updateScreenerWindow: mocks.window, releaseScreenerWindow: mocks.release,
  releaseScreenerWindowOnUnload: mocks.release, fetchScreenerPreview: mocks.preview, persistScreenerPreviewLayout: mocks.layout,
  persistScreenerPanelLayout: mocks.panelLayout,
}));
vi.mock("../../../api/screenerPanels", () => ({
  fetchOrderFlow: vi.fn(() => new Promise(() => undefined)), fetchCvd: mocks.cvd, fetchDepth: vi.fn(() => new Promise(() => undefined)),
  fetchChart: vi.fn(() => new Promise(() => undefined)), fetchFuturesContext: vi.fn(() => new Promise(() => undefined)),
  demandPanels: mocks.demand, releasePanels: mocks.releasePanels, releasePanelsOnUnload: mocks.releasePanels,
}));
vi.mock("../../../api/screenerOptions", () => ({ fetchScreenerOptions: mocks.options }));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34, scrollToIndex: vi.fn(),
  }),
}));
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), createPriceLine: vi.fn((options: unknown) => options), removePriceLine: vi.fn() });
  return { LineStyle: { Dashed: 2, Solid: 0 }, createChart: vi.fn(() => ({ addCandlestickSeries: vi.fn(series), addHistogramSeries: vi.fn(series),
    addBaselineSeries: vi.fn(series), priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
    timeScale: vi.fn(() => ({ setVisibleLogicalRange: vi.fn(), fitContent: vi.fn() })), applyOptions: vi.fn(), remove: vi.fn() })) };
});

beforeAll(() => {
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
});

const SYMBOLS = ["AAPL", "NVDA", "TSLA", "AMD", "MSFT"];
const field = (value: number | null) => ({ value, source: "FINVIZ_ELITE", state: value === null ? "UNAVAILABLE" : "SNAPSHOT", as_of: "2026-09-27T15:00:00Z" });
const makeRow = (symbol: string) => ({
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol, company: `${symbol} Inc`,
  sector: "Technology", industry: "Semiconductors", fields: { price: field(251), change_pct: field(1), volume: field(1000) },
});
const rows = SYMBOLS.map(makeRow);
const screenerPayload = {
  schema_version: "screener/1.0.0", universe: "US_EQUITIES", generated_at: "2026-09-27T15:00:00Z", universe_as_of: "2026-09-27T15:00:00Z",
  screener_as_of: "2026-09-27T15:00:00Z", market_session: "CLOSED", source_error: null,
  provider_health: [{ provider: "FINVIZ_ELITE", state: "HEALTHY", reason: null }], result_count: rows.length, rows,
};
const baseConfig = { schema_version: 1, persistence_available: true, catalog: [], presets: [], saved: [], last: null,
  preview_layout: { version: 1, open: true, width: 400 } };

type Row = Record<string, unknown>;
const contract = (symbol: string, type: "CALL" | "PUT", strike: number, expiration = "2026-10-02", extra: Row = {}): Row => ({
  option_id: `${symbol}${expiration.replace(/-/g, "")}${type[0]}${String(strike * 1000).padStart(8, "0")}`,
  provider_symbol: `${symbol}${expiration.slice(2).replace(/-/g, "")}${type[0]}${String(strike * 1000).padStart(8, "0")}`,
  type, expiration, dte: expiration === "2026-10-02" ? 5 : 19, strike, bid: 1.1, ask: 1.2, mid: 1.15, spread: 0.1, spread_pct: 8.7, last: 1.15,
  volume: 100, open_interest: 1000, volume_oi_ratio: 0.1, iv: type === "CALL" ? 0.29 : 0.33, delta: type === "CALL" ? 0.5 : -0.5,
  gamma: 0.01, theta: -0.05, vega: 0.2, rho: 0.03, last_trade_at: "2026-09-25T19:59:59Z", quality_flags: [], ...extra,
});
const analytics = (overrides: Row = {}) => ({
  contracts: 6, calls: 3, puts: 3, expirations: 2, nearest_expiration: "2026-10-02", call_volume: 42_100, put_volume: 31_700,
  total_volume: 73_800, put_call_volume_ratio: 0.753, call_put_volume_ratio: 1.328, call_open_interest: 614_200, put_open_interest: 522_400,
  total_open_interest: 1_136_600, put_call_oi_ratio: 0.8505, volume_reported: 6, open_interest_reported: 6, iv_reported: 6, two_sided: 5,
  median_spread_pct: 8.7, most_active: [{ option_id: "X", provider_symbol: "X", type: "CALL", expiration: "2026-10-02", strike: 250, volume: 600,
    open_interest: 4000, volume_oi_ratio: 0.15, iv: 0.29, share_of_side_volume_pct: 57.1 }], largest_open_interest: [],
  nearest_strike: { expiration: "2026-10-02", strike: 250, basis_price: 251.2, distance: -1.2, distance_pct: -0.48, exact: false,
    call_iv: 0.29, put_iv: 0.33, call_mid: 1.15, put_mid: 1.2 }, ...overrides,
});
function optionsPayload(id: string, { universe = "US_EQUITIES", view = "chain", expiration = "2026-10-02", state = "MARKET_CLOSED", reason = "OPTIONS_MARKET_CLOSED" }: Row = {}) {
  const exp = expiration as string;
  const chain = ["CURRENT_SNAPSHOT", "MARKET_CLOSED", "STALE"].includes(state as string);
  return {
    schema_version: "screener-options/1.0.0", generated_at: new Date().toISOString(), instrument_id: id, universe, symbol: id, view,
    market_session: "CLOSED", capability: { OPTIONS_UNIVERSE_QUERY: "NOT_SUPPORTED" },
    provider: { id: "options.finviz.elite_export", label: "Finviz Elite", delivery: "SNAPSHOT" }, state, reason,
    clock: chain ? { fetched_at: new Date(Date.now() - 21_000).toISOString(), age_ms: 21_000, provider_as_of: null,
      latest_contract_trade_at: "2026-09-25T19:59:59Z", refresh_after_s: 300, stale_after_s: 600, provider_latency_ms: 420, provider_cache_hit: false } : null,
    underlying: chain ? { price: 251.2, source: "FINVIZ_ELITE", state: "SNAPSHOT", as_of: "2026-09-27T15:00:00Z" } : null,
    completeness: chain ? { provider_rows: 9, usable: 8, dropped: 0, dropped_reasons: {}, expired_excluded: 1, unmapped_columns: ["Change $"] } : null,
    quality_flags: [], fields_supplied: chain ? { bid: true, ask: true, last: true, volume: true, open_interest: true, iv: true, delta: true,
      gamma: true, theta: true, vega: true, rho: true } : null,
    expirations: chain ? [{ expiration: "2026-10-02", dte: 5, contracts: 6, strikes: 3, call_volume: 800, put_volume: 300 },
      { expiration: "2026-10-16", dte: 19, contracts: 2, strikes: 1, call_volume: 50, put_volume: 75 }] : [],
    selected_expiration: chain ? exp : null, summary: chain ? analytics() : null,
    expiry_summary: chain && view === "chain" ? analytics({ contracts: exp === "2026-10-16" ? 2 : 6 }) : null,
    contracts: chain && view === "chain" ? (exp === "2026-10-16" ? [contract(id, "CALL", 250, exp), contract(id, "PUT", 250, exp)] : [
      contract(id, "CALL", 245), contract(id, "PUT", 245), contract(id, "CALL", 250, "2026-10-02", { volume: 600 }), contract(id, "PUT", 250),
      contract(id, "CALL", 255, "2026-10-02", { bid: null, ask: null, mid: null, spread: null, spread_pct: null, iv: null, open_interest: null, volume_oi_ratio: null }),
      contract(id, "PUT", 255, "2026-10-02", { volume: 0 })]) : [],
  };
}
const bar = (index: number, close: number) => ({ time: 1_790_000_000 + index * 300, start: "2026-09-25T14:00:00Z", end: "2026-09-25T14:05:00Z",
  open: close, high: close + 0.1, low: close - 0.1, close, volume: 100, session: "REGULAR" });
const preview = (symbol: string) => ({
  schema_version: "screener-preview/1.0.0", generated_at: "2026-09-27T15:00:00Z", market_session: "CLOSED",
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY", symbol, company: `${symbol} Inc`, sector: "Technology", industry: "Software" },
  quote: { state: "UNAVAILABLE", fields: {} }, key_data: [],
  bars: { timeframe: "5m", session_scope: "EXTENDED", provider: "MOOMOO_OPEND", source_id: "X", state: "SESSION_CLOSED", reason: null, provider_reason: null,
    received_at: null, latest_complete_bar_end: "2026-09-25T20:00:00Z", bar_count: 2, bars: [bar(0, 250), bar(1, 251)], forming: null },
  levels: { method: "AUTO_SR_V1", timeframe: "5m", session_scope: "EXTENDED", bar_state: "CURRENT", state: "UNAVAILABLE", reason: "INSUFFICIENT_BARS", reasons: [],
    calculated_at: null, input_bar_count: 2, input_latest_bar_end: null, min_strength: 20, strength_semantics: "", zones: [], price: null,
    support: null, resistance: null, testing: null },
  why: { matched: { state: "NO_ACTIVE_FILTERS", items: [] }, moving: { headline_window_start: "2026-09-26T20:00:00Z", items: [] } },
  futures: { mapping_version: "V1", causal_note: "Context only.", items: [] },
});

function renderPage(panelLayout?: unknown) {
  mocks.config.mockResolvedValue(panelLayout ? { ...baseConfig, panel_layout: panelLayout } : baseConfig);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/screener"]}><Routes>
    <Route path="/screener" element={<ScreenerPage />} /><Route path="*" element={<div>elsewhere</div>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
const launcher = () => within(screen.getByRole("navigation", { name: "Open panels" }));
const selectRow = async (symbol: string) => {
  await screen.findByText(symbol, { selector: ".screener-symbol strong" });
  await waitFor(() => expect(mocks.window).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
  fireEvent.click(screen.getByText(symbol, { selector: ".screener-symbol strong" }));
};
const optionCalls = (view: string) => mocks.options.mock.calls.filter((call) => call[1].view === view).map((call) => call[0]);
const sleep = (ms: number) => act(() => new Promise((resolve) => setTimeout(resolve, ms)));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  mocks.fetch.mockResolvedValue(screenerPayload);
  mocks.window.mockResolvedValue({ schema_version: "screener/1.0.0", generated_at: new Date().toISOString(), market_session: "CLOSED", active: 0, cap: 32, quotes: {} });
  mocks.release.mockResolvedValue({ released: true });
  mocks.preview.mockImplementation(async (id: string) => preview(id));
  mocks.layout.mockResolvedValue({ result: { version: 1, open: true, width: 400 } });
  mocks.panelLayout.mockResolvedValue({ result: {} });
  mocks.last.mockResolvedValue({ result: {}, saved: [] });
  mocks.demand.mockImplementation(async (_client: string, instrument: string | null, panels: string[]) => ({
    schema_version: "screener-specialist/1.0.0", instrument_id: instrument, panels, capabilities: [], cap: { max_instruments: 6, occupied_instruments: 1 } }));
  mocks.releasePanels.mockResolvedValue({ released: true });
  mocks.cvd.mockReturnValue(new Promise(() => undefined));
  mocks.options.mockImplementation(async (id: string, options: { view: string; expiration?: string | null; universe: string }) =>
    optionsPayload(id, { view: options.view, expiration: options.expiration ?? "2026-10-02", universe: options.universe }));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("S7 options semantics", () => {
  it("emphasises only a deterministic top-decile volume with enough samples", () => {
    const volumes = (values: Array<number | null>) => values.map((volume) => ({ volume }) as never);
    expect(hotVolumeThreshold(volumes([1, 2, 3, 4]))).toBeNull();
    expect(hotVolumeThreshold(volumes([0, null, 5, 1, 2, 3, 4, 10, 9, 8, 7, 6]))).toBe(10);
  });

  it("states every unavailable condition without raw errors", () => {
    expect(stateMessage({ state: "NOT_CONFIGURED", reason: "PROVIDER_NOT_CONFIGURED" })).toBe("Options source not configured for this workstation.");
    expect(stateMessage({ state: "PROVIDER_UNAVAILABLE", reason: "FINVIZ_OPTIONS_HTTP_ERROR" })).toBe("Current option chain unavailable.");
    expect(stateMessage({ state: "NO_CHAIN", reason: "NO_CURRENT_CONTRACTS" })).toBe("No current option contracts returned for this instrument.");
    expect(stateMessage({ state: "MARKET_CLOSED", reason: "OPTIONS_MARKET_CLOSED" })).toBe("Market closed · showing latest available options snapshot");
    expect(stateMessage({ state: "STALE", reason: "SNAPSHOT_AGE_EXCEEDED" })).toBe("Options snapshot stale");
    expect(stateMessage({ state: "NOT_ENTITLED", reason: "FINVIZ_OPTIONS_AUTH_REJECTED" })).toMatch(/not entitled/);
  });
});

describe("S7 Options panel", () => {
  it("adds one Options launcher and makes no options request while arrowing rows with nothing open", async () => {
    renderPage();
    await screen.findByText("AAPL", { selector: ".screener-symbol strong" });
    expect(screen.getAllByRole("navigation", { name: "Open panels" })).toHaveLength(1);
    expect(launcher().getAllByRole("button").map((button) => button.textContent)).toEqual(
      ["Order Flow", "CVD", "Level 2", "Charts", "Futures Context", "Options", "Short Squeeze", "Rates & Curve · unavailable", "News & Analysis",
      "Institutional & Whale · unavailable", "Congress & Government · unavailable", "Setup", "Reset Panel Layout"]);
    await selectRow("AAPL");
    const grid = screen.getByRole("grid");
    for (let step = 0; step < 4; step += 1) fireEvent.keyDown(grid, { key: "ArrowDown" });
    await sleep(700);
    expect(mocks.options).not.toHaveBeenCalled();
  });

  it("renders a snapshot chain with summary, expiry selector, calls and puts, and unavailable values", async () => {
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Options" }));
    const panel = await screen.findByRole("region", { name: "Options for AAPL" });
    const table = await within(panel).findByRole("table");
    expect(mocks.options).toHaveBeenCalledWith("AAPL", expect.objectContaining({ universe: "US_EQUITIES", view: "chain", expiration: null }));
    expect(within(panel).getByText("Market closed")).toBeInTheDocument();
    expect(within(panel).getByText(/Updated \d+s ago/)).toBeInTheDocument();
    expect(within(panel).getByText("Market closed · showing latest available options snapshot")).toBeInTheDocument();
    expect(within(panel).queryByText(/live|streaming/i, { selector: ".screener-panel-state" })).toBeNull();
    expect(within(panel).getByText(/snapshot, not streaming/)).toBeInTheDocument();
    const stats = within(panel).getByLabelText("Chain summary, all expiries");
    expect(within(stats).getByText("42.1K")).toBeInTheDocument();
    expect(within(stats).getByText("0.75")).toBeInTheDocument();
    expect(within(stats).getByText("0.85")).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Calls" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Puts" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Call Implied volatility (provider)" })).toBeInTheDocument();
    expect(within(table).getAllByRole("rowheader").map((cell) => cell.textContent)).toEqual(["245", "250◆ nearest strike to underlying", "255"]);
    const row255 = within(table).getByRole("rowheader", { name: "255" }).closest("tr")!;
    expect(within(row255).getAllByText("—").length).toBeGreaterThanOrEqual(4); // missing bid/ask/IV/OI are unavailable, not zero
    expect(within(row255).getByText("0")).toBeInTheDocument(); // a provider zero volume stays zero
    const select = within(panel).getByRole("combobox", { name: /Expiry/ });
    expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual(["Oct 2, 2026 · 5d · 3 strikes", "Oct 16, 2026 · 19d · 1 strikes"]);
    // Keys inside the panel stay local: the Screener selection does not move.
    fireEvent.keyDown(select, { key: "ArrowDown" });
    fireEvent.keyDown(within(panel).getByRole("region", { name: /AAPL option chain/ }), { key: "ArrowDown" });
    expect(screen.getByText("AAPL", { selector: ".screener-symbol strong" }).closest("[role=row]")).toHaveAttribute("aria-selected", "true");
    fireEvent.change(select, { target: { value: "2026-10-16" } });
    await waitFor(() => expect(within(panel).getAllByRole("rowheader")).toHaveLength(1));
    expect(mocks.options).toHaveBeenLastCalledWith("AAPL", expect.objectContaining({ expiration: "2026-10-16" }));
    fireEvent.click(within(panel).getByRole("button", { name: "More columns" }));
    expect(within(table).getByRole("columnheader", { name: "Put Gamma (provider)" })).toBeInTheDocument();
  });

  it("never lets a slow AAPL chain populate NVDA and resets the expiry choice", async () => {
    let resolveAapl: (value: unknown) => void = () => undefined;
    mocks.options.mockImplementation((id: string, options: { view: string; expiration?: string | null }) => id === "AAPL"
      ? new Promise((resolve) => { resolveAapl = resolve; })
      : Promise.resolve(optionsPayload(id, { view: options.view, expiration: options.expiration ?? "2026-10-02" })));
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Options" }));
    await waitFor(() => expect(optionCalls("chain")).toContain("AAPL"));
    await selectRow("NVDA");
    const panel = await screen.findByRole("region", { name: "Options for NVDA" });
    await within(panel).findByRole("table");
    await act(async () => { resolveAapl(optionsPayload("AAPL")); });
    expect(within(panel).getByRole("table").querySelector("caption")?.textContent).toMatch(/^NVDA calls and puts/);
    expect(screen.queryByRole("region", { name: "Options for AAPL" })).toBeNull();
    expect(mocks.options).toHaveBeenLastCalledWith("NVDA", expect.objectContaining({ expiration: null }));
  });

  it("shows not configured, no chain, stale, not entitled, and request failure states in the panel only", async () => {
    const states: Record<string, Row> = {
      AAPL: { state: "NOT_CONFIGURED", reason: "PROVIDER_NOT_CONFIGURED" }, NVDA: { state: "NO_CHAIN", reason: "NO_CURRENT_CONTRACTS" },
      TSLA: { state: "STALE", reason: "FINVIZ_OPTIONS_HTTP_ERROR" }, AMD: { state: "NOT_ENTITLED", reason: "FINVIZ_OPTIONS_AUTH_REJECTED" },
    };
    mocks.options.mockImplementation(async (id: string, options: { view: string }) => {
      if (id === "MSFT") throw new Error("Request failed: /screener/options");
      return optionsPayload(id, { view: options.view, ...states[id] });
    });
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Options" }));
    fireEvent.click(launcher().getByRole("button", { name: "CVD" }));
    expect(await screen.findByText("Options source not configured for this workstation.")).toBeInTheDocument();
    await selectRow("NVDA");
    expect(await screen.findByText("No current option contracts returned for this instrument.")).toBeInTheDocument();
    await selectRow("TSLA");
    expect(await screen.findByText(/Options snapshot stale · last refresh failed: Current option chain unavailable\./)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Options for TSLA" })).getByRole("table")).toBeInTheDocument();
    await selectRow("AMD");
    expect(await screen.findByText(/rejected the options export credential/)).toBeInTheDocument();
    await selectRow("MSFT");
    const failed = await screen.findByRole("region", { name: "Options for MSFT" });
    // The panel retries once before reporting the failure.
    expect(await within(failed).findByRole("alert", {}, { timeout: 5000 })).toHaveTextContent("Current option chain unavailable.");
    expect(within(failed).queryByText(/Request failed/)).toBeNull();
    expect(screen.getByRole("region", { name: "CVD for MSFT" })).toBeInTheDocument();
    expect(screen.getByRole("grid", { name: "US equity screener" })).toBeInTheDocument();
  });

  it("restores a saved Options panel without duplicating it", async () => {
    renderPage({ version: 1, open_panels: ["options"], active_panel: "options", dock_height: 300, dockview_layout: null });
    expect(await screen.findByText("Select an instrument to view Options.")).toBeInTheDocument();
    fireEvent.click(launcher().getByRole("button", { name: "Options" }));
    await waitFor(() => expect(document.querySelectorAll("#screener-panel-options")).toHaveLength(1));
    expect(mocks.options).not.toHaveBeenCalled();
  });
});

describe("S7 universe capability", () => {
  const props = { layout: { version: 1 as const, open_panels: ["options" as const], active_panel: "options" as const, dock_height: 300, dockview_layout: null },
    quote: undefined, clientId: "dock-s7", pending: null, handleRef: { current: null }, onOpenChange: () => undefined, onLayout: () => undefined };
  it("requests ETF chains under the ETF universe", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ScreenerDock {...props} row={makeRow("SPY") as never} universe="US_ETFS"
      supportedPanels={new Set(["order_flow", "cvd", "level2", "charts", "options"] as const)} /></QueryClientProvider>);
    await waitFor(() => expect(mocks.options).toHaveBeenCalledWith("SPY", expect.objectContaining({ universe: "US_ETFS", view: "chain" })));
    expect(await screen.findByRole("region", { name: "Options for SPY" })).toBeInTheDocument();
    expect(mocks.demand).not.toHaveBeenCalled(); // Options holds no streaming subscription
  });

  it("keeps Futures unavailable and never requests a chain", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ScreenerDock {...props} row={makeRow("ESZ26") as never} universe="FUTURES" supportedPanels={new Set()} /></QueryClientProvider>);
    expect(await screen.findByText("Options is unavailable for this universe. The layout is retained.")).toBeInTheDocument();
    await sleep(400);
    expect(mocks.options).not.toHaveBeenCalled();
  });
});

describe("S7 Quick Preview Options tab", () => {
  it("fetches a summary only when the tab is opened and hands off to the panel", async () => {
    renderPage();
    await selectRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    const tab = await within(pane).findByRole("tab", { name: "Options" });
    await sleep(500);
    expect(mocks.options).not.toHaveBeenCalled();
    fireEvent.click(tab);
    expect(tab).toHaveAttribute("aria-selected", "true");
    const panel = within(pane).getByRole("tabpanel");
    expect(await within(panel).findByText("Options snapshot")).toBeInTheDocument();
    expect(optionCalls("summary")).toEqual(["AAPL"]);
    expect(within(panel).getByText("0.75")).toBeInTheDocument();
    expect(within(panel).getByText("C 29.0% · P 33.0%")).toBeInTheDocument();
    expect(within(panel).getByText(/AAPL Oct 2 250 C · 600 · 57.1% of call volume/)).toBeInTheDocument();
    expect(within(panel).getByText(/Finviz Elite · snapshot, not streaming · Market closed/)).toBeInTheDocument();
    expect(within(panel).queryByRole("table")).toBeNull(); // the full chain lives in the panel
    fireEvent.click(within(panel).getByRole("button", { name: "Open Options Panel" }));
    expect(await screen.findByRole("region", { name: "Options for AAPL" })).toBeInTheDocument();
    expect(launcher().getByRole("button", { name: "Options" })).toHaveAttribute("aria-pressed", "true");
  });

  it("requests only the settled row while arrowing with the Options tab open", async () => {
    renderPage();
    await selectRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    fireEvent.click(await within(pane).findByRole("tab", { name: "Options" }));
    await waitFor(() => expect(optionCalls("summary")).toEqual(["AAPL"]));
    const grid = screen.getByRole("grid");
    for (let step = 0; step < 4; step += 1) {
      fireEvent.keyDown(grid, { key: "ArrowDown" });
      await sleep(60);
    }
    await waitFor(() => expect(optionCalls("summary")).toEqual(["AAPL", "MSFT"]), { timeout: 3000 });
    await sleep(500);
    expect(optionCalls("summary")).toEqual(["AAPL", "MSFT"]);
    expect(await within(pane).findByText(/MSFT/, { selector: "h2" })).toBeInTheDocument();
  });
});

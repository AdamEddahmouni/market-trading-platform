import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "../ScreenerPage";
import { sideLabel, windowLabel } from "./OrderFlowPanel";
import { anchorLabel } from "./CvdPanel";
import { perSecond } from "./CvdChart";
import ScreenerDock, { serializeLayout } from "./ScreenerDock";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), save: vi.fn(), remove: vi.fn(), last: vi.fn(),
  preview: vi.fn(), layout: vi.fn(), panelLayout: vi.fn(),
  flow: vi.fn(), cvd: vi.fn(), depth: vi.fn(), chart: vi.fn(), futures: vi.fn(), squeeze: vi.fn(), demand: vi.fn(), releasePanels: vi.fn(),
}));
vi.mock("../../../api/screener", async (original) => ({
  ...(await original<typeof import("../../../api/screener")>()),
  fetchScreener: mocks.fetch, fetchScreenerConfig: mocks.config, saveScreenerScreen: mocks.save,
  deleteScreenerScreen: mocks.remove, persistLastScreenerConfig: mocks.last, updateScreenerWindow: mocks.window,
  releaseScreenerWindow: mocks.release, releaseScreenerWindowOnUnload: mocks.release,
  fetchScreenerPreview: mocks.preview, persistScreenerPreviewLayout: mocks.layout, persistScreenerPanelLayout: mocks.panelLayout,
}));
vi.mock("../../../api/screenerPanels", () => ({
  fetchOrderFlow: mocks.flow, fetchCvd: mocks.cvd, fetchDepth: mocks.depth, fetchChart: mocks.chart,
  fetchFuturesContext: mocks.futures, demandPanels: mocks.demand, releasePanels: mocks.releasePanels,
  releasePanelsOnUnload: mocks.releasePanels,
}));
vi.mock("../../../api/screenerSqueeze", () => ({ fetchScreenerSqueeze: mocks.squeeze }));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34, scrollToIndex: vi.fn(),
  }),
}));
vi.mock("lightweight-charts", () => {
  const series = () => ({ setData: vi.fn(), createPriceLine: vi.fn((options: unknown) => options), removePriceLine: vi.fn() });
  return {
    LineStyle: { Dashed: 2, Solid: 0 },
    createChart: vi.fn(() => ({
      addCandlestickSeries: vi.fn(series), addHistogramSeries: vi.fn(series), addBaselineSeries: vi.fn(series),
      priceScale: vi.fn(() => ({ applyOptions: vi.fn() })),
      timeScale: vi.fn(() => ({ setVisibleLogicalRange: vi.fn(), fitContent: vi.fn() })), applyOptions: vi.fn(), remove: vi.fn(),
    })),
  };
});

beforeAll(() => {
  // jsdom has no layout engine; Dockview only needs the observer contract.
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
});

const field = (value: number | null) => ({ value, source: "FINVIZ_ELITE", state: value === null ? "UNAVAILABLE" : "SNAPSHOT", as_of: "2026-09-25T15:00:00Z" });
const makeRow = (symbol: string) => ({
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol, company: `${symbol} Inc`,
  sector: "Technology", industry: "Semiconductors", fields: { price: field(10), change_pct: field(1), volume: field(1000) },
});
const rows = [makeRow("AAPL"), makeRow("NVDA")];
const screenerPayload = {
  schema_version: "screener/1.0.0", universe: "US_EQUITIES", generated_at: "2026-09-25T15:00:00Z", universe_as_of: "2026-09-25T15:00:00Z",
  screener_as_of: "2026-09-25T15:00:00Z", market_session: "REGULAR", source_error: null,
  provider_health: [{ provider: "FINVIZ_ELITE", state: "HEALTHY", reason: null }], result_count: 2, rows,
};
const baseConfig = { schema_version: 1, persistence_available: true, catalog: [], presets: [], saved: [], last: null };
const now = Date.now();
const iso = (offset = 0) => new Date(now - offset).toISOString();
const base = (id: string, panel: string, state = "CURRENT") => ({
  schema_version: "screener-specialist/1.0.0", instrument_id: id, provider: "MOOMOO", generated_at: iso(), market_session: "REGULAR",
  state, reason: null, entitlement: "PROBE_VERIFIED", panel,
});
const window_ = { basis: "SINCE_SUBSCRIPTION", anchor_at: iso(60_000), start: iso(50_000), end: iso(1000), max_records: 500, truncated: false };
const flowPayload = (id: string) => ({
  ...base(id, "order_flow"), window: window_, latest_event_at: iso(1000), latest_received_at: iso(900),
  summary: { trade_count: 3, total_volume: 450, buy_volume: 100, sell_volume: 300, unknown_volume: 50, net_signed_volume: -200,
    classified_volume_pct: 88.9, native_count: 0, inferred_count: 2, unknown_count: 1, methods: { PROVIDER_TICKER_DIRECTION: 2, UNCLASSIFIED: 1 },
    trades_per_minute: null, large_print_threshold: null },
  tape: [
    { trade_id: "3", event_time: iso(1000), received_time: iso(900), price: 100.2, size: 50, aggressor: { state: "UNKNOWN", side: null, method: "UNCLASSIFIED" }, condition: "ODD_LOT", large: false },
    { trade_id: "2", event_time: iso(2000), received_time: iso(1900), price: 100.1, size: 300, aggressor: { state: "INFERRED", side: "SELL", method: "PROVIDER_TICKER_DIRECTION" }, condition: null, large: false },
    { trade_id: "1", event_time: iso(3000), received_time: iso(2900), price: 100.0, size: 100, aggressor: { state: "INFERRED", side: "BUY", method: "PROVIDER_TICKER_DIRECTION" }, condition: null, large: false },
  ],
});
const cvdPayload = (id: string, cvd = -200) => ({
  ...base(id, "cvd"), derivation: "DERIVED", window: window_, latest_event_at: iso(1000), latest_received_at: iso(900),
  summary: { cvd, recent_delta: cvd, recent_delta_seconds: 60, trade_count: 3, classified_volume: 400, unknown_volume: 50,
    classified_volume_pct: 88.9, aggressor_states: { NATIVE: 0, INFERRED: 2, UNKNOWN: 1 }, methods: ["PROVIDER_TICKER_DIRECTION"] },
  points: [{ time_ms: now - 3000, cvd: 100, delta: 100 }, { time_ms: now - 2000, cvd: -200, delta: -300 }, { time_ms: now - 1000, cvd: -200, delta: 0 }],
});
const depthPayload = (id: string, state = "CURRENT") => ({
  ...base(id, "level2", state), bids: [{ price: 102.12, size: 500, cumulative_size: 500 }, { price: 102.11, size: 1200, cumulative_size: 1700 }],
  asks: [{ price: 102.14, size: 900, cumulative_size: 900 }, { price: 102.15, size: 250, cumulative_size: 1150 }],
  best_bid: 102.12, best_ask: 102.14, spread: 0.02, mid: 102.13, spread_bps: 1.96,
  imbalance: [{ levels: 5, bid_levels: 2, ask_levels: 2, bid_size: 1700, ask_size: 1150, bid_share: 0.596, signed: 0.19, complete: false }],
  completeness: { basis: "PROVIDER_MBP_TOP_N", bid_levels: 2, ask_levels: 2, venue_scope: "PROVIDER_UNSPECIFIED", update_semantics: "SNAPSHOT" },
  freshness: { status: "FRESH", age_ms: 180, ttl_ms: 5000, policy: "moomoo_l2" }, latest_event_at: iso(200), latest_received_at: iso(180), quality_flags: [],
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

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetch.mockResolvedValue(screenerPayload);
  mocks.window.mockResolvedValue({ schema_version: "screener/1.0.0", generated_at: iso(), market_session: "REGULAR", active: 0, cap: 32, quotes: {} });
  mocks.release.mockResolvedValue({ released: true });
  mocks.preview.mockReturnValue(new Promise(() => undefined));
  mocks.layout.mockResolvedValue({ result: { version: 1, open: true, width: 400 } });
  mocks.panelLayout.mockResolvedValue({ result: {} });
  mocks.last.mockResolvedValue({ result: {}, saved: [] });
  mocks.demand.mockImplementation(async (_client: string, instrument: string | null, panels: string[]) => ({
    schema_version: "screener-specialist/1.0.0", instrument_id: instrument, panels, capabilities: [], cap: { max_instruments: 6, occupied_instruments: 1 } }));
  mocks.releasePanels.mockResolvedValue({ released: true });
  mocks.flow.mockImplementation(async (id: string) => flowPayload(id));
  mocks.cvd.mockImplementation(async (id: string) => cvdPayload(id));
  mocks.depth.mockImplementation(async (id: string) => depthPayload(id));
  mocks.chart.mockReturnValue(new Promise(() => undefined));
  mocks.futures.mockReturnValue(new Promise(() => undefined));
  mocks.squeeze.mockReturnValue(new Promise(() => undefined));
});
afterEach(() => vi.useRealTimers());

describe("S4 specialist panel semantics", () => {
  it("never labels an inferred side as a known buyer or seller", () => {
    expect(sideLabel({ state: "INFERRED", side: "BUY", method: "PROVIDER_TICKER_DIRECTION" })).toBe("Inf. Buy");
    expect(sideLabel({ state: "NATIVE", side: "SELL", method: "EXCHANGE_NATIVE" })).toBe("Sell");
    expect(sideLabel({ state: "UNKNOWN", side: null, method: "UNCLASSIFIED" })).toBe("Unknown");
  });

  it("states the CVD anchor exactly and never calls a captured window a session", () => {
    expect(anchorLabel({ ...window_ })).toMatch(/^CVD since subscription /);
    expect(anchorLabel({ ...window_, basis: "LAST_N_CAPTURED", truncated: true })).toBe("CVD over last 500 captured trades");
    expect(windowLabel({ ...window_, basis: "LAST_N_CAPTURED" })).toBe("Last 500 captured trades");
    expect(anchorLabel(window_)).not.toMatch(/session/i);
  });

  it("aggregates CVD points to one value per second in time order", () => {
    expect(perSecond([{ time_ms: 2_500, cvd: 3 }, { time_ms: 1_100, cvd: 1 }, { time_ms: 1_900, cvd: 2 }]))
      .toEqual([{ time: 1, value: 2 }, { time: 2, value: 3 }]);
  });

  it("serializes presentation only: params and nested values never persist", () => {
    const api = { panels: [{ id: "cvd" }], toJSON: () => ({ grid: { root: {} }, floatingGroups: [{}],
      panels: { cvd: { id: "cvd", contentComponent: "cvd", title: "CVD", params: { cvd: 1 }, nested: { price: 1 } } } }) };
    expect(serializeLayout(api as never)).toEqual({ grid: { root: {} }, panels: { cvd: { id: "cvd", contentComponent: "cvd", title: "CVD" } } });
    expect(serializeLayout({ panels: [] } as never)).toBeNull();
  });
});

describe("S5 universe capability", () => {
  it("releases held panel demand when a universe loses the capability instead of re-demanding the stale instrument", async () => {
    const props = { layout: { version: 1, open_panels: ["order_flow" as const], active_panel: "order_flow" as const, dock_height: 300, dockview_layout: null },
      row: makeRow("SPY"), quote: undefined, clientId: "dock-s5", pending: null, handleRef: { current: null },
      onOpenChange: () => undefined, onLayout: () => undefined };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><ScreenerDock {...props} universe="US_ETFS" supportedPanels={new Set(["order_flow", "cvd", "level2", "charts"] as const)} /></QueryClientProvider>);
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith("dock-s5", "SPY", ["order_flow"], "US_ETFS"));
    view.rerender(<QueryClientProvider client={client}><ScreenerDock {...props} universe="FUTURES" supportedPanels={new Set()} /></QueryClientProvider>);
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith("dock-s5", null, [], "FUTURES"));
    expect(screen.getByText("Order Flow is unavailable for this universe. The layout is retained.")).toBeInTheDocument();
  });
});

describe("S4 Screener dock", () => {
  it("lazily opens one Short Squeeze panel and shares the S4 trade demand", async () => {
    renderPage();
    await selectRow("AAPL");
    expect(mocks.squeeze).not.toHaveBeenCalled();
    fireEvent.click(launcher().getByRole("button", { name: "Short Squeeze" }));
    expect(await screen.findByText("Loading AAPL squeeze evidence…")).toBeInTheDocument();
    await waitFor(() => expect(mocks.squeeze).toHaveBeenCalledWith("AAPL", expect.objectContaining({ view: "detail", universe: "US_EQUITIES" })));
    await waitFor(() => expect(mocks.demand).toHaveBeenCalledWith(expect.any(String), "AAPL", ["short_squeeze"]));
    fireEvent.click(launcher().getByRole("button", { name: "Short Squeeze" }));
    expect(document.querySelectorAll("#screener-panel-short_squeeze")).toHaveLength(1);
  });

  it("keeps one launcher, no dock, and no demand until a panel is opened", async () => {
    renderPage();
    await screen.findByText("AAPL", { selector: "strong" });
    expect(screen.getAllByRole("navigation", { name: "Open panels" })).toHaveLength(1);
    for (const name of ["Order Flow", "CVD", "Level 2", "Charts", "Futures Context"]) expect(launcher().getByRole("button", { name })).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("region", { name: "Specialist panels" })).toBeNull();
    expect(screen.queryByText(/Workbook/)).toBeNull(); // WORKBOOK_SURFACE_ABSENT
    expect(mocks.demand).not.toHaveBeenCalled();
    expect(mocks.cvd).not.toHaveBeenCalled();
  });

  it("opens a panel, focuses instead of duplicating, and asks for a selection", async () => {
    renderPage();
    await screen.findByText("AAPL", { selector: "strong" });
    fireEvent.click(launcher().getByRole("button", { name: "CVD" }));
    expect(await screen.findByText("Select an instrument to view CVD.")).toBeInTheDocument();
    expect(launcher().getByRole("button", { name: "CVD" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(launcher().getByRole("button", { name: "CVD" }));
    await waitFor(() => expect(document.querySelectorAll("#screener-panel-cvd")).toHaveLength(1));
    expect(mocks.cvd).not.toHaveBeenCalled(); // no selection → nothing requested
  });

  it("drives Order Flow and CVD from one demand and renders truthful wording", async () => {
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Order Flow" }));
    fireEvent.click(await screen.findByRole("button", { name: "CVD" }));
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith(expect.any(String), "AAPL", ["order_flow", "cvd"]));
    const flow = await screen.findByRole("region", { name: "Order Flow for AAPL" });
    expect(await within(flow).findByText("Inf. Sell")).toBeInTheDocument();
    expect(within(flow).getByText("Unknown")).toBeInTheDocument();
    expect(within(flow).getByText(/not a known buyer or seller/)).toBeInTheDocument();
    expect(within(flow).getByRole("table")).toBeInTheDocument();
    const cvd = screen.getByRole("region", { name: "CVD for AAPL" });
    expect(await within(cvd).findAllByText(/CVD since subscription/)).not.toHaveLength(0);
    expect(within(cvd).getByText(/Derived estimate/)).toBeInTheDocument();
    expect(within(cvd).queryByText(/session cvd|bullish|bearish/i)).toBeNull();
  });

  it("closing panels releases their demand and the last close removes the dock", async () => {
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Order Flow" }));
    fireEvent.click(await screen.findByRole("button", { name: "CVD" }));
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith(expect.any(String), "AAPL", ["order_flow", "cvd"]));
    fireEvent.click(within(await screen.findByRole("region", { name: "Order Flow for AAPL" })).getByRole("button", { name: "Close Order Flow" }));
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith(expect.any(String), "AAPL", ["cvd"]));
    fireEvent.click(within(screen.getByRole("region", { name: "CVD for AAPL" })).getByRole("button", { name: "Close CVD" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Specialist panels" })).toBeNull());
    await waitFor(() => expect(mocks.releasePanels).toHaveBeenCalled());
    expect(launcher().getByRole("button", { name: "CVD" })).toHaveAttribute("aria-pressed", "false");
  });

  it("never lets a slow older response populate the newer instrument", async () => {
    let resolveAapl: (value: unknown) => void = () => undefined;
    mocks.depth.mockImplementation((id: string) => id === "AAPL" ? new Promise((resolve) => { resolveAapl = resolve; }) : Promise.resolve(depthPayload(id)));
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Level 2" }));
    await waitFor(() => expect(mocks.depth).toHaveBeenCalledWith("AAPL", expect.anything()));
    await selectRow("NVDA");
    const panel = await screen.findByRole("region", { name: "Level 2 for NVDA" });
    await within(panel).findByRole("table");
    await act(async () => { resolveAapl(depthPayload("AAPL")); });
    expect(screen.getByRole("region", { name: "Level 2 for NVDA" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Level 2 for AAPL" })).toBeNull();
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith(expect.any(String), "NVDA", ["level2"]));
  });

  it("renders a semantic ladder and hides invalid books", async () => {
    mocks.depth.mockImplementation(async (id: string) => id === "NVDA" ? { ...depthPayload(id, "INVALID"), bids: [], asks: [], reason: "CROSSED_BOOK" } : depthPayload(id));
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Level 2" }));
    const panel = await screen.findByRole("region", { name: "Level 2 for AAPL" });
    const table = await within(panel).findByRole("table");
    const headers = within(table).getAllByRole("rowheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Ask", "Best ask", "Spread", "Best bid", "Bid"]);
    expect(within(panel).getByText(/Displayed-liquidity imbalance/)).toBeInTheDocument();
    expect(within(panel).queryByText(/buying pressure/i)).toBeNull();
    await selectRow("NVDA");
    const invalid = await screen.findByRole("region", { name: "Level 2 for NVDA" });
    expect(await within(invalid).findByText("Book is crossed and is not displayed")).toBeInTheDocument();
    expect(within(invalid).queryByRole("table")).toBeNull();
  });

  it("contains a failing panel without breaking the table or other panels", async () => {
    mocks.depth.mockImplementation(async (id: string) => ({ ...depthPayload(id), bids: undefined }));
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "CVD" }));
    fireEvent.click(await screen.findByRole("button", { name: "Level 2" }));
    expect(await screen.findByText(/Level 2 failed to render/)).toBeInTheDocument();
    expect(await screen.findByRole("region", { name: "CVD for AAPL" })).toBeInTheDocument();
    expect(screen.getByRole("grid", { name: "US equity screener" })).toBeInTheDocument();
    spy.mockRestore();
  });

  it("keeps arrow keys local to panels and moves rows only from the table", async () => {
    renderPage();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Level 2" }));
    const panel = await screen.findByRole("region", { name: "Level 2 for AAPL" });
    const ladder = await within(panel).findByLabelText("Order book ladder");
    fireEvent.keyDown(ladder, { key: "ArrowDown" });
    expect(screen.getByText("AAPL", { selector: ".screener-symbol strong" }).closest("[role=row]")).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(screen.getByRole("grid", { name: "US equity screener" }), { key: "ArrowDown" });
    expect(await screen.findByRole("region", { name: "Level 2 for NVDA" })).toBeInTheDocument();
  });

  it("persists presentation only, restores a saved layout, and resets", async () => {
    renderPage({ version: 1, open_panels: ["level2"], active_panel: "level2", dock_height: 360,
      dockview_layout: { grid: { root: { type: "branch", data: [{ type: "leaf", data: { views: ["cvd"], activeView: "cvd", id: "1" }, size: 100 }], size: 360 },
        width: 1000, height: 360, orientation: "HORIZONTAL" }, panels: { cvd: { id: "cvd", contentComponent: "cvd", title: "CVD" } } } });
    // The saved arrangement names another panel set, so it is ignored for a default arrangement of the open panels.
    expect(await screen.findByText("Select an instrument to view Level 2.")).toBeInTheDocument();
    expect(screen.queryByText("Select an instrument to view CVD.")).toBeNull();
    const splitter = screen.getByRole("separator", { name: "Resize specialist panels" });
    expect(splitter).toHaveAttribute("aria-valuenow", "360");
    fireEvent.keyDown(splitter, { key: "ArrowDown" });
    fireEvent.keyDown(splitter, { key: "ArrowDown" });
    expect(splitter).toHaveAttribute("aria-valuenow", "328");
    fireEvent.click(launcher().getByRole("button", { name: "Charts" }));
    // Wait for this test's own debounced save (an earlier test's pending save may also land).
    await waitFor(() => expect(mocks.panelLayout.mock.calls.at(-1)?.[0].open_panels).toEqual(["level2", "charts"]), { timeout: 2000 });
    const saved = mocks.panelLayout.mock.calls.at(-1)![0];
    expect(JSON.stringify(saved)).not.toMatch(/"params"|102\.1|price/);
    fireEvent.click(launcher().getByRole("button", { name: "Reset Panel Layout" }));
    expect(splitter).toHaveAttribute("aria-valuenow", "300");
  });
});

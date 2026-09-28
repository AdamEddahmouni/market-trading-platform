import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "../ScreenerPage";
import { marketClock, marketPrice, marketVolume, pricePrecision, providerLabel, signedMarketVolume, spreadBps } from "../panels/shared";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), last: vi.fn(), preview: vi.fn(), layout: vi.fn(),
  panelLayout: vi.fn(), demand: vi.fn(), releasePanels: vi.fn(), cryptoPreview: vi.fn(),
  flow: vi.fn(), cvd: vi.fn(), depth: vi.fn(), chart: vi.fn(),
}));
vi.mock("../../../api/screener", async (original) => ({
  ...(await original<typeof import("../../../api/screener")>()),
  fetchScreener: mocks.fetch, fetchScreenerConfig: mocks.config, saveScreenerScreen: vi.fn(), deleteScreenerScreen: vi.fn(),
  persistLastScreenerConfig: mocks.last, updateScreenerWindow: mocks.window, releaseScreenerWindow: mocks.release,
  releaseScreenerWindowOnUnload: mocks.release, fetchScreenerPreview: mocks.preview, persistScreenerPreviewLayout: mocks.layout,
  persistScreenerPanelLayout: mocks.panelLayout,
}));
vi.mock("../../../api/screenerPanels", () => ({
  fetchOrderFlow: mocks.flow, fetchCvd: mocks.cvd, fetchDepth: mocks.depth, fetchChart: mocks.chart,
  fetchFuturesContext: vi.fn(() => new Promise(() => undefined)),
  demandPanels: mocks.demand, releasePanels: mocks.releasePanels, releasePanelsOnUnload: mocks.releasePanels,
}));
vi.mock("../../../api/screenerCrypto", () => ({ fetchCryptoPreview: mocks.cryptoPreview }));
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
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
});

const AS_OF = "2026-09-27T12:00:00Z"; // a Sunday: Crypto is open, US equities are not
const f = (value: number | null, basis?: string) => ({ value, source: "KRAKEN_SPOT_PUBLIC", state: value === null ? "UNAVAILABLE" : "SNAPSHOT",
  as_of: value === null ? null : AS_OF, ...(basis ? { basis } : {}) });
const pair = (symbol: string, id: string, base: string, quote: string, increment: string, price: number | null) => ({
  instrument: { instrument_id: id, venue_id: "KRAKEN", asset_class: "CRYPTO", instrument_kind: "CRYPTO_PAIR", tradability: "DISCOVERY_ONLY" },
  symbol, company: symbol, sector: null, industry: null, base_asset: base, quote_asset: quote, venue: "KRAKEN", product_type: "SPOT",
  status: "ONLINE", price_increment: increment, min_order_size: "0.00005", provider_symbol: symbol,
  fields: { price: f(price), change_pct: f(price === null ? null : 2.5, "UTC_DAY_OPEN_TO_LAST"), quote_volume: f(price === null ? null : 1.2e6),
    bid: f(price), ask: f(price), spread_pct: f(price === null ? null : 0.012), base_volume: f(10), high_24h: f(price), low_24h: f(price), trade_count: f(200) },
});
const BTC = pair("BTC/USD", "XA01:BTC", "BTC", "USD", "0.1", 83000.1);
const SHIB = pair("SHIB/USD", "XA01:SHIB", "SHIB", "USD", "0.000000001", 0.000005739);
const DARK = pair("NEW/USD", "XA01:NEW", "NEW", "USD", "0.0001", null);
const page = (rows = [BTC, SHIB, DARK]) => ({
  schema_version: "screener/1.0.0", universe: "CRYPTO", generated_at: AS_OF, market_session: "24_7", universe_as_of: AS_OF,
  screener_as_of: AS_OF, evaluation: "SNAPSHOT", snapshot: { id: AS_OF, as_of: AS_OF, source: "KRAKEN_SPOT_PUBLIC", complete: true, total: 3,
    returned: 3, priced: 2, refused: 0, refused_reason: null },
  result_count: rows.length, unfiltered_count: 3, offset: 0, limit: 200, returned: rows.length, has_more: false, result_set_id: "crypto-1",
  source_error: null, provider_health: [{ provider: "KRAKEN_SPOT_PUBLIC", role: "CATALOG", state: "CURRENT", reason: null }], rows,
});
const cryptoViews = {
  Overview: ["symbol", "price", "change_pct", "quote_volume", "bid", "ask", "spread_pct", "venue"],
  Performance: ["symbol", "price", "change_pct", "high_24h", "low_24h", "base_volume", "quote_volume"],
  Liquidity: ["symbol", "bid", "ask", "spread_pct", "quote_volume", "trade_count", "venue"],
  Custom: ["symbol", "base_asset", "quote_asset", "price", "change_pct", "quote_volume"],
};
const caps = (fields: string[], execution: string) => Object.fromEntries(fields.map((field) => [field, { execution, sortable: true, filterable: true }]));
const config = () => ({
  schema_version: 2, persistence_available: true, presets: [], saved: [], last: null, preview_layout: { version: 1, open: true, width: 400 },
  catalog: [
    { field: "change_pct", label: "Change %", category: "Price & Movement", type: "number", unit: "percent", operators: ["gt"], universes: ["US_EQUITIES", "CRYPTO"], availability: "SNAPSHOT" },
    { field: "quote_volume", label: "24h Quote Volume", category: "Volume & Liquidity", type: "number", unit: "QUOTE_UNITS", operators: ["gt"], universes: ["CRYPTO"], availability: "CURRENT_SPOT" },
  ],
  universes: [
    { id: "US_EQUITIES", label: "US Equities", asset_class: "EQUITY", instrument_kind: "X", source: "X", session_model: "US_EQUITY", default_sort: "volume",
      default_columns: ["symbol", "price"], views: { Overview: ["symbol", "price"], Custom: ["symbol"] }, view_order: ["Overview", "Custom"],
      quote_capability: "US_EQUITY_L1", bars_capability: "X", panels: ["order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze"],
      fields: caps(["symbol", "price", "change_pct", "volume"], "CATALOG") },
    { id: "CRYPTO", label: "Crypto", asset_class: "CRYPTO", instrument_kind: "CRYPTO_PAIR", source: "KRAKEN_SPOT_PUBLIC", session_model: "24_7",
      default_sort: "symbol", default_columns: cryptoViews.Overview, views: cryptoViews, view_order: Object.keys(cryptoViews),
      quote_capability: "KRAKEN_PUBLIC_TICKER", bars_capability: "KRAKEN_PUBLIC_OHLC", panels: ["order_flow", "cvd", "level2", "charts"],
      tradability: "DISCOVERY_ONLY",
      fields: { ...caps(["symbol", "venue", "base_asset", "quote_asset"], "CATALOG"),
        ...caps(["price", "quote_volume", "bid", "ask", "spread_pct", "high_24h", "low_24h", "base_volume", "trade_count"], "SNAPSHOT"),
        change_pct: { execution: "SNAPSHOT", sortable: true, filterable: true, label: "UTC Day Change %", unit: "UTC_DAY_PERCENT" } } },
  ],
});
const bars = (count: number) => Array.from({ length: count }, (_, index) => {
  const time = 1790510400 + index * 60;
  return { time, start: new Date(time * 1000).toISOString(), end: new Date((time + 60) * 1000).toISOString(),
    open: 83000, high: 83010, low: 82990, close: 83005, volume: 1.5, session: "24_7" };
});
const preview = (row = BTC) => ({
  schema_version: "screener-crypto-preview/1.0.0", generated_at: AS_OF, market_session: "24_7",
  instrument: { ...row.instrument, symbol: row.symbol, base_asset: row.base_asset, quote_asset: row.quote_asset, venue: "KRAKEN", product_type: "SPOT",
    status: "ONLINE", price_increment: row.price_increment, min_order_size: "0.00005", base_increment: "0.00000001", quote_increment: "0.00001",
    min_order_notional: "0.5", catalog_as_of: AS_OF },
  snapshot_as_of: AS_OF, fields: row.fields,
  quote: { state: "SNAPSHOT", reason: null, fields: row.fields },
  bars: { timeframe: "1m", session_scope: "24_7", provider: "KRAKEN_SPOT_PUBLIC", state: "CURRENT", reason: null, received_at: AS_OF,
    latest_complete_bar_end: bars(30)[29].end, bar_count: 30, bars: bars(30), forming: null },
  levels: { method: "AUTO_SR", state: "CURRENT", reason: null, calculated_at: AS_OF, input_bar_count: 30, min_strength: 40, zones: [], price: null },
  why: { matched: { state: "NO_ACTIVE_FILTERS", items: [] } },
  source_health: { catalog: "CURRENT", snapshot: "SNAPSHOT", quote: "SNAPSHOT", bars: "CURRENT" },
});
const iso = (offset = 0) => new Date(Date.now() - offset).toISOString();
const specialist = (id: string, panel: string, state = "CURRENT", reason: string | null = null) => ({
  schema_version: "screener-specialist/1.0.0", instrument_id: id, provider: "KRAKEN", generated_at: iso(), market_session: "24_7",
  state, reason, entitlement: "PROBE_VERIFIED", panel,
});
const window_ = { basis: "SINCE_SUBSCRIPTION", anchor_at: "2026-09-27T12:00:00Z", start: iso(5000), end: iso(1000), max_records: 5000, truncated: false };
const flow = (id: string) => ({
  ...specialist(id, "order_flow"), window: window_, latest_event_at: "2026-09-27T12:00:05Z", latest_received_at: iso(900),
  summary: { trade_count: 2, total_volume: 0.7, buy_volume: 0.5, sell_volume: 0.2, unknown_volume: 0, net_signed_volume: 0.3,
    classified_volume_pct: 100, native_count: 2, inferred_count: 0, unknown_count: 0, methods: { EXCHANGE_NATIVE: 2 },
    trades_per_minute: null, large_print_threshold: null },
  tape: [
    { trade_id: "2", event_time: "2026-09-27T12:00:05Z", received_time: iso(900), price: 83000.1, size: 0.2, aggressor: { state: "NATIVE", side: "SELL", method: "EXCHANGE_NATIVE" }, condition: "market", large: false },
    { trade_id: "1", event_time: "2026-09-27T12:00:04Z", received_time: iso(1900), price: 83000.2, size: 0.5, aggressor: { state: "NATIVE", side: "BUY", method: "EXCHANGE_NATIVE" }, condition: "limit", large: false },
  ],
});
const depth = (id: string, state = "CURRENT", reason: string | null = null) => ({
  ...specialist(id, "level2", state, reason),
  bids: state === "INVALID" ? [] : [{ price: 0.000005739, size: 2_000_000, cumulative_size: 2_000_000 }],
  asks: state === "INVALID" ? [] : [{ price: 0.000005741, size: 1_000_000, cumulative_size: 1_000_000 }],
  best_bid: 0.000005739, best_ask: 0.000005741, spread: 0.000000002, mid: 0.00000574, spread_bps: 3.48, imbalance: [],
  completeness: { basis: "VENUE_TOP_N", bid_levels: 25, ask_levels: 25, venue_scope: "SINGLE_VENUE_KRAKEN", update_semantics: "SNAPSHOT_PLUS_DELTA_CRC32" },
  freshness: { status: "FRESH", age_ms: 30, ttl_ms: 5000, policy: "kraken_l2" }, latest_event_at: "2026-09-27T12:00:05Z", latest_received_at: iso(30), quality_flags: [],
});

function mount(path = "/screener?universe=CRYPTO") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path="/screener" element={<ScreenerPage />} /><Route path="/workspace/:symbol" element={<div>Instrument workspace</div>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}
const headers = () => screen.getAllByRole("columnheader").map((header) => header.textContent?.replace(/[▲▼]/g, "").trim());
const launcher = () => within(screen.getByRole("navigation", { name: "Open panels" }));
const select = async (symbol: string) => {
  await screen.findByText(symbol, { selector: ".screener-symbol strong" });
  await waitFor(() => expect(mocks.window).toHaveBeenCalled());
  await act(async () => { await Promise.resolve(); });
  fireEvent.click(screen.getByText(symbol, { selector: ".screener-symbol strong" }));
};

describe("Crypto universe", () => {
  beforeEach(() => {
    mocks.config.mockReset().mockResolvedValue(config());
    mocks.fetch.mockReset().mockResolvedValue(page());
    mocks.window.mockReset().mockResolvedValue({ schema_version: "screener/1.0.0", generated_at: AS_OF, market_session: "24_7", active: 0, cap: 30, quotes: {} });
    mocks.release.mockReset().mockResolvedValue({ released: true });
    mocks.last.mockReset().mockResolvedValue({ result: {}, saved: [] });
    mocks.layout.mockReset().mockResolvedValue({}); mocks.panelLayout.mockReset().mockResolvedValue({});
    mocks.preview.mockReset().mockImplementation(() => new Promise(() => undefined));
    mocks.cryptoPreview.mockReset().mockImplementation(async (id: string) => preview(id === "XA01:SHIB" ? SHIB : BTC));
    mocks.demand.mockReset().mockImplementation(async (_client: string, instrument: string | null, panels: string[]) =>
      ({ schema_version: "screener-specialist/1.0.0", instrument_id: instrument, panels, capabilities: [], cap: { max_instruments: 6, occupied_instruments: 1 } }));
    mocks.releasePanels.mockReset().mockResolvedValue({ released: true });
    mocks.flow.mockReset().mockImplementation(async (id: string) => flow(id));
    mocks.cvd.mockReset().mockReturnValue(new Promise(() => undefined));
    mocks.depth.mockReset().mockImplementation(async (id: string) => depth(id));
    mocks.chart.mockReset().mockReturnValue(new Promise(() => undefined));
    vi.stubGlobal("crypto", { randomUUID: () => "abc-123" });
  });

  it("restores Crypto from the URL with pair identity, UTC-day change, 24/7 session, and venue precision", async () => {
    mount();
    await screen.findByText("BTC/USD", { selector: ".screener-symbol strong" });
    expect(screen.getByRole("combobox", { name: "Screener universe" })).toHaveValue("CRYPTO");
    expect(mocks.fetch).toHaveBeenCalledWith(expect.objectContaining({ universe: "CRYPTO" }), expect.anything(), expect.anything());
    expect(headers()).toEqual(["Pair", "Price", "UTC day %", "24h Quote Vol", "Bid", "Ask", "Spread %", "Venue"]);
    // Resize handles name the header the viewer sees, not the shared equity label.
    expect(screen.getByRole("separator", { name: "Resize Pair" })).toBeInTheDocument();
    expect(screen.getByRole("separator", { name: "Resize UTC day %" })).toBeInTheDocument();
    const shib = screen.getByText("SHIB/USD", { selector: ".screener-symbol strong" }).closest("[role=row]") as HTMLElement;
    expect(within(shib).getAllByText("0.000005739").length).toBeGreaterThan(0); // never rounded to 0.00
    const dark = screen.getByText("NEW/USD", { selector: ".screener-symbol strong" }).closest("[role=row]") as HTMLElement;
    expect(within(dark).getAllByText("—").length).toBeGreaterThan(2); // missing price stays missing, never 0
    expect(screen.getAllByText("24/7").length).toBeGreaterThan(0);
    expect(screen.queryByText(/RTH|Pre-market|After hours|Market Cap|Float|Sector/)).not.toBeInTheDocument();
    expect(screen.getAllByText("KRAKEN").length).toBeGreaterThan(0);
    expect(screen.getByText(/^Universe as of \d{2}:\d{2}:\d{2} UTC$/)).toBeInTheDocument(); // venue UTC, like every Crypto clock
  });

  it("labels visible-row venue REST quotes as snapshots, never as live or unavailable", async () => {
    mocks.window.mockResolvedValue({ schema_version: "screener/1.0.0", generated_at: AS_OF, market_session: "24_7", active: 0, cap: 30,
      quotes: { "XA01:BTC": { state: "SNAPSHOT", session_state: "24_7", reason: null, fields: BTC.fields } } });
    mount();
    await screen.findByText("BTC/USD", { selector: ".screener-symbol strong" });
    expect(await screen.findByText("Quotes REST snapshot for visible rows")).toBeInTheDocument();
    await waitFor(() => expect(mocks.window).toHaveBeenCalledWith(expect.any(String), expect.arrayContaining(["XA01:BTC"]), "CRYPTO"));
  });

  it("names the change a UTC-day change in filters", async () => {
    mount();
    await screen.findByText("BTC/USD", { selector: ".screener-symbol strong" });
    fireEvent.click(screen.getByRole("button", { name: "+ Add Filter" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("UTC Day Change %")).toBeInTheDocument();
    expect(within(dialog).queryByText("Change %")).not.toBeInTheDocument();
  });

  it("opens the Crypto Quick Preview, never a Workspace, with structure and source clocks and no equity fields", async () => {
    mount();
    await select("BTC/USD");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    await within(pane).findByRole("region", { name: "Pair structure" });
    await waitFor(() => expect(mocks.cryptoPreview).toHaveBeenCalledWith("XA01:BTC", "1m", [], expect.anything()));
    expect(within(pane).getByText("BTC/USD · KRAKEN · SPOT · 24/7")).toBeInTheDocument();
    expect(within(pane).getByText("UTC day change")).toBeInTheDocument();
    expect(within(pane).getByText("0.00000001 BTC")).toBeInTheDocument();
    expect(within(pane).getByText("0.00001 USD")).toBeInTheDocument();
    expect(within(pane).getByText(/venue ticker carries no event timestamp/)).toBeInTheDocument();
    expect(within(pane).queryByText(/Float|Short|Earnings|Sector|Market cap|RTH/i)).not.toBeInTheDocument();
    fireEvent.doubleClick(screen.getByText("BTC/USD", { selector: ".screener-symbol strong" }));
    expect(screen.queryByText("Instrument workspace")).not.toBeInTheDocument();
  });

  it("never demands or fetches a Crypto pair against another universe after a switch", async () => {
    mount();
    await select("BTC/USD");
    fireEvent.click(launcher().getByRole("button", { name: "Order Flow" }));
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith(expect.any(String), "XA01:BTC", ["order_flow"], "CRYPTO"));
    fireEvent.change(screen.getByRole("combobox", { name: "Screener universe" }), { target: { value: "US_EQUITIES" } });
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Screener universe" })).toHaveValue("US_EQUITIES"));
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    const crossed = mocks.demand.mock.calls.filter((call) => call[1] === "XA01:BTC" && call[3] !== "CRYPTO");
    expect(crossed).toEqual([]);
    expect(mocks.flow.mock.calls.filter((call) => call[0] === "XA01:BTC" && call[2] !== "CRYPTO")).toEqual([]);
  });

  it("says Crypto is not enabled, with no rows or values, when the venue source is not configured", async () => {
    mocks.fetch.mockResolvedValue({ ...page([]), market_session: "UNAVAILABLE", snapshot: null, universe_as_of: null, screener_as_of: null,
      result_count: 0, unfiltered_count: 0, result_set_id: null, source_error: "CRYPTO_NOT_CONFIGURED",
      provider_health: [{ provider: "KRAKEN_SPOT_PUBLIC", role: "CATALOG", state: "NOT_CONFIGURED", reason: "CRYPTO_NOT_CONFIGURED" }] });
    mount();
    expect(await screen.findByText(/Kraken public market data is not enabled/)).toBeInTheDocument();
    expect(screen.queryByText(/could not be refreshed/)).not.toBeInTheDocument();
    expect(screen.queryByText("BTC/USD", { selector: ".screener-symbol strong" })).not.toBeInTheDocument();
  });

  it("offers only the venue-backed panels", async () => {
    mount();
    await screen.findByText("BTC/USD", { selector: ".screener-symbol strong" });
    for (const name of ["Order Flow", "CVD", "Level 2", "Charts"]) expect(launcher().getByRole("button", { name })).toBeEnabled();
    for (const name of ["Futures Context · unavailable", "Options · unavailable", "Short Squeeze · unavailable", "Rates & Curve · unavailable"]) {
      expect(launcher().getByRole("button", { name })).toBeDisabled();
    }
  });

  it("renders Kraken order flow as the venue taker side on UTC clocks", async () => {
    mount();
    await select("BTC/USD");
    fireEvent.click(launcher().getByRole("button", { name: "Order Flow" }));
    const panel = await screen.findByRole("region", { name: "Order Flow for BTC/USD" });
    await within(panel).findByText("Taker buy vol");
    expect(mocks.flow).toHaveBeenCalledWith("XA01:BTC", expect.anything(), "CRYPTO");
    await waitFor(() => expect(mocks.demand).toHaveBeenLastCalledWith(expect.any(String), "XA01:BTC", ["order_flow"], "CRYPTO"));
    expect(within(panel).getByText(/Direction is the venue-reported taker side/)).toBeInTheDocument();
    expect(within(panel).queryByText(/not a known buyer or seller/)).not.toBeInTheDocument();
    expect(within(panel).getByText("Buy")).toBeInTheDocument(); // native, not "Inf. Buy"
    expect(within(panel).getByText("+0.3")).toBeInTheDocument(); // fractional BTC net, not "+0"
    expect(within(panel).getByText("12:00:05")).toBeInTheDocument(); // UTC tape time
    expect(within(panel).getByText(/Kraken/)).toBeInTheDocument();
    expect(within(panel).getByText(/last print 12:00:05 UTC/)).toBeInTheDocument();
    expect(within(panel).queryByText(/ ET\b/)).not.toBeInTheDocument();
  });

  it("shows the checksummed venue book and hides a book that failed the checksum", async () => {
    mocks.depth.mockImplementation(async (id: string) => id === "XA01:BTC" ? depth(id, "INVALID", "CHECKSUM_MISMATCH") : depth(id));
    mount();
    await select("SHIB/USD");
    fireEvent.click(launcher().getByRole("button", { name: "Level 2" }));
    const panel = await screen.findByRole("region", { name: "Level 2 for SHIB/USD" });
    await within(panel).findByRole("table");
    expect(within(panel).getAllByText("0.000005739").length).toBeGreaterThan(0);
    expect(within(panel).getByText(/verified against the venue checksum; one venue, not a consolidated crypto market/)).toBeInTheDocument();
    expect(within(panel).getByText(/Venue book 25×25 levels · Kraken/)).toBeInTheDocument();
    await select("BTC/USD");
    const invalid = await screen.findByRole("region", { name: "Level 2 for BTC/USD" });
    expect(await within(invalid).findByText("Book failed the venue checksum; resyncing")).toBeInTheDocument();
    expect(within(invalid).queryByRole("table")).toBeNull();
  });

  it("charts a continuous 24/7 series without equity session scopes", async () => {
    mocks.chart.mockImplementation(async (id: string) => ({
      schema_version: "screener-chart/1.0.0", generated_at: AS_OF, market_session: "24_7",
      instrument: { instrument_id: id, symbol: "BTC/USD", company: "BTC/USD" }, quote: { state: "SNAPSHOT", fields: {} },
      bars: { ...preview().bars, source_id: "KRAKEN_OHLC:BTC/USD:5m" },
      levels: { method: "AUTO_SR", state: "CURRENT", reason: null, calculated_at: AS_OF, input_bar_count: 30, input_latest_bar_end: null,
        min_strength: 40, zones: [], price: { value: 83000.1, source: "KRAKEN_TICKER_LAST", state: "SNAPSHOT", as_of: AS_OF } },
    }));
    mount();
    await select("BTC/USD");
    fireEvent.click(launcher().getByRole("button", { name: "Charts" }));
    const panel = await screen.findByRole("region", { name: "Charts for BTC/USD" });
    expect((await within(panel).findAllByText(/Kraken last 83,000.10 USD/)).length).toBeGreaterThan(0);
    expect(mocks.chart).toHaveBeenCalledWith("XA01:BTC", "5m", "EXTENDED", expect.anything(), "CRYPTO");
    expect(within(panel).queryByRole("group", { name: "Session scope" })).toBeNull();
    expect(within(panel).getByText(/24\/7 · Kraken public OHLC/)).toBeInTheDocument();
    expect(within(panel).queryByText(/Moomoo|RTH| ET\b/)).not.toBeInTheDocument();
  });
});

describe("Crypto presentation helpers", () => {
  const row = { price_increment: "0.000000001" } as never;
  it("keeps the venue increment and sub-cent precision; US prices keep their format", () => {
    expect(pricePrecision(row, 0.000005739)).toBe(9);
    expect(marketPrice(0.000005739, row, "CRYPTO")).toBe("0.000005739");
    expect(marketPrice(83000.1, { price_increment: "0.1" } as never, "CRYPTO")).toBe("83,000.10");
    expect(marketPrice(12.345, null, "US_EQUITIES")).toBe("12.35");
  });
  it("reads UTC for Crypto and ET for US markets, and names providers", () => {
    expect(marketClock("CRYPTO").clock("2026-09-27T12:00:05Z")).toBe("12:00:05 UTC");
    expect(marketClock("US_EQUITIES").clock("2026-09-27T12:00:05Z")).toBe("08:00:05 ET");
    expect(providerLabel("KRAKEN")).toBe("Kraken");
    expect(providerLabel(null)).toBe("No provider");
  });
  it("never rounds fractional base-unit volume or a sub-0.1 bps spread to zero", () => {
    expect(marketVolume(0.01234567, "CRYPTO")).toBe("0.01235");
    expect(signedMarketVolume(-0.0004501, "CRYPTO")).toBe("−0.0004501");
    expect(signedMarketVolume(0, "CRYPTO")).toBe("0");
    expect(marketVolume(2_427.71, "CRYPTO")).toBe("2.4K");
    expect(marketVolume(0.012, "US_EQUITIES")).toBe("0");
    expect(spreadBps(0.012)).toBe("0.012");
    expect(spreadBps(1.234)).toBe("1.2");
    expect(spreadBps(0)).toBe("0.0");
  });
});

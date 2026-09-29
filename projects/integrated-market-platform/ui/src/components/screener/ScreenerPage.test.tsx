import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StrictMode } from "react";
import { ScreenerPage } from "./ScreenerPage";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), save: vi.fn(), remove: vi.fn(), last: vi.fn(),
}));
vi.mock("../../api/screener", () => ({
  fetchScreener: mocks.fetch,
  fetchScreenerConfig: mocks.config,
  saveScreenerScreen: mocks.save,
  deleteScreenerScreen: mocks.remove,
  persistLastScreenerConfig: mocks.last,
  updateScreenerWindow: mocks.window,
  releaseScreenerWindow: mocks.release,
  releaseScreenerWindowOnUnload: mocks.release,
}));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34,
    scrollToIndex: vi.fn(),
  }),
}));

const field = (value: number | null) => ({ value, source: "FINVIZ_ELITE", state: value === null ? "UNAVAILABLE" : "SNAPSHOT", as_of: "2026-09-25T13:00:00Z" });
const makeRow = (symbol: string, company: string, change: number) => ({
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY" },
  symbol, company, sector: null, industry: null,
  fields: { price: field(12), change_pct: field(change), volume: field(1000),
    rel_volume: field(2), float_shares: field(null), market_cap: field(1000000),
    short_float_pct: field(null), rsi_14: field(60) },
});
const rows = [makeRow("AAPL", "Apple Inc", 2), makeRow("MSFT", "Microsoft Corp", -3)];
const payload = {
  schema_version: "screener/1.0.0", universe: "US_EQUITIES",
  generated_at: "2026-09-25T13:00:00Z", universe_as_of: "2026-09-25T13:00:00Z",
  screener_as_of: "2026-09-25T13:00:00Z", market_session: "REGULAR",
  result_count: 2, source_error: null,
  provider_health: [{ provider: "FINVIZ_ELITE", state: "HEALTHY", reason: null }], rows,
};

// Server-published field capabilities (S6): only CATALOG/SNAPSHOT fields sort the universe.
const caps = (sortable: string[], windowOnly: string[] = []) => Object.fromEntries([
  ...sortable.map((field) => [field, { execution: "SNAPSHOT", sortable: true, filterable: true }]),
  ...windowOnly.map((field) => [field, { execution: "LIVE_WINDOW", sortable: false, filterable: false }]),
]);
const equityViews = {
  Overview: ["symbol", "price", "change_pct", "volume", "rel_volume", "float_shares", "market_cap", "short_float_pct", "bid", "ask", "spread_pct", "rsi_14"],
  Performance: ["symbol", "price", "change_pct", "perf_week", "volume", "rel_volume", "rsi_14", "market_cap"],
  Technical: ["symbol", "price", "change_pct", "rsi_14", "perf_week", "volume", "rel_volume"],
  Volume: ["symbol", "price", "volume", "avg_volume", "rel_volume", "float_shares", "change_pct"],
  "Short Squeeze": ["symbol", "price", "change_pct", "rel_volume", "volume", "float_shares", "short_float_pct", "short_ratio", "bid", "ask", "spread_pct"],
  Fundamentals: ["symbol", "company", "sector", "industry", "market_cap", "eps_ttm", "pe", "fwd_pe", "earnings_date", "recommendation"],
  Custom: ["symbol", "price", "change_pct", "volume"],
};
const equitySpec = { id: "US_EQUITIES", label: "US Equities", asset_class: "EQUITY", instrument_kind: "TRADABLE_SECURITY",
  source: "FINVIZ_ELITE", session_model: "US_EQUITY", default_sort: "volume", default_columns: equityViews.Overview,
  views: equityViews, view_order: Object.keys(equityViews), view_aliases: { Short: "Short Squeeze" }, quote_capability: "US_EQUITY_L1",
  bars_capability: "US_EQUITY_CURRENT_KLINE", panels: ["order_flow", "cvd", "level2", "charts", "futures"],
  fields: caps(["symbol", "company", "price", "change_pct", "volume", "avg_volume", "rel_volume", "float_shares", "market_cap",
    "short_float_pct", "short_ratio", "rsi_14", "eps_ttm", "pe", "fwd_pe", "perf_week"], ["bid", "ask", "spread_pct"]) };
const called = (query: Record<string, unknown>, options: Record<string, unknown> = {}) =>
  [expect.objectContaining(query), expect.objectContaining({ offset: 0 }), expect.objectContaining(options)];

const s5Field = (field: string, label: string, universes: string[], type: "text" | "number" = "text") => ({
  field, label, category: "Contract", type, unit: type === "text" ? "text" : "days",
  operators: type === "text" ? ["eq", "contains"] : ["eq", "lt", "gt"], universes, availability: "CURRENT_METADATA",
});
const s5Config = (saved: unknown[] = []) => ({ schema_version: 2, persistence_available: true,
  catalog: [s5Field("symbol", "Symbol", ["US_EQUITIES", "FUTURES", "US_ETFS"]),
    s5Field("root", "Root", ["FUTURES"]), s5Field("dte", "Days to Expiry", ["FUTURES"], "number"),
    s5Field("exchange", "Exchange", ["FUTURES", "US_ETFS"])],
  universes: [
    { id: "US_EQUITIES", label: "US Equities", asset_class: "EQUITY", instrument_kind: "TRADABLE_SECURITY",
      source: "FINVIZ_ELITE", session_model: "US_EQUITY", default_sort: "volume",
      default_columns: ["symbol", "price", "volume"],
      views: { Overview: ["symbol", "price", "volume"], Technical: ["symbol", "price"], Custom: ["symbol", "price"] },
      quote_capability: "US_EQUITY_L1", bars_capability: "US_EQUITY_CURRENT_KLINE",
      panels: ["order_flow", "cvd", "level2", "charts", "futures"], fields: caps(["symbol", "price", "volume"]) },
    { id: "FUTURES", label: "Futures", asset_class: "FUTURE", instrument_kind: "FUTURE_CONTRACT",
      source: "MOOMOO_OPEND_CONTRACT_CATALOG", session_model: "PROVIDER_STATE", default_sort: "root",
      default_columns: ["symbol", "root", "expiry", "dte"],
      // Server JSON sorts keys; view_order carries the registry order.
      views: { Contract: ["symbol", "root", "expiry", "dte"], Custom: ["symbol", "root"],
        Overview: ["symbol", "root", "expiry", "dte"], Performance: ["symbol", "root"] },
      view_order: ["Overview", "Contract", "Performance", "Custom"],
      quote_capability: "US_FUTURES_QUOTE", bars_capability: "FUTURES_CURRENT_KLINE_UNVERIFIED", panels: [],
      fields: caps(["symbol", "root", "expiry", "dte"]) },
    { id: "US_ETFS", label: "ETFs", asset_class: "ETF_FUND", instrument_kind: "TRADABLE_SECURITY",
      source: "MOOMOO_OPEND_ETF_CATALOG", session_model: "US_EQUITY", default_sort: "symbol",
      default_columns: ["symbol", "company", "exchange"],
      views: { Overview: ["symbol", "company", "exchange"], Performance: ["symbol", "company"],
        Custom: ["symbol", "company"] },
      quote_capability: "US_EQUITY_L1", bars_capability: "US_EQUITY_CURRENT_KLINE",
      panels: ["order_flow", "cvd", "level2", "charts"], fields: caps(["symbol", "company", "exchange"]) },
  ], presets: [], saved, last: null });
const s5Rows = {
  FUTURES: [{ instrument: { instrument_id: "XA01-FUTURE-ESZ26", venue_id: "CME", asset_class: "FUTURE", instrument_kind: "FUTURE_CONTRACT" },
    symbol: "ESZ26", company: "E-mini S&P 500", root: "ES", exchange: "CME", expiry: "2026-12-18", lead: true,
    sector: null, industry: null, fields: { dte: { value: 82, source: "MOOMOO_OPEND", state: "CURRENT_METADATA", as_of: "2026-09-27T12:00:00Z" } } }],
  US_ETFS: [{ instrument: { instrument_id: "XA01-ETF-SPY", venue_id: "NYSE", asset_class: "ETF_FUND", instrument_kind: "TRADABLE_SECURITY" },
    symbol: "SPY", company: "SPDR S&P 500 ETF", exchange: "NYSE", sector: null, industry: null,
    fields: { price: { value: null, source: "MOOMOO_OPEND", state: "UNAVAILABLE", as_of: null } } }],
};

function mockS5(saved: unknown[] = []) {
  mocks.config.mockResolvedValue(s5Config(saved));
  mocks.fetch.mockImplementation(async ({ universe }: { universe: string }) => {
    const selected = universe === "FUTURES" ? s5Rows.FUTURES : universe === "US_ETFS" ? s5Rows.US_ETFS : rows;
    return { ...payload, universe: universe ?? "US_EQUITIES", market_session: universe === "FUTURES" ? "PROVIDER_SPECIFIC" : "REGULAR",
      rows: selected, result_count: selected.length, unfiltered_count: selected.length };
  });
}

function mount(path = "/screener") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <HistoryBack />
    <Routes><Route path="/screener" element={<ScreenerPage />} /><Route path="/workspace/:symbol" element={<div>Instrument workspace</div>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

function HistoryBack() {
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate(-1)}>Browser back</button>;
}

describe("ScreenerPage", () => {
  beforeEach(() => {
    mocks.config.mockReset().mockResolvedValue({ schema_version: 1, persistence_available: true, universes: [equitySpec],
      catalog: [
        { field: "price", label: "Price", category: "Price & Movement", type: "number", unit: "USD", operators: ["gt", "between"], universes: ["US_EQUITIES"], availability: "SNAPSHOT" },
        { field: "rel_volume", label: "Relative Volume", category: "Volume & Liquidity", type: "number", unit: "ratio", operators: ["gt"], universes: ["US_EQUITIES"], availability: "SNAPSHOT" },
      ], presets: [{ id: "UNUSUAL_VOLUME_DISCOVERY", name: "Unusual Volume", version: "1.0.0", status: "SUPPORTED", reason: null,
        filters: [{ id: "u", field: "rel_volume", operator: "gt", value: 2 }] }], saved: [] });
    mocks.save.mockReset().mockImplementation(async (value) => ({ result: { ...value, id: "user-1", version: 1 }, saved: [{ ...value, id: "user-1", version: 1 }] }));
    mocks.remove.mockReset().mockResolvedValue({ result: true, saved: [] });
    mocks.last.mockReset().mockResolvedValue({ result: {}, saved: [] });
    mocks.fetch.mockReset().mockImplementation(async ({ search }: { search: string }) => ({
      ...payload,
      rows: rows.filter((row) => `${row.symbol} ${row.company}`.toLowerCase().includes(search.toLowerCase())),
      result_count: rows.filter((row) => `${row.symbol} ${row.company}`.toLowerCase().includes(search.toLowerCase())).length,
      market_session: "REGULAR",
    }));
    mocks.window.mockReset().mockResolvedValue({ quotes: {}, active: 0, cap: 32 });
    mocks.release.mockReset().mockResolvedValue({ released: true });
    vi.stubGlobal("crypto", { randomUUID: () => "abc-123" });
  });

  it("renders real rows, unavailable values, direction, and canonical navigation", async () => {
    mount();
    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument());
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("+2.00%")).toHaveClass("screener-positive");
    expect(screen.getByText("-3.00%")).toHaveClass("screener-negative");
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("columnheader", { name: /Price/ }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(...called({ search: "", sort: "price", descending: true })));
    fireEvent.click(screen.getByRole("columnheader", { name: /Price/ }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(...called({ search: "", sort: "price", descending: false })));
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    fireEvent.keyDown(grid, { key: "Enter" });
    expect(screen.getByText("Instrument workspace")).toBeInTheDocument();
  });

  it("searches symbol and company, focuses with slash, and shows empty result", async () => {
    mount();
    await screen.findByText("AAPL");
    fireEvent.keyDown(window, { key: "/" });
    const input = screen.getByRole("textbox", { name: "Search instruments" });
    expect(input).toHaveFocus();
    fireEvent.change(input, { target: { value: "Microsoft" } });
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(...called({ search: "Microsoft", sort: "volume", descending: true })));
    fireEvent.change(input, { target: { value: "NO_MATCH" } });
    expect(await screen.findByText("No instruments match this search.")).toBeInTheDocument();
  });

  it("does not display stale bid or ask and starts arrow navigation at the first row", async () => {
    mocks.window.mockResolvedValue({
      quotes: {
        AAPL: {
          state: "STALE", age_ms: 10_000,
          fields: {
            bid: { value: 11.9, source: "MOOMOO", state: "STALE", as_of_ns: 1 },
            ask: { value: 12.1, source: "MOOMOO", state: "STALE", as_of_ns: 1 },
          },
        },
      },
      active: 1, cap: 32,
    });
    mount();
    await screen.findByText("AAPL");
    await waitFor(() => expect(mocks.window).toHaveBeenCalled());
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(screen.getByRole("row", { name: /AAPL/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("11.90")).not.toBeInTheDocument();
    expect(screen.queryByText("12.10")).not.toBeInTheDocument();
  });

  it("releases subscriptions after an in-flight window request on unmount", async () => {
    let resolveWindow!: (value: { quotes: Record<string, never>; active: number; cap: number }) => void;
    mocks.window.mockImplementationOnce(() => new Promise((resolve) => { resolveWindow = resolve; }));
    const view = mount();
    await screen.findByText("AAPL");
    await waitFor(() => expect(mocks.window).toHaveBeenCalled());
    view.unmount();
    expect(mocks.release).not.toHaveBeenCalled();
    resolveWindow({ quotes: {}, active: 0, cap: 32 });
    await waitFor(() => expect(mocks.release).toHaveBeenCalledWith("abc123"));
  });

  it("labels source failure without fixture fallback", async () => {
    mocks.fetch.mockResolvedValueOnce({ ...payload, rows: [], result_count: 0, source_error: "NOT_CONFIGURED" });
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent("Screener source unavailable");
    expect(screen.getByRole("alert")).toHaveTextContent("Finviz access is not configured");
    fireEvent.click(screen.getByRole("button", { name: "Retry source" }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(...called({ sort: "volume" }, { refresh: true })));
    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument(), { timeout: 3_000 });
  });

  it("names an unverifiable ETF classification instead of showing an empty ETF universe", async () => {
    mockS5();
    mocks.fetch.mockImplementation(async ({ universe }: { universe: string }) => ({ ...payload, universe, rows: [],
      result_count: 0, unfiltered_count: 0, result_set_id: null, source_error: "CLASSIFICATION_UNAVAILABLE" }));
    mount("/screener?universe=US_ETFS");
    expect(await screen.findByRole("alert")).toHaveTextContent("ETF membership cannot be verified");
    expect(screen.queryByText("SPY")).not.toBeInTheDocument();
  });

  it("switches views without changing the result query or quote window", async () => {
    mount();
    await screen.findByText("AAPL");
    const calls = mocks.fetch.mock.calls.length;
    const windows = mocks.window.mock.calls.length;
    fireEvent.click(screen.getByRole("tab", { name: "Technical" }));
    expect(screen.getByRole("columnheader", { name: /RSI/ })).toBeInTheDocument();
    expect(mocks.fetch.mock.calls.length).toBe(calls);
    expect(mocks.window.mock.calls.length).toBe(windows);
  });

  it("adds edits and removes a typed filter", async () => {
    mount();
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: /Add Filter/ }));
    fireEvent.click(screen.getByRole("button", { name: "Price" }));
    fireEvent.change(screen.getByLabelText("Filter value"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(...called({ sort: "volume", descending: true,
      filters: [expect.objectContaining({ field: "price", operator: "gt", value: 10 })] })));
    fireEvent.click(screen.getByRole("button", { name: /Edit Price/ }));
    fireEvent.change(screen.getByLabelText("Filter value"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
    expect(screen.getByText(/Price > \$12/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Remove Price/ }));
    expect(screen.queryByText(/Price > \$12/)).not.toBeInTheDocument();
  });

  it("customizes visible order and pinned columns", async () => {
    mount();
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: "Columns" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Price" }));
    expect(screen.queryByRole("columnheader", { name: /Price/ })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Custom" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Move Volume left" }));
    fireEvent.click(screen.getByRole("button", { name: "Pin Volume" }));
    expect(screen.getByRole("button", { name: "Unpin Volume" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset to view default" }));
    expect(screen.getByRole("columnheader", { name: /Price/ })).toBeInTheDocument();
  });

  it("loads a built-in preset and saves edits as a personal screen", async () => {
    mount();
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: /Unsaved Screen/ }));
    fireEvent.click(screen.getByRole("button", { name: "Unusual Volume" }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(...called({ sort: "volume",
      filters: [expect.objectContaining({ field: "rel_volume", value: 2 })] })));
    expect(screen.getByRole("button", { name: /Unusual Volume ▾/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Edit Relative Volume/ }));
    fireEvent.change(screen.getByLabelText("Filter value"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
    expect(screen.getByRole("button", { name: /Unusual Volume \*/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    fireEvent.change(screen.getByLabelText("Screen name"), { target: { value: "My Volume" } });
    fireEvent.click(screen.getByRole("dialog", { name: "Save screen" }).querySelector("button.screener-primary")!);
    await waitFor(() => expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({ name: "My Volume", filters: [expect.objectContaining({ value: 3 })] })));
    expect(screen.getByRole("button", { name: /My Volume/ })).toBeInTheDocument();
  });

  it("restores the unsaved screen when browser history leaves a preset", async () => {
    mount();
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: /Unsaved Screen/ }));
    fireEvent.click(screen.getByRole("button", { name: "Unusual Volume" }));
    await screen.findByRole("button", { name: /Edit Relative Volume/ });
    fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /Unsaved Screen/ })).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /Edit Relative Volume/ })).not.toBeInTheDocument();
  });

  it("restores explicit URL search and view", async () => {
    mount("/screener?q=Apple&view=Technical&sort=price&dir=asc");
    await screen.findByText("AAPL");
    expect(screen.getByRole("textbox", { name: "Search instruments" })).toHaveValue("Apple");
    expect(screen.getByRole("tab", { name: "Technical" })).toHaveAttribute("aria-selected", "true");
    expect(mocks.fetch).toHaveBeenCalledWith(...called({ search: "Apple", sort: "price", descending: false }));
  });

  it("opens the S8 view with registry columns and no selected-only filters", async () => {
    mount();
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("tab", { name: "Short Squeeze" }));
    expect(screen.getByRole("tab", { name: "Short Squeeze" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Columns" }));
    expect(screen.getByRole("checkbox", { name: /Short Float/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Short Ratio/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Bid/ })).toBeChecked();
    expect(screen.queryByRole("checkbox", { name: /Borrow Fee/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Add Filter/ }));
    expect(screen.queryByRole("button", { name: /Borrow Fee/ })).toBeNull();
  });

  it("restores legacy Short links as Short Squeeze", async () => {
    mount("/screener?view=Short");
    await screen.findByText("AAPL");
    expect(screen.getByRole("tab", { name: "Short Squeeze" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("tab", { name: "Short" })).toBeNull();
    expect(screen.getByRole("columnheader", { name: /Short Ratio/ })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Mkt Cap/ })).toBeNull();
  });

  it("lets a direct Short Squeeze link override Last Used columns", async () => {
    const last = { id: "last", version: 2, name: "Last Used", universe: "US_EQUITIES", filters: [], view: "Overview",
      sort: { field: "volume", descending: true }, columns: { visible: equityViews.Overview, order: equityViews.Overview,
        widths: {}, pinned: ["symbol"] } };
    mocks.config.mockResolvedValue({ schema_version: 2, persistence_available: true, universes: [equitySpec], catalog: [], presets: [], saved: [], last });
    mount("/screener?view=Short");
    await screen.findByText("AAPL");
    await waitFor(() => expect(screen.getByRole("columnheader", { name: /Short Ratio/ })).toBeInTheDocument());
    expect(screen.queryByRole("columnheader", { name: /Mkt Cap/ })).toBeNull();
  });

  it("restores legacy saved screens as Short Squeeze", async () => {
    const saved = { id: "legacy-short", version: 2, name: "My old short screen", universe: "US_EQUITIES", filters: [], view: "Short",
      sort: { field: "volume", descending: true }, columns: { visible: equityViews["Short Squeeze"], order: equityViews["Short Squeeze"], widths: {}, pinned: ["symbol"] } };
    mocks.config.mockResolvedValue({ schema_version: 2, persistence_available: true, universes: [equitySpec], catalog: [], presets: [], saved: [saved], last: null });
    mount("/screener?screen=legacy-short");
    await screen.findByText("AAPL");
    await waitFor(() => expect(screen.getByRole("tab", { name: "Short Squeeze" })).toHaveAttribute("aria-selected", "true"));
  });

  it("ignores an unsupported sort in a direct link", async () => {
    mount("/screener?sort=sector");
    await screen.findByText("AAPL");
    expect(mocks.fetch).toHaveBeenCalledWith(...called({ search: "", sort: "volume", descending: true }));
  });

  it("resizes a column by one keyboard step under StrictMode", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<StrictMode><QueryClientProvider client={client}><MemoryRouter initialEntries={["/screener"]}>
      <Routes><Route path="/screener" element={<ScreenerPage />} /></Routes>
    </MemoryRouter></QueryClientProvider></StrictMode>);
    await screen.findByText("AAPL");
    const handle = screen.getByRole("separator", { name: "Resize RVOL" });
    const before = Number(handle.getAttribute("aria-valuenow"));
    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(Number(screen.getByRole("separator", { name: "Resize RVOL" }).getAttribute("aria-valuenow"))).toBe(before + 10);
  });

  it("restores Futures from a URL and reconciles views, filters, rows, and quote subscriptions", async () => {
    mockS5();
    mount("/screener?universe=FUTURES");
    await waitFor(() => expect(screen.getByText("ESZ26")).toBeInTheDocument());
    expect(screen.getByRole("grid", { name: "Futures screener" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Overview", "Contract", "Performance", "Custom", "News"]);
    expect(screen.queryByRole("tab", { name: "Fundamentals" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Add Filter/ }));
    expect(screen.getByRole("button", { name: "Root" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Price" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Screener universe" }), { target: { value: "US_ETFS" } });
    await waitFor(() => expect(screen.getByText("SPY")).toBeInTheDocument());
    expect(screen.getByRole("grid", { name: "ETFs screener" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Contract" })).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.release).toHaveBeenCalledWith("abc123"));
    fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
    await waitFor(() => expect(screen.getByText("ESZ26")).toBeInTheDocument());
  });

  it("names Futures entitlement only when the provider refused on entitlement", async () => {
    mockS5();
    mocks.window.mockResolvedValue({ market_session: "CLOSED", active: 0, cap: 32, quotes: {
      "XA01-FUTURE-ESZ26": { state: "UNAVAILABLE", reason: "PROVIDER_UNAVAILABLE", fields: {}, session_state: "CLOSED" } } });
    const { unmount } = mount("/screener?universe=FUTURES");
    await screen.findByText("ESZ26");
    await waitFor(() => expect(screen.getByText("Quotes unavailable")).toBeInTheDocument());
    expect(screen.queryByText(/entitlement required/)).not.toBeInTheDocument();
    unmount();
    mocks.window.mockResolvedValue({ market_session: "CLOSED", active: 0, cap: 32, quotes: {
      "XA01-FUTURE-ESZ26": { state: "UNAVAILABLE", reason: "MOOMOO_QUOTE_NOT_ENTITLED", fields: {}, session_state: "CLOSED" } } });
    mount("/screener?universe=FUTURES");
    await waitFor(() => expect(screen.getByText("Quotes unavailable · entitlement required")).toBeInTheDocument());
  });

  it("loads a saved Futures screen into its own universe", async () => {
    const saved = { id: "user-futures", version: 2, name: "Quarterly contracts", universe: "FUTURES",
      filters: [{ id: "dte", field: "dte", operator: "lt", value: 90 }], view: "Contract",
      sort: { field: "root", descending: false },
      columns: { visible: ["symbol", "root", "expiry", "dte"], order: ["symbol", "root", "expiry", "dte"],
        widths: {}, pinned: ["symbol"] } };
    mockS5([saved]);
    mount();
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: /Unsaved Screen/ }));
    expect(screen.getByRole("button", { name: "Quarterly contracts · Futures" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Quarterly contracts · Futures" }));
    await waitFor(() => expect(screen.getByText("ESZ26")).toBeInTheDocument());
    expect(screen.getByRole("combobox", { name: "Screener universe" })).toHaveValue("FUTURES");
    expect(screen.getByRole("tab", { name: "Contract" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: /Edit Days to Expiry/ })).toBeInTheDocument();
    expect(mocks.fetch).toHaveBeenCalledWith(...called({ universe: "FUTURES", sort: "root", descending: false,
      filters: [expect.objectContaining({ field: "dte", value: 90 })] }));
  });
});

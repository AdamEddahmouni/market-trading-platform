import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "./ScreenerPage";

// S6: bounded server pages, query identity, and pagination-independent selection.
const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), last: vi.fn(),
}));
vi.mock("../../api/screener", () => ({
  fetchScreener: mocks.fetch,
  fetchScreenerConfig: mocks.config,
  saveScreenerScreen: vi.fn(),
  deleteScreenerScreen: vi.fn(),
  persistLastScreenerConfig: mocks.last,
  updateScreenerWindow: mocks.window,
  releaseScreenerWindow: mocks.release,
  releaseScreenerWindowOnUnload: mocks.release,
}));
vi.mock("./QuickPreview", () => ({
  QuickPreview: ({ row }: { row: { symbol: string } | null }) => <aside aria-label="Preview">{row ? `Preview ${row.symbol}` : "No selection"}</aside>,
}));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34,
    scrollToIndex: vi.fn(),
  }),
}));

type Query = { universe: string; search: string; sort: string; descending: boolean; filters: unknown[] };
type Page = { offset: number; resultSet: string | null };
const field = (value: number | null) => ({ value, source: "MOOMOO_OPEND", state: value === null ? "UNAVAILABLE" : "CURRENT_METADATA", as_of: null });
const row = (symbol: string, universe = "US_ETFS") => ({
  instrument: { instrument_id: `${universe}-${symbol}`, venue_id: "NYSE", asset_class: universe === "FUTURES" ? "FUTURE" : "ETF_FUND" },
  symbol, company: `${symbol} Fund`, sector: null, industry: null, exchange: "NYSE", fields: { price: field(null) },
});
const symbols = (count: number, prefix = "E") => Array.from({ length: count }, (_, index) => `${prefix}${String(index).padStart(4, "0")}`);
const page = (query: Query, rows: ReturnType<typeof row>[], offset: number, total: number, extra: Record<string, unknown> = {}) => ({
  schema_version: "screener/1.0.0", universe: query.universe, generated_at: "2026-09-27T18:00:00Z",
  market_session: "CLOSED", universe_as_of: "2026-09-27T18:00:00Z", screener_as_of: "2026-09-27T18:00:00Z",
  result_count: total, unfiltered_count: total, offset, limit: 200, returned: rows.length,
  has_more: offset + rows.length < total, result_set_id: "catalog|", selected_id: null, selected_index: null,
  provider_health: [{ provider: "MOOMOO_OPEND_ETF_CATALOG", state: "HEALTHY", reason: null }], source_error: null,
  rows, ...extra,
});
const caps = (sortable: string[], windowOnly: string[]) => Object.fromEntries([
  ...sortable.map((name) => [name, { execution: name === "price" ? "SNAPSHOT" : "CATALOG", sortable: true, filterable: true }]),
  ...windowOnly.map((name) => [name, { execution: "LIVE_WINDOW", sortable: false, filterable: false }]),
]);
const config = {
  schema_version: 2, persistence_available: true, presets: [], saved: [], last: null,
  catalog: [{ field: "symbol", label: "Symbol", category: "Identity", type: "text", unit: "text", operators: ["eq"], universes: ["US_ETFS", "FUTURES"], availability: "CURRENT_METADATA" }],
  universes: [
    { id: "US_ETFS", label: "ETFs", asset_class: "ETF_FUND", instrument_kind: "TRADABLE_SECURITY", source: "MOOMOO_OPEND_ETF_CATALOG",
      session_model: "US_EQUITY", default_sort: "symbol", default_columns: ["symbol", "company", "price", "bid"],
      views: { Overview: ["symbol", "company", "price", "bid"], Custom: ["symbol"] }, view_order: ["Overview", "Custom"],
      quote_capability: "US_EQUITY_L1", bars_capability: "US_EQUITY_CURRENT_KLINE", panels: [],
      fields: caps(["symbol", "company", "price"], ["bid"]) },
    { id: "FUTURES", label: "Futures", asset_class: "FUTURE", instrument_kind: "FUTURE_CONTRACT", source: "MOOMOO_OPEND_CONTRACT_CATALOG",
      session_model: "PROVIDER_STATE", default_sort: "root", default_columns: ["symbol", "root"],
      views: { Overview: ["symbol", "root"], Custom: ["symbol"] }, view_order: ["Overview", "Custom"],
      quote_capability: "US_FUTURES_QUOTE", bars_capability: "FUTURES_CURRENT_KLINE_UNVERIFIED", panels: [],
      fields: caps(["symbol", "root"], []) },
  ],
};

/** A server over N ETFs: 200-row pages, stable order, pinned result set. */
function serve(total: number) {
  const all = symbols(total).map((symbol) => row(symbol));
  mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
    const matched = all.filter((item) => item.symbol.toLowerCase().includes(query.search.toLowerCase()));
    return page(query, matched.slice(requested.offset, requested.offset + 200), requested.offset, matched.length);
  });
}

function mount(path = "/screener?universe=US_ETFS") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path="/screener" element={<ScreenerPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}
const footer = () => document.querySelector(".screener-footer")!;

describe("Screener S6 server paging", () => {
  beforeEach(() => {
    mocks.config.mockReset().mockResolvedValue(config);
    mocks.fetch.mockReset();
    mocks.window.mockReset().mockResolvedValue({ quotes: {}, active: 0, cap: 32 });
    mocks.release.mockReset().mockResolvedValue({ released: true });
    mocks.last.mockReset().mockResolvedValue({ result: {}, saved: [] });
    vi.stubGlobal("crypto", { randomUUID: () => "abc-123" });
  });

  it("requests a bounded first page, loads more near the end, and keeps the total count truthful", async () => {
    serve(450);
    mount();
    await screen.findByText("E0000");
    expect(mocks.fetch.mock.calls[0][1]).toEqual({ offset: 0, resultSet: null });
    await waitFor(() => expect(screen.getByText("E0449")).toBeInTheDocument(), { timeout: 5_000 });
    const offsets = mocks.fetch.mock.calls.map((call) => call[1]);
    expect(offsets).toEqual([{ offset: 0, resultSet: null }, { offset: 200, resultSet: "catalog|" }, { offset: 400, resultSet: "catalog|" }]);
    expect(footer()).toHaveTextContent("450 results");
    expect(footer()).not.toHaveTextContent("loaded");
    expect(screen.queryByText("Loading more results…")).not.toBeInTheDocument();
    expect(screen.getByRole("grid")).toHaveAttribute("aria-rowcount", "451");
  });

  it("shows loaded versus matched while more pages remain, and never duplicates rows", async () => {
    const all = symbols(300).map((symbol) => row(symbol));
    let release!: () => void;
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
      if (requested.offset > 0) await new Promise<void>((resolve) => { release = resolve; });
      // The second page overlaps the first by one row; the table shows it once.
      const start = requested.offset === 0 ? 0 : 199;
      return page(query, all.slice(start, start + 200), requested.offset, 300);
    });
    mount();
    await screen.findByText("E0000");
    expect(footer()).toHaveTextContent("300 results · 200 loaded");
    expect(screen.getByText("Loading more results…")).toBeInTheDocument();
    release();
    await screen.findByText("E0299", undefined, { timeout: 5_000 });
    expect(screen.getAllByText("E0199")).toHaveLength(1);
  });

  it("states a truncated view when the source stops paging short of its own count", async () => {
    const all = symbols(200).map((symbol) => row(symbol));
    // The source reports 4,625 matches but serves one page and no continuation.
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => page(query, all, requested.offset, 4625, { has_more: false }));
    mount();
    await screen.findByText("E0000");
    expect(footer()).toHaveTextContent("4,625 results · 200 loaded");
    expect(within(footer() as HTMLElement).getByRole("status")).toHaveTextContent("Showing 200 of 4,625: the source returned no further pages");
    expect(screen.queryByText("Loading more results…")).not.toBeInTheDocument();
  });

  it("does not call a view truncated while more pages can still load", async () => {
    const all = symbols(300).map((symbol) => row(symbol));
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
      if (requested.offset > 0) await new Promise(() => undefined);
      return page(query, all.slice(0, 200), requested.offset, 300);
    });
    mount();
    await screen.findByText("E0000");
    expect(footer()).toHaveTextContent("300 results · 200 loaded");
    expect(document.querySelector(".screener-truncated")).toBeNull();
  });

  it("keeps loaded rows when a later page fails, and retries that page", async () => {
    const all = symbols(300).map((symbol) => row(symbol));
    let failures = 1;
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
      if (requested.offset > 0 && failures-- > 0) throw new Error("offline");
      return page(query, all.slice(requested.offset, requested.offset + 200), requested.offset, 300);
    });
    mount();
    await screen.findByText("Could not load more results", undefined, { timeout: 5_000 });
    expect(screen.getByText("E0000")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText("E0299", undefined, { timeout: 5_000 });
  });

  it("restarts the chain from page one when the pinned result set changed", async () => {
    const all = symbols(300).map((symbol) => row(symbol));
    let changed = true;
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
      if (requested.offset > 0 && changed) {
        changed = false;
        throw Object.assign(new Error("RESULT_SET_CHANGED"), { code: "SCREENER_RESULT_SET_CHANGED" });
      }
      return page(query, all.slice(requested.offset, requested.offset + 200), requested.offset, 300);
    });
    mount();
    await screen.findByText("E0299", undefined, { timeout: 5_000 });
    const firstPages = mocks.fetch.mock.calls.filter((call) => call[1].offset === 0);
    expect(firstPages.length).toBe(2);
  });

  it("never lets a slow page from an old query enter the new query", async () => {
    const all = symbols(300).map((symbol) => row(symbol));
    let releaseOld!: () => void;
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
      if (query.search === "" && requested.offset === 200) await new Promise<void>((resolve) => { releaseOld = resolve; });
      if (query.search === "B") return page(query, [row("BETA")], 0, 1);
      return page(query, all.slice(requested.offset, requested.offset + 200), requested.offset, 300);
    });
    mount();
    await screen.findByText("E0000");
    await waitFor(() => expect(mocks.fetch.mock.calls.some((call) => call[1].offset === 200)).toBe(true));
    fireEvent.change(screen.getByRole("textbox", { name: "Search instruments" }), { target: { value: "B" } });
    await screen.findByText("BETA");
    releaseOld();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText("E0250")).not.toBeInTheDocument();
    expect(screen.queryByText("E0000")).not.toBeInTheDocument();
    expect(footer()).toHaveTextContent("1 results");
  });

  it("resets to the first page on sort change and offers no sort on a live-window column", async () => {
    serve(20);
    mount("/screener?universe=US_ETFS&sort=bid&dir=desc");
    await screen.findByText("E0000");
    // A window-only sort in a link or saved screen orders by the universe default instead.
    expect(mocks.fetch.mock.calls[0][0]).toMatchObject({ sort: "symbol" });
    const bid = screen.getByRole("columnheader", { name: /Bid/ });
    expect(bid).toHaveAttribute("aria-disabled", "true");
    expect(bid).not.toHaveAttribute("aria-sort");
    expect(bid.getAttribute("title")).toMatch(/visible rows only/);
    const calls = mocks.fetch.mock.calls.length;
    fireEvent.click(bid);
    expect(mocks.fetch.mock.calls.length).toBe(calls);
    fireEvent.click(screen.getByRole("columnheader", { name: /Price/ }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort: "price", descending: true }), { offset: 0, resultSet: null }, expect.anything()));
  });

  it("subscribes only visible rows plus the selection, not every loaded row", async () => {
    serve(150);
    mount();
    await screen.findByText("E0149");
    await waitFor(() => expect(mocks.window).toHaveBeenCalled());
    const ids = mocks.window.mock.calls.at(-1)![1] as string[];
    expect(ids.length).toBeLessThanOrEqual(26);
    fireEvent.click(screen.getByText("E0100"));
    await waitFor(() => expect((mocks.window.mock.calls.at(-1)![1] as string[])[0]).toBe("US_ETFS-E0100"));
  });

  it("keeps a still-matched selection and its preview when the new first page does not contain it", async () => {
    const all = symbols(300).map((symbol) => row(symbol));
    mocks.fetch.mockImplementation(async (query: Query, requested: Page, options: { selected?: string | null }) => {
      // In the new (descending) chain the selected row sits on a page that never arrives.
      if (query.descending && requested.offset > 0) await new Promise(() => undefined);
      const ordered = query.descending ? [...all].reverse() : all;
      const payload = page(query, ordered.slice(requested.offset, requested.offset + 200), requested.offset, 300);
      const index = options.selected ? ordered.findIndex((item) => item.instrument.instrument_id === options.selected) : -1;
      return { ...payload, selected_id: options.selected ?? null, selected_index: index >= 0 ? index : null };
    });
    mount();
    await screen.findByText("E0010");
    fireEvent.click(screen.getByText("E0010"));
    expect(within(screen.getByLabelText("Preview")).getByText("Preview E0010")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("columnheader", { name: /Symbol/ }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(expect.objectContaining({ descending: true }),
      { offset: 0, resultSet: null }, expect.objectContaining({ selected: "US_ETFS-E0010" })));
    await screen.findByText("E0299", undefined, { timeout: 5_000 });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByRole("row", { name: /E0010/ })).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("Preview")).getByText("Preview E0010")).toBeInTheDocument();
    const window = mocks.window.mock.calls.at(-1)![1] as string[];
    expect(window[0]).toBe("US_ETFS-E0010");
  });

  it("clears a selection the new query no longer matches", async () => {
    const all = symbols(5).map((symbol) => row(symbol));
    mocks.fetch.mockImplementation(async (query: Query, _requested: Page, options: { selected?: string | null }) => {
      const matched = all.filter((item) => item.symbol.includes(query.search));
      return { ...page(query, matched, 0, matched.length), selected_id: options.selected ?? null, selected_index: null };
    });
    mount();
    fireEvent.click(await screen.findByText("E0003"));
    fireEvent.change(screen.getByRole("textbox", { name: "Search instruments" }), { target: { value: "E0001" } });
    await waitFor(() => expect(screen.queryByText("E0003")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByLabelText("Preview")).toHaveTextContent("No selection"));
  });

  it("moves the keyboard selection into rows appended from the next page", async () => {
    serve(201);
    mount();
    await screen.findByText("E0200", undefined, { timeout: 5_000 });
    const grid = screen.getByRole("grid");
    fireEvent.click(screen.getByText("E0199"));
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    expect(screen.getByRole("row", { name: /E0200/ })).toHaveAttribute("aria-selected", "true");
  });

  it("labels a market-snapshot result with its own clock and coverage", async () => {
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => page(query, [row("SPY")], requested.offset, 1, {
      evaluation: "SNAPSHOT",
      snapshot: { id: "etf-1", as_of: "2026-09-27T18:41:23Z", source: "MOOMOO_OPEND_SNAPSHOT", complete: true,
        total: 6306, returned: 6289, priced: 6264, refused: 17, refused_reason: "MOOMOO_QUOTE_NOT_ENTITLED" },
    }));
    mount("/screener?universe=US_ETFS&sort=price");
    await screen.findByText("SPY");
    expect(footer()).toHaveTextContent(/Market snapshot .* · 6,264 of 6,306 priced/);
  });

  it("shows why a market query cannot run instead of a fake empty result", async () => {
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => ({
      ...page(query, [], requested.offset, 0), result_set_id: null, source_error: "MARKET_SNAPSHOT_INCOMPLETE" }));
    mount("/screener?universe=US_ETFS&sort=price");
    expect(await screen.findByRole("alert")).toHaveTextContent("Market snapshot unavailable");
    expect(footer()).toHaveTextContent("— results");
    expect(screen.queryByText(/No instruments match/)).not.toBeInTheDocument();
  });

  it("drops the ETF page chain and quote window on a switch to Futures", async () => {
    let releaseEtf!: () => void;
    const etfs = symbols(300).map((symbol) => row(symbol));
    mocks.fetch.mockImplementation(async (query: Query, requested: Page) => {
      if (query.universe === "FUTURES") return page(query, [row("ESZ26", "FUTURES")], 0, 1);
      if (requested.offset === 200) await new Promise<void>((resolve) => { releaseEtf = resolve; });
      return page(query, etfs.slice(requested.offset, requested.offset + 200), requested.offset, 300);
    });
    mount();
    await screen.findByText("E0000");
    await waitFor(() => expect(mocks.fetch.mock.calls.some((call) => call[1].offset === 200)).toBe(true));
    fireEvent.change(screen.getByRole("combobox", { name: "Screener universe" }), { target: { value: "FUTURES" } });
    await screen.findByText("ESZ26");
    releaseEtf();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText("E0000")).not.toBeInTheDocument();
    expect(screen.queryByText("E0250")).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.release).toHaveBeenCalledWith("abc123"));
  });
});

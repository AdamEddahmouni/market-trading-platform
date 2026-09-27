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
    mocks.config.mockReset().mockResolvedValue({ schema_version: 1, persistence_available: true,
      catalog: [
        { field: "price", label: "Price", category: "Price & Movement", type: "number", unit: "USD", operators: ["gt", "between"], universes: ["US_EQUITIES"], availability: "SNAPSHOT" },
        { field: "rel_volume", label: "Relative Volume", category: "Volume & Liquidity", type: "number", unit: "ratio", operators: ["gt"], universes: ["US_EQUITIES"], availability: "SNAPSHOT" },
      ], presets: [{ id: "UNUSUAL_VOLUME_DISCOVERY", name: "Unusual Volume", version: "1.0.0", status: "SUPPORTED", reason: null,
        filters: [{ id: "u", field: "rel_volume", operator: "gt", value: 2 }] }], saved: [] });
    mocks.save.mockReset().mockImplementation(async (value) => ({ result: { ...value, id: "user-1", version: 1 }, saved: [{ ...value, id: "user-1", version: 1 }] }));
    mocks.remove.mockReset().mockResolvedValue({ result: true, saved: [] });
    mocks.last.mockReset().mockResolvedValue({ result: {}, saved: [] });
    mocks.fetch.mockReset().mockImplementation(async (search: string) => ({
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
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("", "price", true));
    fireEvent.click(screen.getByRole("columnheader", { name: /Price/ }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("", "price", false));
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
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("Microsoft", "volume", true));
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
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("", "volume", true, true));
    await waitFor(() => expect(screen.getByText("AAPL")).toBeInTheDocument(), { timeout: 3_000 });
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
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("", "volume", true, false,
      [expect.objectContaining({ field: "price", operator: "gt", value: 10 })]));
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
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith("", "volume", true, false,
      [expect.objectContaining({ field: "rel_volume", value: 2 })]));
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
    expect(mocks.fetch).toHaveBeenCalledWith("Apple", "price", false);
  });

  it("ignores an unsupported sort in a direct link", async () => {
    mount("/screener?sort=sector");
    await screen.findByText("AAPL");
    expect(mocks.fetch).toHaveBeenCalledWith("", "volume", true);
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
});

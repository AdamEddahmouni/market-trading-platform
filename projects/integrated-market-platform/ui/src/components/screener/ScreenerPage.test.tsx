import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "./ScreenerPage";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(),
}));
vi.mock("../../api/screener", () => ({
  fetchScreener: mocks.fetch,
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

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/screener"]}>
    <Routes><Route path="/screener" element={<ScreenerPage />} /><Route path="/workspace/:symbol" element={<div>Instrument workspace</div>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

describe("ScreenerPage", () => {
  beforeEach(() => {
    mocks.fetch.mockReset().mockImplementation(async (search: string, sort: string, desc: boolean) => ({
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
});

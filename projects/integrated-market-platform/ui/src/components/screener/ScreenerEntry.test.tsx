import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { queryKeys } from "../../api/hooks";
import { ScreenerEntry } from "./ScreenerEntry";

vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34,
    scrollToIndex: vi.fn(),
  }),
}));

const currentContext = {
  as_of_context: { mode: "LIVE", data_mode: "LIVE_OBSERVATIONAL", execution_mode: "NONE",
    execution_authority: "BLOCKED", as_of_time: "2026-10-10T13:00:00Z", timezone: "America/New_York" },
  capability_states: [], quality_summary: { state: "GOOD" },
};
const replayContext = { ...currentContext,
  as_of_context: { ...currentContext.as_of_context, mode: "REPLAY", data_mode: "FIXTURE_REPLAY" },
};
const config = { schema_version: 2, persistence_available: false, catalog: [], presets: [], saved: [], last: null,
  universes: [{ id: "US_EQUITIES", label: "US Equities", asset_class: "EQUITY", instrument_kind: "TRADABLE_SECURITY",
    source: "FINVIZ_ELITE", session_model: "US_EQUITY", default_sort: "volume", default_columns: ["symbol", "price"],
    views: { Overview: ["symbol", "price"], Custom: ["symbol", "price"] }, quote_capability: "US_EQUITY_L1",
    bars_capability: "US_EQUITY_CURRENT_KLINE", panels: [] }],
};
const currentRows = { schema_version: "screener/1.0.0", universe: "US_EQUITIES", generated_at: "2026-10-10T13:00:00Z",
  universe_as_of: "2026-10-10T13:00:00Z", screener_as_of: "2026-10-10T13:00:00Z", market_session: "REGULAR",
  result_count: 1, source_error: null, provider_health: [{ provider: "FINVIZ_ELITE", state: "HEALTHY", reason: null }],
  rows: [{ instrument: { instrument_id: "AAPL", venue_id: "US_EQUITY", asset_class: "EQUITY" },
    symbol: "AAPL", company: "Apple Inc", sector: null, industry: null, decision_inputs: [],
    fields: { price: { value: 12, source: "FINVIZ_ELITE", state: "SNAPSHOT", as_of: "2026-10-10T13:00:00Z" } } }],
};
const windowResponse = { schema_version: "screener/1.0.0", generated_at: "2026-10-10T13:00:00Z",
  market_session: "REGULAR", quotes: {}, active: 0, cap: 32 };

let context: unknown;
let contextError: boolean;
let pendingContext: Promise<unknown> | null;
let requests: string[];
let client: QueryClient;
const marketReads = () => requests.filter((path) => path.startsWith("/screener") && !path.endsWith("/release"));

function mount() {
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/screener"]}>
    <ScreenerEntry />
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  context = currentContext;
  contextError = false;
  pendingContext = null;
  requests = [];
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    let payload: unknown;
    if (path === "/context") {
      if (contextError) throw new Error("Context unavailable");
      payload = pendingContext ? await pendingContext : context;
    } else if (path === "/screener/config") payload = config;
    else if (path.startsWith("/screener?")) payload = currentRows;
    else if (path === "/screener/window") payload = windowResponse;
    else if (path.endsWith("/release")) payload = { released: true };
    else throw new Error(`Unexpected request: ${path}`);
    return { ok: true, json: async () => payload };
  }));
});
afterEach(() => {
  client.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("current-market Screener session boundary", () => {
  it("does not request current markets while authoritative context is loading", async () => {
    pendingContext = new Promise(() => undefined);
    mount();
    await waitFor(() => expect(requests).toContain("/context"));
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export" })).not.toBeInTheDocument();
    expect(marketReads()).toEqual([]);
  });

  it.each(["FIXTURE_REPLAY", "HISTORICAL_CAPTURE", undefined])("withholds current markets when data mode is %s", async (dataMode) => {
    context = { ...replayContext, as_of_context: { ...replayContext.as_of_context, data_mode: dataMode } };
    mount();
    await waitFor(() => expect(requests).toContain("/context"));
    await screen.findByRole("heading", { name: /Screener unavailable/i });
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export" })).not.toBeInTheDocument();
    expect(marketReads()).toEqual([]);
  });

  it("fails closed on context failure and retries verification before showing current rows", async () => {
    contextError = true;
    mount();
    await screen.findByRole("heading", { name: /Could not verify/i });
    expect(marketReads()).toEqual([]);
    contextError = false;
    fireEvent.click(screen.getByRole("button", { name: /Retry/i }));
    await screen.findByText("AAPL");
    expect(screen.getByRole("button", { name: "Export" })).toBeEnabled();
  });

  it("revalidates a fresh cached Live context before exposing cached current rows or export", async () => {
    client.setQueryData(queryKeys.context, currentContext);
    client.setQueryDefaults(queryKeys.context, { staleTime: Infinity });
    client.setQueryData(["main-screener-config"], config);
    client.setQueryData(["main-screener", "US_EQUITIES", "", "volume", true, []], {
      pages: [currentRows], pageParams: [{ offset: 0, resultSet: null }],
    });
    let resolveContext: (value: unknown) => void = () => undefined;
    pendingContext = new Promise((resolve) => { resolveContext = resolve; });
    mount();
    await waitFor(() => expect(requests).toContain("/context"));
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export" })).not.toBeInTheDocument();
    expect(marketReads()).toEqual([]);
    await act(async () => { resolveContext(replayContext); });
    await screen.findByRole("heading", { name: /Screener unavailable/i });
    expect(marketReads()).toEqual([]);
  });

  it("removes current rows and export immediately when authoritative context changes to replay", async () => {
    mount();
    await screen.findByText("AAPL");
    expect(screen.getByRole("button", { name: "Export" })).toBeEnabled();
    const readsBeforeReplay = marketReads().length;
    context = replayContext;
    await act(async () => { client.setQueryData(queryKeys.context, replayContext); });
    await screen.findByRole("heading", { name: /Screener unavailable/i });
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export" })).not.toBeInTheDocument();
    expect(client.getQueryCache().findAll({ queryKey: ["main-screener"] })).not.toHaveLength(0);
    vi.useFakeTimers();
    await act(async () => { await vi.advanceTimersByTimeAsync(125_000); });
    expect(marketReads()).toHaveLength(readsBeforeReplay);
  });

  it("removes cached current rows when context revalidation fails", async () => {
    mount();
    await screen.findByText("AAPL");
    contextError = true;
    await act(async () => { await client.invalidateQueries({ queryKey: queryKeys.context }); });
    await screen.findByRole("heading", { name: /Could not verify/i });
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Export" })).not.toBeInTheDocument();
  });
});

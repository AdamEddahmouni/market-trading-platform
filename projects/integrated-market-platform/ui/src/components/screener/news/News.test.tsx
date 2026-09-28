import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "../ScreenerPage";
import ScreenerDock from "../panels/ScreenerDock";
import { BondQuickPreview } from "../bonds/BondQuickPreview";
import { PreviewNews } from "./PreviewNews";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), last: vi.fn(), preview: vi.fn(), layout: vi.fn(),
  panelLayout: vi.fn(), demand: vi.fn(), releasePanels: vi.fn(), news: vi.fn(), instrumentNews: vi.fn(), synthesis: vi.fn(),
  bondPreview: vi.fn(),
}));
vi.mock("../../../api/screener", async (original) => ({
  ...(await original<typeof import("../../../api/screener")>()),
  fetchScreener: mocks.fetch, fetchScreenerConfig: mocks.config, saveScreenerScreen: vi.fn(), deleteScreenerScreen: vi.fn(),
  persistLastScreenerConfig: mocks.last, updateScreenerWindow: mocks.window, releaseScreenerWindow: mocks.release,
  releaseScreenerWindowOnUnload: mocks.release, fetchScreenerPreview: mocks.preview, persistScreenerPreviewLayout: mocks.layout,
  persistScreenerPanelLayout: mocks.panelLayout,
}));
vi.mock("../../../api/screenerPanels", () => ({
  fetchOrderFlow: vi.fn(() => new Promise(() => undefined)), fetchCvd: vi.fn(() => new Promise(() => undefined)),
  fetchDepth: vi.fn(() => new Promise(() => undefined)), fetchChart: vi.fn(() => new Promise(() => undefined)),
  fetchFuturesContext: vi.fn(() => new Promise(() => undefined)),
  demandPanels: mocks.demand, releasePanels: mocks.releasePanels, releasePanelsOnUnload: mocks.releasePanels,
}));
vi.mock("../../../api/screenerSqueeze", () => ({ fetchScreenerSqueeze: vi.fn(() => new Promise(() => undefined)) }));
vi.mock("../../../api/screenerBonds", async (original) => ({
  ...(await original<typeof import("../../../api/screenerBonds")>()), fetchBondPreview: mocks.bondPreview,
}));
vi.mock("../../../api/screenerNews", async (original) => ({
  ...(await original<typeof import("../../../api/screenerNews")>()),
  fetchScreenerNews: mocks.news, fetchInstrumentNews: mocks.instrumentNews, postNewsSynthesis: mocks.synthesis,
}));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 30 })),
    getTotalSize: () => count * 30, scrollToIndex: vi.fn(),
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

const T = "2026-09-28T14:00:00Z";
const field = (value: number | null) => ({ value, source: "FINVIZ_ELITE", state: value === null ? "UNAVAILABLE" : "SNAPSHOT", as_of: T });
const makeRow = (symbol: string, company = `${symbol} Inc`) => ({
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol, company,
  sector: "Technology", industry: "Software", fields: { price: field(10), change_pct: field(1), volume: field(1000) },
});
const screenerPayload = {
  schema_version: "screener/1.0.0", universe: "US_EQUITIES", generated_at: T, universe_as_of: T, screener_as_of: T,
  market_session: "REGULAR", source_error: null, provider_health: [{ provider: "FINVIZ_ELITE", state: "HEALTHY", reason: null }],
  result_count: 2, rows: [makeRow("AAPL", "Apple Inc"), makeRow("NVDA", "NVIDIA Corp")],
};
const ALL_PANELS = ["order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze", "news"];
const spec = (id: string, label: string, panels: string[]) => ({
  id, label, asset_class: "X", instrument_kind: "X", source: "X", session_model: "X", default_sort: "symbol",
  default_columns: ["symbol", "price"], views: { Overview: ["symbol", "price"], Custom: ["symbol", "price"] }, view_order: ["Overview", "Custom"],
  quote_capability: "X", bars_capability: "X", panels,
  fields: { symbol: { execution: "CATALOG", sortable: true, filterable: true }, price: { execution: "CATALOG", sortable: true, filterable: true } },
});
const config = {
  schema_version: 2, persistence_available: false, catalog: [], presets: [], saved: [], last: null,
  universes: [spec("US_EQUITIES", "US Equities", ALL_PANELS), spec("FUTURES", "Futures", ["charts", "news"]), spec("US_ETFS", "ETFs", ["charts", "news"]),
    spec("BONDS", "Bonds", ["rates_curve", "news"]), spec("CRYPTO", "Crypto", ["charts", "news"])],
};

const provider = (id: string, label: string, state: string, reason: string | null = null, kind = "NEWS") =>
  ({ id, label, kind, state, reason, fetched_at: state === "CURRENT" ? T : null, item_count: state === "CURRENT" ? 12 : null, scope: "UNIVERSE" });
const PROVIDERS = [provider("finviz", "Finviz Elite", "CURRENT"), provider("newsapi", "NewsAPI", "NOT_CONFIGURED", "IMP_NEWSAPI_LIVE_NOT_SET"),
  provider("finnhub", "Finnhub", "RATE_LIMITED", "HTTP_429"), provider("sec_filings", "SEC EDGAR filings", "CURRENT", null, "OFFICIAL_FILING")];
const source = (publisher: string, providerLabel = "Finviz Elite", published: string | null = T) => ({ provider_id: "finviz", provider_label: providerLabel,
  publisher, url: `https://news.example/${publisher.replace(/\s/g, "")}`, published_at: published, retrieved_at: "2026-09-28T14:02:00Z", source_type: "NEWS" });
const category = (id: string, label: string) => ({ id, label, group: "CORPORATE" });
const scored = (label: "POSITIVE" | "NEUTRAL" | "NEGATIVE") => ({ state: "SCORED", label,
  probabilities: { positive: label === "POSITIVE" ? 0.9 : 0.05, neutral: label === "NEUTRAL" ? 0.9 : 0.05, negative: label === "NEGATIVE" ? 0.9 : 0.05 }, model_id: "ProsusAI/finbert" });
type StoryOverrides = Record<string, unknown>;
const story = (id: string, headline: string, overrides: StoryOverrides = {}) => ({
  story_id: id, headline, summary: null, url: `https://news.example/${id}`, published_at: T, published_time_quality: "KNOWN",
  latest_published_at: T, first_retrieved_at: "2026-09-28T14:02:00Z", source_type: "NEWS", sources: [source("Reuters")],
  source_count: 1, provider_count: 1, categories: [category("earnings", "Earnings")],
  matches: [{ instrument_id: "AAPL", symbol: "AAPL", basis: "EXACT_TICKER", confidence: "EXACT", term: "AAPL" }],
  sentiment: scored("POSITIVE"), quality_flags: [], ...overrides,
});
const LONG = "Apple announces a very long headline about quarterly results, supply chains, services revenue, and several other details that will not fit";
const STORIES = [
  story("s1", LONG),
  story("s2", "Chipmaker shares move after guidance", { published_at: null, published_time_quality: "UNKNOWN", latest_published_at: null,
    sentiment: { state: "NOT_SCORED", label: null, probabilities: null, model_id: null },
    matches: [{ instrument_id: "NVDA", symbol: "NVDA", basis: "EXACT_ENTITY", confidence: "CONTEXT", term: "Nvidia" }] }),
  story("s3", "Syndicated wire story on tech sector", { sources: [source("Reuters"), source("Yahoo Finance", "NewsAPI"), source("MarketWatch", "Finnhub", null)],
    source_count: 3, provider_count: 3, sentiment: { state: "NOT_CONFIGURED", label: null, probabilities: null, model_id: null } }),
  story("s4", "Form 8-K filed", { source_type: "OFFICIAL_FILING", categories: [category("filing", "Filing")], sentiment: scored("NEGATIVE") }),
];
const win = (id = "24h") => ({ id, start: "2026-09-27T14:00:00Z", end: T });
const feed = (overrides: Record<string, unknown> = {}) => ({
  schema_version: "screener-news/1.0.0", generated_at: T, universe: "US_EQUITIES", window: win(), state: "PARTIAL", reason: null,
  providers: PROVIDERS, sentiment_model: { state: "NOT_CONFIGURED", reason: "IMP_FINBERT_NOT_SET", model_id: null, model_revision: null, loaded: false },
  filters: {
    sources: [{ id: "finviz", label: "Finviz Elite", count: 3 }, { id: "sec_filings", label: "SEC EDGAR filings", count: 1 }],
    categories: [{ id: "earnings", label: "Earnings", group: "CORPORATE", count: 3 }, { id: "filing", label: "Filing", group: "FILING", count: 1 }],
    sentiment: { enabled: false, reason: "NOT_ALL_STORIES_SCORED" },
    applied: { source: null, category: null, sentiment: null, instrument: null },
  },
  sorts: [{ id: "newest", label: "Newest" }, { id: "sources", label: "Most sources" }], sort: "newest",
  result_count: STORIES.length, headline_count: 9, offset: 0, limit: 100, has_more: false, stories: STORIES, brief: null, ...overrides,
});

const instrumentNews = (id: string, universe = "US_EQUITIES", overrides: Record<string, unknown> = {}) => ({
  schema_version: "screener-news-instrument/1.0.0", generated_at: T, universe,
  instrument: { instrument_id: id, symbol: id, label: `${id} Inc` },
  capability: { state: "SUPPORTED", reason: null, match_bases: ["EXACT_TICKER", "EXACT_ENTITY"], terms: [id, `${id} Inc`] },
  window: win("72h"), state: "CURRENT", reason: null, providers: [provider("finviz", "Finviz Elite", "CURRENT"), provider("finbert", "FinBERT (local)", "CURRENT", null, "SENTIMENT")],
  coverage: { story_count: 2, headline_count: 3, source_count: 2, latest_published_at: T },
  stories: [story(`${id}-1`, `${id} headline one`), story(`${id}-2`, `${id} second story`, { sentiment: scored("NEGATIVE") })],
  sentiment: { state: "CURRENT", reason: null, model_id: "ProsusAI/finbert", counts: { positive: 1, neutral: 0, negative: 1 }, scored: 2, unscored: 0,
    dominant: "MIXED", latest: { story_id: `${id}-1`, label: "POSITIVE", published_at: T }, method: "FINBERT_HEADLINE_V1" },
  catalysts: [{ category: category("earnings", "Earnings"), story_count: 2, latest_published_at: T, story_ids: [`${id}-1`] }],
  attention: { state: "CURRENT", reason: null, class: "DERIVED", windows: [{ id: "15m", headline_count: 1, story_count: 1, prior_headline_count: null },
    { id: "1h", headline_count: 2, story_count: 2, prior_headline_count: 0 }], independent_sources: 2, latest_published_at: T, method: "HEADLINE_COUNT_WINDOWS_V1" },
  reaction: { state: "NOT_SUPPORTED", reason: "NO_BAR_SOURCE", basis: "LAST_TRADE", timeframe: null,
    note: "Post-headline price reaction; temporal association, not causation.", items: [] },
  analysis: { observed: [{ text: `${id} has 2 matched stories`, source: "IMP", as_of: T, story_id: null }],
    derived: [{ text: "Earnings is the most frequent category", source: "IMP", as_of: T, story_id: null }],
    insufficient: [{ text: "No verified causal driver", source: "IMP", as_of: null, story_id: null }] },
  ai: { state: "NOT_CONFIGURED", reason: "ANTHROPIC_API_KEY_NOT_SET", provider_id: null, model_id: null },
  ...overrides,
});

let currentSearch = "";
function LocationProbe() { currentSearch = useLocation().search; return null; }
function mount(path = "/screener") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><LocationProbe /><Routes>
    <Route path="/screener" element={<ScreenerPage />} /><Route path="*" element={<div>elsewhere</div>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
const newsTab = () => within(screen.getByRole("tablist", { name: "Screener views" })).getByRole("tab", { name: "News" });
const openNews = async (path = "/screener") => {
  mount(path);
  await screen.findByText("AAPL", { selector: ".screener-symbol strong" });
  fireEvent.click(newsTab());
};
const launcher = () => within(screen.getByRole("navigation", { name: "Open panels" }));
const selectRow = async (symbol: string) => {
  await screen.findByText(symbol, { selector: ".screener-symbol strong" });
  fireEvent.click(screen.getByText(symbol, { selector: ".screener-symbol strong" }));
};
const lastNewsCall = () => mocks.news.mock.calls.at(-1)![0];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.config.mockResolvedValue(config);
  mocks.fetch.mockResolvedValue(screenerPayload);
  mocks.window.mockResolvedValue({ schema_version: "screener/1.0.0", generated_at: T, market_session: "REGULAR", active: 0, cap: 32, quotes: {} });
  mocks.release.mockResolvedValue({ released: true });
  mocks.preview.mockReturnValue(new Promise(() => undefined));
  mocks.layout.mockResolvedValue({ result: { version: 1, open: true, width: 400 } });
  mocks.panelLayout.mockResolvedValue({ result: {} });
  mocks.last.mockResolvedValue({ result: {}, saved: [] });
  mocks.demand.mockImplementation(async (_client: string, instrument: string | null, panels: string[]) => ({
    schema_version: "screener-specialist/1.0.0", instrument_id: instrument, panels, capabilities: [], cap: { max_instruments: 6, occupied_instruments: 1 } }));
  mocks.releasePanels.mockResolvedValue({ released: true });
  mocks.news.mockImplementation(async (params: { universe: string; offset?: number }) => feed({ universe: params.universe, offset: params.offset ?? 0 }));
  mocks.instrumentNews.mockImplementation(async (universe: string, id: string) => instrumentNews(id, universe));
  mocks.bondPreview.mockReturnValue(new Promise(() => undefined));
});
afterEach(() => vi.useRealTimers());

describe("S11 contract schemas", () => {
  it("parses contract fixtures and refuses a page for another universe", async () => {
    const actual = await vi.importActual<typeof import("../../../api/screenerNews")>("../../../api/screenerNews");
    expect(actual.NewsFeedSchema.parse(feed()).stories).toHaveLength(4);
    expect(actual.InstrumentNewsSchema.parse(instrumentNews("AAPL")).instrument.symbol).toBe("AAPL");
    expect(() => actual.NewsFeedSchema.parse({ ...feed(), schema_version: "screener-news/2.0.0" })).toThrow();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(feed({ universe: "CRYPTO" })), { status: 200 }));
    await expect(actual.fetchScreenerNews({ universe: "US_EQUITIES" })).rejects.toThrow("SCREENER_NEWS_IDENTITY_MISMATCH");
    expect(String(fetchSpy.mock.calls[0][0])).toMatch(/^\/screener\/news\?universe=US_EQUITIES&window=24h&offset=0&limit=100&view=feed/);
    fetchSpy.mockRestore();
  });
});

describe("S11 Screener News view", () => {
  it("adds a News tab that is a view of the active universe, never a universe", async () => {
    await openNews("/screener?universe=US_ETFS");
    const selector = screen.getByRole("combobox", { name: "Screener universe" }) as HTMLSelectElement;
    expect([...selector.options].map((option) => option.value)).toEqual(["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"]);
    expect([...selector.options].map((option) => option.textContent)).not.toContain("News");
    expect(await screen.findByRole("region", { name: "ETFs news" })).toBeInTheDocument();
    expect(selector.value).toBe("US_ETFS");
    expect(newsTab()).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("grid")).toBeNull();
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ universe: "US_ETFS", window: "24h", offset: 0 }));
    expect(currentSearch).toContain("news=1");
    // A column-view tab exits News mode.
    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));
    expect(await screen.findByRole("grid")).toBeInTheDocument();
    expect(newsTab()).toHaveAttribute("aria-selected", "false");
    expect(currentSearch).not.toContain("news=1");
  });

  it("renders dense rows: truncated headline with full title and safe link, times, chips, sentiment, type", async () => {
    await openNews();
    const table = await screen.findByRole("table", { name: "US Equities news feed" });
    const link = within(table).getByRole("link", { name: LONG });
    expect(link).toHaveAttribute("title", LONG);
    expect(link).toHaveClass("news-headline");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(table).getByText(/time unknown · retrieved/)).toBeInTheDocument();
    expect(within(table).getByText("Positive")).toBeInTheDocument();
    expect(within(table).getByText("Negative")).toBeInTheDocument();
    expect(within(table).getByText("not scored")).toBeInTheDocument();
    expect(within(table).getByText("model not configured")).toBeInTheDocument();
    expect(within(table).getByText("Official filing")).toBeInTheDocument();
    // A context match is distinguished by text, not colour alone.
    expect(within(table).getByRole("button", { name: /Filter news by NVDA \(exact entity · context match/ })).toHaveTextContent("NVDA ctx");
    expect(within(table).queryByText(/bullish|bearish|buy|sell/i)).toBeNull();
  });

  it("keeps rows dense: at most three match chips plus an overflow count, and a quiet unconfigured-sentiment cell", async () => {
    const many = ["AAPL", "MSFT", "GOOG", "AMZN", "DELL"].map((symbol) => ({ instrument_id: symbol, symbol, basis: "PROVIDER_TICKER", confidence: "EXACT", term: symbol }));
    mocks.news.mockImplementation(async (params: { universe: string; offset?: number }) => feed({ universe: params.universe, offset: params.offset ?? 0,
      stories: [story("m1", "Big tech story", { matches: many, sentiment: { state: "NOT_CONFIGURED", label: null, probabilities: null, model_id: null } })], result_count: 1 }));
    await openNews();
    const table = await screen.findByRole("table", { name: "US Equities news feed" });
    expect(within(table).getAllByRole("button", { name: /^Filter news by/ })).toHaveLength(3);
    const more = within(table).getByText("+2");
    expect(more).toHaveAttribute("title", "AMZN (exact), DELL (exact)");
    const cell = within(table).getByText("model not configured");
    expect(cell).toHaveClass("sr-only");
    expect(cell.parentElement).toHaveAttribute("title", "Sentiment model not configured");
  });

  it("builds sort, source, category, and sentiment controls only from the server", async () => {
    await openNews();
    await screen.findByRole("table", { name: "US Equities news feed" });
    const sort = screen.getByRole("combobox", { name: "News sort" }) as HTMLSelectElement;
    expect([...sort.options].map((option) => option.textContent)).toEqual(["Newest", "Most sources"]);
    const sources = screen.getByRole("combobox", { name: "News source" }) as HTMLSelectElement;
    expect([...sources.options].map((option) => option.textContent)).toEqual(["All sources", "Finviz Elite (3)", "SEC EDGAR filings (1)"]);
    const categories = screen.getByRole("combobox", { name: "News category" }) as HTMLSelectElement;
    expect([...categories.options].map((option) => option.textContent)).toEqual(["All categories", "Earnings (3)", "Filing (1)"]);
    const sentiment = screen.getByRole("combobox", { name: "News sentiment" });
    expect(sentiment).toBeDisabled();
    expect(screen.getByText("Sentiment filter unavailable · not all stories scored")).toBeInTheDocument();
    fireEvent.change(sources, { target: { value: "sec_filings" } });
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ source: "sec_filings", offset: 0 }));
    fireEvent.change(sort, { target: { value: "sources" } });
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ sort: "sources", source: "sec_filings" }));
    fireEvent.change(screen.getByRole("combobox", { name: "News window" }), { target: { value: "4h" } });
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ window: "4h" }));
  });

  it("shows each provider state separately with the sentiment model state", async () => {
    await openNews();
    const strip = await screen.findByRole("list", { name: "News providers" });
    const items = within(strip).getAllByRole("listitem").map((item) => item.textContent);
    expect(items).toEqual(["Finviz Elite current", "NewsAPI not configured", "Finnhub rate limited", "SEC EDGAR filings current"]);
    expect(within(strip).getByText("NewsAPI").closest("li")).toHaveAttribute("title", expect.stringContaining("IMP_NEWSAPI_LIVE_NOT_SET"));
    expect(screen.getByText("Sentiment model").parentElement).toHaveTextContent("Sentiment model not configured");
    // Partial: the not-current providers are named, never folded into "available".
    const notice = screen.getByText("Partial coverage").parentElement!;
    expect(notice).toHaveTextContent(/NewsAPI \(not configured · IMP_NEWSAPI_LIVE_NOT_SET\); Finnhub \(rate limited · HTTP_429\)/);
  });

  it("expands a syndicated story into its member sources", async () => {
    await openNews();
    const toggle = await screen.findByRole("button", { name: "1 story · 3 sources" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    const list = screen.getByRole("list", { name: "Sources for Syndicated wire story on tech sector" });
    expect(within(list).getAllByRole("listitem").map((item) => item.querySelector("span")?.textContent)).toEqual(["Reuters", "Yahoo Finance", "MarketWatch"]);
    expect(within(list).getByText(/time unknown · retrieved/)).toBeInTheDocument();
    expect(within(list).getAllByRole("link", { name: "open" })[0]).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("explains a not-configured feed without claiming no news exists", async () => {
    mocks.news.mockImplementation(async (params: { universe: string }) => feed({ universe: params.universe, state: "NOT_CONFIGURED",
      reason: "NO_NEWS_PROVIDER_CONFIGURED", stories: [], result_count: 0, headline_count: 0,
      providers: [provider("finviz", "Finviz Elite", "NOT_CONFIGURED", "FINVIZ_TOKEN_NOT_SET"), provider("newsapi", "NewsAPI", "LIVE_DISABLED", "IMP_NEWSAPI_LIVE_NOT_SET")] }));
    await openNews();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("News providers are not configured for US Equities");
    expect(alert).toHaveTextContent("not an absence of news");
    expect(alert).toHaveTextContent("Finviz Elite (not configured · FINVIZ_TOKEN_NOT_SET)");
    expect(screen.queryByText(/No stories in this window/)).toBeNull();
  });

  it("states an empty window from current providers", async () => {
    mocks.news.mockImplementation(async (params: { universe: string }) => feed({ universe: params.universe, state: "CURRENT", stories: [], result_count: 0,
      headline_count: 0, providers: [provider("finviz", "Finviz Elite", "CURRENT")] }));
    await openNews();
    expect(await screen.findByText("No stories in this window from current providers.")).toBeInTheDocument();
  });

  it("shows loading, then an error with retry", async () => {
    let fail: (error: Error) => void = () => undefined;
    mocks.news.mockImplementationOnce(() => new Promise((_resolve, reject) => { fail = reject; }));
    await openNews();
    expect(await screen.findByText("Loading US Equities news…")).toBeInTheDocument();
    await act(async () => { fail(new Error("boom")); });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("News request failed.");
    fireEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("table", { name: "US Equities news feed" })).toBeInTheDocument();
  });

  it("pages with offset and keeps the loaded count distinct from the result count", async () => {
    const many = (start: number, count: number) => Array.from({ length: count }, (_, index) => story(`p${start + index}`, `Paged story ${start + index}`));
    mocks.news.mockImplementation(async (params: { universe: string; offset?: number }) => (params.offset ?? 0) === 0
      ? feed({ universe: params.universe, result_count: 150, headline_count: 210, has_more: true, stories: many(0, 100) })
      : feed({ universe: params.universe, result_count: 150, headline_count: 210, has_more: false, offset: 100, stories: many(100, 50) }));
    await openNews();
    await waitFor(() => expect(mocks.news).toHaveBeenCalledWith(expect.objectContaining({ offset: 100, limit: 100 }), expect.anything()));
    expect(await screen.findByText("150 stories · 210 headlines · 150 loaded")).toBeInTheDocument();
    expect(screen.getByText("Paged story 149")).toBeInTheDocument();
  });

  it("filters by an instrument chip with a removable chip, and a universe switch keeps News but resets filters", async () => {
    await openNews();
    const table = await screen.findByRole("table", { name: "US Equities news feed" });
    fireEvent.click(within(table).getAllByRole("button", { name: /Filter news by AAPL/ })[0]);
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ instrument: "AAPL" }));
    expect(await screen.findByText("Instrument: AAPL")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove instrument filter AAPL" }));
    await waitFor(() => expect(screen.queryByText("Instrument: AAPL")).toBeNull());
    expect(currentSearch).not.toContain("ninst");
    fireEvent.change(screen.getByRole("combobox", { name: "News category" }), { target: { value: "filing" } });
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ category: "filing" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Screener universe" }), { target: { value: "CRYPTO" } });
    await waitFor(() => expect(lastNewsCall()).toMatchObject({ universe: "CRYPTO", category: null }));
    expect(newsTab()).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("region", { name: "Crypto news" })).toBeInTheDocument();
  });

  it("renders a deterministic, labelled Brief", async () => {
    mocks.news.mockImplementation(async (params: { universe: string; view?: string }) => feed({ universe: params.universe,
      brief: params.view === "brief" ? { generated_at: T, window: win(), method: "CATEGORY_GROUPING_V1", story_count: 4, headline_count: 9, source_count: 3,
        missing_providers: ["newsapi", "finnhub"], groups: [{ category: category("earnings", "Earnings"), story_count: 3, source_count: 2, latest_published_at: T, story_ids: ["s1"] }],
        uncategorized_count: 1, coverage_note: "Sparse coverage: 4 stories from 2 providers" } : null }));
    await openNews();
    await screen.findByRole("table", { name: "US Equities news feed" });
    fireEvent.click(screen.getByRole("button", { name: "Brief" }));
    const brief = await screen.findByRole("region", { name: "News brief" });
    expect(within(brief).getByText("DERIVED")).toBeInTheDocument();
    expect(within(brief).getByText("Sparse coverage: 4 stories from 2 providers")).toBeInTheDocument();
    expect(within(brief).getByText("Missing providers: NewsAPI, Finnhub")).toBeInTheDocument();
    expect(within(brief).getByRole("rowheader", { name: "Earnings" })).toBeInTheDocument();
    expect(lastNewsCall()).toMatchObject({ view: "brief" });
  });
});

describe("S11 News & Analysis panel", () => {
  it("is in the launcher, opens one instance, and asks for a selection", async () => {
    mount();
    await screen.findByText("AAPL", { selector: ".screener-symbol strong" });
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    expect(await screen.findByText("Select an instrument to view News & Analysis.")).toBeInTheDocument();
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    await waitFor(() => expect(document.querySelectorAll("#screener-panel-news")).toHaveLength(1));
    expect(mocks.instrumentNews).not.toHaveBeenCalled();
    // Not a live panel: no provider demand.
    expect(mocks.demand).not.toHaveBeenCalledWith(expect.anything(), expect.anything(), expect.arrayContaining(["news"]));
  });

  it("renders every section truthfully and shows AI NOT_CONFIGURED without posting", async () => {
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    const panel = await screen.findByRole("region", { name: "News & Analysis for AAPL" });
    await within(panel).findByText("AAPL headline one");
    expect(mocks.instrumentNews).toHaveBeenCalledWith("US_EQUITIES", "AAPL", false, expect.anything());
    expect(within(panel).getByText(/AAPL Inc · 72h · 2 stories · 2\/2 providers current/)).toBeInTheDocument();
    for (const name of ["Latest headlines", "Sentiment", "Catalysts / Events", "Attention", "Post-headline price reaction", "Analysis", "AI synthesis", "Provenance"]) {
      expect(within(panel).getByRole("heading", { name: new RegExp(`^${name.replace("/", "\\/")}`) })).toBeInTheDocument();
    }
    const sentiment = within(panel).getByRole("region", { name: "Sentiment" });
    expect(sentiment).toHaveTextContent("Mixed");
    expect(sentiment).toHaveTextContent(/describes the language of matched headlines; it is not a forecast/i);
    expect(within(panel).getByRole("region", { name: "Attention" })).toHaveTextContent("DERIVED");
    expect(within(panel).getByRole("region", { name: "Attention" })).toHaveTextContent("unknown");
    expect(within(panel).getByRole("region", { name: "Catalysts / Events" })).toHaveTextContent("Earnings");
    const reaction = within(panel).getByRole("region", { name: "Post-headline price reaction" });
    expect(reaction).toHaveTextContent("Post-headline price reaction; temporal association, not causation.");
    expect(reaction).toHaveTextContent("Not supported for this instrument · NO_BAR_SOURCE");
    const analysis = within(panel).getByRole("region", { name: "Analysis" });
    for (const name of ["Observed", "Derived", "Insufficient evidence"]) expect(within(analysis).getByRole("heading", { name })).toBeInTheDocument();
    const ai = within(panel).getByRole("region", { name: "AI synthesis" });
    expect(ai).toHaveTextContent("AI synthesis not configured · ANTHROPIC_API_KEY_NOT_SET");
    expect(within(ai).queryByRole("button", { name: "Generate AI synthesis" })).toBeNull();
    expect(mocks.synthesis).not.toHaveBeenCalled();
    expect(within(panel).getByRole("region", { name: "Provenance" })).toHaveTextContent("FinBERT (local) current");
    expect(within(panel).queryByText(/bullish|bearish|\bBUY\b|\bSELL\b/)).toBeNull();
  });

  it("refetches for a new settled selection and ignores a slow stale response", async () => {
    let resolveAapl: (value: unknown) => void = () => undefined;
    mocks.instrumentNews.mockImplementation((universe: string, id: string) => id === "AAPL"
      ? new Promise((resolve) => { resolveAapl = resolve; }) : Promise.resolve(instrumentNews(id, universe)));
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("US_EQUITIES", "AAPL", false, expect.anything()));
    await selectRow("NVDA");
    const panel = await screen.findByRole("region", { name: "News & Analysis for NVDA" });
    await within(panel).findByText("NVDA headline one");
    await act(async () => { resolveAapl(instrumentNews("AAPL")); });
    expect(screen.queryByText("AAPL headline one")).toBeNull();
    expect(screen.getByText("NVDA headline one")).toBeInTheDocument();
  });

  it("never renders a payload whose identity does not match the settled selection", async () => {
    mocks.instrumentNews.mockImplementation(async () => instrumentNews("MSFT"));
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    const panel = await screen.findByRole("region", { name: "News & Analysis for AAPL" });
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalled());
    await act(async () => { await Promise.resolve(); });
    expect(within(panel).getByText("Loading AAPL news…")).toBeInTheDocument();
    expect(within(panel).queryByText("MSFT headline one")).toBeNull();
  });

  it("only fetches the settled id while arrowing rapidly", async () => {
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("US_EQUITIES", "AAPL", false, expect.anything()));
    mocks.instrumentNews.mockClear();
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    fireEvent.keyDown(grid, { key: "ArrowUp" });
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    await screen.findByRole("region", { name: "News & Analysis for NVDA" });
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("US_EQUITIES", "NVDA", false, expect.anything()));
    expect(mocks.instrumentNews.mock.calls.every((call) => call[1] === "NVDA")).toBe(true);
  });

  it("generates an AI synthesis only on request and labels every block with sources", async () => {
    mocks.instrumentNews.mockImplementation(async (universe: string, id: string) => instrumentNews(id, universe,
      { ai: { state: "AVAILABLE", reason: null, provider_id: "anthropic", model_id: "claude-test" } }));
    mocks.synthesis.mockResolvedValue({
      schema_version: "screener-news-synthesis/1.0.0", state: "CURRENT", reason: null, epistemic_class: "AI_SYNTHESIS", generated_at: T,
      provider_id: "anthropic", model_id: "claude-test", prompt_id: "news_synthesis", prompt_version: "1", input_hash: "abc", cache: "MISS",
      story_ids: ["AAPL-1", "AAPL-2"], coverage: { story_count: 2, source_count: 2, window: win(), missing_providers: [] },
      synthesis: { summary: "Two stories discuss quarterly results.", observed_facts: [{ text: "Results were reported", refs: ["AAPL-1"] }],
        derived_context: [{ text: "Coverage clusters on earnings", refs: ["AAPL-1", "AAPL-2"] }], uncertainties: ["Guidance details are unclear"],
        conflicting_evidence: [], potential_market_relevance: [{ text: "Relevant to earnings-sensitive holders", refs: ["AAPL-2"] }] },
    });
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    const panel = await screen.findByRole("region", { name: "News & Analysis for AAPL" });
    await within(panel).findByText("AAPL headline one");
    expect(mocks.synthesis).not.toHaveBeenCalled();
    fireEvent.click(within(panel).getByRole("button", { name: "Generate AI synthesis" }));
    await waitFor(() => expect(mocks.synthesis).toHaveBeenCalledWith({ universe: "US_EQUITIES", scope: "INSTRUMENT", instrument: "AAPL", window: "24h" }));
    const result = await within(panel).findByLabelText("AI synthesis result");
    expect(within(result).getAllByText(/^AI synthesis · model claude-test · generated /)).toHaveLength(6);
    expect(within(result).getByText("Two stories discuss quarterly results.")).toBeInTheDocument();
    expect(within(result).getByRole("heading", { name: "Uncertainties" })).toBeInTheDocument();
    expect(within(result).getAllByRole("link", { name: "AAPL headline one" }).length).toBeGreaterThan(0);
  });

  it("discards a synthesis that arrives after the selection changed", async () => {
    let finish: (value: unknown) => void = () => undefined;
    mocks.instrumentNews.mockImplementation(async (universe: string, id: string) => instrumentNews(id, universe,
      { ai: { state: "AVAILABLE", reason: null, provider_id: "anthropic", model_id: "claude-test" } }));
    mocks.synthesis.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    const panel = await screen.findByRole("region", { name: "News & Analysis for AAPL" });
    await within(panel).findByText("AAPL headline one");
    fireEvent.click(within(panel).getByRole("button", { name: "Generate AI synthesis" }));
    await selectRow("NVDA");
    await screen.findByText("NVDA headline one");
    await act(async () => { finish({ schema_version: "screener-news-synthesis/1.0.0", state: "CURRENT", reason: null, epistemic_class: "AI_SYNTHESIS",
      generated_at: T, provider_id: "anthropic", model_id: "claude-test", prompt_id: "p", prompt_version: "1", input_hash: null, cache: null, story_ids: [],
      coverage: { story_count: 0, source_count: 0, window: win(), missing_providers: [] },
      synthesis: { summary: "Stale AAPL synthesis", observed_facts: [], derived_context: [], uncertainties: [], conflicting_evidence: [], potential_market_relevance: [] } }); });
    expect(screen.queryByText("Stale AAPL synthesis")).toBeNull();
  });

  it("states partial provider coverage and survives close and reopen", async () => {
    mocks.instrumentNews.mockImplementation(async (universe: string, id: string) => instrumentNews(id, universe, { state: "PARTIAL",
      providers: [provider("finviz", "Finviz Elite", "CURRENT"), provider("newsapi", "NewsAPI", "AUTH_FAILED", "HTTP_401")] }));
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    const panel = await screen.findByRole("region", { name: "News & Analysis for AAPL" });
    expect(await within(panel).findByText(/Partial coverage · not current: NewsAPI \(auth failed · HTTP_401\)/)).toBeInTheDocument();
    fireEvent.click(within(panel).getByRole("button", { name: "Close News & Analysis" }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "News & Analysis for AAPL" })).toBeNull());
    expect(launcher().getByRole("button", { name: "News & Analysis" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(launcher().getByRole("button", { name: "News & Analysis" }));
    expect(await screen.findByRole("region", { name: "News & Analysis for AAPL" })).toBeInTheDocument();
    expect(await screen.findByText("AAPL headline one")).toBeInTheDocument();
  });

  it("follows a universe change of the canonical selection", async () => {
    const props = { layout: { version: 1 as const, open_panels: ["news" as const], active_panel: "news" as const, dock_height: 300, dockview_layout: null },
      quote: undefined, clientId: "dock-s11", pending: null, handleRef: { current: null }, onOpenChange: () => undefined, onLayout: () => undefined,
      supportedPanels: new Set(["news"] as const) };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><ScreenerDock {...props} row={makeRow("SPY") as never} universe="US_ETFS" /></QueryClientProvider>);
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("US_ETFS", "SPY", false, expect.anything()));
    view.rerender(<QueryClientProvider client={client}><ScreenerDock {...props} row={makeRow("XA01:BTC") as never} universe="CRYPTO" /></QueryClientProvider>);
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("CRYPTO", "XA01:BTC", false, expect.anything()));
    expect(await screen.findByText("XA01:BTC headline one")).toBeInTheDocument();
    expect(mocks.demand).not.toHaveBeenCalledWith(expect.anything(), expect.anything(), expect.arrayContaining(["news"]), expect.anything());
  });
});

const bar = (index: number, close: number) => ({ time: 1_790_000_000 + index * 300, start: T, end: T, open: close, high: close + 0.1,
  low: close - 0.1, close, volume: 100, session: "REGULAR" });
const previewPayload = (symbol: string) => ({
  schema_version: "screener-preview/1.0.0", generated_at: T, market_session: "REGULAR",
  instrument: { instrument_id: symbol, venue_id: "US_EQUITY", asset_class: "EQUITY", symbol, company: `${symbol} Co`, sector: "Technology", industry: "Software" },
  quote: { state: "UNAVAILABLE", fields: {} }, key_data: [],
  bars: { timeframe: "5m", session_scope: "EXTENDED", provider: "MOOMOO_OPEND", source_id: "X", state: "CURRENT", reason: null, provider_reason: null,
    received_at: T, latest_complete_bar_end: T, bar_count: 2, bars: [bar(0, 10), bar(1, 11)], forming: null },
  levels: { method: "AUTO_SR_V1", timeframe: "5m", session_scope: "EXTENDED", bar_state: "CURRENT", state: "UNAVAILABLE", reason: "INSUFFICIENT_BARS",
    reasons: [], calculated_at: null, input_bar_count: 2, input_latest_bar_end: T, min_strength: 20, strength_semantics: "x", zones: [], price: null,
    support: null, resistance: null, testing: null },
  why: { matched: { state: "NO_ACTIVE_FILTERS", items: [] }, moving: { headline_window_start: T, items: [] } },
  futures: { mapping_version: "X", causal_note: "Context only.", items: [] },
});

describe("S11 Quick Preview news", () => {
  it("fetches nothing until the News tab opens, then shows compact news and opens the panel", async () => {
    mocks.preview.mockImplementation(async (id: string) => previewPayload(id));
    mount();
    await selectRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    const tab = await within(pane).findByRole("tab", { name: "News" });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 250)); });
    expect(mocks.instrumentNews).not.toHaveBeenCalled();
    fireEvent.click(tab);
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("US_EQUITIES", "AAPL", true, expect.anything()));
    const news = await within(pane).findByRole("region", { name: "News for AAPL" });
    expect(await within(news).findByText("AAPL headline one")).toBeInTheDocument();
    expect(within(news).getByText(/AAPL · AAPL Inc · last 72h · 2 stories/)).toBeInTheDocument();
    expect(within(news).getByText(/Sentiment \(language, not a forecast\): 1 positive · 0 neutral · 1 negative · 0 unscored · dominant mixed/)).toBeInTheDocument();
    expect(within(news).getByText(/Latest catalyst: Earnings/)).toBeInTheDocument();
    expect(within(news).getByText(/Providers: Finviz Elite current · FinBERT \(local\) current/)).toBeInTheDocument();
    fireEvent.click(within(news).getByRole("button", { name: "Open News & Analysis" }));
    expect(await screen.findByRole("region", { name: "News & Analysis for AAPL" })).toBeInTheDocument();
  });

  it("ignores a stale compact response for another instrument", async () => {
    mocks.instrumentNews.mockImplementation(async () => instrumentNews("MSFT"));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><PreviewNews row={makeRow("AAPL") as never} settledId="AAPL" universe="US_EQUITIES" /></QueryClientProvider>);
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("US_EQUITIES", "AAPL", true, expect.anything()));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText("Loading AAPL news…")).toBeInTheDocument();
    expect(screen.queryByText("MSFT headline one")).toBeNull();
  });

  it("keeps the Bond preview News section collapsed and unfetched until expanded", async () => {
    const onOpenNews = vi.fn();
    const bond = { ...makeRow("912828XX1", "UST 4.25% 2030"), cusip: "912828XX1", security_type: "Note", issuer: "U.S. Treasury", maturity: "2030-08-15" };
    mocks.instrumentNews.mockImplementation(async (universe: string, id: string) => instrumentNews(id, universe));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><BondQuickPreview row={bond as never} filters={[]} screenLabel={null} overlay={false} width={400}
      onClose={() => undefined} ratesSupported newsSupported onOpenNews={onOpenNews} /></QueryClientProvider>);
    const toggle = screen.getByRole("button", { name: "News" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 250)); });
    expect(mocks.instrumentNews).not.toHaveBeenCalled();
    fireEvent.click(toggle);
    await waitFor(() => expect(mocks.instrumentNews).toHaveBeenCalledWith("BONDS", "912828XX1", true, expect.anything()));
    expect(await screen.findByText("912828XX1 headline one")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open News & Analysis" }));
    expect(onOpenNews).toHaveBeenCalledTimes(1);
  });
});

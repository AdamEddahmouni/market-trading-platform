import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerPage } from "../ScreenerPage";
import { PreviewParticipants } from "./PreviewParticipants";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), last: vi.fn(), preview: vi.fn(), layout: vi.fn(),
  panelLayout: vi.fn(), demand: vi.fn(), releasePanels: vi.fn(), news: vi.fn(), instrumentNews: vi.fn(),
  congress: vi.fn(), ownership: vi.fn(), positioning: vi.fn(), instrument: vi.fn(),
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
vi.mock("../../../api/screenerNews", async (original) => ({
  ...(await original<typeof import("../../../api/screenerNews")>()),
  fetchScreenerNews: mocks.news, fetchInstrumentNews: mocks.instrumentNews, postNewsSynthesis: vi.fn(),
}));
vi.mock("../../../api/screenerParticipants", async (original) => ({
  ...(await original<typeof import("../../../api/screenerParticipants")>()),
  fetchCongressView: mocks.congress, fetchOwnershipView: mocks.ownership, fetchPositioningView: mocks.positioning,
  fetchParticipantInstrument: mocks.instrument,
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
const EQUITY_PANELS = ["order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze", "news", "institutional", "congress_gov"];
const spec = (id: string, label: string, panels: string[], intelligence_views: string[]) => ({
  id, label, asset_class: "X", instrument_kind: "X", source: "X", session_model: "X", default_sort: "symbol",
  default_columns: ["symbol", "price"], views: { Overview: ["symbol", "price"], Custom: ["symbol", "price"] }, view_order: ["Overview", "Custom"],
  quote_capability: "X", bars_capability: "X", panels, intelligence_views,
  fields: { symbol: { execution: "CATALOG", sortable: true, filterable: true }, price: { execution: "CATALOG", sortable: true, filterable: true } },
});
const config = {
  schema_version: 2, persistence_available: false, catalog: [], presets: [], saved: [], last: null,
  universes: [spec("US_EQUITIES", "US Equities", EQUITY_PANELS, ["ownership", "congress"]),
    spec("FUTURES", "Futures", ["charts", "news", "institutional"], ["positioning"]),
    spec("US_ETFS", "ETFs", ["charts", "news", "institutional", "congress_gov"], ["congress"]),
    spec("BONDS", "Bonds", ["rates_curve", "news"], []), spec("CRYPTO", "Crypto", ["charts", "news"], [])],
};

const provider = (id: string, label: string, family: string, state: string, reason: string | null = null) => ({
  id, label, family, scope: "UNIVERSE", state, reason, fetched_at: state.startsWith("CURRENT") || state === "PUBLICATION_CURRENT" ? T : null,
  published: null, item_count: null, cadence: "Daily index",
});
const BOUNDARIES = ["A transaction date is not a disclosure date.", "A disclosed amount range is not an exact amount."];
const congressRow = (id: string, symbol: string, overrides: Record<string, unknown> = {}) => ({
  id, chamber: "HOUSE", member: { name: "Member Alpha", state_district: "NJ05", member_id: "alpha-nj05" }, owner: "JOINT",
  asset_description: `${symbol} Corporation - Common Stock (${symbol}) [ST]`, asset_type_code: "ST", disclosed_ticker: symbol,
  transaction_type: "SALE_PARTIAL", transaction_date: "2026-08-10", notification_date: "2026-08-12", filing_date: "2026-09-02",
  available_at: "2026-09-03T00:00:00Z", available_basis: "clerk.index_filing_date", retrieved_at: T,
  amount: { min_amount: 1001, max_amount: 15000, display: "$1,001 – $15,000", exact_value_disclosed: false },
  disclosure_lag_days: 23, source_url: `https://disclosures-clerk.house.gov/${id}.pdf`, quality_flags: [],
  instrument: { instrument_id: symbol, symbol, basis: "EXACT_TICKER", confidence: "EXACT", is_option: false }, ...overrides,
});
const congressView = (universe: string, overrides: Record<string, unknown> = {}) => ({
  schema_version: "screener-participants/1.0.0", generated_at: T, universe, view: "congress",
  window: { id: "60d", days: 60, since: "2026-07-30", basis: "FILING_DATE" }, state: "PUBLICATION_CURRENT", reason: null,
  providers: [provider("house_ptr", "House Clerk PTR", "CONGRESSIONAL", "PUBLICATION_CURRENT"),
    provider("senate_efd", "Senate eFD", "CONGRESSIONAL", "NOT_CONFIGURED", "SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE")],
  sorts: [{ id: "filed", label: "Latest filed" }, { id: "traded", label: "Latest traded" }, { id: "amount", label: "Disclosed band" }], sort: "filed",
  filters: { transaction_types: [{ id: "PURCHASE", count: 1 }, { id: "SALE_PARTIAL", count: 1 }], amount_floors: [1001, 15001, 50001],
    members: [{ id: "alpha-nj05", name: "Member Alpha", state_district: "NJ05" }],
    applied: { transaction_type: null, min_amount: null, member: null } },
  rows: [congressRow("h1", "AAPL"), congressRow("h2", "NVDA", { transaction_type: "PURCHASE", owner: "SELF", transaction_date: null,
    amount: { min_amount: 50001, max_amount: 100000, display: "$50,001 – $100,000", exact_value_disclosed: false }, disclosure_lag_days: null })],
  result_count: 2, offset: 0, limit: 100, has_more: false,
  coverage: { filings: 133, parsed: 114, not_machine_readable: 19, loading: 0, matched: 2, ticker_outside_universe: 30, no_disclosed_ticker: 12,
    transactions_in_window: 44, window_counts: { house_filings: 120, house_machine_readable: 101, house_scanned: 19, house_unreadable: 0,
      house_loading: 0, house_transactions: 44, senate_transactions: 0, senate_in_view: false } },
  boundaries: BOUNDARIES, time_note: "Rows are placed by filing date, the date they became public.",
  neutrality_note: "Members are listed as filed; no member is ranked or characterized.", ...overrides,
});
const ownershipView = (universe: string) => ({
  schema_version: "screener-participants/1.0.0", generated_at: T, universe, view: "ownership",
  window: { id: "5d", business_days: 5 }, state: "CURRENT_AS_FILED", reason: null,
  providers: [provider("sec_index", "SEC EDGAR daily index", "INSTITUTIONAL", "CURRENT_AS_FILED")],
  families: [{ id: "INSIDER", label: "Insider (Form 4)" }, { id: "BENEFICIAL_13D", label: "Beneficial owner 13D" }],
  family_counts: { INSIDER: 1, BENEFICIAL_13D: 1 }, applied: { family: null },
  sorts: [{ id: "latest", label: "Latest filed" }, { id: "symbol", label: "Symbol" }], sort: "latest",
  rows: [
    { accession: "0001-26-1", form_type: "4", family: "INSIDER", is_amendment: false, filed_date: "2026-09-25",
      instrument: { instrument_id: "AAPL", symbol: "AAPL" }, issuer_name: "Apple Inc.", filers: ["Insider One"], filer_count: 1,
      match: { basis: "SEC_CIK", confidence: "MATCH_EXACT", role_basis: "SINGLE_CANDIDATE" }, source_url: "https://www.sec.gov/a" },
    { accession: "0002-26-2", form_type: "SCHEDULE 13D/A", family: "BENEFICIAL_13D", is_amendment: true, filed_date: "2026-09-24",
      instrument: { instrument_id: "NVDA", symbol: "NVDA" }, issuer_name: "NVIDIA Corp", filers: ["Holder A", "Holder B", "Holder C"], filer_count: 3,
      match: { basis: "SEC_CIK", confidence: "ROLE_UNVERIFIED", role_basis: "ROLE_UNVERIFIED" }, source_url: "https://www.sec.gov/b" },
  ],
  result_count: 2, offset: 0, limit: 100, has_more: false,
  coverage: { instruments_with_cik: 2, universe_instruments: 2, days: ["2026-09-24", "2026-09-25"] },
  boundaries: ["A filing reports a stake as of its event date, not a live position."], time_note: "Filed dates are SEC acceptance dates.",
});
const category = (id: string, label: string, long: number, short: number) => ({ id, label, long, short, spreading: 10, change_long: 5,
  change_short: -5, net: long - short, net_change: 10, traders_long: 20, traders_short: 18 });
const cotReport = { root: "ES", report: "TFF", report_label: "Traders in Financial Futures", cftc_contract_market_code: "13874A",
  market_name: "E-MINI S&P 500", report_date: "2026-09-22", publication_time: "2026-09-25T19:30:00Z", publication_basis: "CFTC_RELEASE_SCHEDULE",
  open_interest: 2_000_000, change_open_interest: -1500, categories: [category("asset_mgr", "Asset manager", 900, 300), category("lev_money", "Leveraged funds", 200, 700)],
  net_method: "Net = long − short (derived)", source_url: "https://publicreporting.cftc.gov/x" };
const positioningView = (universe: string) => ({
  schema_version: "screener-participants/1.0.0", generated_at: T, universe, view: "positioning", state: "PARTIAL",
  reason: "SOME_ROOTS_NOT_MAPPED_TO_A_CFTC_MARKET", providers: [provider("cftc", "CFTC COT", "INSTITUTIONAL", "PUBLICATION_CURRENT")],
  groups: [{ report: "TFF", label: "Traders in Financial Futures", rows: [cotReport] }, { report: "DISAGG", label: "Disaggregated", rows: [] }],
  coverage: { universe_roots: 2, mapped_roots: 1, unmapped_roots: ["XYZ"] },
  boundaries: ["COT reports positions as of Tuesday; it is not a prediction."], time_note: "Released Friday 15:30 ET.",
});
const filing = (accession: string, form: string) => ({ accession, form_type: form, filing_date: "2026-09-24", accepted_at: "2026-09-24T21:05:00Z",
  available_at: "2026-09-24T21:05:00Z", available_basis: "SEC_ACCEPTANCE", state: "CURRENT_AS_FILED", reason: null,
  source_url: `https://www.sec.gov/${accession}` });
const instrument = (id: string, universe: string, lens: "institutional" | "congress_gov", compact: boolean, overrides: Record<string, unknown> = {}) => ({
  schema_version: "screener-participants/1.0.0", generated_at: T, universe, lens, compact,
  instrument: { instrument_id: id, symbol: id, label: `${id} Inc` }, state: "CURRENT_AS_FILED",
  providers: lens === "institutional"
    ? [provider("sec_edgar", "SEC EDGAR", "INSTITUTIONAL", "CURRENT_AS_FILED"), provider("thirteen_f", "13F data sets", "INSTITUTIONAL", "NOT_CONFIGURED", "THIRTEEN_F_INDEX_NOT_BUILT")]
    : [provider("house_ptr", "House Clerk PTR", "CONGRESSIONAL", "PUBLICATION_CURRENT"), provider("usaspending", "USAspending", "GOVERNMENT", "PUBLICATION_CURRENT"),
      provider("lda", "Senate LDA", "GOVERNMENT", "CURRENT_AS_FILED")],
  sections: lens === "institutional" ? {
    beneficial_ownership: { state: "CURRENT_AS_FILED", reason: null, filings: [{ ...filing("0003-26-3", "SCHEDULE 13G"), event_date: "2026-09-15",
      reporting_persons: [{ name: "Holder Fund LP", aggregate_shares: 1_200_000, percent_of_class: 8.1, person_types: ["IA"] }] }] },
    insiders: { state: "CURRENT_AS_FILED", reason: null, code_counts: { P: 0, S: 1, other: 0 }, filings: [{ ...filing("0004-26-4", "4"),
      owners: [{ name: "Insider One", roles: ["Director"], officer_title: "Chief Executive Officer" }], rule_10b5_1: true,
      transactions: [{ security_title: "Common Stock", derivative: false, transaction_date: "2026-09-22", code: "S", code_label: "Open market sale",
        acquired_disposed: "D", shares: 1000, price: 180.5, shares_owned_after: 5000, ownership: "D" }] }] },
    holdings_13f: { state: "NOT_CONFIGURED", reason: "THIRTEEN_F_INDEX_NOT_BUILT" },
    large_activity: { state: "SEE_ORDER_FLOW", reason: "LIVE_SUBSCRIPTION_PANEL", method: "Large prints are in Order Flow; the participant is unknown." },
  } : {
    congressional: { state: "PUBLICATION_CURRENT", reason: null, window_days: 90, total: 1, transactions: [congressRow("h1", id)] },
    awards: { state: "PUBLICATION_CURRENT", reason: null, window_days: 90, query: `${id} Inc`, published: "2026-09-26",
      match: { note: "Recipient name matched as written." }, sum_note: "Sums are signed obligations.",
      families: {
        contract: { count: 6, has_more: true, recipients: [], obligation_sum: null, rows: [{ family: "contract", award_id: "C-1", modification: "P00003",
          recipient_name: `${id} INC`, action_date: "2026-09-10", obligation_amount: -12000, award_type: "Definitive contract", description: "Deobligation",
          awarding_agency: "Department of Defense", awarding_sub_agency: "Department of the Navy", source_url: "https://www.usaspending.gov/award/C-1" }] },
        grant: { count: 1, has_more: false, recipients: [], obligation_sum: 250000, rows: [] },
      } },
    lobbying: { state: "CURRENT_AS_FILED", reason: null, total_filings: 2, top_issues: [{ label: "Taxation", filings: 2 }], clients: [],
      match: { note: "Client name matched as filed." },
      filings: [
        { filing_uuid: "l1", filing_type_display: "2nd Quarter - Report", filing_year: 2026, filing_period: "second_quarter", posted_at: T,
          registrant_name: `${id} Inc`, client_name: `${id} Inc`, self_filed: true, income: null, expenses: 1_200_000, amount_note: "Expenses (in-house)",
          issues: [], source_url: "https://lda.senate.gov/l1" },
        { filing_uuid: "l2", filing_type_display: "2nd Quarter - Report", filing_year: 2026, filing_period: "second_quarter", posted_at: T,
          registrant_name: "Outside Firm LLC", client_name: `${id} Inc`, self_filed: false, income: 80000, expenses: null, amount_note: "Income (outside firm)",
          issues: [], source_url: "https://lda.senate.gov/l2" },
      ] },
  },
  identity: { ticker: id, cik: "0000320193", cusips: [] }, boundaries: BOUNDARIES,
  neutrality_note: lens === "congress_gov" ? "Public records as filed; no member, company, or agency is scored." : undefined, ...overrides,
});

let currentSearch = "";
function LocationProbe() { currentSearch = useLocation().search; return null; }
function mount(path = "/screener") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><LocationProbe /><Routes>
    <Route path="/screener" element={<ScreenerPage />} /><Route path="*" element={<div>elsewhere</div>} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
const tabs = () => within(screen.getByRole("tablist", { name: "Screener views" }));
const launcher = () => within(screen.getByRole("navigation", { name: "Open panels" }));
const selectRow = async (symbol: string) => {
  await screen.findByText(symbol, { selector: ".screener-symbol strong" });
  fireEvent.click(screen.getByText(symbol, { selector: ".screener-symbol strong" }));
};
const universeSelect = () => screen.getByRole("combobox", { name: "Screener universe" }) as HTMLSelectElement;
const SCORE_WORDS = /score|bullish|bearish|smart money|democrat|republican|party|buy signal|sell signal/i;

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
  mocks.demand.mockImplementation(async (_client: string, id: string | null, panels: string[]) => ({
    schema_version: "screener-specialist/1.0.0", instrument_id: id, panels, capabilities: [], cap: { max_instruments: 6, occupied_instruments: 1 } }));
  mocks.releasePanels.mockResolvedValue({ released: true });
  mocks.news.mockReturnValue(new Promise(() => undefined));
  mocks.instrumentNews.mockReturnValue(new Promise(() => undefined));
  mocks.congress.mockImplementation(async (params: { universe: string; offset?: number }) => congressView(params.universe, { offset: params.offset ?? 0 }));
  mocks.ownership.mockImplementation(async (params: { universe: string }) => ownershipView(params.universe));
  mocks.positioning.mockImplementation(async (universe: string) => positioningView(universe));
  mocks.instrument.mockImplementation(async (universe: string, id: string, lens: "institutional" | "congress_gov", compact: boolean) =>
    instrument(id, universe, lens, compact));
});
afterEach(() => vi.useRealTimers());

describe("S12 contract schemas", () => {
  it("parses contract fixtures and refuses a response for another instrument, universe, or lens", async () => {
    const actual = await vi.importActual<typeof import("../../../api/screenerParticipants")>("../../../api/screenerParticipants");
    expect(actual.CongressViewSchema.parse(congressView("US_EQUITIES")).rows).toHaveLength(2);
    expect(actual.OwnershipViewSchema.parse(ownershipView("US_EQUITIES")).rows).toHaveLength(2);
    expect(actual.PositioningViewSchema.parse(positioningView("FUTURES")).groups[0].rows[0].root).toBe("ES");
    expect(actual.ParticipantInstrumentSchema.parse(instrument("AAPL", "US_EQUITIES", "institutional", false)).lens).toBe("institutional");
    // A disclosed amount is a band: a point value is refused by the contract.
    const pointAmount = congressView("US_EQUITIES", { rows: [congressRow("x", "AAPL", { amount: { min_amount: 1, max_amount: 1, display: "$1", exact_value_disclosed: true } })] });
    expect(() => actual.CongressViewSchema.parse(pointAmount)).toThrow();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(instrument("MSFT", "US_EQUITIES", "institutional", true)), { status: 200 }));
    await expect(actual.fetchParticipantInstrument("US_EQUITIES", "AAPL", "institutional", true)).rejects.toThrow("SCREENER_PARTICIPANTS_IDENTITY_MISMATCH");
    expect(String(fetchSpy.mock.calls[0][0])).toBe("/screener/participants/instrument?universe=US_EQUITIES&instrument=AAPL&lens=institutional&compact=1");
    fetchSpy.mockResolvedValue(new Response(JSON.stringify(congressView("CRYPTO")), { status: 200 }));
    await expect(actual.fetchCongressView({ universe: "US_EQUITIES", type: "PURCHASE", minAmount: 15001 })).rejects.toThrow("SCREENER_PARTICIPANTS_IDENTITY_MISMATCH");
    expect(String(fetchSpy.mock.calls[1][0])).toBe("/screener/participants/congress?universe=US_EQUITIES&window=60d&offset=0&limit=100&type=PURCHASE&min_amount=15001");
    fetchSpy.mockRestore();
  });
});

describe("S12 intelligence views", () => {
  it("adds intelligence tabs per universe without adding a universe", async () => {
    mount();
    await screen.findByText("AAPL", { selector: ".screener-symbol strong" });
    expect([...universeSelect().options].map((option) => option.value)).toEqual(["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"]);
    expect(tabs().getByRole("tab", { name: "Institutional" })).toHaveAttribute("aria-selected", "false");
    expect(tabs().getByRole("tab", { name: "Congress" })).toBeInTheDocument();
    expect(tabs().queryByRole("tab", { name: "Positioning" })).toBeNull();
    fireEvent.change(universeSelect(), { target: { value: "FUTURES" } });
    expect(await tabs().findByRole("tab", { name: "Positioning" })).toBeInTheDocument();
    expect(tabs().queryByRole("tab", { name: "Congress" })).toBeNull();
    fireEvent.change(universeSelect(), { target: { value: "BONDS" } });
    await waitFor(() => expect(tabs().queryByRole("tab", { name: "Positioning" })).toBeNull());
    expect(tabs().queryByRole("tab", { name: "Institutional" })).toBeNull();
    // Nothing is fetched until a view is entered.
    expect(mocks.congress).not.toHaveBeenCalled();
    expect(mocks.ownership).not.toHaveBeenCalled();
    expect(mocks.positioning).not.toHaveBeenCalled();
  });

  it("shows congressional transactions as filed: separate clocks, disclosed bands, and no characterization", async () => {
    mount();
    await screen.findByText("AAPL", { selector: ".screener-symbol strong" });
    fireEvent.click(tabs().getByRole("tab", { name: "Congress" }));
    const view = await screen.findByRole("region", { name: "Congressional disclosures · US Equities" });
    expect(currentSearch).toContain("intel=congress");
    expect(tabs().getByRole("tab", { name: "Congress" })).toHaveAttribute("aria-selected", "true");
    expect(tabs().getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "false");
    expect(screen.queryByRole("grid")).toBeNull();
    const table = await within(view).findByRole("table", { name: "Congressional transactions in this universe filed since 2026-07-30" });
    const [, first, second] = within(table).getAllByRole("row");
    expect(first).toHaveTextContent("Member Alpha (NJ05)");
    expect(first).toHaveTextContent("Joint");
    expect(first).toHaveTextContent("Partial sale");
    expect(first).toHaveTextContent("$1,001 – $15,000");
    expect(first).toHaveTextContent("2026-08-10");
    expect(first).toHaveTextContent("2026-09-02");
    expect(first).toHaveTextContent("23d");
    expect(within(first).getByText("2026-09-02")).toHaveAttribute("title", expect.stringContaining("Available 2026-09-03 00:00 UTC"));
    // An undisclosed transaction date and lag stay unknown, never zero.
    expect(within(second).getAllByText("—")).toHaveLength(2);
    expect(within(first).getByRole("link", { name: "PTR" })).toHaveAttribute("rel", "noopener noreferrer");
    expect(table.textContent).not.toMatch(SCORE_WORDS);
    // House filing (document) counts and both chambers' transaction counts are separate sentences, both over the selected window.
    expect(within(view).getByText(/House filings in the last 60 days: 120 PTRs · 101 machine-readable · 19 scanned/)).toBeInTheDocument();
    expect(within(view).getByText(/Transactions filed in the last 60 days: 44 House \(Senate not imported\) — of these, 2 match this universe · 30 name other tickers · 12 have no ticker/))
      .toBeInTheDocument();
    expect(view.textContent).not.toMatch(/House PTR filings in the window/);
    expect(within(view).getByRole("list", { name: "Evidence boundaries" })).toHaveTextContent("A transaction date is not a disclosure date.");
    const providers = within(screen.getByRole("list", { name: "Congressional sources" })).getAllByRole("listitem").map((item) => item.textContent);
    expect(providers).toEqual(["House Clerk PTR Current publication", "Senate eFD Not configured"]);
  });

  it("drives filters, sort, and paging through URL params and server requests", async () => {
    mocks.congress.mockImplementation(async (params: { universe: string; offset?: number }) => congressView(params.universe,
      { offset: params.offset ?? 0, result_count: 150, has_more: (params.offset ?? 0) === 0 }));
    mount("/screener?intel=congress");
    await screen.findByRole("region", { name: "Congressional disclosures · US Equities" });
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ universe: "US_EQUITIES", window: "60d", sort: "filed", offset: 0 }), expect.anything()));
    const type = await screen.findByRole("combobox", { name: "Transaction type" }) as HTMLSelectElement;
    expect([...type.options].map((option) => option.textContent)).toEqual(["All types", "Purchase (1)", "Partial sale (1)"]);
    fireEvent.change(type, { target: { value: "PURCHASE" } });
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ type: "PURCHASE", offset: 0 }), expect.anything()));
    expect(currentSearch).toContain("itype=PURCHASE");
    fireEvent.change(screen.getByRole("combobox", { name: "Minimum disclosed amount" }), { target: { value: "15001" } });
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ minAmount: 15001 }), expect.anything()));
    fireEvent.change(screen.getByRole("combobox", { name: "Member" }), { target: { value: "alpha-nj05" } });
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ member: "alpha-nj05" }), expect.anything()));
    fireEvent.change(screen.getByRole("combobox", { name: "Congress sort" }), { target: { value: "amount" } });
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "amount" }), expect.anything()));
    const pager = await screen.findByRole("group", { name: "Pages" });
    expect(pager).toHaveTextContent("1–100 of 150");
    expect(within(pager).getByRole("button", { name: "Previous" })).toBeDisabled();
    fireEvent.click(within(pager).getByRole("button", { name: "Next" }));
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 100, sort: "amount", type: "PURCHASE" }), expect.anything()));
    expect(currentSearch).toContain("ioff=100");
    // A column view leaves the intelligence view and clears its params.
    fireEvent.click(tabs().getByRole("tab", { name: "Overview" }));
    expect(await screen.findByRole("grid")).toBeInTheDocument();
    expect(currentSearch).not.toMatch(/intel=|itype=|ioff=|iamt=|imem=|isort=/);
  });

  it("keeps an intelligence view across a universe switch only where the next universe offers it", async () => {
    mount("/screener?intel=congress&itype=PURCHASE");
    await screen.findByRole("region", { name: "Congressional disclosures · US Equities" });
    fireEvent.change(universeSelect(), { target: { value: "US_ETFS" } });
    expect(await screen.findByRole("region", { name: "Congressional disclosures · ETFs" })).toBeInTheDocument();
    expect(currentSearch).toContain("intel=congress");
    expect(currentSearch).not.toContain("itype=");
    await waitFor(() => expect(mocks.congress).toHaveBeenLastCalledWith(expect.objectContaining({ universe: "US_ETFS", type: null }), expect.anything()));
    fireEvent.change(universeSelect(), { target: { value: "BONDS" } });
    await waitFor(() => expect(currentSearch).not.toContain("intel="));
    expect(screen.queryByRole("region", { name: /Congressional disclosures/ })).toBeNull();
    // A hand-written param for a view the universe does not offer is ignored.
    expect(mocks.congress.mock.calls.some((call) => call[0].universe === "BONDS")).toBe(false);
  });

  it("explains a not-configured source without claiming there are no disclosures", async () => {
    mocks.congress.mockImplementation(async (params: { universe: string }) => congressView(params.universe, { state: "LIVE_DISABLED",
      reason: "IMP_PUBLIC_RECORDS_LIVE_NOT_SET", rows: [], result_count: 0,
      providers: [provider("house_ptr", "House Clerk PTR", "CONGRESSIONAL", "LIVE_DISABLED", "IMP_PUBLIC_RECORDS_LIVE_NOT_SET")] }));
    mount("/screener?intel=congress");
    const view = await screen.findByRole("region", { name: "Congressional disclosures · US Equities" });
    const notice = await within(view).findByText(/Official public-record access is off \(IMP_PUBLIC_RECORDS_LIVE\)/);
    expect(notice.closest("[role=status]")).toHaveTextContent("This is a source state, not an absence of disclosures.");
    expect(within(view).queryByText("No disclosed transactions match this universe and these filters.")).toBeNull();
  });

  it("shows loading, then an error with retry", async () => {
    let fail: (error: Error) => void = () => undefined;
    // The view retries once on its own; both attempts fail before the error shows.
    mocks.ownership.mockImplementationOnce(() => new Promise((_resolve, reject) => { fail = reject; }))
      .mockRejectedValueOnce(new Error("boom again"));
    mount("/screener?intel=ownership");
    expect(await screen.findByText("Loading institutional filings…")).toBeInTheDocument();
    await act(async () => { fail(new Error("boom")); });
    const alert = await screen.findByRole("alert", {}, { timeout: 4000 });
    expect(alert).toHaveTextContent("Institutional filings request failed.");
    fireEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("table", { name: "SEC ownership filings for this universe" })).toBeInTheDocument();
  });

  it("lists ownership filings with their match basis and never implies the filer's role when unverified", async () => {
    mount("/screener?intel=ownership");
    const table = await screen.findByRole("table", { name: "SEC ownership filings for this universe" });
    const [, insider, beneficial] = within(table).getAllByRole("row");
    expect(insider).toHaveTextContent("Insider · Form 4");
    expect(insider).toHaveTextContent("CIK exact");
    expect(beneficial).toHaveTextContent("Beneficial owner · 13D · amendment");
    expect(beneficial).toHaveTextContent("Holder A; Holder B +1");
    const unverified = within(beneficial).getByText("role unverified");
    expect(unverified).toHaveAttribute("title", expect.stringContaining("open it to confirm which is the subject"));
    const family = screen.getByRole("combobox", { name: "Filing family" }) as HTMLSelectElement;
    expect([...family.options].map((option) => option.textContent)).toEqual(["All families", "Insider (Form 4) (1)", "Beneficial owner 13D (1)"]);
    fireEvent.change(family, { target: { value: "INSIDER" } });
    await waitFor(() => expect(mocks.ownership).toHaveBeenLastCalledWith(expect.objectContaining({ family: "INSIDER", offset: 0 }), expect.anything()));
    fireEvent.change(screen.getByRole("combobox", { name: "Ownership window" }), { target: { value: "10d" } });
    await waitFor(() => expect(mocks.ownership).toHaveBeenLastCalledWith(expect.objectContaining({ window: "10d" }), expect.anything()));
    expect(table.textContent).not.toMatch(SCORE_WORDS);
  });

  it("keeps acronyms in loading text and explains a still-loading universe catalog", async () => {
    let finish: (value: unknown) => void = () => undefined;
    mocks.positioning.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve; }));
    mount("/screener?universe=FUTURES&intel=positioning");
    expect(await screen.findByText("Loading CFTC positioning…")).toBeInTheDocument();
    await act(async () => { finish({ ...positioningView("FUTURES"), state: "PENDING", reason: "UNIVERSE_INDEX_LOADING", groups: [],
      coverage: { universe_roots: 0, mapped_roots: 0, unmapped_roots: [] } }); });
    expect(await screen.findByText(/Universe catalog loading/)).toBeInTheDocument();
  });

  it("shows CFTC positioning with report and publication clocks, and names unmapped roots", async () => {
    mount("/screener?universe=FUTURES&intel=positioning");
    const view = await screen.findByRole("region", { name: "CFTC positioning · Futures" });
    const group = await within(view).findByRole("region", { name: "Traders in Financial Futures" });
    expect(within(group).getByText(/ES · E-MINI S&P 500 · as of 2026-09-22 · published 2026-09-25 19:30 UTC · OI 2,000,000/)).toBeInTheDocument();
    const table = within(group).getByRole("table", { name: "Traders in Financial Futures categories for ES" });
    const [, assetMgr, levMoney] = within(table).getAllByRole("row");
    expect(assetMgr).toHaveTextContent("+600");
    expect(levMoney).toHaveTextContent("-500");
    expect(within(view).queryByRole("region", { name: "Disaggregated" })).toBeNull();
    expect(within(view).getByText("No CFTC market mapped for: XYZ.")).toBeInTheDocument();
    expect(view).toHaveTextContent("it is not a prediction");
    expect(screen.getByText(/Some roots have no CFTC market/)).toBeInTheDocument();
  });
});

describe("S12 dock panels", () => {
  it("opens Institutional & Whale with each evidence family separate and no score", async () => {
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Institutional & Whale" }));
    const panel = await screen.findByRole("region", { name: "Institutional & Whale for AAPL" });
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "AAPL", "institutional", false, expect.anything()));
    const beneficial = await within(panel).findByRole("region", { name: "Beneficial owners · 13D / 13G" });
    // The header badge speaks plain language, never the raw state code.
    expect(panel.querySelector(".screener-panel-state")).toHaveTextContent("Current as filed");
    expect(panel.querySelector(".screener-panel-header")).not.toHaveTextContent("CURRENT_AS_FILED");
    expect(within(beneficial).getByText("Holder Fund LP").closest("tr")).toHaveTextContent("SCHEDULE 13G2026-09-24 21:05 UTC2026-09-15Holder Fund LP8.1%1,200,000Filing");
    const insiders = within(panel).getByRole("region", { name: "Insiders · Form 4" });
    expect(insiders).toHaveTextContent("Insider One (Chief Executive Officer)");
    expect(insiders).toHaveTextContent("10b5-1 plan");
    expect(insiders).toHaveTextContent("P 0 · S 1 · other 0");
    // A source state is never shown as "no holders".
    const holdings = within(panel).getByRole("region", { name: "13F holdings (quarter-end)" });
    expect(holdings).toHaveTextContent("Local 13F index not built · this is a source state, not an absence of disclosures.");
    const large = within(panel).getByRole("region", { name: "Large market activity (participant unknown)" });
    expect(large).toHaveTextContent("the participant is unknown");
    fireEvent.click(within(large).getByRole("button", { name: "Open Order Flow" }));
    expect(await screen.findByRole("region", { name: "Order Flow for AAPL" })).toBeInTheDocument();
    expect(panel).toHaveTextContent("No smart-money, whale, or ownership score is computed.");
    expect(within(panel).getByRole("list", { name: "Evidence boundaries" })).toBeInTheDocument();
  });

  it("opens Congress & Government with awards never summed past a page and lobbying amounts never added", async () => {
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Congress & Government" }));
    const panel = await screen.findByRole("region", { name: "Congress & Government for AAPL" });
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "AAPL", "congress_gov", false, expect.anything()));
    const congress = await within(panel).findByRole("region", { name: "Congressional disclosures" });
    expect(within(congress).getByRole("table", { name: "House transactions disclosing this ticker" })).toHaveTextContent("$1,001 – $15,000");
    const awards = within(panel).getByRole("region", { name: "Federal awards" });
    expect(awards).toHaveTextContent("Contracts · 6 actions+ · not summed (more actions than listed)");
    expect(awards).toHaveTextContent("Grants & assistance · 1 actions · sum $250,000");
    expect(awards).toHaveTextContent("-$12,000");
    expect(awards).toHaveTextContent("An award is not revenue and not a signal.");
    const lobbying = within(panel).getByRole("region", { name: "Lobbying disclosures (LDA)" });
    const [, inHouse, outside] = within(lobbying).getAllByRole("row");
    expect(inHouse).toHaveTextContent("AAPL Inc (in-house)");
    expect(inHouse).toHaveTextContent("—$1,200,000");
    expect(outside).toHaveTextContent("$80,000—");
    expect(lobbying).toHaveTextContent("never added together");
    expect(lobbying).not.toHaveTextContent("$1,280,000");
    expect(panel.textContent).not.toMatch(/bullish|bearish|smart money|democrat|republican/i);
  });

  it("follows the settled selection only and discards a response for another instrument", async () => {
    mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Institutional & Whale" }));
    await screen.findByRole("region", { name: "Institutional & Whale for AAPL" });
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "AAPL", "institutional", false, expect.anything()));
    mocks.instrument.mockClear();
    const grid = screen.getByRole("grid");
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    fireEvent.keyDown(grid, { key: "ArrowUp" });
    fireEvent.keyDown(grid, { key: "ArrowDown" });
    await screen.findByRole("region", { name: "Institutional & Whale for NVDA" });
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "NVDA", "institutional", false, expect.anything()));
    expect(mocks.instrument.mock.calls.every((call) => call[1] === "NVDA")).toBe(true);
  });
});

const bar = (index: number, close: number) => ({ time: 1_790_000_000 + index * 300, start: T, end: T, open: close, high: close + 0.1,
  low: close - 0.1, close, volume: 100, session: "REGULAR" });
const previewPayload = (symbol: string, universe = "US_EQUITIES") => ({
  schema_version: "screener-preview/1.0.0", generated_at: T, market_session: "REGULAR", universe,
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

describe("S12 Quick Preview participants", () => {
  it("fetches nothing until the Participants tab opens, then shows compact lenses that open their panels", async () => {
    mocks.preview.mockImplementation(async (id: string) => previewPayload(id));
    mount();
    await selectRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    const tab = await within(pane).findByRole("tab", { name: "Participants" });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 250)); });
    expect(mocks.instrument).not.toHaveBeenCalled();
    fireEvent.click(tab);
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "AAPL", "institutional", true, expect.anything()));
    expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "AAPL", "congress_gov", true, expect.anything());
    const section = await within(pane).findByRole("region", { name: "Participants and public records for AAPL" });
    expect(await within(section).findByLabelText("Institutional & Whale summary")).toHaveTextContent("Current as filed");
    const government = await within(section).findByLabelText("Congress & Government summary");
    expect(government).toHaveTextContent("Member Alpha · sale partial · $1,001 – $15,000 · traded 2026-08-10 · filed 2026-09-02");
    fireEvent.click(within(section).getByRole("button", { name: "Open Congress & Government" }));
    expect(await screen.findByRole("region", { name: "Congress & Government for AAPL" })).toBeInTheDocument();
  });

  it("shows only the lenses the universe offers: Futures has Institutional & Whale, not Congress & Government", async () => {
    mocks.preview.mockImplementation(async (id: string, ...rest: unknown[]) => previewPayload(id, String(rest[4])));
    mount("/screener?universe=FUTURES");
    await selectRow("AAPL");
    const pane = await screen.findByRole("complementary", { name: "Quick preview" });
    fireEvent.click(await within(pane).findByRole("tab", { name: "Participants" }));
    const section = await within(pane).findByRole("region", { name: "Participants and public records for AAPL" });
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("FUTURES", "AAPL", "institutional", true, expect.anything()));
    expect(mocks.instrument.mock.calls.some((call) => call[2] === "congress_gov")).toBe(false);
    expect(within(section).getByRole("button", { name: "Open Institutional & Whale" })).toBeInTheDocument();
    expect(within(section).queryByRole("button", { name: "Open Congress & Government" })).toBeNull();
  });

  it("ignores a stale compact response for another instrument", async () => {
    mocks.instrument.mockImplementation(async (universe: string, _id: string, lens: "institutional" | "congress_gov") => instrument("MSFT", universe, lens, true));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><PreviewParticipants row={makeRow("AAPL") as never} settledId="AAPL" universe="US_EQUITIES"
      institutional government={false} /></QueryClientProvider>);
    await waitFor(() => expect(mocks.instrument).toHaveBeenCalledWith("US_EQUITIES", "AAPL", "institutional", true, expect.anything()));
    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText("Loading institutional & whale…")).toBeInTheDocument();
    expect(screen.queryByText("Holder Fund LP")).toBeNull();
    expect(mocks.instrument.mock.calls.some((call) => call[2] === "congress_gov")).toBe(false);
  });
});

describe("Screener panel layout persistence", () => {
  it("flushes a pending layout save on unmount and never fires the timer afterwards", async () => {
    mocks.config.mockResolvedValue({ ...config, persistence_available: true });
    // A persist mock that returns nothing must not throw either.
    mocks.panelLayout.mockReturnValue(undefined);
    const view = mount();
    await selectRow("AAPL");
    fireEvent.click(launcher().getByRole("button", { name: "Institutional & Whale" }));
    await screen.findByRole("region", { name: "Institutional & Whale for AAPL" });
    mocks.panelLayout.mockClear();
    fireEvent.click(launcher().getByRole("button", { name: "Congress & Government" }));
    await screen.findByRole("region", { name: "Congress & Government for AAPL" });
    // Unmount inside the 500 ms debounce: the save is flushed once, not dropped and not fired later.
    view.unmount();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(mocks.panelLayout).toHaveBeenCalledTimes(1);
    expect(mocks.panelLayout.mock.calls[0][0].open_panels).toEqual(expect.arrayContaining(["institutional", "congress_gov"]));
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 700)); });
    expect(mocks.panelLayout).toHaveBeenCalledTimes(1);
  });
});

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { BondPreviewSchema, RatesCurveSchema } from "../../../api/screenerBonds";
import { ScreenerPage } from "../ScreenerPage";
import { bondValue, isoDate } from "./bondFormat";

const mocks = vi.hoisted(() => ({
  fetch: vi.fn(), window: vi.fn(), release: vi.fn(), config: vi.fn(), last: vi.fn(), save: vi.fn(), preview: vi.fn(),
  layout: vi.fn(), panelLayout: vi.fn(), demand: vi.fn(), releasePanels: vi.fn(), bondPreview: vi.fn(), rates: vi.fn(),
}));
vi.mock("../../../api/screener", async (original) => ({
  ...(await original<typeof import("../../../api/screener")>()),
  fetchScreener: mocks.fetch, fetchScreenerConfig: mocks.config, saveScreenerScreen: mocks.save, deleteScreenerScreen: vi.fn(),
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
vi.mock("../../../api/screenerBonds", async (original) => ({
  ...(await original<typeof import("../../../api/screenerBonds")>()),
  fetchBondPreview: mocks.bondPreview, fetchRatesCurve: mocks.rates,
}));
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () => Array.from({ length: count }, (_, index) => ({ index, start: index * 34 })),
    getTotalSize: () => count * 34, scrollToIndex: vi.fn(),
  }),
}));
vi.mock("lightweight-charts", () => ({ createChart: vi.fn(), LineStyle: { Dashed: 2 } }));

beforeAll(() => {
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
});

const f = (value: number | null, state = "CURRENT_METADATA", basis?: string, as_of = "2026-09-27T20:00:00Z") =>
  ({ value, source: "US_TREASURY_FISCAL_DATA_AUCTIONS", state: value === null ? "UNAVAILABLE" : state,
    as_of: value === null ? null : as_of, ...(basis ? { basis } : {}) });
const bond = (cusip: string, id: string, type: string, company: string, maturity: string, coupon: number | null, years: number,
  extra: Record<string, unknown> = {}) => ({
  instrument: { instrument_id: id, venue_id: "US_TREASURY", asset_class: "SOVEREIGN_DEBT", instrument_kind: "SOVEREIGN_SECURITY", tradability: "REFERENCE_ONLY" },
  symbol: cusip, company, sector: null, industry: null, country: "USA", earnings_date: null, recommendation: null, exchange: null,
  cusip, isin: null, identity_source: "CUSIP", issuer: "U.S. Treasury", security_type: type, term: "10-Year", issue_date: "2026-08-17",
  maturity, maturity_bucket: years < 1 ? "<1Y" : "7-10Y", tips: type === "TIPS" ? "Yes" : "No", frn: "No", callable: "No",
  auction_date: "2026-09-09", series: null, reference_tenor: "10Y", reference_date: "2026-09-25", reference_reason: null,
  fields: { coupon: f(coupon), years_to_maturity: f(years, "DERIVED"), days_to_maturity: f(Math.round(years * 365.25), "DERIVED"),
    maturity_year: f(Number(maturity.slice(0, 4))), outstanding: f(52.623, "PUBLICATION"),
    auction_yield: f(type === "Bill" ? 4.161 : 4.834, "AUCTION_RESULT", type === "Bill" ? "HIGH_INVESTMENT_RATE" : "HIGH_YIELD", "2026-09-09"),
    auction_real_yield: f(null), auction_discount_margin: f(null), bid_to_cover: f(2.44, "AUCTION_RESULT"),
    reference_rate: f(5.17, "REFERENCE", "NOMINAL_PAR_10Y", "2026-09-25"), indicative_rate: f(null) },
  ...extra,
});
const NOTE = bond("91282CRF0", "XA01:NOTE", "Note", "U.S. Treasury Note 4.625% Aug 2036", "2036-08-15", 4.625, 9.88);
const BILL = bond("912797WA1", "XA01:BILL", "Bill", "U.S. Treasury Bill Sep 2 2027", "2027-09-02", null, 0.93, { term: "52-Week", reference_tenor: "1Y" });
const coverage = { TREASURY: { state: "CURRENT", count: 2 }, CORPORATE: { state: "CORPORATE_COVERAGE_UNAVAILABLE", count: null },
  AGENCY: { state: "UNAVAILABLE", count: null } };
const bondPage = (rows = [BILL, NOTE], extra: Record<string, unknown> = {}) => ({
  schema_version: "screener/1.0.0", universe: "BONDS", generated_at: "2026-09-27T20:00:00Z", market_session: "PUBLICATION_BASED",
  universe_as_of: "2026-09-27T20:00:00Z", screener_as_of: "2026-09-27T20:00:00Z", evaluation: "CATALOG", snapshot: null,
  result_count: rows.length, unfiltered_count: 2, offset: 0, limit: 200, returned: rows.length, has_more: false,
  result_set_id: "2026-09-27T20:00:00Z", coverage, source_error: null,
  provider_health: [{ provider: "US_TREASURY_FISCAL_DATA", role: "IDENTITY_SOURCE", state: "HEALTHY", reason: null }], rows, ...extra,
});
const equityRow = { instrument: { instrument_id: "AAPL", venue_id: "US_EQUITY", asset_class: "EQUITY" }, symbol: "AAPL", company: "Apple Inc",
  sector: null, industry: null, fields: { price: f(250, "SNAPSHOT"), float_shares: f(15e9, "SNAPSHOT") } };
const futureRow = { instrument: { instrument_id: "XA01:ES", venue_id: "CME", asset_class: "FUTURE" }, symbol: "ESZ26", company: "E-mini S&P 500",
  root: "ES", expiry: "2026-12-18", sector: null, industry: null, fields: { dte: f(82) } };

const caps = (fields: string[], execution = "CATALOG") => Object.fromEntries(fields.map((field) => [field, { execution, sortable: execution === "CATALOG", filterable: execution === "CATALOG" }]));
const bondViews = {
  Overview: ["symbol", "security_type", "coupon", "maturity", "years_to_maturity", "auction_yield", "auction_date", "outstanding"],
  Treasuries: ["symbol", "security_type", "term", "coupon", "issue_date", "maturity", "tips", "frn", "auction_yield", "auction_real_yield",
    "auction_discount_margin", "bid_to_cover", "reference_tenor", "reference_rate"],
  "Rates & Curve": ["symbol", "security_type", "maturity", "years_to_maturity", "maturity_bucket", "reference_tenor", "reference_rate", "indicative_rate", "auction_yield"],
  Custom: ["symbol", "security_type", "coupon", "maturity"],
};
const spec = (id: string, label: string, views: Record<string, string[]>, extra: Record<string, unknown>) => ({
  id, label, asset_class: "X", instrument_kind: "X", source: "X", session_model: "X", default_sort: "symbol",
  default_columns: views.Overview, views, view_order: Object.keys(views), quote_capability: "US_EQUITY_L1",
  bars_capability: "X", panels: [], ...extra });
const config = () => ({
  schema_version: 2, persistence_available: true, presets: [], saved: [], last: null, preview_layout: { version: 1, open: true, width: 400 },
  catalog: [
    { field: "coupon", label: "Coupon", category: "Terms", type: "number", unit: "percent", operators: ["gt", "between"], universes: ["BONDS"], availability: "CURRENT_METADATA" },
    { field: "tips", label: "TIPS", category: "Terms", type: "text", unit: "text", operators: ["eq"], universes: ["BONDS"], availability: "CURRENT_METADATA" },
    { field: "float_shares", label: "Float", category: "Size", type: "number", unit: "shares", operators: ["lt"], universes: ["US_EQUITIES"], availability: "SNAPSHOT" },
  ],
  universes: [
    spec("US_EQUITIES", "US Equities", { Overview: ["symbol", "price", "float_shares"], Custom: ["symbol", "price"] },
      { default_sort: "volume", panels: ["order_flow", "charts", "options", "short_squeeze"], fields: caps(["symbol", "price", "float_shares", "volume"], "CATALOG") }),
    spec("FUTURES", "Futures", { Overview: ["symbol", "root", "expiry", "dte"], Custom: ["symbol", "root"] },
      { default_sort: "root", quote_capability: "US_FUTURES_QUOTE", fields: caps(["symbol", "root", "expiry", "dte"]) }),
    spec("US_ETFS", "ETFs", { Overview: ["symbol", "company"], Custom: ["symbol"] }, { fields: caps(["symbol", "company"]) }),
    spec("BONDS", "Bonds", bondViews, { default_sort: "maturity", quote_capability: "NO_STREAMING_QUOTE", bars_capability: "NO_PRICE_HISTORY",
      panels: ["rates_curve"], tradability: "REFERENCE_ONLY", source: "US_TREASURY_FISCAL_DATA",
      fields: { ...caps(["symbol", "security_type", "term", "coupon", "issue_date", "maturity", "years_to_maturity", "maturity_bucket", "tips", "frn",
        "auction_date", "auction_yield", "auction_real_yield", "auction_discount_margin", "bid_to_cover", "outstanding"]),
      ...caps(["reference_tenor", "reference_rate", "indicative_rate"], "REFERENCE") } }),
  ],
});

const item = (id: string, label: string, value: number | string | null, unit: string, klass = "OBSERVED", note: string | null = null) =>
  ({ id, label, value, unit, class: value === null ? "UNAVAILABLE" : klass, source: "US_TREASURY_FISCAL_DATA_AUCTIONS", as_of: "2026-09-09", note });
const bondPreview = (id = "XA01:NOTE", cusip = "91282CRF0") => ({
  schema_version: "screener-bond-preview/1.0.0", universe: "BONDS", generated_at: "2026-09-27T20:00:00Z", market_session: "PUBLICATION_BASED",
  instrument: { instrument_id: id, venue_id: "US_TREASURY", asset_class: "SOVEREIGN_DEBT", instrument_kind: "SOVEREIGN_SECURITY",
    tradability: "REFERENCE_ONLY", cusip, isin: null, identity_source: "CUSIP", issuer: "U.S. Treasury",
    description: "U.S. Treasury Note 4.625% Aug 2036", security_type: "Note", series: null },
  sections: [
    { id: "identity", title: "Identity", items: [item("cusip", "CUSIP", cusip, "text")] },
    { id: "terms", title: "Terms", items: [item("coupon", "Coupon", 4.625, "percent"), item("maturity", "Maturity", "2036-08-15", "date"),
      item("par", "Price basis", "Per 100 of par", "text")] },
    { id: "market", title: "Market", items: [item("price", "Current price", null, "per_100_par", "UNAVAILABLE", "No permitted security-level Treasury price source is integrated"),
      item("latest_trade", "Latest trade", null, "per_100_par", "UNAVAILABLE", "FINRA TRACE security prints require a licensed feed")] },
    { id: "auction", title: "Latest auction · 2026-09-09", items: [item("price", "Price", 98.361116, "per_100_par"),
      item("bid_to_cover", "Bid-to-cover", 2.44, "ratio", "OBSERVED", "An auction fact; not a directional signal")] },
    { id: "analytics", title: "Analytics", items: [item("modified", "Modified duration at auction", 7.8274, "years", "DERIVED", "At the 2026-09-09 auction yield"),
      item("ytm", "Yield to maturity (current)", null, "percent", "UNAVAILABLE", "Needs a current security price")] },
    { id: "rates", title: "Rates context", items: [item("reference", "10Y nominal par yield", 5.17, "percent", "REFERENCE", "Curve point for the nearest published tenor; not this security's yield"),
      item("shape", "Curve shape (3m10y, 2s10s)", "UPWARD_SLOPING", "state", "DERIVED")] },
  ],
  why: { matched: { state: "NO_ACTIVE_FILTERS", items: [] } },
  sources: [
    { id: "TREASURY_CATALOG", label: "Treasury terms & auctions", provider: "U.S. Treasury Fiscal Data", clock: "EVENT_REFERENCE", state: "CURRENT", as_of: "2026-09-27T20:00:00Z", reason: null },
    { id: "TREASURY_CURVE", label: "Par yield curve (nominal)", provider: "U.S. Treasury", clock: "DAILY_PUBLICATION", state: "PUBLICATION_CURRENT", as_of: "2026-09-25", reason: null },
    { id: "FINRA_TRACE", label: "Security trade prints (TRACE)", provider: "FINRA", clock: "TRANSACTION", state: "FINRA_TERMS_REQUIRED", as_of: null, reason: "LICENSED_TRACE_FEED_REQUIRED" },
  ],
  capabilities: [{ panel: "rates_curve", state: "SUPPORTED", reason: null }, { panel: "options", state: "NOT_APPLICABLE", reason: "NOT_AN_OPTIONABLE_INSTRUMENT" }],
});
const points = (values: number[], tenors: [string, number][]) => tenors.map(([tenor, years], index) => ({ tenor, years, value: values[index] }));
const NOMINAL_TENORS: [string, number][] = [["3M", 0.25], ["2Y", 2], ["10Y", 10], ["30Y", 30]];
const REAL_TENORS: [string, number][] = [["5Y", 5], ["10Y", 10], ["30Y", 30]];
const ratesPayload = (instrumentId: string | null, extra: Record<string, unknown> = {}) => ({
  schema_version: "screener-rates-curve/1.0.0", universe: "BONDS", generated_at: "2026-09-27T20:00:00Z", instrument_id: instrumentId,
  nominal: { state: "PUBLICATION_CURRENT", publication_date: "2026-09-25", points: points([4.24, 4.81, 5.17, 5.49], NOMINAL_TENORS),
    previous: { publication_date: "2026-09-24", points: points([4.24, 4.87, 5.18, 5.47], NOMINAL_TENORS) }, month_ago: null },
  real: { state: "PUBLICATION_CURRENT", publication_date: "2026-09-25", points: points([2.64, 2.83, 3.22], REAL_TENORS), previous: null, month_ago: null },
  spreads: [{ id: "2s10s", long_tenor: "10Y", short_tenor: "2Y", formula: "10Y − 2Y", value_bp: 36, publication_date: "2026-09-25", class: "DERIVED" },
    { id: "3m10y", long_tenor: "10Y", short_tenor: "3M", formula: "10Y − 3M", value_bp: 93, publication_date: "2026-09-25", class: "DERIVED" }],
  shape: { state: "UPWARD_SLOPING", rule: "UPWARD_SLOPING if 3m10y and 2s10s ≥ +10 bp", publication_date: "2026-09-25", class: "DERIVED" },
  breakevens: { state: "DERIVED", reason: null, publication_date: "2026-09-25", method: "Par-curve breakeven", items: [{ tenor: "10Y", nominal: 5.17, real: 2.83, value: 2.34 }] },
  selected: instrumentId ? { instrument_id: instrumentId, cusip: "91282CRF0", description: "U.S. Treasury Note 4.625% Aug 2036", security_type: "Note",
    maturity: "2036-08-15", years_to_maturity: 9.88,
    reference: { state: "REFERENCE", reason: null, tenor: "10Y", tenor_years: 10, value: 5.17, distance_years: 0.12, curve: "NOMINAL_PAR",
      publication_date: "2026-09-25", method: "NEAREST_PUBLISHED_TENOR" },
    indicative: null, auction_yield: { value: 4.834, source: "X", state: "AUCTION_RESULT", as_of: "2026-09-09", basis: "HIGH_YIELD" },
    auction_real_yield: { value: null, source: "X", state: "UNAVAILABLE", as_of: null, basis: "REAL_HIGH_YIELD" },
    spread: { state: "UNAVAILABLE", reason: "NO_CURRENT_SECURITY_YIELD", note: "A spread needs this security's current yield." } } : null,
  policy: { state: "NOT_CONFIGURED", reason: "FRED_API_KEY_MISSING", items: [] },
  credit: { state: "NOT_CONFIGURED", reason: "FRED_API_KEY_MISSING", items: [], note: "Broad index context; never an individual bond's spread." },
  finra: { trace: { source: "FINRA_TRACE", state: "FINRA_TERMS_REQUIRED", reason: "licensed", corporate_coverage: "CORPORATE_COVERAGE_UNAVAILABLE", agency_coverage: "UNAVAILABLE" },
    aggregates: { source: "FINRA_TRACE_AGGREGATES", state: "NOT_CONFIGURED", reason: "IMP_FINRA_LIVE_NOT_SET", trade_date: null, rows: [] } },
  sources: bondPreview().sources, ...extra,
});

let location = "";
function Probe() {
  const current = useLocation();
  location = `${current.pathname}${current.search}`;
  const navigate = useNavigate();
  return <button type="button" onClick={() => navigate(-1)}>Browser back</button>;
}
function mount(path = "/screener?universe=BONDS") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Probe />
    <Routes><Route path="/screener" element={<ScreenerPage />} /><Route path="/workspace/:symbol" element={<div>Instrument workspace</div>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}
const headers = () => screen.getAllByRole("columnheader").map((header) => header.textContent?.replace(/[▲▼]/g, "").trim());

describe("Bonds universe", () => {
  beforeEach(() => {
    mocks.config.mockReset().mockResolvedValue(config());
    mocks.fetch.mockReset().mockImplementation(async ({ universe, search }: { universe: string; search: string }) =>
      universe === "BONDS" ? bondPage([BILL, NOTE].filter((row) => `${row.cusip} ${row.company}`.toLowerCase().includes(search.toLowerCase()))) :
        { ...bondPage([universe === "FUTURES" ? futureRow : equityRow] as never), universe, coverage: undefined, market_session: "CLOSED" });
    mocks.window.mockReset().mockResolvedValue({ quotes: {}, active: 0, cap: 32, market_session: "CLOSED" });
    mocks.release.mockReset().mockResolvedValue({ released: true });
    mocks.last.mockReset().mockResolvedValue({ result: {}, saved: [] });
    mocks.save.mockReset().mockImplementation(async (value) => ({ result: { ...value, id: "user-1", version: 2 }, saved: [{ ...value, id: "user-1", version: 2 }] }));
    mocks.layout.mockReset().mockResolvedValue({}); mocks.panelLayout.mockReset().mockResolvedValue({});
    mocks.demand.mockReset().mockResolvedValue({ instrument_id: null, panels: {} }); mocks.releasePanels.mockReset().mockResolvedValue({});
    mocks.preview.mockReset().mockImplementation(() => new Promise(() => undefined));
    mocks.bondPreview.mockReset().mockImplementation(async (id: string) => BondPreviewSchema.parse(bondPreview(id, id === "XA01:BILL" ? "912797WA1" : "91282CRF0")));
    mocks.rates.mockReset().mockImplementation(async (id: string | null) => RatesCurveSchema.parse(ratesPayload(id)));
    vi.stubGlobal("crypto", { randomUUID: () => "abc-123" });
  });

  it("restores Bonds from the URL with bond columns, CUSIP identity, maturity-ascending default, and no quote window", async () => {
    mount();
    await screen.findByText("91282CRF0");
    expect(screen.getByRole("combobox", { name: "Screener universe" })).toHaveValue("BONDS");
    expect(mocks.fetch).toHaveBeenCalledWith(expect.objectContaining({ universe: "BONDS", sort: "maturity", descending: false }), expect.anything(), expect.anything());
    expect(headers()).toEqual(["Security · CUSIP", "Type", "Coupon", "Maturity", "Yrs", "Auction Yld", "Last Auction", "Outstanding"]);
    expect(screen.getByText("U.S. Treasury Note 4.625% Aug 2036")).toBeInTheDocument();
    expect(screen.getByText("4.625%")).toBeInTheDocument();
    const billRow = screen.getByText("912797WA1").closest("[role=row]") as HTMLElement;
    expect(within(billRow).getAllByText("—").length).toBeGreaterThan(0); // no coupon for a bill, never 0
    expect(within(billRow).getByText("4.161%").getAttribute("title")).toContain("HIGH_INVESTMENT_RATE");
    expect(screen.queryByText(/Float|Short Float|Mkt Cap/)).not.toBeInTheDocument();
    expect(screen.getByText("Treasury 2 · Corporate unavailable · Agency unavailable")).toBeInTheDocument();
    expect(screen.getByText("Quotes none · publication data")).toBeInTheDocument();
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 50)); });
    expect(mocks.window).not.toHaveBeenCalled();
  });

  it("uses bond views, reference columns that never sort, server search, and bond filters", async () => {
    mount();
    await screen.findByText("91282CRF0");
    fireEvent.click(screen.getByRole("tab", { name: "Rates & Curve" }));
    expect(headers()).toEqual(["Security · CUSIP", "Type", "Maturity", "Yrs", "Bucket", "Ref. Tenor", "Ref. Par Yld", "Closing Bid", "Auction Yld"]);
    expect(location).toContain("view=Rates+%26+Curve");
    const ref = screen.getByRole("columnheader", { name: /Ref\. Par Yld/ });
    expect(ref).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(ref);
    expect(mocks.fetch).not.toHaveBeenCalledWith(expect.objectContaining({ sort: "reference_rate" }), expect.anything(), expect.anything());
    expect(screen.getAllByText("5.170%")[0].getAttribute("title")).toContain("not this security's yield");
    fireEvent.click(screen.getByRole("columnheader", { name: /Maturity/ }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(expect.objectContaining({ universe: "BONDS", sort: "maturity", descending: true }), expect.anything(), expect.anything()));
    fireEvent.change(screen.getByRole("textbox", { name: "Search instruments" }), { target: { value: "912797" } });
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(expect.objectContaining({ universe: "BONDS", search: "912797" }), expect.anything(), expect.anything()));
    await waitFor(() => expect(screen.queryByText("91282CRF0")).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "+ Add Filter" }));
    const picker = screen.getByRole("dialog", { name: "Add filter" });
    expect(within(picker).queryByRole("button", { name: "Float" })).not.toBeInTheDocument();
    fireEvent.click(within(picker).getByRole("button", { name: "Coupon" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "Filter value" }), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
    await waitFor(() => expect(mocks.fetch).toHaveBeenCalledWith(expect.objectContaining({ universe: "BONDS",
      filters: [expect.objectContaining({ field: "coupon", operator: "gt", value: 4 })] }), expect.anything(), expect.anything()));
  });

  it("previews a bond with terms, auction, reference, and clocks, and never opens a Workspace", async () => {
    mount();
    await screen.findByText("91282CRF0");
    const grid = screen.getByRole("grid");
    fireEvent.click(within(grid).getByText("91282CRF0"));
    const preview = await screen.findByRole("complementary", { name: "Quick preview" });
    await within(preview).findByText("98.361116 per 100");
    expect(within(preview).getByText("Quick Preview · Bond")).toBeInTheDocument();
    expect(within(preview).getByText("Reference only")).toBeInTheDocument();
    expect(within(preview).getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(within(preview).getByText("Reference")).toBeInTheDocument();
    expect(within(preview).getByText("Upward sloping")).toBeInTheDocument();
    expect(within(preview).getByText("Licence required")).toBeInTheDocument();
    expect(within(preview).queryByText(/Float|Short|P\/E|Options|Squeeze|Market Cap/i)).not.toBeInTheDocument();
    expect(mocks.preview).not.toHaveBeenCalled(); // the equity preview endpoint is never used for a CUSIP
    fireEvent.keyDown(grid, { key: "Enter" });
    fireEvent.doubleClick(within(grid).getByText("91282CRF0"));
    expect(screen.queryByText("Instrument workspace")).not.toBeInTheDocument();
    expect(location.startsWith("/screener")).toBe(true);
  });

  it("opens one Rates & Curve panel with the curve, spreads, selected bond, and truthful unavailable sources", async () => {
    mount();
    await screen.findByText("91282CRF0");
    const launcher = screen.getByRole("navigation", { name: "Open panels" });
    expect(within(launcher).getByRole("button", { name: "Options · unavailable" })).toBeDisabled();
    expect(within(launcher).getByRole("button", { name: "Short Squeeze · unavailable" })).toBeDisabled();
    fireEvent.click(within(screen.getByRole("grid")).getByText("91282CRF0"));
    fireEvent.click(await screen.findByRole("button", { name: "Open Rates & Curve" }));
    const panel = await screen.findByRole("region", { name: /Rates & Curve for 91282CRF0/ }, { timeout: 5000 });
    await within(panel).findByText("+36.0 bp", undefined, { timeout: 5000 });
    expect(within(panel).getByRole("img", { name: /Treasury yield curve by maturity/ })).toBeInTheDocument();
    expect(within(panel).getByText("Upward sloping")).toBeInTheDocument();
    expect(within(panel).getByText(/not this security's yield/)).toBeInTheDocument();
    expect(within(panel).getAllByText(/FRED not configured · FRED API key not configured/, { selector: "p" })).toHaveLength(2);
    expect(within(panel).getAllByText(/licensed TRACE feed required/).length).toBeGreaterThan(0);
    expect(within(panel).getByRole("table", { name: "Published par yields by tenor" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.rates).toHaveBeenLastCalledWith("XA01:NOTE", expect.anything()));
    fireEvent.click(within(launcher).getByRole("button", { name: "Rates & Curve" }));
    expect(screen.getAllByRole("region", { name: /Rates & Curve for/ })).toHaveLength(1);
    // Selection change: the panel follows the settled selection.
    fireEvent.click(within(screen.getByRole("grid")).getByText("912797WA1"));
    await waitFor(() => expect(mocks.rates).toHaveBeenLastCalledWith("XA01:BILL", expect.anything()), { timeout: 5000 });
    expect(mocks.demand).not.toHaveBeenCalledWith(expect.anything(), expect.anything(), expect.arrayContaining(["rates_curve"]), expect.anything());
  });

  it("switches Equity → Bonds → Futures → Bonds → ETF without stale columns or equity leakage", async () => {
    mount("/screener");
    await screen.findByText("AAPL");
    const select = screen.getByRole("combobox", { name: "Screener universe" });
    fireEvent.change(select, { target: { value: "BONDS" } });
    await screen.findByText("91282CRF0");
    expect(headers()).not.toContain("Float");
    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
    fireEvent.change(select, { target: { value: "FUTURES" } });
    await screen.findByText("ESZ26");
    expect(headers()).not.toContain("Coupon");
    fireEvent.change(select, { target: { value: "BONDS" } });
    await screen.findByText("91282CRF0");
    expect(headers()[0]).toBe("Security · CUSIP");
    fireEvent.change(select, { target: { value: "US_ETFS" } });
    await waitFor(() => expect(headers()).not.toContain("Coupon"));
    expect(screen.queryByText("91282CRF0")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Browser back" }));
    await screen.findByText("91282CRF0");
    expect(screen.getByRole("combobox", { name: "Screener universe" })).toHaveValue("BONDS");
  });

  it("restores a direct view link and saves a bond screen as configuration only", async () => {
    mount("/screener?universe=BONDS&view=Treasuries");
    await screen.findByText("91282CRF0");
    expect(headers()).toContain("Orig. Term");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Screen name" }), { target: { value: "Treasuries" } });
    fireEvent.click(within(screen.getByRole("dialog", { name: "Save screen" })).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.save).toHaveBeenCalled());
    const saved = mocks.save.mock.calls[0][0];
    expect(saved).toMatchObject({ universe: "BONDS", view: "Treasuries", sort: { field: "maturity", descending: false } });
    expect(JSON.stringify(saved)).not.toMatch(/5\.17|98\.36|reference_date|publication/);
  });

  it("shows the not-configured Treasury source truthfully instead of an empty universe", async () => {
    mocks.fetch.mockImplementation(async () => bondPage([], { source_error: "TREASURY_NOT_CONFIGURED", result_count: 0, result_set_id: null, coverage: {
      TREASURY: { state: "UNAVAILABLE", count: 0 }, CORPORATE: { state: "CORPORATE_COVERAGE_UNAVAILABLE", count: null } },
      provider_health: [{ provider: "US_TREASURY_FISCAL_DATA", state: "NOT_CONFIGURED", reason: "TREASURY_NOT_CONFIGURED" }] }));
    mount();
    expect(await screen.findByText(/U.S. Treasury Fiscal Data is not enabled/)).toBeInTheDocument();
    expect(screen.getByText(/— results/)).toBeInTheDocument();
  });
});

describe("bond formatting", () => {
  it("keeps units explicit and missing values as an em dash", () => {
    expect(bondValue(4.125, "percent")).toBe("4.125%");
    expect(bondValue(98.361116, "per_100_par")).toBe("98.361116 per 100");
    expect(bondValue(null, "percent")).toBe("—");
    expect(bondValue(0, "percent")).toBe("0.000%");
    expect(bondValue(-1, "bp")).toBe("-1.0 bp");
    expect(bondValue("UPWARD_SLOPING", "state")).toBe("Upward sloping");
    expect(isoDate("2033-09-30")).toBe("Sep 30, 2033");
  });

  it("rejects payloads that would blur identity or add unknown fields", () => {
    expect(() => BondPreviewSchema.parse({ ...bondPreview(), instrument: { ...bondPreview().instrument, tradability: "TRADABLE" } })).toThrow();
    expect(() => BondPreviewSchema.parse({ ...bondPreview(), bid: 99.5 })).toThrow();
    expect(() => RatesCurveSchema.parse({ ...ratesPayload(null), shape: { ...ratesPayload(null).shape, state: "RECESSION_GUARANTEED" } })).toThrow();
  });
});

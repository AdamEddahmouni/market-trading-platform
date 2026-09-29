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
  "Credit & Munis": ["symbol", "issuer", "category", "security_type", "coupon", "coupon_type", "maturity", "years_to_maturity",
    "fund_count", "fund_par_held", "fund_value_pct", "report_date"],
  Observed: ["symbol", "security_type", "maturity", "observed_price", "observed_yield", "benchmark_spread", "observed_date",
    "reference_tenor", "reference_rate"],
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
        "auction_date", "auction_yield", "auction_real_yield", "auction_discount_margin", "bid_to_cover", "outstanding",
        "company", "category", "coupon_type", "fund_count", "fund_par_held", "fund_value_pct", "report_date"]),
      ...caps(["reference_tenor", "reference_rate", "indicative_rate", "observed_price", "observed_yield", "benchmark_spread",
        "observed_date"], "REFERENCE") } }),
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

// ------------------------------------------------------------------ S16: categories, fund-held rows, observations
const nport = (value: number | null, state = "FUND_REPORTED_REFERENCE", basis?: string) =>
  ({ value, source: value === null ? "NONE" : "SEC_FORM_NPORT", state: value === null ? "UNAVAILABLE" : state,
    as_of: value === null ? null : "2026-04-30", ...(basis ? { basis } : {}) });
const MUNI = {
  instrument: { instrument_id: "XA01:MUNI", venue_id: "US_OTC_FIXED_INCOME", asset_class: "BOND", instrument_kind: "BOND", tradability: "REFERENCE_ONLY" },
  symbol: "13063DAB0", company: "CALIFORNIA ST 5.00% 2035", sector: null, industry: null, country: "US", earnings_date: null,
  recommendation: null, exchange: null, cusip: "13063DAB0", isin: "US13063DAB04", isin_source: "DERIVED", identity_source: "CUSIP",
  issuer: "State of California", category: "Municipal", security_type: "Municipal", term: null, issue_date: null,
  maturity: "2035-08-01", maturity_bucket: "7-10Y", tips: "No", frn: "No", callable: null, coupon_type: "Fixed", in_default: "No",
  convertible: "No", pik: "No", auction_date: null, series: null, report_date: "2026-04-30", reference_tenor: "10Y",
  reference_date: "2026-09-25", reference_reason: null, observed_date: null,
  fields: { coupon: nport(5), years_to_maturity: f(8.84, "DERIVED"), days_to_maturity: f(3230, "DERIVED"), maturity_year: nport(2035),
    fund_count: nport(12, "FUND_REPORTED_REFERENCE", "REPORTING_FUND_SERIES"), fund_par_held: nport(48.25),
    fund_value_pct: nport(101.42, "FUND_REPORTED_STALE", "MEDIAN_FUND_FAIR_VALUE_PCT_OF_PAR"), outstanding: nport(null),
    auction_yield: nport(null), observed_price: nport(null), reference_rate: f(5.17, "REFERENCE", "NOMINAL_PAR_10Y", "2026-09-25") },
};
const OBSERVED_NOTE = bond("91282CRF0", "XA01:NOTE", "Note", "U.S. Treasury Note 4.625% Aug 2036", "2036-08-15", 4.625, 9.88, {
  category: "Treasury", observed_date: "2026-09-24" });
Object.assign(OBSERVED_NOTE.fields, {
  observed_price: { value: 99.5, source: "US_TREASURY_FISCAL_DATA_BUYBACKS", state: "DATED_OBSERVATION", as_of: "2026-09-24", basis: "TREASURY_BUYBACK" },
  observed_yield: { value: 4.689, source: "IMP_DERIVED", state: "DERIVED", as_of: "2026-09-24", basis: "YTM" },
  benchmark_spread: { value: -44.2, source: "IMP_DERIVED", state: "DERIVED", as_of: "2026-09-24", basis: "NOMINAL_PAR_LINEAR_7Y_10Y" },
});
const s16Coverage = { TREASURY: { state: "CURRENT", count: 2 }, CORPORATE: { state: "FUND_HELD_REFERENCE", count: 23510 },
  AGENCY: { state: "FUND_HELD_REFERENCE", count: 4477 }, MUNICIPAL: { state: "FUND_HELD_REFERENCE", count: 141445 },
  SECURITIZED: { state: "FUND_HELD_REFERENCE", count: 158921 } };
const fundItem = (id: string, label: string, value: number | string | null, unit: string, klass = "OBSERVED", note: string | null = null) =>
  ({ id, label, value, unit, class: value === null ? "UNAVAILABLE" : klass, source: "SEC_FORM_NPORT", as_of: "2026-04-30", note });
const muniPreview = () => ({
  ...bondPreview("XA01:MUNI", "13063DAB0"),
  instrument: { instrument_id: "XA01:MUNI", venue_id: "US_OTC_FIXED_INCOME", asset_class: "BOND", instrument_kind: "BOND",
    tradability: "REFERENCE_ONLY", cusip: "13063DAB0", isin: "US13063DAB04", identity_source: "CUSIP", issuer: "State of California",
    description: "CALIFORNIA ST 5.00% 2035", security_type: "Municipal", series: null, category: "Municipal" },
  sections: [
    { id: "identity", title: "Identity", items: [fundItem("cusip", "CUSIP", "13063DAB0", "text")] },
    { id: "terms", title: "Terms (fund-reported)", items: [fundItem("coupon", "Coupon", 5, "percent"),
      fundItem("frequency", "Coupon frequency", null, "text", "UNAVAILABLE", "Not reported in Form N-PORT")] },
    { id: "market", title: "Market", items: [
      fundItem("price", "Current price", null, "per_100_par", "UNAVAILABLE", "No permitted security-level price source is integrated"),
      fundItem("latest_trade", "Latest trade", null, "per_100_par", "UNAVAILABLE", "MSRB EMMA trade data is not licensed for redistribution; not scraped"),
      fundItem("fund_value", "Fund fair value (median, % of par)", 101.42, "per_100_par", "STALE", "The funds' own valuations at their report dates")] },
    { id: "holdings", title: "Fund holdings · 2026-04-30", items: [fundItem("fund_count", "Reporting fund series", 12, "count"),
      fundItem("par_held", "Principal reported held (sum)", 48.25, "USD_MILLIONS")] },
    { id: "ratings", title: "Ratings", items: [fundItem("rating", "Credit ratings", null, "text", "UNAVAILABLE", "NRSRO ratings require a licensed feed (terms required); not scraped")] },
  ],
  sources: [{ id: "NPORT_CATALOG", label: "Fund-held bonds (Form N-PORT)", provider: "SEC EDGAR", clock: "QUARTERLY_PUBLICATION_60_DAY_LAG",
    state: "CURRENT_AS_FILED", as_of: "2026-04-30", reason: null, licence: "Public SEC data; attribution" },
    { id: "MSRB_EMMA", label: "Municipal trades & disclosures", provider: "MSRB EMMA", clock: "TRANSACTION", state: "TERMS_REQUIRED",
      as_of: null, reason: "NOT_LICENSED_FOR_REDISTRIBUTION" }],
});
const observedSpread = { state: "DERIVED", reason: null, value: -44.2, unit: "bp", yield: 4.689, yield_basis: "YTM", price: 99.5,
  price_kind: "TREASURY_BUYBACK", source: "US_TREASURY_FISCAL_DATA_BUYBACKS", operation_date: "2026-09-24", settlement_date: "2026-09-25",
  curve: "NOMINAL_PAR", curve_date: "2026-09-24", par_yield: 5.131, tenors: ["7Y", "10Y"],
  note: "Yield at a dated operation price minus the same-day par curve; an observation on the operation date, not a current spread." };

describe("Bonds S16 categories", () => {
  beforeEach(() => {
    mocks.config.mockReset().mockResolvedValue(config());
    mocks.fetch.mockReset().mockImplementation(async () => bondPage([OBSERVED_NOTE, MUNI] as never, { coverage: s16Coverage, unfiltered_count: 327355 }));
    mocks.window.mockReset().mockResolvedValue({ quotes: {}, active: 0, cap: 32, market_session: "CLOSED" });
    mocks.last.mockReset().mockResolvedValue({ result: {}, saved: [] });
    mocks.layout.mockReset().mockResolvedValue({}); mocks.panelLayout.mockReset().mockResolvedValue({});
    mocks.demand.mockReset().mockResolvedValue({ instrument_id: null, panels: {} }); mocks.releasePanels.mockReset().mockResolvedValue({});
    mocks.bondPreview.mockReset().mockImplementation(async (id: string) => BondPreviewSchema.parse(id === "XA01:MUNI" ? muniPreview() : bondPreview(id)));
    mocks.rates.mockReset().mockImplementation(async (id: string | null) => RatesCurveSchema.parse(ratesPayload(id, {
      selected: id ? { ...ratesPayload(id).selected, category: "Treasury", spread: observedSpread } : null,
      nyfed: { state: "PUBLICATION_CURRENT", reason: null, items: [{ id: "SOFR", label: "Secured Overnight Financing Rate", value: 4.31,
        unit: "percent", effective_date: "2026-09-25", volume_billions: 2400, class: "OBSERVED", source: "NY_FED_REFERENCE_RATES" }] },
      soma: { state: "PUBLICATION_CURRENT", as_of: "2026-09-23", counts: { MBS: 8387 } } })));
    vi.stubGlobal("crypto", { randomUUID: () => "abc-123" });
  });

  it("lists fund-held categories inside Bonds with per-category counts and stale fund values", async () => {
    mount("/screener?universe=BONDS&view=Credit+%26+Munis");
    await screen.findByText("13063DAB0");
    expect(headers()).toEqual(["Security · CUSIP", "Issuer", "Category", "Type", "Coupon", "Cpn Type", "Maturity", "Yrs", "Funds",
      "Fund Par", "Fund Value", "Reported"]);
    const row = screen.getByText("13063DAB0").closest("[role=row]") as HTMLElement;
    expect(within(row).getAllByText("Municipal", { selector: "span" })).toHaveLength(2); // category and asset type
    expect(within(row).getByText("101.420").getAttribute("title")).toContain("FUND_REPORTED_STALE");
    expect(within(row).getByText("$48.3M")).toBeInTheDocument();
    expect(screen.getByText("Treasury 2 · Corporate 23,510 · Agency 4,477 · Municipal 141,445 · Securitized 158,921")).toBeInTheDocument();
  });

  it("shows dated observations as reference columns that never sort", async () => {
    mount("/screener?universe=BONDS&view=Observed");
    await screen.findByText("91282CRF0");
    expect(screen.getByText("99.500").getAttribute("title")).toContain("DATED_OBSERVATION");
    expect(screen.getByText("-44.2 bp")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Obs\. Price/ })).toHaveAttribute("aria-disabled", "true");
  });

  it("previews a fund-held bond with its reported issuer, stale value, and licence-required sources", async () => {
    mount();
    await screen.findByText("13063DAB0");
    fireEvent.click(within(screen.getByRole("grid")).getByText("13063DAB0"));
    const preview = await screen.findByRole("complementary", { name: "Quick preview" });
    await within(preview).findByText("Fund fair value (median, % of par)");
    expect(within(preview).getByText("State of California")).toBeInTheDocument();
    expect(within(preview).queryByText("U.S. Treasury")).not.toBeInTheDocument();
    expect(within(preview).getByText("Fund value")).toBeInTheDocument();
    expect(within(preview).getAllByText("Stale").length).toBeGreaterThan(0);
    expect(within(preview).getByText(/MSRB EMMA trade data is not licensed/)).toBeInTheDocument();
    expect(within(preview).getAllByText("Licence required").length).toBeGreaterThan(0);
    expect(within(preview).getByText("$48.3M")).toBeInTheDocument();
  });

  it("places an observed Treasury price's dated spread and NY Fed rates in Rates & Curve", async () => {
    mount();
    await screen.findByText("91282CRF0");
    fireEvent.click(within(screen.getByRole("grid")).getByText("91282CRF0"));
    fireEvent.click(await screen.findByRole("button", { name: "Open Rates & Curve" }));
    const panel = await screen.findByRole("region", { name: /Rates & Curve for 91282CRF0/ }, { timeout: 5000 });
    await within(panel).findByText("-44.2 bp", undefined, { timeout: 5000 });
    expect(within(panel).getByText(/dated, not current/)).toBeInTheDocument();
    expect(within(panel).getByText("SOFR")).toBeInTheDocument();
    expect(within(panel).getByText(/SOMA holdings as of Sep 23, 2026: 8,387 MBS/)).toBeInTheDocument();
  });

  it("accepts only the two spread shapes and the declared item classes", () => {
    expect(() => RatesCurveSchema.parse(ratesPayload("X", { selected: { ...ratesPayload("X").selected, spread: { ...observedSpread, state: "CURRENT" } } }))).toThrow();
    expect(() => BondPreviewSchema.parse({ ...muniPreview(), sections: [{ id: "m", title: "M", items: [{ ...fundItem("p", "Price", 99, "per_100_par"), class: "LIVE" }] }] })).toThrow();
    expect(BondPreviewSchema.parse(muniPreview()).instrument.category).toBe("Municipal");
  });
});

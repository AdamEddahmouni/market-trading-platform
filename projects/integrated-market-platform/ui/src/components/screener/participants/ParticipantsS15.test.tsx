import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PositioningReport, RootCoverage } from "../../../api/screenerParticipants";
import IntelligenceView from "./IntelligenceView";
import { PreviewParticipants } from "./PreviewParticipants";
import { CoverageSummary, FuturesPositioning, UnmappedRoots } from "./sections";

/** S15: every Futures root's CFTC coverage decision on the existing S12 surfaces (view, panel, Quick Preview). */
const mocks = vi.hoisted(() => ({ positioning: vi.fn(), instrument: vi.fn() }));
vi.mock("../../../api/screenerParticipants", async (importActual) => ({
  ...(await importActual<typeof import("../../../api/screenerParticipants")>()),
  fetchPositioningView: mocks.positioning, fetchParticipantInstrument: mocks.instrument,
}));

const T = "2026-09-29T14:40:00Z";
const cat = (id: string, label: string, long: number | null, short: number | null, extra: Record<string, unknown> = {}) => ({
  id, label, long, short, spreading: null, change_long: 100, change_short: -50,
  net: long != null && short != null ? long - short : null, net_change: 150, traders_long: 20, traders_short: 18,
  long_pct_oi: long == null ? null : 12.5, short_pct_oi: short == null ? null : 5.0, ...extra });
const tff: PositioningReport = {
  root: "ES", report: "TFF", report_label: "Traders in Financial Futures (futures only)", cftc_contract_market_code: "13874A",
  market_name: "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE", report_date: "2026-09-22", publication_time: "2026-09-25T19:30:00Z",
  publication_basis: "CFTC_OFFICIAL_SCHEDULE", open_interest: 2_000_000, change_open_interest: -1500,
  categories: [cat("DEALER_INTERMEDIARY", "Dealer / intermediary", 100, 900, { spreading: 42 }),
    cat("ASSET_MANAGER_INSTITUTIONAL", "Asset manager / institutional", 900, 300),
    cat("LEVERAGED_FUNDS", "Leveraged funds", 200, 700), cat("NON_REPORTABLES", "Non-reportables", 50, null)],
  net_method: "DERIVED: net = reported long − reported short for the category. Positioning is not a price forecast.",
  oi_method: "DERIVED: category long (short) ÷ total open interest × 100, for the same report.",
  source_url: "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm", contract: "ESZ26", coverage_state: "MAPPED",
  quality_state: "OK", quality_flags: [], latest_scheduled_report_date: "2026-09-22",
  mapping: { basis: "EXCHANGE_PLUS_PRODUCT", confidence: "EXACT", note: null, cftc_exchange: "CHICAGO MERCANTILE EXCHANGE",
    provider_exchange: "US_CME", former_names: [] },
};
const dis: PositioningReport = { ...tff, root: "CL", report: "DISAGGREGATED", report_label: "Disaggregated (futures only)",
  cftc_contract_market_code: "067651", market_name: "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE", contract: "CLX26",
  categories: [cat("PRODUCER_MERCHANT", "Producer / merchant / processor / user", 400, 600),
    cat("SWAP_DEALER", "Swap dealers", 300, 100, { spreading: 80 }), cat("MANAGED_MONEY", "Managed money", 250, 50)],
  mapping: { ...tff.mapping!, cftc_exchange: "NEW YORK MERCANTILE EXCHANGE", provider_exchange: "US_NYMEX" } };
const decision = (root: string, status: string, reason: string | null, label: string, note: string | null): RootCoverage => ({
  root, status, reason, label, note, provider_exchange: null, candidate_code: null });
const MAPPED = (root: string) => decision(root, "MAPPED", null, "Mapped to a CFTC market", null);
const STOCK = decision("SNVDA", "NO_CFTC_REPORT", "PRODUCT_NOT_COVERED", "Single-stock future · no COT market",
  "Single-stock future. No COT report (Legacy, TFF, or Disaggregated, 2012 onward) contains a single-stock market.");
const NO_MARKET = decision("M6E", "NO_CFTC_REPORT", "NO_CFTC_MARKET_FOUND", "No CFTC market",
  "CFTC reports the full-size EURO FX market only; there is no micro market.");
const VXM = { ...decision("VXM", "AMBIGUOUS", "AMBIGUOUS_MAPPING", "Ambiguous CFTC market",
  "CFTC publishes one VIX FUTURES market; its identity does not state whether Mini VIX positions are included."), candidate_code: "1170E1" };

const mapped = (report: PositioningReport) => ({ state: "PUBLICATION_CURRENT", reason: null, root: report.root, contract: report.contract,
  coverage: MAPPED(report.root), report, evidence_basis: "CFTC_LARGE_TRADER_CONTEXT" });
const unmapped = (coverage: RootCoverage) => ({ state: "NO_MATCH", reason: coverage.reason, root: coverage.root, contract: `${coverage.root}Z26`, coverage });
const REALTIME = /\b(real-?time|live)\b/i;

beforeEach(() => { mocks.positioning.mockReset(); mocks.instrument.mockReset(); });

describe("S15 Institutional & Whale Futures positioning", () => {
  it("shows the CFTC market, positions, change, context, and provenance for a mapped TFF root", () => {
    render(<FuturesPositioning compact={false} section={mapped(tff)} />);
    const section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
    for (const heading of ["CFTC market", "Positions & weekly change", "Context", "Provenance"]) {
      expect(within(section).getByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(section).toHaveTextContent("E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE · code 13874A · Traders in Financial Futures (futures only)"
      + " · positions as of 2026-09-22 · released 2026-09-25 19:30 UTC");
    const table = within(section).getByRole("table", { name: /categories for ES/ });
    const headers = within(table).getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["Category", "Long", "Short", "Spreading", "Wk chg L / S", "Net (derived)", "Net chg (derived)",
      "% OI L / S (derived)", "Traders L / S"]);
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Dealer / intermediary10090042+100 / -50-800+15012.5% / 5.0%20 / 18");
    expect(rows[4]).toHaveTextContent("Non-reportables50——+100 / -50—+15012.5% / —");   // missing short: no net, never 0
    expect(section).toHaveTextContent("Open interest 2,000,000 (-1,500 published weekly change)");
    expect(section).toHaveTextContent("DERIVED: net = reported long − reported short");
    expect(section).toHaveTextContent("Mapping: exchange + product (exact) · CFTC exchange CHICAGO MERCANTILE EXCHANGE · provider venue US_CME · coverage mapped");
    expect(section.textContent).not.toMatch(REALTIME);
    expect(section.textContent).not.toMatch(/score/i);
  });

  it("keeps Disaggregated categories and labels distinct from TFF", () => {
    render(<FuturesPositioning compact={false} section={mapped(dis)} />);
    const section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
    expect(section).toHaveTextContent("Disaggregated (futures only)");
    expect(section).toHaveTextContent("Managed money");
    expect(section).toHaveTextContent("Producer / merchant / processor / user");
    expect(section).not.toHaveTextContent("Asset manager");
    expect(section).not.toHaveTextContent("Leveraged funds");
  });

  it.each([[STOCK, "Single-stock future · no COT market"], [NO_MARKET, "No CFTC market"], [VXM, "Ambiguous CFTC market"]])(
    "explains an unmapped root (%#) and never shows zero positions", (coverage, label) => {
      render(<FuturesPositioning compact={false} section={unmapped(coverage)} />);
      const section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
      expect(section).toHaveTextContent(`CFTC positioning unavailable · ${label}. ${coverage.note}`);
      expect(within(section).queryByRole("table")).toBeNull();
      expect(section.textContent).not.toMatch(/\b0\b/);
    });

  it("keeps Mini VIX ambiguous rather than showing VIX positioning", () => {
    render(<FuturesPositioning compact={false} section={unmapped(VXM)} />);
    expect(screen.getByRole("region", { name: "CFTC Commitments of Traders" })).toHaveTextContent("Mini VIX");
    expect(screen.queryByText(/VIX FUTURES - CBOE/)).toBeNull();
  });

  it("distinguishes a known market with no recent report from a root with no market", () => {
    render(<FuturesPositioning compact={false} section={{ state: "NO_DISCLOSURES", reason: "KNOWN_MARKET_NOT_IN_RECENT_RELEASES",
      root: "QG", coverage: MAPPED("QG") }} />);
    const section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
    expect(section).toHaveTextContent("A known CFTC market, but it has no public report in the loaded window");
    expect(section).not.toHaveTextContent("CFTC positioning unavailable");
  });

  it("states when a market is missing from the latest release and when rows conflict", () => {
    const { unmount } = render(<FuturesPositioning compact={false} section={mapped({ ...tff, report_date: "2026-09-15",
      quality_flags: ["KNOWN_MARKET_NOT_IN_LATEST_RELEASE"] })} />);
    expect(screen.getByText("This market is not in the latest CFTC release (as of 2026-09-22); its newest report is shown.")).toBeInTheDocument();
    unmount();
    render(<FuturesPositioning compact={false} section={{ ...mapped({ ...tff, categories: [], open_interest: null, quality_state: "CONFLICTING_DUPLICATE_ROWS",
      quality_flags: ["CONFLICTING_DUPLICATE_ROWS"] }), state: "UNAVAILABLE", reason: "CONFLICTING_DUPLICATE_ROWS" }} />);
    const section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
    expect(section).toHaveTextContent("Conflicting CFTC rows; values withheld");
    expect(section).toHaveTextContent("values are withheld");
  });
});

describe("S15 Quick Preview Futures context", () => {
  it("shows a compact summary with the categories each report is read for", () => {
    const { unmount } = render(<FuturesPositioning compact section={mapped(tff)} />);
    let section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
    expect(section).toHaveTextContent("Traders in Financial Futures (futures only) · as of 2026-09-22 · released 2026-09-25 19:30 UTC");
    expect(within(section).getAllByRole("row").slice(1).map((row) => within(row).getByRole("rowheader").textContent))
      .toEqual(["Asset manager / institutional", "Leveraged funds"]);
    expect(within(section).queryByRole("heading", { name: "Provenance" })).toBeNull();
    unmount();
    render(<FuturesPositioning compact section={mapped(dis)} />);
    section = screen.getByRole("region", { name: "CFTC Commitments of Traders" });
    expect(within(section).getAllByRole("row").slice(1).map((row) => within(row).getByRole("rowheader").textContent))
      .toEqual(["Producer / merchant / processor / user", "Managed money"]);
  });

  it("renders only the last selected root after rapid switching (mapped → unmapped → mapped)", async () => {
    const payload = (id: string, section: unknown) => ({ schema_version: "screener-participants/1.0.0", generated_at: T, universe: "FUTURES",
      lens: "institutional", compact: true, instrument: { instrument_id: id, symbol: id, label: id }, state: "PUBLICATION_CURRENT",
      providers: [], sections: { futures_positioning: section }, boundaries: [] });
    let finishEs: (value: unknown) => void = () => undefined;
    mocks.instrument.mockImplementation((_universe: string, id: string) => {
      if (id === "ESZ26") return new Promise((resolve) => { finishEs = resolve; });   // the slow first root
      return Promise.resolve(id === "SNVDAZ26" ? payload(id, unmapped(STOCK)) : payload(id, mapped(dis)));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const row = (id: string) => ({ instrument: { instrument_id: id }, symbol: id }) as never;
    const view = (id: string) => <QueryClientProvider client={client}>
      <PreviewParticipants row={row(id)} settledId={id} universe="FUTURES" institutional government={false} /></QueryClientProvider>;
    const { rerender } = render(view("ESZ26"));
    rerender(view("SNVDAZ26"));
    rerender(view("CLX26"));
    await screen.findByText(/Disaggregated \(futures only\) · as of 2026-09-22/);
    await act(async () => { finishEs(payload("ESZ26", mapped(tff))); await Promise.resolve(); });
    const summary = screen.getByLabelText("Institutional & Whale summary");
    expect(summary).toHaveTextContent("Managed money");
    expect(summary).not.toHaveTextContent("Asset manager");
    expect(summary).not.toHaveTextContent("Single-stock");
    await waitFor(() => expect(mocks.instrument).toHaveBeenLastCalledWith("FUTURES", "CLX26", "institutional", true, expect.anything()));
  });
});

describe("S15 Positioning view coverage", () => {
  const coverage = { universe_roots: 178, mapped_roots: 67, unmapped_roots: ["M6E", "SNVDA", "VXM"], reported_roots: 61,
    by_status: { MAPPED: 67, NO_CFTC_REPORT: 110, AMBIGUOUS: 1, UNCLASSIFIED: 0 }, registry_verified: "2026-09-29",
    breakdown: [{ id: "MAPPED", label: "Mapped to a CFTC market", count: 67 },
      { id: "PRODUCT_NOT_COVERED", label: "Single-stock future · no COT market", count: 77 },
      { id: "NO_CFTC_MARKET_FOUND", label: "No CFTC market", count: 33 }, { id: "AMBIGUOUS_MAPPING", label: "Ambiguous CFTC market", count: 1 }],
    mapped_without_report: ["QG"] };

  it("summarizes coverage from the payload, never from fixed prose", () => {
    render(<CoverageSummary coverage={coverage} />);
    expect(screen.getByLabelText("CFTC coverage by root")).toHaveTextContent("Coverage · 178 roots: 67 mapped to a cftc market · "
      + "77 single-stock future · no cot market · 33 no cftc market · 1 ambiguous cftc market · 0 unclassified · decisions verified 2026-09-29.");
  });

  it("groups unmapped roots by reason, with ambiguity open by default", () => {
    render(<UnmappedRoots roots={[{ ...STOCK, contract: "SNVDAZ26" }, NO_MARKET, VXM]} />);
    const groups = screen.getAllByRole("group");
    expect(groups.map((item) => item.querySelector("summary")?.textContent)).toEqual(
      ["Single-stock future · no COT market · 1", "No CFTC market · 1", "Ambiguous CFTC market · 1"]);
    expect(groups.map((item) => (item as HTMLDetailsElement).open)).toEqual([false, false, true]);
    expect(within(groups[0]).getByRole("row", { name: /SNVDA/ })).toHaveTextContent("SNVDASNVDAZ26—Single-stock future.");
  });

  it("renders the full view: coverage header, both report families, and unmapped explanations", async () => {
    mocks.positioning.mockResolvedValue({ schema_version: "screener-participants/1.0.0", generated_at: T, universe: "FUTURES",
      view: "positioning", state: "PUBLICATION_CURRENT", reason: null,
      providers: [{ id: "cftc_cot", label: "CFTC Commitments of Traders", family: "WHALE", scope: "UNIVERSE", state: "PUBLICATION_CURRENT",
        reason: null, fetched_at: T, published: null, item_count: 120, cadence: "Weekly; Tuesday positions, Friday 15:30 ET release" }],
      groups: [{ report: "TFF", label: "Traders in Financial Futures (futures only)", rows: [tff] },
        { report: "DISAGGREGATED", label: "Disaggregated (futures only)", rows: [dis] }],
      coverage, unmapped: [STOCK, NO_MARKET, VXM], report_policy: "Financial futures use Traders in Financial Futures; physical commodities "
        + "use Disaggregated. Legacy (commercial / non-commercial) is used only as mapping reference.",
      oi_method: tff.oi_method, boundaries: ["CFTC positioning describes reported categories; it is not a price forecast."],
      time_note: "Positions as of the report date (Tuesday); public from the official release time." });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><IntelligenceView universe="FUTURES" universeLabel="Futures" view="positioning" search=""
      onUpdate={() => undefined} /></QueryClientProvider>);
    const view = await screen.findByRole("region", { name: "CFTC positioning by root" });
    expect(within(view).getByLabelText("CFTC coverage by root")).toHaveTextContent("178 roots: 67 mapped");
    const tffGroup = within(view).getByRole("region", { name: "Traders in Financial Futures (futures only)" });
    expect(tffGroup).toHaveTextContent("ESZ26 · CFTC 13874A · mapped by exchange plus product · OI weekly change -1,500 (published)");
    expect(within(tffGroup).getByRole("columnheader", { name: "Net (derived)" })).toBeInTheDocument();
    expect(within(view).getByRole("region", { name: "Disaggregated (futures only)" })).toHaveTextContent("Managed money");
    expect(view).toHaveTextContent("Known CFTC markets with no public report in the loaded window (below the CFTC reporting threshold): QG.");
    expect(within(view).getByRole("region", { name: "Roots without CFTC positioning" })).toHaveTextContent("Ambiguous CFTC market · 1");
    expect(view).toHaveTextContent("Legacy (commercial / non-commercial) is used only as mapping reference.");
    expect(view.textContent).not.toMatch(REALTIME);
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PaperPerformanceView } from "./PaperPerformancePanel";
import { PerformanceReportSchema } from "../../api/paperPerformance";

export const fixture = {
  schema_version: "paper-performance/1.0.0", report_id: "PPEVAL-test", run_id: "PPR-test",
  experiment_id: "PPE-test", account_id: "a", currency: "USD", initial_capital_minor: 10000000,
  first_session: "2026-10-27", fixed_sessions: 20, covered_sessions: 19, complete: false,
  configuration: {}, calendar_version: "test", authority: { trading_mutation: false, live_capital: false },
  assumptions: ["Whole selected Paper account; internal simulation."],
  milestones: {
    fixed_10: { clock: "fixed", day: 10, status: "Fail", session_date: "2026-11-09", equity_minor: 9999999,
      completed_trades: 15, conditions: { above_start: false }, reasons: [], supplemental: false },
    fixed_20: { clock: "fixed", day: 20, status: "Cannot determine", session_date: "2026-11-23", equity_minor: 10100000,
      completed_trades: 30, conditions: { above_start: true, completed_30_trades: true, above_spy: null },
      reasons: ["MANUAL_FILLS", "COVERAGE_GAP"], supplemental: false },
    covered_10: { clock: "covered", day: 10, status: "Cannot determine", session_date: "2026-11-10", equity_minor: 10000001,
      completed_trades: 16, conditions: { above_start: true }, reasons: ["COVERAGE_GAP"], supplemental: true },
    covered_20: { clock: "covered", day: 20, status: "Not due", session_date: null, equity_minor: null,
      completed_trades: 0, conditions: { above_start: null }, reasons: [], supplemental: true },
  },
  sessions: [
    { session_date: "2026-10-27", cutoff_ns: 1793131200000000000, covered: true, equity_minor: 10000000,
      ledger_equity_minor: 10000000, spy_equity_minor: "10000000", completed_trades: 1, reasons: [],
      costs: { commission_minor: 5, fees_minor: 2, posted_borrow_minor: 1, unposted_borrow_minor: 1 },
      coverage: { reasons: [], gaps: [], observations: 391 } },
    { session_date: "2026-10-28", cutoff_ns: 1793217600000000000, covered: false, equity_minor: null,
      ledger_equity_minor: null, spy_equity_minor: null, completed_trades: 2, reasons: ["CLOSING_VALUATION_UNAVAILABLE"],
      costs: { commission_minor: 10, fees_minor: 4, posted_borrow_minor: 1, unposted_borrow_minor: 0 },
      coverage: { reasons: ["COVERAGE_GAP"], gaps: [{ start_ns: 1, end_ns: 2, seconds: 180 }], observations: 10 } },
    { session_date: "2026-10-29", cutoff_ns: 1793304000000000000, covered: true, equity_minor: 10100000,
      ledger_equity_minor: 10100000, spy_equity_minor: "10050000", completed_trades: 30, reasons: [],
      costs: { commission_minor: 20, fees_minor: 8, posted_borrow_minor: 2, unposted_borrow_minor: 1 },
      coverage: { reasons: [], gaps: [], observations: 391 } },
  ],
};

describe("Paper performance scorecard", () => {
  it("keeps fixed and covered outcomes distinct and explains mixed account", () => {
    render(<PaperPerformanceView report={PerformanceReportSchema.parse(fixture)} onDownload={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Day 10 and day 20 results" })).toBeInTheDocument();
    expect(screen.getByText("Fixed day 10")).toBeInTheDocument();
    expect(screen.getByText("Covered day 20")).toBeInTheDocument();
    expect(screen.getAllByText("Cannot determine").length).toBeGreaterThan(0);
    expect(screen.getByText(/Manual trades make this a mixed run/)).toBeInTheDocument();
    expect(screen.getByText(/19 covered sessions/)).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Daily account and SPY values" })).toBeInTheDocument();
  });
  it("shows gaps, both curves, costs and download actions with no trading buttons", () => {
    const download = vi.fn();
    const { container } = render(<PaperPerformanceView report={PerformanceReportSchema.parse(fixture)} onDownload={download} />);
    expect(screen.getByRole("img", { name: /Account and SPY/ })).toBeInTheDocument();
    expect(container.querySelectorAll("polyline")).toHaveLength(4);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText(/Unposted borrow/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download HTML" }));
    expect(download).toHaveBeenCalledWith("html");
    expect(screen.queryByRole("button", { name: /Submit|Arm|Trade/ })).not.toBeInTheDocument();
  });
  it("rejects unsupported report versions and invalid verdicts", () => {
    expect(PerformanceReportSchema.safeParse({ ...fixture, schema_version: "future" }).success).toBe(false);
    expect(PerformanceReportSchema.safeParse({ ...fixture, milestones: { bad: { ...fixture.milestones.fixed_10, status: "Guaranteed" } } }).success).toBe(false);
  });
});

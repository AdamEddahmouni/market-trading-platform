import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { CountBarChartPanel, SignalTimelineChartPanel } from "./ResearchChartPanels";

// recharts needs layout; jsdom never lays out. Stub the chart primitives so
// the tabular summaries (the a11y-critical content) can be asserted.
vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Bar: () => null,
  LineChart: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Line: () => null,
  CartesianGrid: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
}));

describe("CountBarChartPanel", () => {
  it("renders a tabular summary with scoped headers alongside the chart", () => {
    render(
      <CountBarChartPanel
        title="Strategy interpretation outcomes"
        series={[
          { label: "signal", count: 12 },
          { label: "abstention", count: 3 },
        ]}
        provenance={{ source: "phase 5R walk-forward + phase 6 strategy" }}
        ariaLabel="Strategy outcome bar chart"
      />,
    );
    expect(screen.getByRole("img", { name: "Strategy outcome bar chart" })).toBeInTheDocument();
    const caption = screen.getByText("Strategy interpretation outcomes tabular summary");
    expect(caption).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Label" })).toHaveAttribute("scope", "col");
    expect(screen.getByRole("cell", { name: "signal" })).toBeInTheDocument();
    expect(screen.getByText(/Source: phase 5R walk-forward/)).toBeInTheDocument();
  });

  it("renders the empty state with the given reason and no fake chart", () => {
    render(
      <CountBarChartPanel
        title="Squeeze screener outcomes"
        series={[]}
        provenance={{ source: "short-squeeze-project" }}
        emptyMessage="Not available at this cutoff: donor bridge unavailable."
        ariaLabel="Squeeze outcome bar chart"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/donor bridge unavailable/i);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("renders interpretation-first children between heading and chart", () => {
    render(
      <CountBarChartPanel
        title="Attention tier distribution"
        series={[{ label: "1", count: 4 }]}
        provenance={{ source: "replay attention feed" }}
        ariaLabel="Attention tier bar chart"
      >
        <p>The claim in words.</p>
      </CountBarChartPanel>,
    );
    expect(screen.getByText("The claim in words.")).toBeInTheDocument();
  });
});

describe("SignalTimelineChartPanel", () => {
  it("ships a tabular summary (closes the chart text-alternative gap)", () => {
    render(
      <SignalTimelineChartPanel
        title="Cumulative strategy signals (walk-forward)"
        timeline={[
          { observation_index: 1, cumulative_signals: 1, outcome: "signal" },
          { observation_index: 2, cumulative_signals: 1, outcome: "abstention" },
        ]}
        provenance={{ source: "phase 5R walk-forward + phase 6 strategy" }}
        ariaLabel="Walk-forward signal timeline chart"
      />,
    );
    expect(
      screen.getByRole("img", { name: "Walk-forward signal timeline chart" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Cumulative strategy signals (walk-forward) tabular summary"),
    ).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Cumulative signals" })).toHaveAttribute(
      "scope",
      "col",
    );
    expect(screen.getByRole("cell", { name: "abstention" })).toBeInTheDocument();
  });

  it("renders the empty state when no timeline rows exist", () => {
    render(
      <SignalTimelineChartPanel
        title="Cumulative strategy signals (walk-forward)"
        timeline={[]}
        provenance={{ source: "test" }}
        ariaLabel="Walk-forward signal timeline chart"
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/no walk-forward interpretations/i);
  });
});

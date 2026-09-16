import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { ResearchEvidenceSection } from "./ResearchEvidenceSection";

const analyticsFixture = {
  as_of_context: { mode: "REPLAY", as_of_time: "2026-09-15T13:30:00Z", timezone: "UTC" },
  authority_boundary: "READ_ONLY_RESEARCH_VISUALIZATION",
  disclaimer: "Research only.",
  epistemic_class: "RESEARCH_PROJECTION",
  panels: {
    attention_tiers: {
      available: true,
      provenance: { source: "replay attention feed", method: "tier aggregation" },
      series: [{ label: "1", count: 4 }],
    },
    squeeze_outcomes: {
      available: false,
      reason: "donor bridge unavailable",
      provenance: { source: "short-squeeze-project" },
      series: [],
    },
    squeeze_historical_cohort: {
      available: true,
      provenance: { source: "cohort fixture" },
      series: [],
      cohort_metadata: { cohort_size: 42 },
    },
    strategy_outcomes: {
      available: true,
      provenance: { source: "phase 5R walk-forward + phase 6 strategy" },
      series: [
        { label: "signal", count: 12 },
        { label: "abstention", count: 3 },
      ],
      signal_timeline: [{ observation_index: 1, cumulative_signals: 1, outcome: "signal" }],
    },
    risk_decisions: {
      available: true,
      provenance: { source: "phase 7 risk simulation" },
      series: [{ label: "APPROVE", count: 9 }],
    },
  },
};

const analyticsState = {
  isLoading: false,
  isError: false,
  error: null as Error | null,
  data: analyticsFixture as typeof analyticsFixture | undefined,
  refetch: vi.fn(),
};

vi.mock("../../api/hooks", () => ({
  useResearchAnalyticsQuery: () => analyticsState,
}));

vi.mock("../charts/ResearchChartPanels", () => ({
  CountBarChartPanel: ({
    title,
    children,
    series,
    emptyMessage,
  }: {
    title: string;
    children?: ReactNode;
    series: Array<{ label: string; count: number }>;
    emptyMessage?: string;
  }) => (
    <section data-testid={`count-chart-${title}`}>
      <h3>{title}</h3>
      {children}
      {series.length ? (
        <ul>
          {series.map((row) => (
            <li key={row.label}>
              {row.label}:{row.count}
            </li>
          ))}
        </ul>
      ) : (
        <p role="status">{emptyMessage}</p>
      )}
    </section>
  ),
  SignalTimelineChartPanel: ({ title }: { title: string }) => (
    <section data-testid="timeline-chart">
      <h3>{title}</h3>
    </section>
  ),
}));

function renderSection(initialEntry = "/research/evidence") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ResearchEvidenceSection />
    </MemoryRouter>,
  );
}

describe("ResearchEvidenceSection", () => {
  beforeEach(() => {
    analyticsState.isLoading = false;
    analyticsState.isError = false;
    analyticsState.error = null;
    analyticsState.data = analyticsFixture;
    vi.clearAllMocks();
  });

  it("shows a loading state", () => {
    analyticsState.isLoading = true;
    renderSection();
    expect(screen.getByRole("status")).toHaveTextContent(/loading research evidence/i);
  });

  it("shows a humanized error state with retry when the endpoint fails", () => {
    analyticsState.isError = true;
    analyticsState.data = undefined;
    analyticsState.error = new Error("VALIDATION_ERROR: bad payload");
    renderSection();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /research evidence is unavailable right now/i,
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("leads each finding with its claim, state, and evidence class", () => {
    renderSection();
    expect(
      screen.getByText(/How often the walk-forward strategy evaluation produced a signal/i),
    ).toBeInTheDocument();
    // Evidence class appears in both the finding meta row and its Methodology
    // disclosure — both are intentional.
    expect(screen.getAllByText("Walk-forward backtest (replay-bound)").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Historical (donor bridge)").length).toBeGreaterThan(0);
    // signal_timeline present → timeline chart rendered for strategy outcomes.
    expect(screen.getByTestId("timeline-chart")).toBeInTheDocument();
  });

  it("renders unavailable findings with the backend reason, not a fake chart", () => {
    renderSection();
    expect(screen.getByText(/Not available at this cutoff: donor bridge unavailable/i))
      .toBeInTheDocument();
  });

  it("renders empty-but-available findings honestly", () => {
    renderSection();
    expect(
      screen.getByText(/Available, but no rows fall inside the current replay window/i),
    ).toBeInTheDocument();
  });

  it("marks the ?panel= deep-link target", () => {
    renderSection("/research/evidence?panel=squeeze_outcomes");
    const target = document.getElementById("research-finding-squeeze-outcomes");
    expect(target).not.toBeNull();
    expect(target).toHaveAttribute("data-highlighted", "true");
    const other = document.getElementById("research-finding-attention-tiers");
    expect(other).not.toHaveAttribute("data-highlighted");
  });

  it("filters findings on this page only and discloses that there is no catalog search", () => {
    renderSection();
    expect(screen.getByText(/There is no research catalog search API/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Show findings"), { target: { value: "unavailable" } });
    expect(screen.getByText("Squeeze screener outcomes")).toBeInTheDocument();
    expect(screen.queryByText("Attention tier distribution")).not.toBeInTheDocument();
  });

  it("keeps provenance and cohort metadata behind methodology disclosure", () => {
    renderSection();
    const methodologies = screen.getAllByText("Methodology");
    expect(methodologies.length).toBe(5);
    expect(screen.getByText("Cohort metadata")).toBeInTheDocument();
  });
});

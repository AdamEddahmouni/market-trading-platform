import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchOverviewSection } from "./ResearchOverviewSection";

const analyticsFixture = {
  as_of_context: {
    mode: "REPLAY",
    as_of_time: "2026-09-15T13:30:00Z",
    timezone: "UTC",
    replay_session_id: "session-abc123def456",
  },
  authority_boundary: "READ_ONLY_RESEARCH_VISUALIZATION",
  disclaimer: "Research only.",
  epistemic_class: "RESEARCH_PROJECTION",
  panels: {
    attention_tiers: {
      available: true,
      provenance: { source: "replay attention feed" },
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
    },
    strategy_outcomes: {
      available: true,
      provenance: { source: "phase 5R walk-forward + phase 6 strategy" },
      series: [{ label: "signal", count: 12 }],
    },
    risk_decisions: {
      available: true,
      provenance: { source: "phase 7 risk simulation" },
      series: [{ label: "APPROVE", count: 9 }],
    },
  },
};

const modelsFixture = {
  authority_boundary: "READ_ONLY_RESEARCH",
  epistemic_class: "RESEARCH_PROJECTION",
  walk_forward_fold_count: 5,
  preregistration_status: "PASS",
  model_summary: {},
  strategy_spec: {},
  dataset_manifest: {},
  preregistration: {},
  interpretation_summary: { abstention_count: 3, signal_count: 12, total_at_cutoff: 15 },
  interpretations: [],
};

const simulationFixture = {
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  epistemic_class: "SIMULATION_PROJECTION",
  ledger_summary: { cash_minor: 100000, position_shares: 0, realized_pnl_minor: 0, entry_count: 7 },
  risk_decisions: [],
  fills: [],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
};

const analyticsState = {
  isLoading: false,
  isError: false,
  data: analyticsFixture as typeof analyticsFixture | undefined,
  refetch: vi.fn(),
};
const modelsState = {
  isLoading: false,
  isError: false,
  data: modelsFixture as typeof modelsFixture | undefined,
  refetch: vi.fn(),
};
const simulationState = {
  isLoading: false,
  isError: false,
  data: simulationFixture as typeof simulationFixture | undefined,
  refetch: vi.fn(),
};

vi.mock("../../api/hooks", () => ({
  useResearchAnalyticsQuery: () => analyticsState,
  useResearchModelsQuery: () => modelsState,
  useResearchSimulationQuery: () => simulationState,
}));

function renderSection(mode: "DEMO" | "PAPER" | "LIVE" = "DEMO") {
  return render(
    <MemoryRouter>
      <ResearchOverviewSection mode={mode} />
    </MemoryRouter>,
  );
}

describe("ResearchOverviewSection", () => {
  beforeEach(() => {
    analyticsState.isLoading = false;
    analyticsState.isError = false;
    analyticsState.data = analyticsFixture;
    modelsState.isLoading = false;
    modelsState.isError = false;
    modelsState.data = modelsFixture;
    simulationState.isLoading = false;
    simulationState.isError = false;
    simulationState.data = simulationFixture;
    vi.clearAllMocks();
  });

  it("shows a loading state while any source is loading", () => {
    modelsState.isLoading = true;
    renderSection();
    expect(screen.getAllByRole("status").some((node) => /loading research evidence/i.test(node.textContent ?? ""))).toBe(
      true,
    );
  });

  it("leads with the payload-derived synthesis and trust summary", () => {
    renderSection();
    expect(
      screen.getByText(/12 signals and 3 abstentions across 15 observations/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/4 of 5 evidence findings have data/i)).toBeInTheDocument();
    expect(screen.getByText("Research projection")).toBeInTheDocument();
    expect(screen.getByText("Research-only evidence — not tradeable")).toBeInTheDocument();
  });

  it("degrades independently when one source fails", () => {
    simulationState.isError = true;
    simulationState.data = undefined;
    renderSection();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /part of the research evidence could not be loaded/i,
    );
    // The sources that did respond still synthesize.
    expect(screen.getByText(/12 signals and 3 abstentions/i)).toBeInTheDocument();
  });

  it("maps evidence availability with deep links to findings", () => {
    renderSection();
    const squeeze = screen.getByRole("link", { name: "Squeeze screener outcomes" });
    expect(squeeze).toHaveAttribute("href", "/research/evidence?panel=squeeze_outcomes");
    expect(screen.getByText(/Not available at this cutoff: donor bridge unavailable/i))
      .toBeInTheDocument();
  });

  it("does not treat still-loading sources as unavailable coverage", () => {
    modelsState.isLoading = true;
    renderSection();
    expect(screen.getByText(/loading coverage/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Squeeze screener outcomes" })).not.toBeInTheDocument();
  });

  it("states honestly which operator concepts have no contract", () => {
    renderSection();
    expect(
      screen.getByRole("heading", { name: "What this surface cannot tell you yet" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Hypothesis tracking/i)).toBeInTheDocument();
    expect(screen.getByText(/Supporting vs contradictory flags/i)).toBeInTheDocument();
    expect(screen.getByText(/Experiment campaigns \(FTEP\)/i)).toBeInTheDocument();
  });

  it("keeps the replay session id in the methodology disclosure", () => {
    renderSection();
    expect(screen.getByText("Methodology and technical detail")).toBeInTheDocument();
    expect(screen.queryByText("session-abc123def456")).not.toBeInTheDocument();
  });

  it("links Paper mode to strategy outcomes and Live mode to the canary", () => {
    const { unmount } = renderSection("PAPER");
    expect(screen.getByRole("link", { name: "Strategy outcomes in Paper" })).toBeInTheDocument();
    unmount();
    renderSection("LIVE");
    expect(screen.getByText(/stays replay-bound in Live mode/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "live canary" })).toHaveAttribute("href", "/live-canary");
  });
});

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchSimulationSection } from "./ResearchSimulationSection";

const simulationFixture = {
  as_of_context: { mode: "REPLAY", as_of_time: "2026-09-15T13:30:00Z", timezone: "UTC" },
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  disclaimer: "Simulation only.",
  epistemic_class: "SIMULATION_PROJECTION",
  risk_policy_id: "default-policy-001",
  ledger_summary: { cash_minor: 100000, position_shares: 4, realized_pnl_minor: -250, entry_count: 7 },
  risk_decisions: [
    {
      risk_decision_id: "rd-1",
      decision: "APPROVE",
      constraint_detail: "within size limits",
      signal_prediction_cutoff: 1_757_500_300_000_000_000,
      intent_id: "intent-abc123def456",
    },
  ],
  fills: [
    {
      fill_id: "fill-1",
      fill_time: 1_757_500_400_000_000_000,
      direction: "BUY",
      fill_quantity: 4,
      fill_price_minor: 10125,
    },
  ],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
  fill_audit: { status: "PASS" },
};

const simulationState = {
  isLoading: false,
  isError: false,
  error: null as Error | null,
  data: simulationFixture as typeof simulationFixture | undefined,
  refetch: vi.fn(),
};

vi.mock("../../api/hooks", () => ({
  useResearchSimulationQuery: () => simulationState,
}));

vi.mock("../charts/ResearchChartPanels", () => ({
  CountBarChartPanel: ({ title }: { title: string }) => (
    <section data-testid="count-chart">
      <h3>{title}</h3>
    </section>
  ),
  SignalTimelineChartPanel: () => null,
}));

function renderSection() {
  return render(
    <MemoryRouter>
      <ResearchSimulationSection mode="DEMO" />
    </MemoryRouter>,
  );
}

describe("ResearchSimulationSection", () => {
  beforeEach(() => {
    simulationState.isLoading = false;
    simulationState.isError = false;
    simulationState.error = null;
    simulationState.data = simulationFixture;
    vi.clearAllMocks();
  });

  it("shows a loading state", () => {
    simulationState.isLoading = true;
    renderSection();
    expect(screen.getByRole("status")).toHaveTextContent(/loading simulation record/i);
  });

  it("shows a humanized error state with retry", () => {
    simulationState.isError = true;
    simulationState.data = undefined;
    renderSection();
    expect(screen.getByRole("alert")).toHaveTextContent(
      /simulation record is unavailable right now/i,
    );
  });

  it("leads with the ledger headline and honest check states", () => {
    renderSection();
    expect(screen.getByText(/7 ledger entries · 1 risk decision · 1 fill/i)).toBeInTheDocument();
    // Heading + epistemic StatePill both carry the label — both intentional.
    expect(screen.getAllByText("Deterministic simulation").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Reconciliation: Pass")).toBeInTheDocument();
    expect(screen.getByText("Fill audit: Pass")).toBeInTheDocument();
  });

  it("keeps simulation distinct from campaign results and production readiness", () => {
    renderSection();
    expect(
      screen.getByText(/not a governed campaign result, not a calibration claim, not a prospective forward test/i),
    ).toBeInTheDocument();
  });

  it("renders decisions with humanized states and truncated intent ids", () => {
    renderSection();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.getByText("within size limits")).toBeInTheDocument();
    expect(screen.queryByText("intent-abc123def456")).not.toBeInTheDocument();
  });

  it("renders fills with human times and minor-unit honesty", () => {
    renderSection();
    expect(screen.getByText("Price (minor units)")).toBeInTheDocument();
    expect(screen.queryByText("1757500400000000000")).not.toBeInTheDocument();
  });

  it("keeps raw orders/intents/attributions in the audit disclosure", () => {
    renderSection();
    expect(screen.getByText("Audit and technical detail")).toBeInTheDocument();
    expect(screen.getByText("Orders (raw)")).toBeInTheDocument();
    expect(screen.getByText("Reconciliation detail")).toBeInTheDocument();
  });

  it("is honest when the simulation has no fills or decisions", () => {
    simulationState.data = { ...simulationFixture, fills: [], risk_decisions: [] };
    renderSection();
    expect(screen.getByText(/No simulated fills fall inside the current replay window/i))
      .toBeInTheDocument();
  });
});

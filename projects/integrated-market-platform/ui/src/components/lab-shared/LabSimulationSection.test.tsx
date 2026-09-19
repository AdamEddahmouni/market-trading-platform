import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LabSimulationSection } from "./LabSimulationSection";

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

const diagnosticsState = {
  isLoading: false,
  isError: false,
  data: {
    schema_version: "operator-diagnostics/1.0.0",
    severity: "OK",
    sections: {
      runtime: {
        item9_corpus_status: {
          availability: "AVAILABLE",
          report: {
            calibration_state: "NOT_CALIBRATED",
            fitting_allowed: false,
            sample_gate_progress: { distinct_rth_dates: "2/3" },
          },
        },
      },
      governance: { live_execution_env: false },
    },
  } as Record<string, unknown> | undefined,
};

vi.mock("../../api/hooks", () => ({
  useResearchSimulationQuery: () => simulationState,
  useOperatorDiagnosticsQuery: () => diagnosticsState,
}));

describe("LabSimulationSection", () => {
  beforeEach(() => {
    simulationState.isLoading = false;
    simulationState.isError = false;
    simulationState.error = null;
    simulationState.data = simulationFixture;
    diagnosticsState.isLoading = false;
    diagnosticsState.isError = false;
    diagnosticsState.data = {
      schema_version: "operator-diagnostics/1.0.0",
      severity: "OK",
      sections: {
        runtime: {
          item9_corpus_status: {
            availability: "AVAILABLE",
            report: {
              calibration_state: "NOT_CALIBRATED",
              fitting_allowed: false,
              sample_gate_progress: { distinct_rth_dates: "2/3" },
            },
          },
        },
        governance: { live_execution_env: false },
      },
    };
    vi.clearAllMocks();
  });

  it("shows loading and error states", () => {
    simulationState.isLoading = true;
    const { rerender } = render(
      <MemoryRouter>
        <LabSimulationSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/loading simulation workflow/i);
    simulationState.isLoading = false;
    simulationState.isError = true;
    simulationState.data = undefined;
    rerender(
      <MemoryRouter>
        <LabSimulationSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/simulation workflow snapshot is unavailable/i);
    expect(screen.getByRole("heading", { name: "Item 9, Live, and what Lab is not" })).toBeInTheDocument();
    expect(screen.getByLabelText("Item 9 date-gate: IDLE")).toBeInTheDocument();
  });

  it("keeps simulation distinct from FTEP and production readiness", () => {
    render(
      <MemoryRouter>
        <LabSimulationSection />
      </MemoryRouter>,
    );
    expect(
      screen.getByText(/not forward-test evidence and not production readiness/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/no run-history list/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View interpretation in Research" })).toHaveAttribute(
      "href",
      "/research/simulation",
    );
    expect(screen.queryByRole("button", { name: /run/i })).not.toBeInTheDocument();
  });

  it("renders minor units and keeps raw ids in copyable/audit form", () => {
    render(
      <MemoryRouter>
        <LabSimulationSection />
      </MemoryRouter>,
    );
    expect(screen.getByText("Cash (minor units)")).toBeInTheDocument();
    expect(screen.getByText("Approved")).toBeInTheDocument();
    expect(screen.queryByText("intent-abc123def456")).not.toBeInTheDocument();
    expect(screen.queryByText("1757500400000000000")).not.toBeInTheDocument();
    expect(screen.getByText(/Cost and fill assumptions/i)).toBeInTheDocument();
    expect(screen.getByText("How this snapshot was produced")).toBeInTheDocument();
    expect(screen.getByLabelText("Item 9 calibration: NOT CALIBRATED")).toBeInTheDocument();
    expect(screen.getByLabelText("Live real-money execution: Live OFF")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(0);
  });

  it("is honest when the snapshot has no fills or decisions", () => {
    simulationState.data = { ...simulationFixture, fills: [], risk_decisions: [] };
    render(
      <MemoryRouter>
        <LabSimulationSection />
      </MemoryRouter>,
    );
    expect(
      screen.getByText(/No simulated decisions or fills fall inside the current replay window/i),
    ).toBeInTheDocument();
  });
});

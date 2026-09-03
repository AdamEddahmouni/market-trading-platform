import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SimulationLabPanel } from "./SimulationLabPanel";

vi.mock("../charts/ResearchChartPanels", () => ({
  CountBarChartPanel: () => <div data-testid="chart-stub" />,
}));

const simulationFixture = {
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  disclaimer: "Simulation only.",
  epistemic_class: "SIMULATION_PROJECTION",
  risk_policy_id: "default",
  ledger_summary: {
    cash_minor: 100000,
    position_shares: 0,
    realized_pnl_minor: 0,
    entry_count: 0,
  },
  risk_decisions: [{ decision: "REJECT", constraint_detail: "KILL_SWITCH", signal_prediction_cutoff: 1 }],
  fills: [],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
  fill_audit: { status: "PASS" },
};

describe("SimulationLabPanel", () => {
  it("renders simulation boundary without order controls", () => {
    render(<SimulationLabPanel payload={simulationFixture} />);
    expect(screen.getByText("SIMULATION")).toBeInTheDocument();
    expect(screen.getByText("READ_ONLY_SIMULATION")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit/i })).not.toBeInTheDocument();
  });
});

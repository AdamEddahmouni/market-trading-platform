import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperResearchPage } from "./PaperResearchPage";

const simulationFixture = {
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  disclaimer: "Simulation only.",
  epistemic_class: "SIMULATION_PROJECTION",
  risk_policy_id: "default",
  ledger_summary: { cash_minor: 100000, position_shares: 0, realized_pnl_minor: 0, entry_count: 0 },
  risk_decisions: [],
  fills: [],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
  fill_audit: { status: "PASS" },
};

vi.mock("../../api/hooks", () => ({
  useResearchAnalyticsQuery: () => ({ isLoading: false, data: undefined }),
  useResearchModelsQuery: () => ({ isLoading: false, data: undefined }),
  useResearchSimulationQuery: () => ({ isLoading: false, data: simulationFixture }),
}));

vi.mock("../research/SimulationLabPanel", () => ({
  SimulationLabPanel: () => <div data-testid="simulation-panel">Simulation Lab</div>,
}));

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <PaperResearchPage />
    </QueryClientProvider>,
  );
}

describe("PaperResearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("opens on simulation tab by default for paper research", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByText(/Research to simulation/i)).toBeInTheDocument();
    expect(screen.getByTestId("simulation-panel")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Simulation" })).toHaveAttribute("aria-selected", "true");
  });
});

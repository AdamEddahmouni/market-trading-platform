import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LabOverviewSection } from "./LabOverviewSection";

const modelsFixture = {
  authority_boundary: "READ_ONLY_RESEARCH",
  epistemic_class: "RESEARCH_PROJECTION",
  walk_forward_fold_count: 5,
  preregistration_status: "PASS",
  model_summary: { model_family: "naive_last_value.v1" },
  strategy_spec: {},
  dataset_manifest: {},
  preregistration: {},
  interpretation_summary: { abstention_count: 1, signal_count: 2, total_at_cutoff: 3 },
  interpretations: [],
};

const simulationFixture = {
  authority_boundary: "READ_ONLY_SIMULATION",
  mode_label: "SIMULATION",
  epistemic_class: "SIMULATION_PROJECTION",
  ledger_summary: { entry_count: 7, cash_minor: 1, position_shares: 0, realized_pnl_minor: 0 },
  risk_decisions: [{}],
  fills: [],
  orders: [],
  intents: [],
  attributions: [],
  reconciliation: { status: "PASS" },
};

const modelsState = {
  isLoading: false,
  isError: false,
  error: null as Error | null,
  data: modelsFixture as typeof modelsFixture | undefined,
  refetch: vi.fn(),
};

const simulationState = {
  isLoading: false,
  isError: false,
  error: null as Error | null,
  data: simulationFixture as typeof simulationFixture | undefined,
  refetch: vi.fn(),
};

vi.mock("../../api/hooks", () => ({
  useResearchModelsQuery: () => modelsState,
  useResearchSimulationQuery: () => simulationState,
}));

describe("LabOverviewSection", () => {
  beforeEach(() => {
    modelsState.isLoading = false;
    modelsState.isError = false;
    modelsState.data = modelsFixture;
    simulationState.isLoading = false;
    simulationState.isError = false;
    simulationState.data = simulationFixture;
    vi.clearAllMocks();
  });

  it("states that no backend Lab mutation exists", () => {
    render(
      <MemoryRouter>
        <LabOverviewSection />
      </MemoryRouter>,
    );
    expect(screen.getByText(/No Lab backend mutation exists/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run/i })).not.toBeInTheDocument();
  });

  it("lists inspectable workflows and unsupported FTEP/hypothesis gaps", () => {
    render(
      <MemoryRouter>
        <LabOverviewSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Model validation" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Deterministic simulation" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "FTEP campaign" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Benchmark comparison" })).toBeInTheDocument();
    expect(screen.getByText("Test versus forward-test")).toBeInTheDocument();
    expect(screen.getAllByText("Not yet available").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/Do not treat the deterministic simulation snapshot as a forward test/i))
      .toBeInTheDocument();
  });

  it("bridges completed results into Research", () => {
    render(
      <MemoryRouter>
        <LabOverviewSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Research Validation" })).toHaveAttribute(
      "href",
      "/research/validation",
    );
    expect(screen.getByRole("link", { name: "Research Simulation" })).toHaveAttribute(
      "href",
      "/research/simulation",
    );
  });

  it("shows loading then a combined error when both snapshots fail", () => {
    modelsState.isLoading = true;
    simulationState.isLoading = true;
    const { rerender } = render(
      <MemoryRouter>
        <LabOverviewSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/loading lab workbench/i);

    modelsState.isLoading = false;
    simulationState.isLoading = false;
    modelsState.isError = true;
    simulationState.isError = true;
    modelsState.data = undefined;
    simulationState.data = undefined;
    rerender(
      <MemoryRouter>
        <LabOverviewSection />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/cannot load the current experimental snapshots/i);
  });
});

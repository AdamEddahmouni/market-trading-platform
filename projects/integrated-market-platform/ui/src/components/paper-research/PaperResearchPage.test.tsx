import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperResearchPage } from "./PaperResearchPage";

const modelsFixture = {
  authority_boundary: "READ_ONLY_RESEARCH",
  disclaimer: "Model lab only.",
  epistemic_class: "RESEARCH_PROJECTION",
  walk_forward_fold_count: 5,
  preregistration_status: "PASS",
  model_summary: { model_family: "naive_last_value.v1", alignment_type: "FORECAST_MOMENTUM" },
  strategy_spec: {},
  dataset_manifest: {},
  preregistration: {},
  interpretation_summary: { abstention_count: 3, signal_count: 12, total_at_cutoff: 15 },
  interpretations: [],
};

vi.mock("../../api/hooks", () => ({
  useResearchAnalyticsQuery: () => ({ isLoading: false, data: undefined }),
  useResearchModelsQuery: () => ({ isLoading: false, data: modelsFixture }),
  useResearchSimulationQuery: () => ({ isLoading: false, data: undefined }),
  usePaperStrategyProfitabilityQuery: () => ({ isLoading: false, isError: true, data: undefined }),
}));

function renderPage(section: "overview" | "evidence" | "validation" | "simulation" = "overview") {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/research"]}>
        <PaperResearchPage section={section} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PaperResearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the paper research frame", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByText(/Research to simulation/i)).toBeInTheDocument();
  });

  it("shows strategy outcomes in Paper on the validation section", () => {
    renderPage("validation");
    expect(
      screen.getByRole("heading", { name: "How validated is this research?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Strategy outcomes in Paper" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Profitability lineage" })).toBeInTheDocument();
  });

  it("does not show the Paper strategy panel outside Paper validation", () => {
    renderPage("overview");
    expect(
      screen.queryByRole("heading", { name: "Strategy outcomes in Paper" }),
    ).not.toBeInTheDocument();
  });
});

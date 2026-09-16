import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoResearchPage } from "./DemoResearchPage";

const analyticsFixture = {
  epistemic_class: "RESEARCH_PROJECTION",
  authority_boundary: "READ_ONLY_RESEARCH_VISUALIZATION",
  disclaimer: "Research only.",
  panels: {
    attention_tiers: { available: false, provenance: { source: "test" }, series: [] },
    squeeze_outcomes: { available: false, provenance: { source: "test" }, series: [] },
    squeeze_historical_cohort: { available: false, provenance: { source: "test" }, series: [] },
    strategy_outcomes: { available: false, provenance: { source: "test" }, series: [] },
    risk_decisions: { available: false, provenance: { source: "test" }, series: [] },
  },
};

vi.mock("../../api/hooks", () => ({
  useResearchAnalyticsQuery: () => ({ isLoading: false, data: analyticsFixture }),
  useResearchModelsQuery: () => ({ isLoading: false, data: undefined }),
  useResearchSimulationQuery: () => ({ isLoading: false, data: undefined }),
}));

function renderPage(section: "overview" | "evidence" | "validation" | "simulation" = "overview") {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/research"]}>
        <DemoResearchPage section={section} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DemoResearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders read-only demo research without mutation controls", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
  });

  it("renders routable research section tabs", () => {
    renderPage();
    const tabs = screen.getByTestId("imp-ui-link-tabs");
    expect(tabs).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Evidence" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Validation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Simulation" })).toBeInTheDocument();
  });

  it("leads the overview with the evidence synthesis", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: "Current research picture" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/0 of 5 evidence findings have data/i)).toBeInTheDocument();
  });
});

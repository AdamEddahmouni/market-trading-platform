import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveResearchPage } from "./LiveResearchPage";

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

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LiveResearchPage section="overview" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LiveResearchPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders read-only live research with canary link", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Research" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
  });

  it("states that Live research stays replay-bound in the bridges", () => {
    renderPage();
    expect(screen.getByText(/stays replay-bound in Live mode/i)).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoResearchPage } from "./DemoResearchPage";

const analyticsFixture = {
  epistemic_class: "RESEARCH_PROJECTION",
  authority_boundary: "READ_ONLY",
  disclaimer: "Research only.",
  panels: [],
};

vi.mock("../../api/hooks", () => ({
  useResearchAnalyticsQuery: () => ({ isLoading: false, data: analyticsFixture }),
  useResearchModelsQuery: () => ({ isLoading: false, data: undefined }),
  useResearchSimulationQuery: () => ({ isLoading: false, data: undefined }),
}));

vi.mock("../research/ResearchAnalyticsPanel", () => ({
  ResearchAnalyticsPanel: () => <div data-testid="analytics-panel" />,
}));

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <DemoResearchPage />
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
    expect(screen.getByTestId("analytics-panel")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /place order/i })).not.toBeInTheDocument();
  });
});

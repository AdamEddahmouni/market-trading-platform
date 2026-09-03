import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveResearchPage } from "./LiveResearchPage";

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
      <MemoryRouter>
        <LiveResearchPage />
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
    expect(screen.getByTestId("analytics-panel")).toBeInTheDocument();
  });
});

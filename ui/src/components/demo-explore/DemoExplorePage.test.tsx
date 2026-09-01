import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoExplorePage } from "./DemoExplorePage";

const squeezePayload = {
  available: true,
  source: "donor-screener",
  row_count: 1,
  disclaimer: "Research only.",
  rows: [
    {
      screener_id: "sq-1",
      symbol: "GME",
      outcome_status: "OPEN",
      evidence_coverage: "FULL",
      research_detection: "DETECTED",
      freshness: "FRESH",
    },
  ],
  outcome_summary: [],
};

vi.mock("../../api/hooks", () => ({
  useExploreSqueezeQuery: () => ({ isLoading: false, data: squeezePayload }),
  useExploreSqueezeScannerQuery: () => ({
    isLoading: false,
    data: { available: false, reason: "Unavailable in test." },
  }),
  useExploreFuturesQuery: () => ({ isLoading: false, data: { available: false } }),
  useExploreCatalystQuery: () => ({ isLoading: false, data: { available: false } }),
}));

vi.mock("../charts/ResearchChartPanels", () => ({
  CountBarChartPanel: () => null,
}));

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <DemoExplorePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DemoExplorePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders read-only demo explore with frozen cohort", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.getByText("Frozen research cohort")).toBeInTheDocument();
    expect(screen.getByText("GME")).toBeInTheDocument();
  });
});

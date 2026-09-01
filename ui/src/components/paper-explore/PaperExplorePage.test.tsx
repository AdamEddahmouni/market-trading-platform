import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { PaperExplorePage } from "./PaperExplorePage";

const squeezePayload = {
  available: true,
  source: "donor-screener",
  row_count: 0,
  disclaimer: "Research only.",
  rows: [],
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
        <PaperExplorePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PaperExplorePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders paper candidate discovery header and portfolio link", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByText(/Candidate discovery/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open paper portfolio" })).toHaveAttribute(
      "href",
      "/portfolio",
    );
  });
});

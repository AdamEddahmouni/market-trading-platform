import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LiveExplorePage } from "./LiveExplorePage";

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
  useProviderHealthQuery: () => ({
    isLoading: false,
    data: { available: false, reason: "Live observational mode disabled in test." },
  }),
}));

vi.mock("../charts/ResearchChartPanels", () => ({
  CountBarChartPanel: () => null,
}));

vi.mock("../live/LiveObservationalPanel", () => ({
  LiveObservationalPanel: () => <div data-testid="live-panel">Live panel</div>,
}));

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <LiveExplorePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LiveExplorePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders read-only live explore with canary link and live panel", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: "Explore" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/read-only/i);
    expect(screen.getByRole("link", { name: "Open live canary" })).toHaveAttribute(
      "href",
      "/live-canary",
    );
    expect(screen.getByTestId("live-panel")).toBeInTheDocument();
  });
});

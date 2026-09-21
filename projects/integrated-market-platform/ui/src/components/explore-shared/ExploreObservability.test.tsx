import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ExploreObservability } from "./ExploreObservability";

vi.mock("../../api/hooks", () => ({
  useExploreSqueezeQuery: () => ({
    isLoading: false,
    data: {
      available: false,
      source: "test-fixture",
      rows: [],
      row_count: 0,
      disclaimer: "Research only.",
      reason: "UNAVAILABLE — squeeze fixture not loaded in this test.",
    },
  }),
  useExploreSqueezeScannerQuery: () => ({ isLoading: false, data: undefined }),
  useExploreFuturesQuery: () => ({ isLoading: false, data: undefined }),
  useExploreCatalystQuery: () => ({
    isLoading: false,
    data: {
      available: false,
      source: "internship-project-main",
      reason:
        "UNAVAILABLE — leftover donor public-catalyst demo state is not seeded. This overlay is not a live market feed and is not Opportunity Engine.",
    },
  }),
}));

describe("ExploreObservability catalyst honesty", () => {
  it("does not present leftover donor overlay as an internship demo or live feed", () => {
    render(
      <MemoryRouter>
        <ExploreObservability />
      </MemoryRouter>,
    );

    expect(screen.getByText(/leftover donor public-catalyst demo state is not seeded/i)).toBeInTheDocument();
    expect(screen.getByText(/canonical catalyst replay uses the admitted boxl fixture/i)).toBeInTheDocument();
    expect(screen.queryByText(/internship demo/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/news_momentum_agent/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/seed demo state/i)).not.toBeInTheDocument();
  });
});

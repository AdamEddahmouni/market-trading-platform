import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DemoPortfolioPage } from "./DemoPortfolioPage";
import { paperPortfolio } from "../paper-now/paperNowTestFixtures";

vi.mock("../../api/hooks", () => ({
  usePaperPortfolioQuery: () => ({
    isLoading: false,
    isError: false,
    data: paperPortfolio(),
    refetch: vi.fn(),
  }),
}));

describe("DemoPortfolioPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders read-only demo portfolio without order controls", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <DemoPortfolioPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "Demo Portfolio" })).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/exploration only/i);
    expect(screen.queryByText("Order ticket")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Positions" })).toBeInTheDocument();
    expect(screen.getAllByText("BIYA").length).toBeGreaterThan(0);
    expect(screen.getByText(/simulated Demo account — not live capital/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Inspect in Workspace" })[0]).toHaveAttribute(
      "href",
      "/workspace/BIYA",
    );
  });
});

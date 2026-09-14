import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { ImpTopOpportunityCards } from "./ImpTopOpportunityCards";

const row: OpportunityReviewRow = {
  summary_id: "sum-1",
  headline: "Breakout continuation",
  instrument_id: "NVDA",
  rank_order: 1,
  eligibility_state: "ELIGIBLE",
  next_safe_action: "OPEN_WORKSPACE",
  ranking_vector: {
    basis: "COMPARATOR_LEXICOGRAPHIC",
    dimensions: [{ name: "MOMENTUM", status: "PRESENT", value: 0.8 }],
  },
};

describe("ImpTopOpportunityCards", () => {
  it("renders compact cards from API rows without prices", () => {
    render(
      <MemoryRouter>
        <ImpTopOpportunityCards
          items={[row]}
          state="ready"
          feedStatus="READY"
          onExplain={vi.fn()}
          onInspect={vi.fn()}
          onOpenWorkspace={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Top opportunities" })).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("Breakout continuation")).toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });

  it("shows empty state when queue is valid but empty", () => {
    render(
      <MemoryRouter>
        <ImpTopOpportunityCards
          items={[]}
          state="ready"
          feedStatus="READY"
          onExplain={vi.fn()}
          onInspect={vi.fn()}
          onOpenWorkspace={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/empty queue is valid/i)).toBeInTheDocument();
  });
});

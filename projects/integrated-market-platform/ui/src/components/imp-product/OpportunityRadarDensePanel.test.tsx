import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { OpportunityRadarDensePanel } from "./OpportunityRadarDensePanel";

const eligible: OpportunityReviewRow = {
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

const ineligible: OpportunityReviewRow = {
  summary_id: "sum-2",
  headline: "Stale candidate",
  instrument_id: "AAPL",
  rank_order: 2,
  eligibility_state: "INELIGIBLE",
  next_safe_action: "STOP",
};

const mocks = vi.hoisted(() => ({
  query: {
    data: {
      items: [] as OpportunityReviewRow[],
      feed_status: "EMPTY" as string,
      unready_reason: undefined as string | undefined,
      next_action: undefined as string | undefined,
    },
    isLoading: false,
    isError: false,
  },
}));

vi.mock("../../api/opportunityClient", () => ({
  useOpportunitiesSummaryQuery: () => mocks.query,
}));

function renderPanel(
  data: {
    items: OpportunityReviewRow[];
    feed_status: string;
    unready_reason?: string;
    next_action?: string;
  },
  props: { readOnly?: boolean } = {},
) {
  mocks.query.data = data;
  mocks.query.isLoading = false;
  mocks.query.isError = false;
  const onExplain = vi.fn();
  const onInspect = vi.fn();
  const onOpenWorkspace = vi.fn();
  return {
    onExplain,
    onInspect,
    onOpenWorkspace,
    ...render(
      <MemoryRouter>
        <OpportunityRadarDensePanel
          readOnly={props.readOnly}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      </MemoryRouter>,
    ),
  };
}

describe("OpportunityRadarDensePanel", () => {
  it("shows an empty ranked queue without prices", () => {
    renderPanel({ items: [], feed_status: "EMPTY" });
    expect(screen.getByRole("heading", { name: "Opportunity review density" })).toBeInTheDocument();
    expect(screen.getByText(/no candidates in the ranked queue/i)).toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("does not open Workspace for INELIGIBLE or STOP rows", () => {
    const { onOpenWorkspace } = renderPanel({
      items: [eligible, ineligible],
      feed_status: "READY",
    });
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Workspace" })).toHaveLength(1);
    expect(screen.getAllByText("STOP")).toHaveLength(1);
    expect(onOpenWorkspace).not.toHaveBeenCalled();
  });

  it("marks read-only radar and still shows feed status", () => {
    renderPanel({ items: [eligible], feed_status: "READY" }, { readOnly: true });
    expect(screen.getByText("Feed READY")).toBeInTheDocument();
    expect(screen.getByText("Read-only")).toBeInTheDocument();
  });
});

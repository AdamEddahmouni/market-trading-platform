import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunitiesClient";
import { OpportunityReviewCard } from "./OpportunityReviewCard";

const comparatorRow: OpportunityReviewRow = {
  summary_id: "OPP-1",
  headline: "AAPL governed candidate",
  instrument_id: "AAPL",
  opportunity_id: "OPP-1",
  identity_kind: "OPPORTUNITY_V1",
  eligibility_state: "ELIGIBLE",
  lifecycle_state: "RANKED",
  next_safe_action: "OPEN_WORKSPACE",
  rank_order: 1,
  ranking_vector: {
    basis: "COMPARATOR_LEXICOGRAPHIC",
    dimensions: [
      { name: "actionability", status: "PRESENT", value: "ACTIONABLE" },
      { name: "expected_net_pnl_minor", status: "UNAVAILABLE", reason_code: "SIDECAR_FIELD_ABSENT" },
    ],
  },
  data_quality: { status: "GOOD" },
};

const attentionRow: OpportunityReviewRow = {
  summary_id: "att-1",
  headline: "Attention only",
  instrument_id: "NVDA",
  identity_kind: "NOT_OPPORTUNITY_V1",
  eligibility_state: "ELIGIBLE",
  lifecycle_state: "RANKED",
  next_safe_action: "OPEN_WORKSPACE",
  rank_order: 2,
  ranking_vector: { basis: "ATTENTION_ORDER", dimensions: [] },
  data_quality: { status: "UNAVAILABLE" },
};

describe("OpportunityReviewCard", () => {
  it("explains comparator dimensions and omits a universal score", () => {
    render(<OpportunityReviewCard row={comparatorRow} mode="PAPER" accountId="paper-acct" />);
    expect(screen.getByRole("heading", { name: "AAPL governed candidate" })).toBeInTheDocument();
    expect(screen.getByText(/actionability: ACTIONABLE/)).toBeInTheDocument();
    expect(screen.queryByText(/0–100|rank_score|quality score/i)).not.toBeInTheDocument();
    expect(screen.getByText(/account paper-acct/)).toBeInTheDocument();
  });

  it("labels attention rows as not OpportunityV1 and blocks Demo preview", () => {
    const onOpen = vi.fn();
    render(<OpportunityReviewCard row={attentionRow} mode="DEMO" onOpenWorkspace={onOpen} />);
    expect(screen.getByText(/not OpportunityV1/)).toBeInTheDocument();
    expect(screen.getByText(/Provisional order/)).toBeInTheDocument();
    expect(screen.getByText(/Demo is read-only/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Paper workspace" })).not.toBeInTheDocument();
  });

  it("stops preview when ineligible", () => {
    render(
      <OpportunityReviewCard
        row={{ ...comparatorRow, eligibility_state: "INELIGIBLE", lifecycle_state: "INELIGIBLE", next_safe_action: "STOP" }}
        mode="PAPER"
        onOpenWorkspace={vi.fn()}
      />,
    );
    expect(screen.getByText(/Ineligible — no preview/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Paper workspace" })).not.toBeInTheDocument();
  });
});

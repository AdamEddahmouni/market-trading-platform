import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ImpOverviewPrimaryQueue } from "./ImpOverviewPrimaryQueue";

const actions = {
  onWhy: vi.fn(),
  onExplain: vi.fn(),
  onInspect: vi.fn(),
  onOpenWorkspace: vi.fn(),
};

describe("ImpOverviewPrimaryQueue", () => {
  it("defaults to ranked and switches to attention without duplicate top cards", () => {
    render(
      <MemoryRouter>
        <ImpOverviewPrimaryQueue
          attentionItems={[
            {
              attention_id: "att-1",
              priority_rank: 1,
              headline: "Attention headline",
              explanation_ref: "explain:att:1",
              reasons: [{ code: "R1", label: "Reason" }],
              instrument_id: "BIYA",
            },
          ]}
          attentionState="ready"
          opportunityItems={[]}
          opportunityState="ready"
          feedStatus="EMPTY"
          {...actions}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Primary review queue" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Ranked", selected: true })).toBeInTheDocument();
    expect(screen.queryByText("Attention headline")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Attention" }));
    expect(screen.getByText("Attention headline")).toBeInTheDocument();
  });

  it("renders ranked opportunities through the shared opportunity queue", () => {
    render(
      <MemoryRouter>
        <ImpOverviewPrimaryQueue
          attentionItems={[]}
          attentionState="ready"
          opportunityItems={[
            {
              summary_id: "sum-cmd-1",
              opportunity_id: "opp-cmd-1",
              headline: "BIYA momentum ignition watch",
              instrument_id: "BIYA",
              identity_kind: "OPPORTUNITY_V1",
              eligibility_state: "ELIGIBLE",
              lifecycle_state: "ACTIVE",
              next_safe_action: "OPEN_WORKSPACE",
              rank_order: 1,
              ranking_vector: {
                basis: "COMPARATOR_LEXICOGRAPHIC",
                dimensions: [{ name: "attention_score", status: "PRESENT", value: 74.5 }],
                rank_order: 1,
              },
              data_quality: { status: "PASS", freshness: "FRESH" },
            },
          ]}
          opportunityState="ready"
          feedStatus="READY"
          {...actions}
        />
      </MemoryRouter>,
    );

    const card = screen.getByTestId("imp-opportunity-card");
    expect(card).toHaveTextContent("BIYA momentum ignition watch");
    expect(card).toHaveTextContent("Detected");
    expect(card).toHaveTextContent("1/1 inputs");
    expect(card).toHaveTextContent("Fresh");
    expect(card).toHaveTextContent("Open workspace");
    expect(screen.getByRole("link", { name: "Open full radar" })).toHaveAttribute("href", "/radar");
  });

  it("explains an empty ranked queue instead of dumping enums", () => {
    render(
      <MemoryRouter>
        <ImpOverviewPrimaryQueue
          attentionItems={[]}
          attentionState="ready"
          opportunityItems={[]}
          opportunityState="ready"
          feedStatus="EMPTY"
          {...actions}
        />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("imp-ui-empty-state")).toHaveTextContent(/No opportunities right now/);
  });
});

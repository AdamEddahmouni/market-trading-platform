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

const attentionItem = {
  attention_id: "att-1",
  priority_rank: 1,
  headline: "Attention headline",
  explanation_ref: "explain:att:1",
  reasons: [{ code: "R1", label: "Reason" }],
  instrument_id: "BIYA",
};

const rankedRow = {
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
};

function renderQueue(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("ImpOverviewPrimaryQueue", () => {
  it("shows both queues by default with subsection headings and tab counts", () => {
    renderQueue(
      <ImpOverviewPrimaryQueue
        attentionItems={[attentionItem]}
        attentionState="ready"
        opportunityItems={[rankedRow]}
        opportunityState="ready"
        feedStatus="READY"
        {...actions}
      />,
    );

    expect(screen.getByRole("heading", { name: "Primary review queue" })).toBeInTheDocument();
    // Both queues visible by default — the page's two core questions.
    expect(screen.getByRole("heading", { name: "Ranked opportunities" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Attention queue" })).toBeInTheDocument();
    expect(screen.getByText("BIYA momentum ignition watch")).toBeInTheDocument();
    expect(screen.getByText("Attention headline")).toBeInTheDocument();
    // Tabs carry counts so hidden content is visible without switching.
    expect(screen.getByRole("tab", { name: "Ranked (1)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Attention (1)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Both", selected: true })).toBeInTheDocument();
  });

  it("focuses a single queue from the tabs", () => {
    renderQueue(
      <ImpOverviewPrimaryQueue
        attentionItems={[attentionItem]}
        attentionState="ready"
        opportunityItems={[rankedRow]}
        opportunityState="ready"
        feedStatus="READY"
        {...actions}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Ranked (1)" }));
    expect(screen.getByText("BIYA momentum ignition watch")).toBeInTheDocument();
    expect(screen.queryByText("Attention headline")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Attention (1)" }));
    expect(screen.getByText("Attention headline")).toBeInTheDocument();
    expect(screen.queryByText("BIYA momentum ignition watch")).not.toBeInTheDocument();
  });

  it("supports the ARIA tabs keyboard pattern with roving tabindex", () => {
    renderQueue(
      <ImpOverviewPrimaryQueue
        attentionItems={[]}
        attentionState="ready"
        opportunityItems={[]}
        opportunityState="ready"
        feedStatus="EMPTY"
        {...actions}
      />,
    );
    const both = screen.getByRole("tab", { name: "Both" });
    const ranked = screen.getByRole("tab", { name: "Ranked (0)" });
    expect(both).toHaveAttribute("tabindex", "0");
    expect(ranked).toHaveAttribute("tabindex", "-1");

    const tablist = screen.getByRole("tablist", { name: "Queue source" });
    both.focus();
    fireEvent.keyDown(tablist, { key: "ArrowLeft" });
    expect(screen.getByRole("tab", { name: "Attention (0)" })).toHaveFocus();
    fireEvent.keyDown(tablist, { key: "Home" });
    expect(screen.getByRole("tab", { name: "Ranked (0)" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Ranked (0)", selected: true })).toBeInTheDocument();
  });

  it("renders ranked opportunities through the shared opportunity queue", () => {
    renderQueue(
      <ImpOverviewPrimaryQueue
        attentionItems={[]}
        attentionState="ready"
        opportunityItems={[rankedRow]}
        opportunityState="ready"
        feedStatus="READY"
        {...actions}
      />,
    );

    const card = screen.getByTestId("imp-opportunity-card");
    expect(card).toHaveTextContent("BIYA momentum ignition watch");
    expect(card).toHaveTextContent("Detected");
    expect(card).toHaveTextContent("1/1 inputs");
    expect(card).toHaveTextContent("Fresh");
    expect(card).toHaveTextContent("Open workspace");
    expect(screen.getByRole("link", { name: "Open full radar" })).toHaveAttribute("href", "/radar");
  });

  it("bridges a ranked signal to its Radar detail without duplicating the card", () => {
    // The backend ingests attention rows with summary_id = attention_id.
    const ingested = {
      ...rankedRow,
      summary_id: "att-1",
      opportunity_id: null,
      identity_kind: "NOT_OPPORTUNITY_V1",
      rank_order: 2,
    };
    renderQueue(
      <ImpOverviewPrimaryQueue
        attentionItems={[attentionItem]}
        attentionState="ready"
        opportunityItems={[ingested]}
        opportunityState="ready"
        feedStatus="READY"
        {...actions}
      />,
    );
    const signalCard = screen.getByText("Attention headline").closest("article");
    expect(signalCard).toHaveTextContent("Also ranked #2");
    expect(
      screen.getByRole("link", { name: /Open ranked opportunity for Attention headline in Radar/ }),
    ).toHaveAttribute("href", "/radar?selected=att-1");
  });

  it("explains an empty ranked queue instead of dumping enums", () => {
    renderQueue(
      <ImpOverviewPrimaryQueue
        attentionItems={[]}
        attentionState="ready"
        attentionEmptyMessage="Nothing requires attention right now."
        opportunityItems={[]}
        opportunityState="ready"
        feedStatus="EMPTY"
        {...actions}
      />,
    );
    const empties = screen.getAllByTestId("imp-ui-empty-state");
    expect(empties[0]).toHaveTextContent(/No opportunities right now/);
    // The attention queue explains its own empty state too.
    expect(empties[1]).toHaveTextContent(/Attention queue is clear/);
    expect(empties[1]).toHaveTextContent(/Nothing requires attention right now/);
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../../api/client";
import { PaperCandidateQueue } from "./PaperCandidateQueue";

const item: AttentionItem = {
  attention_id: "attention-1",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "BIYA setup",
  explanation_ref: "explain:attention:1",
  reasons: [{ code: "PRICE_VOLUME", label: "Price and volume expanded" }],
};

describe("PaperCandidateQueue", () => {
  it("keeps attention candidates and can host an empty opportunity review", () => {
    const onSelect = vi.fn();
    const onOpenWorkspace = vi.fn();
    render(
      <PaperCandidateQueue
        items={[item]}
        state="ready"
        selectedAttentionId="attention-1"
        onSelect={onSelect}
        onWhy={vi.fn()}
        onExplain={vi.fn()}
        onInspect={vi.fn()}
        onOpenWorkspace={onOpenWorkspace}
        opportunityItems={[]}
        opportunityState="ready"
        feedStatus="EMPTY"
        paperAccountId="paper-acct"
      />,
    );
    expect(screen.getByText(/No OpportunityV1 candidates/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Draft BIYA in Paper workspace" }));
    expect(onOpenWorkspace).toHaveBeenCalledWith(item);
  });
});

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
  it("presents attention signals as draftable candidates, not opportunities", () => {
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
      />,
    );
    expect(screen.getByRole("radiogroup", { name: "Paper candidates" })).toBeInTheDocument();
    expect(screen.getByText("1 signals")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Draft BIYA in Paper workspace" }));
    expect(onOpenWorkspace).toHaveBeenCalledWith(item);
  });

  it("marks signal-only items as research only", () => {
    render(
      <PaperCandidateQueue
        items={[{ ...item, attention_id: "attention-2", instrument_id: undefined, headline: "Macro review" }]}
        state="ready"
        selectedAttentionId={null}
        onSelect={vi.fn()}
        onWhy={vi.fn()}
        onExplain={vi.fn()}
        onInspect={vi.fn()}
        onOpenWorkspace={vi.fn()}
      />,
    );
    expect(screen.getByText("Research only")).toBeInTheDocument();
    expect(screen.getByText(/No instrument-backed candidate is available/)).toBeInTheDocument();
  });
});

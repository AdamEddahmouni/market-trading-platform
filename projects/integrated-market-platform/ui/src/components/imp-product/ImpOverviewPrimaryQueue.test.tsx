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
});

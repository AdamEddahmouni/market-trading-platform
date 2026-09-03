import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { PaperCandidateQueue } from "./PaperCandidateQueue";
import { PaperExceptionsPanel } from "./PaperExceptionsPanel";
import { PaperRiskRibbon } from "./PaperRiskRibbon";
import { attentionItem, paperPortfolio } from "./paperNowTestFixtures";

describe("Paper decision panels", () => {
  it("presents truthful risk, accessible candidates, and explicit exceptions", () => {
    const instrumentCandidate = attentionItem();
    const researchCandidate = attentionItem({
      attention_id: "attention-macro",
      priority_rank: 1,
      instrument_id: undefined,
      headline: "Macro review",
      explanation_ref: "explain:attention:macro",
    });

    render(
      <MemoryRouter>
        <PaperRiskRibbon portfolio={paperPortfolio()} state="ready" />
        <PaperCandidateQueue
          items={[instrumentCandidate, researchCandidate]}
          state="ready"
          selectedAttentionId="attention-biya"
          onSelect={vi.fn()}
          onWhy={vi.fn()}
          onExplain={vi.fn()}
          onInspect={vi.fn()}
          onOpenWorkspace={vi.fn()}
        />
        <PaperExceptionsPanel portfolio={paperPortfolio({ positions: [] })} state="ready" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("region", { name: "Risk summary" })).toHaveTextContent("Largest position200 / 500 sh");
    expect(screen.getByRole("meter", { name: "Largest position utilization" })).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByRole("radiogroup", { name: "Paper candidates" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /BIYA/ })).toBeChecked();
    expect(screen.getByText("Macro review").closest("article")).toHaveTextContent("Research only");
    expect(screen.getByRole("button", { name: "Explain Macro review" })).toBeEnabled();
    expect(screen.getByRole("region", { name: "Active exceptions" })).toHaveTextContent("No active exceptions");
    expect(screen.getByRole("link", { name: "Open full portfolio" })).toHaveAttribute("href", "/portfolio");
  });

  it("keeps confirmed risk visible when attention fails", () => {
    render(
      <MemoryRouter>
        <PaperRiskRibbon portfolio={paperPortfolio()} state="ready" />
        <PaperCandidateQueue
          items={[]}
          state="error"
          selectedAttentionId={null}
          onSelect={vi.fn()}
          onWhy={vi.fn()}
          onExplain={vi.fn()}
          onInspect={vi.fn()}
          onOpenWorkspace={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("region", { name: "Risk summary" })).toHaveTextContent("$2,500.00");
    expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable");
  });

  it("keeps candidate research actions visible when portfolio fails", () => {
    render(
      <MemoryRouter>
        <PaperRiskRibbon state="error" />
        <PaperCandidateQueue
          items={[attentionItem()]}
          state="ready"
          selectedAttentionId="attention-biya"
          onSelect={vi.fn()}
          onWhy={vi.fn()}
          onExplain={vi.fn()}
          onInspect={vi.fn()}
          onOpenWorkspace={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("region", { name: "Risk summary" })).toHaveTextContent("Unavailable");
    expect(screen.getByRole("button", { name: "Explain BIYA setup" })).toBeEnabled();
  });
});

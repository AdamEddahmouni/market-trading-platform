import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { OpportunityReviewCard, OpportunityReviewList } from "./OpportunityReviewCard";

function renderCard(ui: ReactElement) {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function row(overrides: Partial<OpportunityReviewRow> = {}): OpportunityReviewRow {
  return {
    summary_id: "sum-attn-1",
    headline: "AAPL attention adapter",
    instrument_id: "AAPL",
    identity_kind: "NOT_OPPORTUNITY_V1",
    eligibility_state: "UNAVAILABLE",
    lifecycle_state: "NORMALIZED",
    next_safe_action: "OPEN_WORKSPACE",
    rank_order: 1,
    explanation_ref: "explain:summary:sum-attn-1",
    ranking_vector: {
      basis: "ATTENTION_ORDER",
      rank_order: 1,
      dimensions: [
        { name: "actionability", status: "UNAVAILABLE", reason_code: "SIDECAR_ABSENT" },
        { name: "expected_net_pnl_minor", status: "PRESENT", value: 12, unit: "minor" },
      ],
    },
    data_quality: {
      status: "GOOD",
      freshness: "UNAVAILABLE",
      entitlement: "UNAVAILABLE",
      source: "REPLAY",
      reason_codes: ["FIXTURE_OR_REPLAY_SOURCE"],
    },
    decision_support: {
      authority: "DOWNSTREAM_RISK_NOT_RANKING",
      kill_switch: "UNAVAILABLE",
    },
    ...overrides,
  };
}

describe("OpportunityReviewCard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ opportunity_id: "sum-attn-1", items: [] }),
      }),
    );
  });

  it("shows explainable dimensions, UNAVAILABLE honesty, and no 0-100 score", () => {
    const onExplain = vi.fn();
    const onInspect = vi.fn();
    const onOpenWorkspace = vi.fn();
    const onAck = vi.fn();
    const { container } = renderCard(
      <OpportunityReviewCard
        row={row()}
        paperAccountId="paper-acct"
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
        onAck={onAck}
      />,
    );
    expect(screen.getAllByText(/not OpportunityV1/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Provisional order — not FTEP-tuned/)).toBeInTheDocument();
    const reasonCodes = container.querySelector(".reason-codes");
    expect(reasonCodes).not.toBeNull();
    expect(within(reasonCodes as HTMLElement).getByText("actionability")).toBeInTheDocument();
    expect(screen.getAllByText(/UNAVAILABLE/).length).toBeGreaterThan(0);
    expect(screen.getByText(/12 minor/)).toBeInTheDocument();
    expect(screen.getByText(/Paper account/)).toHaveTextContent("paper-acct");
    expect(screen.getByText(/DOWNSTREAM_RISK_NOT_RANKING/)).toBeInTheDocument();
    expect(screen.queryByText(/rank_score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Explain" }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    expect(onExplain).toHaveBeenCalled();
    expect(onInspect).toHaveBeenCalled();
    expect(onOpenWorkspace).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(onAck).toHaveBeenCalledWith(expect.objectContaining({ summary_id: "sum-attn-1" }), "watch");
  });

  it("keeps Demo review read-only without watch or dismiss", () => {
    renderCard(
      <OpportunityReviewCard
        row={row()}
        readOnly
        onExplain={vi.fn()}
        onInspect={vi.fn()}
        onOpenWorkspace={vi.fn()}
      />,
    );
    expect(screen.getByText(/Demo is read-only/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
  });

  it("stops preview for ineligible rows", () => {
    renderCard(
      <OpportunityReviewCard
        row={row({ next_safe_action: "STOP", eligibility_state: "INELIGIBLE" })}
        onExplain={vi.fn()}
        onInspect={vi.fn()}
        onOpenWorkspace={vi.fn()}
      />,
    );
    expect(screen.getByText(/Next safe action: STOP/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open workspace" })).not.toBeInTheDocument();
  });
});

describe("OpportunityReviewList", () => {
  it("treats an empty queue as success and links Control Center when unready", () => {
    const actions = { onExplain: vi.fn(), onInspect: vi.fn(), onOpenWorkspace: vi.fn() };
    const { rerender } = render(<OpportunityReviewList items={[]} state="ready" feedStatus="EMPTY" {...actions} />);
    expect(screen.getByText(/No OpportunityV1 candidates/)).toBeInTheDocument();

    rerender(
      <OpportunityReviewList
        items={[]}
        state="ready"
        feedStatus="UNREADY"
        unreadyReason="QUALITY_SUMMARY_NOT_HEALTHY"
        nextAction="/control"
        {...actions}
      />,
    );
    expect(screen.getByRole("link", { name: "Open Control Center" })).toHaveAttribute("href", "/control");
  });
});

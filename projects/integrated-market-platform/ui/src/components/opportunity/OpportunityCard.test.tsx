import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { OpportunityCard } from "./OpportunityCard";
import { OpportunityQueue } from "./OpportunityQueue";

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

function renderCard(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

function actions() {
  return { onExplain: vi.fn(), onInspect: vi.fn(), onOpenWorkspace: vi.fn(), onAck: vi.fn() };
}

describe("OpportunityCard", () => {
  it("renders the shared state/evidence/freshness/next-action language without scores", () => {
    const handlers = actions();
    renderCard(<OpportunityCard row={row()} paperAccountId="paper-acct" {...handlers} />);
    const card = screen.getByTestId("imp-opportunity-card");
    expect(card).toHaveTextContent("AAPL attention adapter");
    expect(card).toHaveTextContent("Provisional");
    expect(card).toHaveTextContent("1/2 inputs");
    expect(card).toHaveTextContent("Unavailable"); // freshness word humanized
    expect(card).toHaveTextContent("Open workspace");
    expect(card).toHaveTextContent("Provisional order — not FTEP-tuned");
    expect(card).toHaveTextContent("Visibility is not actionability");
    expect(card).not.toHaveTextContent(/rank_score/i);
    expect(card).not.toHaveTextContent(/%/);
  });

  it("wires explain/inspect/workspace actions through the attention bridge", () => {
    const handlers = actions();
    renderCard(<OpportunityCard row={row()} paperAccountId="paper-acct" {...handlers} />);
    fireEvent.click(screen.getByRole("button", { name: "Explain" }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    expect(handlers.onExplain).toHaveBeenCalledWith(
      expect.objectContaining({ explanation_ref: "explain:summary:sum-attn-1" }),
    );
    expect(handlers.onInspect).toHaveBeenCalled();
    expect(handlers.onOpenWorkspace).toHaveBeenCalled();
  });

  it("offers ack actions only with a paper account and ack handler", () => {
    const handlers = actions();
    const { unmount } = renderCard(
      <OpportunityCard row={row()} paperAccountId="paper-acct" {...handlers} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Watch" }));
    expect(handlers.onAck).toHaveBeenCalledWith(expect.objectContaining({ summary_id: "sum-attn-1" }), "watch");
    unmount();

    renderCard(<OpportunityCard row={row()} {...handlers} />);
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
  });

  it("keeps read-only modes free of ack actions and says so", () => {
    renderCard(
      <OpportunityCard row={row()} readOnly paperAccountId="paper-acct" {...actions()} />,
    );
    expect(screen.getByText(/Read-only in this mode/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
  });

  it("stops workspace preview and acks for ineligible rows", () => {
    renderCard(
      <OpportunityCard
        row={row({ next_safe_action: "STOP", eligibility_state: "INELIGIBLE" })}
        paperAccountId="paper-acct"
        {...actions()}
      />,
    );
    const card = screen.getByTestId("imp-opportunity-card");
    expect(card).toHaveTextContent("Stop — do not act on this opportunity");
    expect(card).toHaveTextContent("Eligibility gate failed");
    expect(screen.queryByRole("button", { name: "Open workspace" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Watch" })).not.toBeInTheDocument();
  });
});

describe("OpportunityQueue", () => {
  it("renders compact cards when the feed is ready", () => {
    renderCard(
      <OpportunityQueue items={[row()]} state="ready" feedStatus="READY" {...actions()} />,
    );
    expect(screen.getByTestId("imp-opportunity-queue")).toBeInTheDocument();
    expect(screen.getByTestId("imp-opportunity-card")).toHaveTextContent("AAPL attention adapter");
  });

  it("treats an empty queue as valid and says why", () => {
    renderCard(
      <OpportunityQueue items={[]} state="ready" feedStatus="EMPTY" {...actions()} />,
    );
    expect(screen.getByTestId("imp-ui-empty-state")).toHaveTextContent(/No opportunities right now/);
    expect(screen.getByTestId("imp-ui-empty-state")).toHaveTextContent(/empty queue is valid/i);
  });

  it("renders UNREADY as a human banner with a Control action", () => {
    renderCard(
      <OpportunityQueue
        items={[]}
        state="ready"
        feedStatus="UNREADY"
        unreadyReason="QUALITY_SUMMARY_NOT_HEALTHY"
        nextAction="/control"
        {...actions()}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/Opportunity radar isn't ready/);
    expect(screen.getByRole("link", { name: "Open Control" })).toHaveAttribute("href", "/control");
  });

  it("renders the live by-design empty state when the feed is unavailable", () => {
    renderCard(
      <OpportunityQueue items={[]} state="ready" feedStatus="UNAVAILABLE" mode="LIVE" {...actions()} />,
    );
    expect(screen.getByTestId("imp-ui-empty-state")).toHaveTextContent(
      /Live mode has no opportunity engine/i,
    );
  });

  it("treats a non-live UNAVAILABLE feed as a fault with a Control action", () => {
    renderCard(
      <OpportunityQueue
        items={[]}
        state="ready"
        feedStatus="UNAVAILABLE"
        mode="PAPER"
        nextAction="/control"
        {...actions()}
      />,
    );
    const empty = screen.getByTestId("imp-ui-empty-state");
    expect(empty).toHaveTextContent(/Opportunity feed unavailable/i);
    expect(empty).not.toHaveTextContent(/Live mode has no opportunity engine/i);
    expect(screen.getByRole("link", { name: "Open Control" })).toHaveAttribute("href", "/control");
  });

  it("renders the error state with retry", () => {
    const onRetry = vi.fn();
    renderCard(
      <OpportunityQueue items={[]} state="error" onRetry={onRetry} {...actions()} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/Opportunity ranking is unavailable/);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders a loading state", () => {
    renderCard(<OpportunityQueue items={[]} state="loading" {...actions()} />);
    expect(screen.getByRole("status")).toHaveTextContent(/Loading ranked opportunities/);
  });
});

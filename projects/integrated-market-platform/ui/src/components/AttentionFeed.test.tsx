import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../api/client";
import { AttentionFeed } from "./AttentionFeed";
import type { AttentionOpportunityLink } from "./attentionPresentation";

const item: AttentionItem = {
  attention_id: "attention-1",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "Volume expands into the replay event",
  explanation_ref: "explain:attention:1",
  reasons: [{ code: "VOLUME_EXPANSION", label: "Volume exceeds the admitted baseline" }],
};

function callbacks() {
  return {
    onWhy: vi.fn(),
    onExplain: vi.fn(),
    onInspect: vi.fn(),
    onOpenWorkspace: vi.fn(),
  };
}

function renderFeed(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("AttentionFeed", () => {
  it("presents tier urgency, why-now, and all existing item actions", () => {
    const actions = callbacks();
    renderFeed(<AttentionFeed items={[item]} state="ready" {...actions} />);

    const card = screen.getByRole("article");
    expect(card).toHaveClass("tier-1");
    // Tier is text + tone (StatePill), never color alone.
    expect(card).toHaveTextContent("Tier 1 — act now");
    // Object class is explicit: this is a signal, not an opportunity.
    expect(card).toHaveTextContent("Signal");
    // Why-now leads with the human reason label, not the raw code.
    expect(card).toHaveTextContent("Why now: Volume exceeds the admitted baseline");
    // Raw codes stay available in the L4 disclosure.
    expect(screen.getByText("Reason codes")).toBeInTheDocument();
    expect(screen.getByText("VOLUME_EXPANSION")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Why here?" }));
    fireEvent.click(screen.getByRole("button", { name: "Explain" }));
    fireEvent.click(screen.getByRole("button", { name: "Inspect" }));
    fireEvent.click(screen.getByRole("button", { name: "Open workspace" }));
    expect(actions.onWhy).toHaveBeenCalledWith(item);
    expect(actions.onExplain).toHaveBeenCalledWith(item);
    expect(actions.onInspect).toHaveBeenCalledWith(item);
    expect(actions.onOpenWorkspace).toHaveBeenCalledWith(item);
  });

  it("uses h3 card headings inside the page heading hierarchy", () => {
    renderFeed(<AttentionFeed items={[item]} state="ready" {...callbacks()} />);
    expect(
      screen.getByRole("heading", { level: 3, name: "Volume expands into the replay event" }),
    ).toBeInTheDocument();
  });

  it("makes the signal→opportunity bridge explicit when the signal is ranked", () => {
    const links = new Map<string, AttentionOpportunityLink>([
      [
        "attention-1",
        {
          summaryId: "attention-1",
          rank: "#2",
          stateLabel: "Provisional",
          stateTone: "caution",
          evidence: "2/3 inputs",
        },
      ],
    ]);
    renderFeed(
      <AttentionFeed items={[item]} state="ready" opportunityLinks={links} {...callbacks()} />,
    );
    const card = screen.getByRole("article");
    expect(card).toHaveTextContent("Also ranked #2");
    expect(card).toHaveTextContent("Evidence 2/3 inputs");
    expect(card).toHaveTextContent("Provisional");
    expect(
      screen.getByRole("link", { name: /Open ranked opportunity for .* in Radar/ }),
    ).toHaveAttribute("href", "/radar?selected=attention-1");
  });

  it("implies no opportunity when the signal is not ranked", () => {
    renderFeed(
      <AttentionFeed
        items={[item]}
        state="ready"
        opportunityLinks={new Map()}
        {...callbacks()}
      />,
    );
    const card = screen.getByRole("article");
    expect(card).not.toHaveTextContent(/Also ranked/);
    expect(screen.queryByRole("link", { name: /Radar/ })).not.toBeInTheDocument();
  });

  it("renders replay-bound surfaced time as absolute as-of, not a decaying age", () => {
    const surfaced = Date.parse("2026-07-14T14:31:00Z") * 1_000_000; // epoch ns
    renderFeed(
      <AttentionFeed items={[{ ...item, surfaced_time: surfaced }]} state="ready" {...callbacks()} />,
    );
    const freshness = screen.getByTestId("imp-ui-freshness");
    expect(freshness).toHaveAttribute("data-tone", "replay");
    expect(freshness).toHaveTextContent("as of");
    expect(freshness).not.toHaveTextContent("ago");
  });

  it("renders shared loading, error, and empty states with operator guidance", () => {
    const actions = callbacks();
    const onRetry = vi.fn();
    const { rerender } = render(
      <MemoryRouter>
        <AttentionFeed items={[]} state="loading" emptyMessage="Nothing requires attention." {...actions} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading attention feed");

    rerender(
      <MemoryRouter>
        <AttentionFeed
          items={[]}
          state="error"
          emptyMessage="Nothing requires attention."
          onRetry={onRetry}
          {...actions}
        />
      </MemoryRouter>,
    );
    const error = screen.getByRole("alert");
    expect(error).toHaveTextContent("Attention feed unavailable");
    expect(error).toHaveTextContent(/Ranked opportunities and Radar remain available/);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();

    rerender(
      <MemoryRouter>
        <AttentionFeed items={[]} state="ready" emptyMessage="Nothing requires attention." {...actions} />
      </MemoryRouter>,
    );
    const empty = screen.getByTestId("imp-ui-empty-state");
    expect(empty).toHaveTextContent("Attention queue is clear");
    expect(empty).toHaveTextContent("Nothing requires attention.");

    rerender(
      <MemoryRouter>
        <AttentionFeed items={[]} state="ready" {...actions} />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("imp-ui-empty-state")).not.toBeInTheDocument();
  });

  it("does not offer workspace navigation without an instrument", () => {
    renderFeed(
      <AttentionFeed items={[{ ...item, instrument_id: undefined }]} state="ready" {...callbacks()} />,
    );
    expect(screen.queryByRole("button", { name: "Open workspace" })).not.toBeInTheDocument();
  });
});

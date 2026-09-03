import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../api/client";
import { AttentionFeed } from "./AttentionFeed";

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

describe("AttentionFeed", () => {
  it("preserves reason codes, tier identity, and all existing item actions", () => {
    const actions = callbacks();
    render(<AttentionFeed items={[item]} state="ready" {...actions} />);

    expect(screen.getByRole("article")).toHaveClass("tier-1");
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

  it("renders local loading, error, and optional empty messages", () => {
    const actions = callbacks();
    const { rerender } = render(
      <AttentionFeed items={[]} state="loading" emptyMessage="Nothing requires attention." {...actions} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading attention feed");

    rerender(<AttentionFeed items={[]} state="error" emptyMessage="Nothing requires attention." {...actions} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Attention feed unavailable");

    rerender(<AttentionFeed items={[]} state="ready" emptyMessage="Nothing requires attention." {...actions} />);
    expect(screen.getByText("Nothing requires attention.")).toBeInTheDocument();

    rerender(<AttentionFeed items={[]} state="ready" {...actions} />);
    expect(screen.queryByText("Nothing requires attention.")).not.toBeInTheDocument();
  });

  it("does not offer workspace navigation without an instrument", () => {
    render(
      <AttentionFeed items={[{ ...item, instrument_id: undefined }]} state="ready" {...callbacks()} />,
    );
    expect(screen.queryByRole("button", { name: "Open workspace" })).not.toBeInTheDocument();
  });
});

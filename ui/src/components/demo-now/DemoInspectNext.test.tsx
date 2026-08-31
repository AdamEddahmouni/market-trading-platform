import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AttentionItem } from "../../api/client";
import { DemoInspectNext, topAttentionItem } from "./DemoInspectNext";

const lower: AttentionItem = {
  attention_id: "lower",
  priority_rank: 8,
  tier: 2,
  instrument_id: "OTHER",
  headline: "Lower priority item",
  explanation_ref: "explain:lower",
  reasons: [],
};
const top: AttentionItem = {
  attention_id: "top",
  priority_rank: 1,
  tier: 1,
  instrument_id: "BIYA",
  headline: "Top replay signal",
  explanation_ref: "explain:top",
  reasons: [],
};

describe("DemoInspectNext", () => {
  it("selects the lowest priority rank without mutating the source array", () => {
    const items = [lower, top];
    expect(topAttentionItem(items)).toBe(top);
    expect(items).toEqual([lower, top]);
  });

  it("guides explain, workspace, then replay advance for the top item", () => {
    const onExplain = vi.fn();
    const onInspect = vi.fn();
    const onOpenWorkspace = vi.fn();
    const onAdvance = vi.fn();
    render(
      <DemoInspectNext
        items={[lower, top]}
        canAdvance
        replayPending={false}
        onExplain={onExplain}
        onInspect={onInspect}
        onOpenWorkspace={onOpenWorkspace}
        onAdvance={onAdvance}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Explain Top replay signal" }));
    fireEvent.click(screen.getByRole("button", { name: "Open BIYA workspace" }));
    fireEvent.click(screen.getByRole("button", { name: "Advance one event" }));
    expect(onExplain).toHaveBeenCalledWith(top);
    expect(onOpenWorkspace).toHaveBeenCalledWith(top);
    expect(onInspect).not.toHaveBeenCalled();
    expect(onAdvance).toHaveBeenCalledOnce();
  });

  it("uses inspection when the top item has no instrument", () => {
    const noInstrument = { ...top, instrument_id: undefined };
    const onInspect = vi.fn();
    render(
      <DemoInspectNext
        items={[noInstrument]}
        canAdvance={false}
        replayPending={false}
        onExplain={vi.fn()}
        onInspect={onInspect}
        onOpenWorkspace={vi.fn()}
        onAdvance={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Inspect supporting evidence" }));
    expect(onInspect).toHaveBeenCalledWith(noInstrument);
    expect(screen.getByRole("button", { name: "Advance one event" })).toBeDisabled();
  });

  it("explains an empty attention state and retains a safe advance when available", () => {
    const onAdvance = vi.fn();
    render(
      <DemoInspectNext
        items={[]}
        canAdvance
        replayPending={false}
        onExplain={vi.fn()}
        onInspect={vi.fn()}
        onOpenWorkspace={vi.fn()}
        onAdvance={onAdvance}
      />,
    );
    expect(screen.getByText(/No item requires inspection/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Advance one event" }));
    expect(onAdvance).toHaveBeenCalledOnce();
  });
});

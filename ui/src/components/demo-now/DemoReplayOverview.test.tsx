import type { ComponentProps } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DemoReplayOverview, deriveReplayProgress } from "./DemoReplayOverview";

describe("deriveReplayProgress", () => {
  it.each([
    [0, 4, { cursorIndex: 0, ordinal: 1, eventCount: 4, percent: 25, hasPrevious: false, hasNext: true }],
    [2, 4, { cursorIndex: 2, ordinal: 3, eventCount: 4, percent: 75, hasPrevious: true, hasNext: true }],
    [99, 4, { cursorIndex: 3, ordinal: 4, eventCount: 4, percent: 100, hasPrevious: true, hasNext: false }],
    [0, 0, { cursorIndex: 0, ordinal: 0, eventCount: 0, percent: 0, hasPrevious: false, hasNext: false }],
  ] as const)("derives bounded progress for cursor %s of %s", (cursor, count, expected) => {
    expect(deriveReplayProgress(cursor, count)).toEqual(expected);
  });

  it.each([[Number.NaN, 4], [1.5, 4], [0, -1], [0, undefined]] as const)(
    "rejects invalid replay data",
    (cursor, count) => expect(deriveReplayProgress(cursor, count)).toBeNull(),
  );
});

function renderReplay(overrides: Partial<ComponentProps<typeof DemoReplayOverview>> = {}) {
  const props: ComponentProps<typeof DemoReplayOverview> = {
    cursorIndex: 1,
    eventCount: 4,
    state: "ready",
    scrubState: "idle",
    onScrub: vi.fn(),
    onOpenTimeline: vi.fn(),
    ...overrides,
  };
  render(<DemoReplayOverview {...props} />);
  return props;
}

describe("DemoReplayOverview", () => {
  it("shows truthful BIYA identity and invokes bounded replay actions", () => {
    const props = renderReplay();
    expect(screen.getByRole("region", { name: "Replay overview" })).toHaveTextContent("BIYA admitted replay");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByText("Event 2 of 4")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Replay progress" })).toHaveAttribute("aria-valuenow", "2");
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    fireEvent.click(screen.getByRole("button", { name: "Open full timeline" }));
    expect(props.onScrub).toHaveBeenNthCalledWith(1, 0);
    expect(props.onScrub).toHaveBeenNthCalledWith(2, 2);
    expect(props.onOpenTimeline).toHaveBeenCalledOnce();
  });

  it("enforces first, final, empty, and pending boundaries", () => {
    const { rerender } = render(
      <DemoReplayOverview
        cursorIndex={0}
        eventCount={4}
        state="ready"
        scrubState="idle"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    rerender(
      <DemoReplayOverview
        cursorIndex={3}
        eventCount={4}
        state="ready"
        scrubState="idle"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Next event" })).toBeDisabled();
    rerender(
      <DemoReplayOverview
        cursorIndex={0}
        eventCount={0}
        state="ready"
        scrubState="idle"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByText("0 events")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next event" })).toBeDisabled();
    rerender(
      <DemoReplayOverview
        cursorIndex={1}
        eventCount={4}
        state="ready"
        scrubState="pending"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next event" })).toBeDisabled();
  });

  it("degrades loading, invalid, and failed scrub states locally", () => {
    const { rerender } = render(
      <DemoReplayOverview
        cursorIndex={0}
        eventCount={undefined}
        state="loading"
        scrubState="idle"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading replay status");
    rerender(
      <DemoReplayOverview
        cursorIndex={0}
        eventCount={undefined}
        state="error"
        scrubState="idle"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByText(/Replay status unavailable/)).toBeInTheDocument();
    rerender(
      <DemoReplayOverview
        cursorIndex={1}
        eventCount={4}
        state="ready"
        scrubState="error"
        onScrub={vi.fn()}
        onOpenTimeline={vi.fn()}
      />,
    );
    expect(screen.getByText("Event 2 of 4")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Replay could not move");
  });

  it("does not optimistically change a controlled cursor", () => {
    renderReplay({ cursorIndex: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Next event" }));
    expect(screen.getByText("Event 2 of 4")).toBeInTheDocument();
  });
});

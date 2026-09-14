import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyIncrementalTick, createGovernedFeed } from "./governedSyntheticFeed";
import { ImpVelaChartAdapter } from "./ImpVelaChartAdapter";

const velaMocks = vi.hoisted(() => {
  const destroy = vi.fn();
  const resize = vi.fn();
  const ready = vi.fn().mockResolvedValue(undefined);
  const setMarket = vi.fn().mockResolvedValue(undefined);
  const setTheme = vi.fn();
  const remove = vi.fn();
  const add = vi.fn(() => ({ id: "drawing-1" }));
  const instance = {
    ready,
    destroy,
    resize,
    setMarket,
    setTheme,
    drawings: { supported: true, add, remove },
  };
  const Vela = vi.fn(() => instance);
  return { destroy, resize, ready, setMarket, Vela, instance, remove };
});

vi.mock("./velaDynamicLoader", () => ({
  loadVelaConstructor: vi.fn(async () => velaMocks.Vela),
}));

describe("ImpVelaChartAdapter", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe = vi.fn();
        disconnect = vi.fn();
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("mounts Vela lazily, observes resize, and cleans up on unmount", async () => {
    const feed = createGovernedFeed("IMP:ADMITTED:ES", "5m", 8);
    const { unmount } = render(<ImpVelaChartAdapter bars={feed.bars} markers={[]} />);

    await waitFor(() => expect(velaMocks.ready).toHaveBeenCalled());
    expect(velaMocks.Vela).toHaveBeenCalledTimes(1);

    unmount();
    expect(velaMocks.destroy).toHaveBeenCalledTimes(1);
  });

  it("pushes incremental bar updates through setMarket when ready", async () => {
    const feed = createGovernedFeed("IMP:ADMITTED:ES", "5m", 8);
    const { rerender } = render(<ImpVelaChartAdapter bars={feed.bars} />);
    await waitFor(() => expect(velaMocks.ready).toHaveBeenCalled());

    const ticked = applyIncrementalTick(feed, 99);
    rerender(<ImpVelaChartAdapter bars={ticked.bars} />);
    await waitFor(() => expect(velaMocks.setMarket).toHaveBeenCalled());
  });
});
